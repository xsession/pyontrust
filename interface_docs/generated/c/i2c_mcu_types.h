#ifndef GENERATED_TYPES_H
#define GENERATED_TYPES_H

/* Auto-generated — do not edit */

#include <stdint.h>

typedef union {
    uint16_t all;
    tmp117_config_tst_t bits;
} tmp117_config_tun_t;

typedef struct __attribute__((packed)) {
    uint16_t reserved_0 : 1;
    uint16_t soft_reset : 1;
    uint16_t dr_alert : 1;
    uint16_t pol : 1;
    uint16_t t_na : 1;
    uint16_t avg : 2;
    uint16_t conv : 3;
    uint16_t mod : 2;
    uint16_t eeprom_busy : 1;
    uint16_t data_ready : 1;
    uint16_t low_alert : 1;
    uint16_t high_alert : 1;
} tmp117_config_tst_t;

typedef struct __attribute__((packed)) {
    uint64_t magic : 16;
    uint64_t version : 8;
    uint64_t length : 8;
    uint64_t crc16 : 16;
    uint64_t reserved : 16;
} cal_header_tst_t;

typedef union {
    uint8_t all;
    gpio_expander_tst_t bits;
} gpio_expander_tun_t;

typedef struct __attribute__((packed)) {
    uint8_t p0 : 1;
    uint8_t p1 : 1;
    uint8_t p2 : 1;
    uint8_t p3 : 1;
    uint8_t p4 : 1;
    uint8_t p5 : 1;
    uint8_t p6 : 1;
    uint8_t p7 : 1;
} gpio_expander_tst_t;

typedef union {
    uint16_t all;
    ina219_config_tst_t bits;
} ina219_config_tun_t;

typedef struct __attribute__((packed)) {
    uint16_t mode : 3;
    uint16_t sadc : 4;
    uint16_t badc : 4;
    uint16_t pg : 2;
    uint16_t brng : 1;
    uint16_t reserved : 1;
    uint16_t rst : 1;
} ina219_config_tst_t;

typedef union {
    uint16_t all;
    ina219_bus_voltage_tst_t bits;
} ina219_bus_voltage_tun_t;

typedef struct __attribute__((packed)) {
    uint16_t ovf : 1;
    uint16_t cnvr : 1;
    uint16_t reserved : 1;
    uint16_t bd : 13;
} ina219_bus_voltage_tst_t;

#endif /* GENERATED_TYPES_H */
