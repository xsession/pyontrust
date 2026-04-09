#ifndef GENERATED_TYPES_H
#define GENERATED_TYPES_H

/* Auto-generated — do not edit */

#include <stdint.h>

typedef enum {
    OK = 0x0,
    ERR_INVALID_CMD = 0x1,
    ERR_INVALID_PARAM = 0x2,
    ERR_BUSY = 0x3,
    ERR_NOT_FOUND = 0x4,
    ERR_TIMEOUT = 0x5,
    ERR_INTERNAL = 0xff,
} tcp_result_ten_t;

typedef enum {
    IN_PROGRESS = 0x0,
    DONE = 0x1,
    ERROR = 0x2,
    CANCELLED = 0x3,
} meas_status_ten_t;

#endif /* GENERATED_TYPES_H */
