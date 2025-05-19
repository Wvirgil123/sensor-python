#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import smbus
import time

class BH1750:
    # BH1750 device address
    DEVICE_ADDRESS = 0x23
    
    # Commands
    POWER_ON = 0x01
    CONTINUOUS_HIGH_RES_MODE = 0x10
    CONTINUOUS_HIGH_RES_MODE_2 = 0x11
    CONTINUOUS_LOW_RES_MODE = 0x13
    ONE_TIME_HIGH_RES_MODE = 0x20
    ONE_TIME_HIGH_RES_MODE_2 = 0x21
    ONE_TIME_LOW_RES_MODE = 0x23

    def __init__(self, bus_number=1):
        """
        Initialize BH1750 sensor
        :param bus_number: I2C bus number, usually 1 for Raspberry Pi
        """
        self.bus = smbus.SMBus(bus_number)
        self.power_on()
        self.set_mode(self.CONTINUOUS_HIGH_RES_MODE)

    def power_on(self):
        """Turn on sensor power"""
        self.bus.write_byte(self.DEVICE_ADDRESS, self.POWER_ON)

    def power_off(self):
        """Turn off sensor power"""
        self.bus.write_byte(self.DEVICE_ADDRESS, 0x00)

    def set_mode(self, mode):
        """
        Set sensor operation mode
        :param mode: operation mode
        """
        self.bus.write_byte(self.DEVICE_ADDRESS, mode)

    def read_light(self):
        """
        Read light intensity
        :return: light intensity value in lux
        """
        try:
            # Read two bytes of data
            data = self.bus.read_i2c_block_data(self.DEVICE_ADDRESS, self.CONTINUOUS_HIGH_RES_MODE, 2)
            # Combine two bytes into a 16-bit integer
            result = (data[0] << 8) + data[1]
            # Convert to actual light intensity value (lux)
            return result / 1.2
        except Exception as e:
            print(f"Error reading light intensity: {e}")
            return None

    def __del__(self):
        """Destructor to ensure sensor power is turned off"""
        try:
            self.power_off()
        except:
            pass 