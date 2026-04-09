#ifndef LOCATOR_BASE_UART_DEBUG_INTERFACE_H
#define LOCATOR_BASE_UART_DEBUG_INTERFACE_H

/* Locator Base UART Debug Interface — auto-generated */

#include <stdint.h>
#include "uart_mcu_types.h"

/* Physical: TX=PA10, RX=PA11, Baud=115200 */
#define UART_BAUD_RATE       115200
#define UART_START_BYTE      0xaa
#define UART_END_BYTE        0x55

#define CMD_GET_VERSION                              0x01
#define CMD_GET_STATUS                               0x02
#define CMD_RESET                                    0x03
#define CMD_SET_LED                                  0x10
#define CMD_GET_LED                                  0x11
#define CMD_SET_GPIO                                 0x12
#define CMD_GET_GPIO                                 0x13
#define CMD_READ_ADC                                 0x20
#define CMD_SET_PWM                                  0x30
#define CMD_WRITE_CAL                                0x40
#define CMD_READ_CAL                                 0x41
#define CMD_ASYNC_EVENT                              0xe0


#endif /* LOCATOR_BASE_UART_DEBUG_INTERFACE_H */
