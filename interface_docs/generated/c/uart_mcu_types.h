#ifndef GENERATED_TYPES_H
#define GENERATED_TYPES_H

/* Auto-generated — do not edit */

#include <stdint.h>

typedef struct __attribute__((packed)) {
    uint32_t start : 8;
    uint32_t cmd_id : 8;
    uint32_t payload_len : 8;
    uint32_t seq : 8;
} uart_frame_header_tst_t;

typedef enum {
    EVT_BUTTON_PRESS = 0x1,
    EVT_BUTTON_RELEASE = 0x2,
    EVT_TEMP_WARNING = 0x10,
    EVT_TEMP_CRITICAL = 0x11,
    EVT_VOLTAGE_LOW = 0x20,
    EVT_VOLTAGE_HIGH = 0x21,
    EVT_CAN_BUS_OFF = 0x30,
    EVT_WATCHDOG = 0xfe,
    EVT_FAULT = 0xff,
} uart_event_code_ten_t;

typedef enum {
    ACK = 0x6,
    NAK = 0x15,
    NAK_INVALID_CMD = 0x80,
    NAK_INVALID_PARAM = 0x81,
    NAK_BUSY = 0x82,
    NAK_CRC_ERROR = 0x83,
} uart_ack_ten_t;

#endif /* GENERATED_TYPES_H */
