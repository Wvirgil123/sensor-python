# sensor-python

A Python sensor driver library for Raspberry Pi, supporting various commonly used sensors.

## Supported Sensors

1. BME280 - Temperature, Humidity and Pressure Sensor
   - Measurement Ranges:
     - Temperature: -40°C ~ 85°C
     - Humidity: 0% ~ 100%
     - Pressure: 300hPa ~ 1100hPa

2. BH1750 - Light Intensity Sensor
   - Measurement Range: 1 ~ 65535 lux
   - Supports multiple measurement modes

3. ZPHS01C - Air Quality Sensor
   - Measurement Parameters:
     - CO2: 400-5000ppm
     - VOC: 0-3
     - PM2.5/PM10/PM1.0: 0-1000μg/m³
     - Temperature and Humidity

4. MMWaveRadar - Millimeter Wave Radar Sensor
   - Moving target detection
   - Static target detection
   - Configurable detection distance and sensitivity

## Dependencies

- smbus2: For I2C communication
- pyserial: For serial communication
- time: System time module

## Installation

```bash
pip install smbus2 pyserial
```

## Usage Example

Please refer to the example code in `sensor_test.py`.
