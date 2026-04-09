#ifndef LOCATOR_BASE_RS_485_MODBUS_INTERFACE_H
#define LOCATOR_BASE_RS_485_MODBUS_INTERFACE_H

/* Locator Base RS-485 Modbus Interface — auto-generated */

#include <stdint.h>
#include "rs485_mcu_types.h"
#include "canopen_mcu_types.h"

#define MODBUS_SLAVE_ID      0x10

#define HREG_DEVICE_STATUS                            0x0000
#define HREG_LED_CONTROL                              0x0001
#define HREG_FW_VERSION_MAJOR                         0x0002
#define HREG_FW_VERSION_MINOR                         0x0003
#define HREG_NODE_ID                                  0x0004
#define HREG_BAUD_RATE_CODE                           0x0005
#define HREG_PARITY_MODE                              0x0006
#define HREG_SAVE_CONFIG                              0x0007
#define HREG_PWM0_FREQ_HZ                             0x0010
#define HREG_PWM0_DUTY_PCT                            0x0011
#define HREG_PWM1_FREQ_HZ                             0x0012
#define HREG_PWM1_DUTY_PCT                            0x0013
#define HREG_PWM2_FREQ_HZ                             0x0014
#define HREG_PWM2_DUTY_PCT                            0x0015
#define HREG_PWM3_FREQ_HZ                             0x0016
#define HREG_PWM3_DUTY_PCT                            0x0017
#define HREG_DOUT_MASK                                0x0020

#define IREG_BOARD_TEMPERATURE                        0x0000
#define IREG_SUPPLY_VOLTAGE                           0x0001
#define IREG_ADC_CH0                                  0x0002
#define IREG_ADC_CH1                                  0x0003
#define IREG_ADC_CH2                                  0x0004
#define IREG_ADC_CH3                                  0x0005
#define IREG_DIN_STATE                                0x0006
#define IREG_UPTIME_S                                 0x0007
#define IREG_CAN_RX_COUNT                             0x0008
#define IREG_CAN_TX_COUNT                             0x0009
#define IREG_ERROR_COUNT                              0x000a

#define DREG_DIN0                                     0x0000
#define DREG_DIN1                                     0x0001
#define DREG_DIN2                                     0x0002
#define DREG_DIN3                                     0x0003
#define DREG_CAN_BUS_OK                               0x0004
#define DREG_TEMP_WARNING                             0x0005


#endif /* LOCATOR_BASE_RS_485_MODBUS_INTERFACE_H */
