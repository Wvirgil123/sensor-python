#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time

class ZPHS01C:
    # Serial port configuration
    BAUDRATE = 9600
    BYTESIZE = 8
    PARITY = 'N'
    STOPBITS = 1
    
    # Protocol constants
    HEADER_SEND = 0x11
    HEADER_RESP = 0x16
    CMD_ACTIVE_UPLOAD = 0x01
    CMD_QUERY = 0x02
    CMD_DUST_CONTROL = 0x0C
    
    def __init__(self, port='/dev/ttyUSB0'):
        """
        Initialize ZPHS01C sensor
        :param port: Serial port name, default is '/dev/ttyUSB0'
        """
        self.port = port
        self.serial = None
        self._connect()
        
    def _connect(self):
        """Connect to sensor via serial port"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.BAUDRATE,
                bytesize=self.BYTESIZE,
                parity=self.PARITY,
                stopbits=self.STOPBITS,
                timeout=1
            )
            # Wait for sensor to stabilize
            time.sleep(1)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to ZPHS01C sensor: {e}")

    def _calculate_checksum(self, data):
        """
        Calculate checksum
        :param data: Byte array
        :return: Checksum value
        """
        # Calculate sum of all bytes except checksum
        checksum = sum(data)
        # Invert and add 1
        return (~checksum + 1) & 0xFF

    def _send_command(self, cmd, data=None):
        """
        Send command to sensor
        :param cmd: Command number
        :param data: Data byte array
        :return: Response data
        """
        if data is None:
            data = []
        
        # Build command frame (excluding checksum)
        frame = [self.HEADER_SEND, len(data) + 1, cmd] + data
        # Calculate and add checksum
        frame.append(self._calculate_checksum(frame))
        
        # Print sent command
        # print(f"-->{' '.join([f'{x:02X}' for x in frame])}")
        
        # Clear receive buffer
        self.serial.reset_input_buffer()
        
        # Send command
        self.serial.write(bytes(frame))
        
        # Wait for response
        start_time = time.time()
        timeout = 1.0  # 1 second timeout
        
        # Read frame header and length
        response = bytearray()
        while time.time() - start_time < timeout:
            if self.serial.in_waiting >= 2:
                response.extend(self.serial.read(2))
                if response[0] != self.HEADER_RESP:
                    print(f"Response error: Invalid frame header {response[0]:02X}")
                    return None
                break
            time.sleep(0.01)
        
        if len(response) < 2:
            print("Response timeout: No frame header and length received")
            return None
            
        # Read remaining data
        length = response[1]
        remaining_length = length
        while time.time() - start_time < timeout:
            if self.serial.in_waiting > 0:
                data = self.serial.read(self.serial.in_waiting)
                response.extend(data)
                remaining_length -= len(data)
                if remaining_length <= 0:
                    break
            time.sleep(0.01)
        
        if remaining_length > 0:
            print(f"Response timeout: Incomplete data, missing {remaining_length} bytes")
            return None
        
        # Print received response
        # print(f"<--{' '.join([f'{x:02X}' for x in response])}")
        
        # Verify checksum
        if self._calculate_checksum(response[:-1]) != response[-1]:
            print(f"Checksum error: Calculated={self._calculate_checksum(response[:-1]):02X}, Received={response[-1]:02X}")
            return None
            
        return response

    def start_active_upload(self):
        """
        Start active upload mode
        :return: Success status
        """
        print("Starting active upload mode...")
        response = self._send_command(self.CMD_ACTIVE_UPLOAD, [0x00])
        return response is not None

    def query_data(self):
        """
        Query sensor data
        :return: Dictionary containing all sensor data
        """
        response = self._send_command(self.CMD_QUERY, [0x00])
        if response is None or len(response) < 15:
            print("Incomplete data response")
            return None
            
        data = {
            'co2': int.from_bytes(response[3:5], 'big'),  # 400-5000ppm
            'voc': int.from_bytes(response[5:7], 'big'),  # 0-3, no unit
            'humidity': int.from_bytes(response[7:9], 'big') / 10.0,  # 0-100%
            'temperature': (int.from_bytes(response[9:11], 'big') - 500) / 10.0,  # 0-65℃
            'pm25': int.from_bytes(response[11:13], 'big'),  # 0-1000ug/m3
            'pm10': int.from_bytes(response[13:15], 'big'),  # 0-1000ug/m3
            'pm1': int.from_bytes(response[15:17], 'big')  # 0-1000ug/m3
        }
        return data

    def control_dust_measurement(self, enable=True):
        """
        Control dust measurement
        :param enable: True to start measurement, False to stop
        :return: Success status
        """
        print(f"{'Starting' if enable else 'Stopping'} dust measurement...")
        data = [0x02 if enable else 0x01, 0x1E]
        response = self._send_command(self.CMD_DUST_CONTROL, data)
        return response is not None

    def read_data(self):
        """
        Read sensor data (using query mode)
        :return: Dictionary containing all sensor data
        """
        return self.query_data()
    
    def __del__(self):
        """Ensure serial port is closed"""
        if self.serial and self.serial.is_open:
            self.serial.close() 