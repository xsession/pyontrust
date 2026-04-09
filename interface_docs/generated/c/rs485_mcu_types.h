#ifndef GENERATED_TYPES_H
#define GENERATED_TYPES_H

/* Auto-generated — do not edit */

#include <stdint.h>

typedef enum {
    BAUD_1200 = 0x0,
    BAUD_2400 = 0x1,
    BAUD_4800 = 0x2,
    BAUD_9600 = 0x3,
    BAUD_19200 = 0x4,
    BAUD_38400 = 0x5,
    BAUD_57600 = 0x6,
    BAUD_115200 = 0x7,
} baud_rate_ten_t;

typedef enum {
    ILLEGAL_FUNCTION = 0x1,
    ILLEGAL_DATA_ADDRESS = 0x2,
    ILLEGAL_DATA_VALUE = 0x3,
    SLAVE_DEVICE_FAILURE = 0x4,
    ACKNOWLEDGE = 0x5,
    SLAVE_DEVICE_BUSY = 0x6,
} modbus_exception_ten_t;

#endif /* GENERATED_TYPES_H */
