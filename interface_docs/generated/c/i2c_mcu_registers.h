#ifndef LOCATOR_BASE_I2C_SENSOR_BUS_INTERFACE_H
#define LOCATOR_BASE_I2C_SENSOR_BUS_INTERFACE_H

/* Locator Base I2C Sensor Bus Interface — auto-generated */

#include <stdint.h>
#include "i2c_mcu_types.h"

#define I2C_ADDR_TEMP_SENSOR                          0x48
#define TEMP_SENSOR_REG_TEMPERATURE                  0x00
#define TEMP_SENSOR_REG_CONFIG                       0x01
#define TEMP_SENSOR_REG_T_HIGH_LIMIT                 0x02
#define TEMP_SENSOR_REG_T_LOW_LIMIT                  0x03
#define TEMP_SENSOR_REG_EEPROM_UNLOCK                0x04
#define TEMP_SENSOR_REG_EEPROM1                      0x05
#define TEMP_SENSOR_REG_EEPROM2                      0x06
#define TEMP_SENSOR_REG_TEMPERATURE_OFFSET           0x07
#define TEMP_SENSOR_REG_DEVICE_ID                    0x0f

#define I2C_ADDR_EEPROM                               0x50
#define EEPROM_REG_CAL_HEADER                   0x00
#define EEPROM_REG_CAL_DATA                     0x08
#define EEPROM_REG_BOARD_INFO                   0xf8

#define I2C_ADDR_GPIO_EXPANDER                        0x20

#define I2C_ADDR_POWER_MONITOR                        0x40
#define POWER_MONITOR_REG_CONFIG                       0x00
#define POWER_MONITOR_REG_SHUNT_VOLTAGE                0x01
#define POWER_MONITOR_REG_BUS_VOLTAGE                  0x02
#define POWER_MONITOR_REG_POWER                        0x03
#define POWER_MONITOR_REG_CURRENT                      0x04
#define POWER_MONITOR_REG_CALIBRATION                  0x05


#endif /* LOCATOR_BASE_I2C_SENSOR_BUS_INTERFACE_H */
