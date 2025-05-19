#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import smbus
import time

class BME280:
    # BME280 device address
    DEVICE_ADDRESS = 0x76
    
    # Register addresses
    REG_ID = 0xD0
    REG_RESET = 0xE0
    REG_CTRL_HUM = 0xF2
    REG_STATUS = 0xF3
    REG_CTRL_MEAS = 0xF4
    REG_CONFIG = 0xF5
    REG_PRESS_MSB = 0xF7
    REG_TEMP_MSB = 0xFA
    REG_HUM_MSB = 0xFD
    
    # Calibration data registers
    REG_CALIB = 0x88
    REG_CALIB_H1 = 0xA1
    REG_CALIB_H2 = 0xE1
    
    # 配置参数
    CONFIG_INIT_VALUE = 0x3F
    CONFIG_VALUE = 0x00
    CTRL_HUM_VALUE = 0x05
    CTRL_MEAS_VALUE = 0xB7
    
    # 数据范围限制
    PRESSURE_MIN = 300.0  # hPa
    PRESSURE_MAX = 1100.0  # hPa
    HUMIDITY_MIN = 0.0    # %
    HUMIDITY_MAX = 100.0  # %
    
    def __init__(self, bus_number=1):
        """
        Initialize BME280 sensor
        :param bus_number: I2C bus number, usually 1 for Raspberry Pi
        """
        self.bus = smbus.SMBus(bus_number)
        self.calibration_data = {}
        
        # Check if sensor is present
        if self.bus.read_byte_data(self.DEVICE_ADDRESS, self.REG_ID) != 0x60:
            raise RuntimeError("BME280 sensor not found!")
        
        # Read calibration data
        self._read_calibration_data()
        
        # Configure sensor
        self._configure_sensor()
    
    def _read_calibration_data(self):
        """Read calibration data from sensor"""
        # Read temperature and pressure calibration data
        calib_data = self.bus.read_i2c_block_data(self.DEVICE_ADDRESS, self.REG_CALIB, 24)
        
        # Temperature calibration
        self.calibration_data['dig_T1'] = (calib_data[1] << 8) | calib_data[0]
        self.calibration_data['dig_T2'] = (calib_data[3] << 8) | calib_data[2]
        self.calibration_data['dig_T3'] = (calib_data[5] << 8) | calib_data[4]
        
        # Handle negative values for T2 and T3
        if self.calibration_data['dig_T2'] > 32767:
            self.calibration_data['dig_T2'] -= 65536
        if self.calibration_data['dig_T3'] > 32767:
            self.calibration_data['dig_T3'] -= 65536
        
        # Pressure calibration
        self.calibration_data['dig_P1'] = (calib_data[7] << 8) | calib_data[6]
        self.calibration_data['dig_P2'] = (calib_data[9] << 8) | calib_data[8]
        self.calibration_data['dig_P3'] = (calib_data[11] << 8) | calib_data[10]
        self.calibration_data['dig_P4'] = (calib_data[13] << 8) | calib_data[12]
        self.calibration_data['dig_P5'] = (calib_data[15] << 8) | calib_data[14]
        self.calibration_data['dig_P6'] = (calib_data[17] << 8) | calib_data[16]
        self.calibration_data['dig_P7'] = (calib_data[19] << 8) | calib_data[18]
        self.calibration_data['dig_P8'] = (calib_data[21] << 8) | calib_data[20]
        self.calibration_data['dig_P9'] = (calib_data[23] << 8) | calib_data[22]
        
        # Handle negative values for P2-P9
        for i in range(2, 10):
            if self.calibration_data[f'dig_P{i}'] > 32767:
                self.calibration_data[f'dig_P{i}'] -= 65536
        
        # Read humidity calibration data
        self.calibration_data['dig_H1'] = self.bus.read_byte_data(self.DEVICE_ADDRESS, self.REG_CALIB_H1)
        
        calib_data = self.bus.read_i2c_block_data(self.DEVICE_ADDRESS, self.REG_CALIB_H2, 7)
        self.calibration_data['dig_H2'] = (calib_data[1] << 8) | calib_data[0]
        self.calibration_data['dig_H3'] = calib_data[2]
        self.calibration_data['dig_H4'] = (calib_data[3] << 4) | (calib_data[4] & 0x0F)
        self.calibration_data['dig_H5'] = (calib_data[4] >> 4) | (calib_data[5] << 4)
        self.calibration_data['dig_H6'] = calib_data[6]
        
        # Handle negative values for H2, H4, H5, H6
        if self.calibration_data['dig_H2'] > 32767:
            self.calibration_data['dig_H2'] -= 65536
        if self.calibration_data['dig_H4'] > 32767:
            self.calibration_data['dig_H4'] -= 65536
        if self.calibration_data['dig_H5'] > 32767:
            self.calibration_data['dig_H5'] -= 65536
        if self.calibration_data['dig_H6'] > 127:
            self.calibration_data['dig_H6'] -= 256
    
    def _configure_sensor(self):
        """Configure sensor for normal operation"""
        # Set humidity oversampling
        self.bus.write_byte_data(self.DEVICE_ADDRESS, self.REG_CTRL_HUM, self.CTRL_HUM_VALUE)
        
        # Set temperature and pressure oversampling and normal mode
        self.bus.write_byte_data(self.DEVICE_ADDRESS, self.REG_CTRL_MEAS, self.CTRL_MEAS_VALUE)
        
        # # Set standby time and filter
        # self.bus.write_byte_data(self.DEVICE_ADDRESS, self.REG_CONFIG, self.CONFIG_VALUE)
        
        # Wait for sensor to stabilize
        time.sleep(0.1)
    
    def _read_raw_data(self):
        """Read raw data from sensor"""
        data = self.bus.read_i2c_block_data(self.DEVICE_ADDRESS, self.REG_PRESS_MSB, 8)
        
        # 使用uint32_t确保正确的位操作
        pres_raw = ((data[0] & 0xFF) << 12) | ((data[1] & 0xFF) << 4) | ((data[2] & 0xFF) >> 4)
        temp_raw = ((data[3] & 0xFF) << 12) | ((data[4] & 0xFF) << 4) | ((data[5] & 0xFF) >> 4)
        hum_raw = ((data[6] & 0xFF) << 8) | (data[7] & 0xFF)
        
        return pres_raw, temp_raw, hum_raw
    
    def _compensate_temperature(self, temp_raw):
        """Compensate raw temperature data"""
        var1 = ((temp_raw/16384.0 - self.calibration_data['dig_T1']/1024.0) * 
                self.calibration_data['dig_T2'])
        var2 = ((temp_raw/131072.0 - self.calibration_data['dig_T1']/8192.0) * 
                (temp_raw/131072.0 - self.calibration_data['dig_T1']/8192.0) * 
                self.calibration_data['dig_T3'])
        t_fine = var1 + var2
        temperature = t_fine / 5120.0
        return temperature, t_fine
    
    def _compensate_pressure(self, pres_raw, t_fine):
        """Compensate raw pressure data"""
        # 使用乘法代替位移操作
        var1 = t_fine - 128000
        var2 = var1 * var1 * self.calibration_data['dig_P6']
        var2 = var2 + (var1 * self.calibration_data['dig_P5'] * 131072)  # 2^17
        var2 = var2 + (self.calibration_data['dig_P4'] * 34359738368)    # 2^35
        var1 = ((var1 * var1 * self.calibration_data['dig_P3']) / 256) + (var1 * self.calibration_data['dig_P2'] * 4096)  # 2^12
        var1 = (((1 * 140737488355328) + var1) * self.calibration_data['dig_P1']) / 8589934592  # 2^47 and 2^33
        
        if var1 == 0:
            raise ValueError("Invalid pressure calculation: division by zero")
        
        pressure = 1048576 - pres_raw
        pressure = (((pressure * 2147483648) - var2) * 3125) / var1  # 2^31
        var1 = (self.calibration_data['dig_P9'] * (pressure / 8192) * (pressure / 8192)) / 33554432  # 2^13 and 2^25
        var2 = (self.calibration_data['dig_P8'] * pressure) / 524288  # 2^19
        
        pressure = ((pressure + var1 + var2) / 256) + (self.calibration_data['dig_P7'] * 16)  # 2^8 and 2^4
        pressure = pressure / 25600.0  # 转换为hPa
        
        # 检查气压值是否在合理范围内
        if pressure < 300.0 or pressure > 1100.0:
            raise ValueError(f"Pressure value {pressure} hPa is outside normal range (300-1100 hPa)")
            
        return pressure
    
    def _compensate_humidity(self, hum_raw, t_fine):
        """Compensate raw humidity data"""
        humidity = t_fine - 76800.0
        
        humidity = (hum_raw - (self.calibration_data['dig_H4'] * 64.0 + 
                              self.calibration_data['dig_H5'] / 16384.0 * humidity)) * (
            self.calibration_data['dig_H2'] / 65536.0 * (1.0 + 
            self.calibration_data['dig_H6'] / 67108864.0 * humidity * 
            (1.0 + self.calibration_data['dig_H3'] / 67108864.0 * humidity)))
        
        humidity = humidity * (1.0 - self.calibration_data['dig_H1'] * humidity / 524288.0)
        
        if humidity > 100.0:
            humidity = 100.0
        elif humidity < 0.0:
            humidity = 0.0
            
        return humidity
    
    def read_data(self):
        """
        Read temperature, pressure and humidity data
        :return: tuple of (temperature in °C, pressure in hPa, humidity in %)
        """
        try:
            pres_raw, temp_raw, hum_raw = self._read_raw_data()
            temperature, t_fine = self._compensate_temperature(temp_raw)
            pressure = self._compensate_pressure(pres_raw, t_fine)
            humidity = self._compensate_humidity(hum_raw, t_fine)
            
            return temperature, pressure, humidity
        except Exception as e:
            print(f"Error reading BME280 data: {e}")
            return None, None, None 