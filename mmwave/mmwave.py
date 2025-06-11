#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import struct
import threading
import queue

class MMWaveRadar:
    """
    MMWave radar driver class for XIAO board (24GHz mmWave sensor)
    """
    class TargetStatus:
        NoTarget = 0
        MovingTarget = 1
        StaticTarget = 2
        BothTargets = 3
        ErrorFrame = 4

    class RadarMode:
        Normal = 0
        Engineering = 1

    class AskStatus:
        Success = 0
        Error = 1

    def __init__(self, port='/dev/ttyUSB0', baudrate=256000):
        """
        Initialize the MMWave radar driver
        
        Args:
            port (str): Serial port name
            baudrate (int): Serial baudrate (default: 256000)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.engineering_mode = False
        self.config_mode = False
        self.data_queue = queue.Queue(maxsize=2)  # 添加数据队列，设置最大大小为2，只存储最新的两条数据
        self.reading_thread = None  # 添加读取线程
        self.running = False  # 添加运行状态标志

    def connect(self):
        """
        Connect to the radar device
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            # 清空缓冲区
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            return True
        except Exception as e:
            print(f"Failed to connect to radar: {e}")
            return False

    def disconnect(self):
        """
        Disconnect from the radar device
        """
        self.stop_reading()  # 停止数据读取线程
        if self.serial:
            self.serial.close()

    def start_reading(self):
        """
        启动数据读取线程
        在完成所有配置后调用此函数开始读取数据
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if not self.serial:
            print("Radar not connected")
            return False
            
        if self.running:
            print("Reading thread already running")
            return True
            
        try:
            self.running = True
            self.reading_thread = threading.Thread(target=self._read_loop)
            self.reading_thread.daemon = True
            self.reading_thread.start()
            print("Started radar data reading thread")
            return True
        except Exception as e:
            print(f"Failed to start reading thread: {e}")
            self.running = False
            return False

    def stop_reading(self):
        """
        停止数据读取线程
        """
        if not self.running:
            return
            
        self.running = False
        if self.reading_thread:
            self.reading_thread.join(timeout=1.0)
            self.reading_thread = None
            print("Stopped radar data reading thread")

    def _read_loop(self):
        """数据读取循环"""
        buffer = bytearray()
        while self.running:
            try:
                if self.serial:
                    # 读取可用数据
                    if self.serial.in_waiting > 0:
                        data = self.serial.read(self.serial.in_waiting)
                        buffer.extend(data)
                        # print(f"<--{' '.join([f'{x:02X}' for x in data])}")
                        
                        # 查找帧头
                        while len(buffer) >= 4:
                            # 查找帧头 (F4 F3 F2 F1)
                            if buffer[0] == 0xF4 and buffer[1] == 0xF3 and \
                               buffer[2] == 0xF2 and buffer[3] == 0xF1:
                                # 检查是否有足够的数据来确定帧长度
                                if len(buffer) >= 8:

                                    # 根据帧类型确定长度
                                    frame_length = buffer[4] + 10
                                    
                                    # 检查是否有完整帧
                                    if len(buffer) >= frame_length:
                                        # 检查帧尾 (F8 F7 F6 F5)
                                        if buffer[frame_length-4] == 0xF8 and \
                                           buffer[frame_length-3] == 0xF7 and \
                                           buffer[frame_length-2] == 0xF6 and \
                                           buffer[frame_length-1] == 0xF5:
                                            # 提取完整帧
                                            frame = bytes(buffer[:frame_length])
                                            # 移除已处理的数据
                                            buffer = buffer[frame_length:]
                                            
                                            # 解析数据
                                            parsed_data = self._parse_data(frame)
                                            if parsed_data:
                                                # 如果队列已满，移除最旧的数据
                                                if self.data_queue.full():
                                                    try:
                                                        self.data_queue.get_nowait()
                                                    except queue.Empty:
                                                        pass
                                                self.data_queue.put(parsed_data)
                                        else:
                                            # 帧尾不匹配，移除第一个字节继续查找
                                            buffer = buffer[1:]
                                    else:
                                        # 数据不足，等待更多数据
                                        break
                                else:
                                    # 数据不足，等待更多数据
                                    break
                            else:
                                # 不是帧头，移除第一个字节继续查找
                                buffer = buffer[1:]
            except Exception as e:
                print(f"Error in read loop: {e}")
            time.sleep(0.01)  # 短暂休眠，避免CPU占用过高

    def send_command(self, send_data):
        """
        Send command and wait for ACK
        
        Args:
            send_data (bytes): Command data to send
            
        Returns:
            tuple: (bool, bytes) - (Success status, Response data)
        """
        try:
            max_retries = 3
            retry_count = 0
            start_time = time.time()
            last_send_time = 0
            send_interval = 1.0  # 减少重试间隔到1秒
            buffer = bytearray()
            
            while retry_count < max_retries:
                current_time = time.time()
                
                # 检查是否该发送命令
                if current_time - last_send_time >= send_interval:
                    # 清空输入缓冲区
                    self.serial.reset_input_buffer()
                    # 发送数据
                    self.serial.write(send_data)
                    # print(f"-->{' '.join([f'{x:02X}' for x in send_data])}")
                    retry_count += 1
                    last_send_time = current_time
                
                # 等待设备响应
                time.sleep(0.2)  # 减少等待时间
                
                # 读取所有可用数据
                if self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    # print(f"<--{' '.join([f'{x:02X}' for x in data])}")
                    buffer.extend(data)
                    
                    # 检查是否收到完整的帧
                    if len(buffer) >= 4:
                        # 查找帧头 (0xFD, 0xFC, 0xFB, 0xFA)
                        start_index = -1
                        for i in range(len(buffer) - 3):
                            if (buffer[i] == 0xFD and buffer[i+1] == 0xFC and 
                                buffer[i+2] == 0xFB and buffer[i+3] == 0xFA):
                                start_index = i
                                break
                        
                        if start_index != -1:
                            # 查找帧尾 (0x04, 0x03, 0x02, 0x01)
                            end_index = -1
                            for i in range(start_index + 4, len(buffer) - 3):
                                if (buffer[i] == 0x04 and buffer[i+1] == 0x03 and 
                                    buffer[i+2] == 0x02 and buffer[i+3] == 0x01):
                                    end_index = i + 3
                                    break
                            
                            if end_index != -1:
                                # 提取完整帧
                                frame = bytes(buffer[start_index:end_index+1])
                                # 清除已处理的数据
                                buffer = buffer[end_index+1:]
                                
                                # 检查ACK状态
                                if len(frame) >= 9 and frame[8] == 0:
                                    return True, frame
                                else:
                                    return False, frame
                
                # 检查总超时
                if current_time - start_time > 4.0:  # 减少总超时时间到4秒
                    break
                    
        except Exception as e:
            print(f"Failed to send command: {e}")
        return False, None

    def enable_config_mode(self):
        """
        Enable configuration mode
        
        Returns:
            AskStatus: Success or Error
        """
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x04, 0x00, 0xFF, 0x00, 0x01, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success:
                self.config_mode = True  # 设置配置模式状态为True
                return self.AskStatus.Success
        except Exception as e:
            print(f"Failed to enable config mode: {e}")
        return self.AskStatus.Error

    def disable_config_mode(self):
        """
        Disable configuration mode
        
        Returns:
            AskStatus: Success or Error
        """
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0xFE, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success:
                self.config_mode = False  # 设置配置模式状态为False
                return self.AskStatus.Success
        except Exception as e:
            print(f"Failed to disable config mode: {e}")
        return self.AskStatus.Error

    def enable_engineering_mode(self):
        """
        Enable engineering mode for detailed data output
        
        Returns:
            AskStatus: Success or Error
        """
        if self.enable_config_mode() == self.AskStatus.Success:
            try:
                cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0x62, 0x00, 0x04, 0x03, 0x02, 0x01])
                success, response = self.send_command(cmd)
                if success:
                    self.engineering_mode = True
                    self.disable_config_mode()
                    return self.AskStatus.Success
            except Exception as e:
                print(f"Failed to enable engineering mode: {e}")
            self.disable_config_mode()
        return self.AskStatus.Error

    def disable_engineering_mode(self):
        """
        Disable engineering mode
        
        Returns:
            AskStatus: Success or Error
        """
        if self.enable_config_mode() == self.AskStatus.Success:
            try:
                cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0x63, 0x00, 0x04, 0x03, 0x02, 0x01])
                success, response = self.send_command(cmd)
                if success:
                    self.engineering_mode = False
                    self.disable_config_mode()
                    return self.AskStatus.Success
            except Exception as e:
                print(f"Failed to disable engineering mode: {e}")
            self.disable_config_mode()
        return self.AskStatus.Error

    def get_version(self):
        """
        Get sensor software version
        
        Returns:
            str: Version string or None if failed
        """
        if not self.config_mode:
            return None
            
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0xA0, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success and len(response) >= 17 and response[7] == 0x01:
                version = f"V{response[13]:02x}.{response[12]:02x}.{response[17]:02x}{response[16]:02x}{response[15]:02x}{response[14]:02x}"
                return version
        except Exception as e:
            print(f"Failed to get version: {e}")
        return None
    
    def set_bluetooth(self, enable):
        """
        Set Bluetooth on/off

        Args:
            enable (bool): True to turn on Bluetooth, False to turn off

        Returns:
            AskStatus: Success or Error
        """
        if not self.config_mode:
            return self.AskStatus.Error

        try:
            if enable:
                # Turn on Bluetooth
                cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x04, 0x00, 0xA4, 0x00, 0x01, 0x00, 0x04, 0x03, 0x02, 0x01])
            else:
                # Turn off Bluetooth
                cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x04, 0x00, 0xA4, 0x00, 0x00, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success and len(response) >= 14 and response[7] == 0x01:
                return self.AskStatus.Success
        except Exception as e:
            print(f"Failed to set bluetooth: {e}")
        return self.AskStatus.Error

    def set_detection_distance(self, distance, times):
        """
        Set detection distance and no-target duration
        
        Args:
            distance (int): Detection distance (1-8)
            times (int): No-target duration in seconds
            
        Returns:
            AskStatus: Success or Error
        """
        if not self.config_mode:
            return self.AskStatus.Error
            
        if 1 <= distance <= 8 and times > 0:
            try:
                cmd = bytearray([0xFD, 0xFC, 0xFB, 0xFA, 0x14, 0x00, 0x60, 0x00,
                               0x00, 0x00, 0x08, 0x00, 0x00, 0x00,
                               0x01, 0x00, 0x08, 0x00, 0x00, 0x00,
                               0x02, 0x00, 0x05, 0x00, 0x00, 0x00,
                               0x04, 0x03, 0x02, 0x01])
                cmd[10] = distance
                cmd[16] = distance
                cmd[22] = times & 0xFF
                cmd[23] = (times >> 8) & 0xFF
                cmd[24] = (times >> 16) & 0xFF
                cmd[25] = (times >> 24) & 0xFF
                
                success, response = self.send_command(bytes(cmd))
                if success and len(response) >= 14 and response[7] == 0x01:
                    return self.AskStatus.Success
            except Exception as e:
                print(f"Failed to set detection distance: {e}")
        return self.AskStatus.Error

    def set_gate_power(self, gate, move_power, static_power):
        """
        Set gate sensitivity
        
        Args:
            gate (int): Gate number (1-8)
            move_power (int): Movement sensitivity (1-100)
            static_power (int): Static sensitivity (1-100)
            
        Returns:
            AskStatus: Success or Error
        """
        if not self.config_mode:
            return self.AskStatus.Error
            
        if 1 <= gate <= 8 and 1 <= move_power <= 100 and 1 <= static_power <= 100:
            try:
                cmd = bytearray([0xFD, 0xFC, 0xFB, 0xFA, 0x14, 0x00, 0x64, 0x00,
                               0x00, 0x00, 0x08, 0x00, 0x00, 0x00,
                               0x01, 0x00, 0x08, 0x00, 0x00, 0x00,
                               0x02, 0x00, 0x05, 0x00, 0x00, 0x00,
                               0x04, 0x03, 0x02, 0x01])
                cmd[10] = gate
                cmd[16] = move_power & 0xFF
                cmd[17] = (move_power >> 8) & 0xFF
                cmd[18] = (move_power >> 16) & 0xFF
                cmd[19] = (move_power >> 24) & 0xFF
                cmd[22] = static_power & 0xFF
                cmd[23] = (static_power >> 8) & 0xFF
                cmd[24] = (static_power >> 16) & 0xFF
                cmd[25] = (static_power >> 24) & 0xFF
                
                success, response = self.send_command(bytes(cmd))
                if success and len(response) >= 14 and response[7] == 0x01:
                    return self.AskStatus.Success
            except Exception as e:
                print(f"Failed to set gate power: {e}")
        return self.AskStatus.Error

    def set_resolution(self, resolution):
        """
        Set distance gate resolution
        
        Args:
            resolution (int): 0 for 0.75M, 1 for 0.25M
            
        Returns:
            AskStatus: Success or Error
        """
        if not self.config_mode:
            return self.AskStatus.Error
            
        if resolution in [0, 1]:
            try:
                cmd = bytearray([0xFD, 0xFC, 0xFB, 0xFA, 0x04, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x04, 0x03, 0x02, 0x01])
                cmd[8] = resolution
                
                success, response = self.send_command(bytes(cmd))
                if success:
                    self.reboot()
                    return self.AskStatus.Success
            except Exception as e:
                print(f"Failed to set resolution: {e}")
        return self.AskStatus.Error

    def get_resolution(self):
        """
        Get current distance gate resolution
        
        Returns:
            int: 0 for 0.75M, 1 for 0.25M, or None if failed
        """
        if not self.config_mode:
            return None
            
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0xAB, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success and len(response) >= 14:
                resolution = response[10]
                return resolution
        except Exception as e:
            print(f"Failed to get resolution: {e}")
        return None

    def get_config(self):
        """
        Get radar configuration
        
        Returns:
            dict: Configuration data or None if failed
        """
        if not self.config_mode:
            return None
            
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0x61, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success and len(response) >= 33 and response[7] == 0x01:
                config = {
                    'detection_distance': response[11],
                    'move_set_distance': response[12],
                    'static_set_distance': response[13],
                    'move_power': list(response[14:23]),
                    'static_power': list(response[23:32]),
                    'no_target_duration': struct.unpack('<H', response[32:34])[0]
                }
                return config
        except Exception as e:
            print(f"Failed to get config: {e}")
        return None

    def reset_factory(self):
        """
        Reset radar to factory settings
        
        Returns:
            AskStatus: Success or Error
        """
        if not self.config_mode:
            return self.AskStatus.Error
            
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0xA2, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success:
                self.reboot()
                return self.AskStatus.Success
        except Exception as e:
            print(f"Failed to reset factory settings: {e}")
        return self.AskStatus.Error

    def reboot(self):
        """
        Reboot the radar
        
        Returns:
            AskStatus: Success or Error
        """
        if not self.config_mode:
            return self.AskStatus.Error
            
        try:
            cmd = bytes([0xFD, 0xFC, 0xFB, 0xFA, 0x02, 0x00, 0xA3, 0x00, 0x04, 0x03, 0x02, 0x01])
            success, response = self.send_command(cmd)
            if success:
                return self.AskStatus.Success
        except Exception as e:
            print(f"Failed to reboot radar: {e}")
        return self.AskStatus.Error

    def _parse_data(self, data):
        """
        Parse the raw data from the radar
        
        Args:
            data (bytes): Raw data from the radar
        """
        try:
            # Parse basic data
            radar_mode = data[6]
            if data[7] != 0xAA:
                return None
            target_status = data[8]
            moving_distance = struct.unpack('<H', data[9:11])[0]
            moving_power = data[11]
            static_distance = struct.unpack('<H', data[12:14])[0]
            static_power = data[14]
            result = {
                'target_status': target_status,
                'moving_distance': moving_distance,
                'moving_power': moving_power,
                'static_distance': static_distance,
                'static_power': static_power,
                'radar_mode': radar_mode,
                'timestamp': time.time()
            }
            
            # Parse engineering mode data if enabled
            if self.engineering_mode and radar_mode == self.RadarMode.Engineering:
                move_power = list(data[19:28])
                static_power = list(data[28:37])
                photosensitive = data[37]
                
                result.update({
                    'move_power': move_power,
                    'static_power': static_power,
                    'photosensitive': photosensitive
                })
            
            return result
        except Exception as e:
            print(f"Error parsing radar data: {e}")
            return None

    def read_data(self):
        """
        Read the latest data from the radar queue
        
        Returns:
            dict: Dictionary containing radar data or None if no data available
        """
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None

    def __del__(self):
        """
        Cleanup when the object is destroyed
        """
        self.disconnect() 