#ifndef GENERATED_TYPES_H
#define GENERATED_TYPES_H

/* Auto-generated — do not edit */

#include <stdint.h>

typedef union {
    uint16_t all;
    ads8681_rst_pwrctl_tst_t bits;
} ads8681_rst_pwrctl_tun_t;

typedef struct __attribute__((packed)) {
    uint16_t reserved_lo : 1;
    uint16_t nap_en : 1;
    uint16_t pwdn : 1;
    uint16_t reserved_mid : 5;
    uint16_t rst_n : 1;
    uint16_t reserved_hi : 7;
} ads8681_rst_pwrctl_tst_t;

typedef union {
    uint16_t all;
    ads8681_sdo_ctl_tst_t bits;
} ads8681_sdo_ctl_tun_t;

typedef struct __attribute__((packed)) {
    uint16_t ssc_en : 1;
    uint16_t sdo_mode : 2;
    uint16_t reserved : 13;
} ads8681_sdo_ctl_tst_t;

typedef enum {
    RANGE_3VREF = 0x0,
    RANGE_2_5VREF = 0x1,
    RANGE_1_5VREF = 0x2,
    RANGE_1_25VREF = 0x3,
    RANGE_0_625VREF = 0x4,
    RANGE_UNI_3VREF = 0x8,
    RANGE_UNI_2_5VREF = 0x9,
    RANGE_UNI_1_5VREF = 0xa,
    RANGE_UNI_1_25VREF = 0xb,
} ads8681_range_ten_t;

typedef union {
    uint8_t all;
    w25q_status1_tst_t bits;
} w25q_status1_tun_t;

typedef struct __attribute__((packed)) {
    uint8_t busy : 1;
    uint8_t wel : 1;
    uint8_t bp0 : 1;
    uint8_t bp1 : 1;
    uint8_t bp2 : 1;
    uint8_t tb : 1;
    uint8_t sec : 1;
    uint8_t srp0 : 1;
} w25q_status1_tst_t;

typedef union {
    uint8_t all;
    w25q_status2_tst_t bits;
} w25q_status2_tun_t;

typedef struct __attribute__((packed)) {
    uint8_t srl : 1;
    uint8_t qe : 1;
    uint8_t reserved : 1;
    uint8_t lb1 : 1;
    uint8_t lb2 : 1;
    uint8_t lb3 : 1;
    uint8_t cmp : 1;
    uint8_t sus : 1;
} w25q_status2_tst_t;

#endif /* GENERATED_TYPES_H */
