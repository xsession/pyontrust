#ifndef GENERATED_TYPES_H
#define GENERATED_TYPES_H

/* Auto-generated — do not edit */

#include <stdint.h>

typedef union {
    uint8_t all;
    led_control_tst_t bits;
} led_control_tun_t;

typedef struct __attribute__((packed)) {
    uint8_t led_status : 1;
    uint8_t led_user : 1;
    uint8_t led_error : 1;
    uint8_t led_comm : 1;
    uint8_t reserved : 4;
} led_control_tst_t;

typedef union {
    uint8_t all;
    button_state_tst_t bits;
} button_state_tun_t;

typedef struct __attribute__((packed)) {
    uint8_t btn_user : 1;
    uint8_t reserved : 7;
} button_state_tst_t;

typedef union {
    uint16_t all;
    device_status_tst_t bits;
} device_status_tun_t;

typedef struct __attribute__((packed)) {
    uint16_t active : 1;
    uint16_t error : 1;
    uint16_t can_ok : 1;
    uint16_t temp_warn : 1;
    uint16_t cal_valid : 1;
    uint16_t reserved : 11;
} device_status_tst_t;

#endif /* GENERATED_TYPES_H */
