#ifndef LOCATOR_BASE_ETHERNET_CONTROL_INTERFACE_H
#define LOCATOR_BASE_ETHERNET_CONTROL_INTERFACE_H

/* Locator Base Ethernet Control Interface — auto-generated */

#include <stdint.h>
#include "tcp_udp_mcu_types.h"
#include "canopen_mcu_types.h"

#define TCP_PORT             5200
#define TCP_CMD_PING                             0x0000
#define TCP_CMD_GET_DEVICE_INFO                  0x0001
#define TCP_CMD_GET_STATUS                       0x0002
#define TCP_CMD_SET_LED                          0x0010
#define TCP_CMD_SET_GPIO                         0x0011
#define TCP_CMD_GET_GPIO                         0x0012
#define TCP_CMD_START_MEASUREMENT                0x0020
#define TCP_CMD_GET_MEASUREMENT                  0x0021
#define TCP_CMD_CAN_SEND                         0x0030
#define TCP_CMD_CAN_SUBSCRIBE                    0x0031

#define UDP_PORT             5201
#define UDP_MSG_HEARTBEAT                        0x0100
#define UDP_MSG_TELEMETRY                        0x0101
#define UDP_MSG_CAN_FRAME                        0x0102


#endif /* LOCATOR_BASE_ETHERNET_CONTROL_INTERFACE_H */
