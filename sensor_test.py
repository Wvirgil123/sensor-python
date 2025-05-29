#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from bh1750.bh1750 import BH1750
from bme280.bme280 import BME280
from zphs01c.zphs01c import ZPHS01C
from mmwave.mmwave import MMWaveRadar

# Sensor enable/disable configuration
SENSOR_CONFIG = {
    'BH1750': True,    # Enable light sensor
    'BME280': True,   # Enable temperature/humidity/pressure sensor
    'ZPHS01C': True,    # Enable air quality sensor
    'MMWAVE': True     # Enable mmWave radar
}

# Radar configuration
RADAR_CONFIG = {
    'port': '/dev/ttyACM1',
    'baudrate': 115200,
    'detection_distance': 5,  # 1-8
    'no_target_duration': 10,  # seconds
    'resolution': 0,  # 0: 0.75M, 1: 0.25M
    'gate_power': {
        'gate': 1,
        'move_power': 50,
        'static_power': 50
    }
}

def target_status_to_string(status):
    """
    Convert target status code to string
    
    Args:
        status (int): Target status code
        
    Returns:
        str: Status description
    """
    status_map = {
        MMWaveRadar.TargetStatus.NoTarget: "No Target",
        MMWaveRadar.TargetStatus.MovingTarget: "Moving Target",
        MMWaveRadar.TargetStatus.StaticTarget: "Static Target",
        MMWaveRadar.TargetStatus.BothTargets: "Both Moving and Static Targets",
        MMWaveRadar.TargetStatus.ErrorFrame: "Error Frame"
    }
    return status_map.get(status, "Unknown Status")

def initialize_radar(radar):
    """
    Initialize and configure the radar
    
    Args:
        radar (MMWaveRadar): Radar instance
        
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        # 进入配置模式
        if radar.enable_config_mode() != MMWaveRadar.AskStatus.Success:
            print("Failed to enter config mode")
            return False
            
        # Get and print version
        version = radar.get_version()
        if version:
            print(f"mmWave Radar Version: {version}")
        else:
            print("Failed to get radar version")
            radar.disable_config_mode()
            return False
        
        # Get and print current configuration
        config = radar.get_config()
        if config:
            print("\nCurrent Radar Configuration:")
            print(f"Detection Distance: {config['detection_distance']} gates")
            print(f"Moving Target Distance: {config['move_set_distance']} gates")
            print(f"Static Target Distance: {config['static_set_distance']} gates")
            print(f"No Target Duration: {config['no_target_duration']} seconds")
            print(f"Moving Target Power Values: {config['move_power']}")
            print(f"Static Target Power Values: {config['static_power']}")
        
        # Set detection distance and no-target duration
        if radar.set_detection_distance(RADAR_CONFIG['detection_distance'], 
                                      RADAR_CONFIG['no_target_duration']) == MMWaveRadar.AskStatus.Success:
            print(f"\nSet Detection Distance: {RADAR_CONFIG['detection_distance']} gates")
            print(f"Set No Target Duration: {RADAR_CONFIG['no_target_duration']} seconds")
        else:
            print("Failed to set detection distance and no-target duration")
            radar.disable_config_mode()
            return False
        
        # Set gate power
        gate_power = RADAR_CONFIG['gate_power']
        if radar.set_gate_power(gate_power['gate'], 
                              gate_power['move_power'], 
                              gate_power['static_power']) == MMWaveRadar.AskStatus.Success:
            print(f"\nSet Gate {gate_power['gate']} Sensitivity:")
            print(f"Moving Target Sensitivity: {gate_power['move_power']}")
            print(f"Static Target Sensitivity: {gate_power['static_power']}")
        else:
            print("Failed to set gate sensitivity")
            radar.disable_config_mode()
            return False
        
        # Set resolution
        if radar.set_resolution(RADAR_CONFIG['resolution']) == MMWaveRadar.AskStatus.Success:
            print(f"\nSet Gate Resolution: {'0.25M' if RADAR_CONFIG['resolution'] == 1 else '0.75M'}")
        else:
            print("Failed to set gate resolution")
            radar.disable_config_mode()
            return False
        
        # 退出配置模式
        radar.disable_config_mode()

        # 启动数据读取线程
        if not radar.start_reading():
            print("Failed to start radar data reading")
            return False
            
        print("Radar data reading started successfully")
        return True
        
    except Exception as e:
        print(f"Error during radar initialization: {e}")
        # 确保在发生异常时也退出配置模式
        try:
            radar.disable_config_mode()
        except:
            pass
        return False

def main():
    try:
        # Create sensor instances based on configuration
        sensors = {}
        
        if SENSOR_CONFIG['BH1750']:
            try:
                sensors['light'] = BH1750(bus_number=5)
                print("BH1750 sensor initialized successfully")
            except Exception as e:
                print(f"Failed to initialize BH1750 sensor: {e}")
                SENSOR_CONFIG['BH1750'] = False
        
        if SENSOR_CONFIG['BME280']:
            try:
                sensors['bme'] = BME280(bus_number=5)
                print("BME280 sensor initialized successfully")
            except Exception as e:
                print(f"Failed to initialize BME280 sensor: {e}")
                SENSOR_CONFIG['BME280'] = False
        
        if SENSOR_CONFIG['ZPHS01C']:
            try:
                sensors['air'] = ZPHS01C(port="/dev/ttyACM2")
                # 开启粉尘测量
                sensors['air'].control_dust_measurement(True)
                # 启动主动上传模式
                sensors['air'].start_active_upload()
                print("ZPHS01C sensor initialized successfully")
            except Exception as e:
                print(f"Failed to initialize ZPHS01C sensor: {e}")
                SENSOR_CONFIG['ZPHS01C'] = False

        if SENSOR_CONFIG['MMWAVE']:
            try:
                sensors['radar'] = MMWaveRadar(port=RADAR_CONFIG['port'], 
                                             baudrate=RADAR_CONFIG['baudrate'])
                if sensors['radar'].connect():
                    print("mmWave radar connected successfully")
                    if not initialize_radar(sensors['radar']):
                        print("Failed to initialize mmWave radar")
                        SENSOR_CONFIG['MMWAVE'] = False
                else:
                    print("Failed to connect to mmWave radar")
                    SENSOR_CONFIG['MMWAVE'] = False
            except Exception as e:
                print(f"Failed to initialize mmWave radar: {e}")
                SENSOR_CONFIG['MMWAVE'] = False
        
        print("\nStarting to read sensor data...")
        print("Press Ctrl+C to stop the program")
        
        while True:
            # Read light intensity if enabled
            if SENSOR_CONFIG['BH1750'] and 'light' in sensors:
                light = sensors['light'].read_light()
                if light is not None:
                    print(f"Light Intensity: {light:.2f} lux")
                else:
                    print("Failed to read light data")
            
            # Read temperature, pressure and humidity from BME280 if enabled
            if SENSOR_CONFIG['BME280'] and 'bme' in sensors:
                temp, press, hum = sensors['bme'].read_data()
                if all(v is not None for v in [temp, press, hum]):
                    print(f"BME280 - Temperature: {temp:.1f}°C")
                    print(f"BME280 - Pressure: {press:.1f} hPa")
                    print(f"BME280 - Humidity: {hum:.1f}%")
                else:
                    print("Failed to read BME280 data")
            
            # Read air quality data from ZPHS01C if enabled
            if SENSOR_CONFIG['ZPHS01C'] and 'air' in sensors:
                data = sensors['air'].read_data()
                if data:
                    print(f"ZPHS01C - CO2: {data['co2']} ppm")
                    print(f"ZPHS01C - PM2.5: {data['pm25']} μg/m³")
                    print(f"ZPHS01C - VOC: {data['voc']}")
                    print(f"ZPHS01C - PM10: {data['pm10']} μg/m³")
                    print(f"ZPHS01C - PM1.0: {data['pm1']} μg/m³")
                    print(f"ZPHS01C - Temperature: {data['temperature']:.1f}°C")
                    print(f"ZPHS01C - Humidity: {data['humidity']:.1f}%")
                else:
                    print("Failed to read ZPHS01C data")

            # Read mmWave radar data if enabled
            if SENSOR_CONFIG['MMWAVE'] and 'radar' in sensors:
                try:
                    # 使用新的队列方式读取数据
                    radar_data = sensors['radar'].read_data()
                    if radar_data is not None:
                        print(f"mmWave Radar - Status: {target_status_to_string(radar_data['target_status'])}")
                        print(f"mmWave Radar - Moving Distance: {radar_data['moving_distance']} mm")
                        print(f"mmWave Radar - Moving Power: {radar_data['moving_power']}")
                        print(f"mmWave Radar - Static Distance: {radar_data['static_distance']} mm")
                        print(f"mmWave Radar - Static Power: {radar_data['static_power']}")
                        print(f"mmWave Radar - Mode: {'Engineering Mode' if radar_data['radar_mode'] == MMWaveRadar.RadarMode.Engineering else 'Normal Mode'}")
                        
                        # Print engineering mode data if available
                        if 'move_power' in radar_data:
                            print("mmWave Radar - Moving Target Power Values:", end=" ")
                            for power in radar_data['move_power']:
                                print(f"{power},", end=" ")
                            print()
                            
                            print("mmWave Radar - Static Target Power Values:", end=" ")
                            for power in radar_data['static_power']:
                                print(f"{power},", end=" ")
                            print()
                            
                            print(f"mmWave Radar - Photosensitive Value: {radar_data['photosensitive']}")
                except Exception as e:
                    print(f"Error reading mmWave radar data: {e}")
                    # 如果连续多次读取失败，可以考虑重新初始化雷达
                    if not sensors['radar'].connect():
                        print("Failed to reconnect to mmWave radar")
                        SENSOR_CONFIG['MMWAVE'] = False
            
            print("-" * 30)
            # 减少等待时间，提高数据读取频率
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nProgram stopped")
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        # Clean up all initialized sensors
        for sensor in sensors.values():
            try:
                if isinstance(sensor, MMWaveRadar):
                    sensor.disconnect()
                del sensor
            except:
                pass

if __name__ == "__main__":
    main()
