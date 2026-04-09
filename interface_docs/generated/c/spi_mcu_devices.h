#ifndef LOCATOR_BASE_SPI_PERIPHERAL_BUS_INTERFAC_H
#define LOCATOR_BASE_SPI_PERIPHERAL_BUS_INTERFAC_H

/* Locator Base SPI Peripheral Bus Interface — auto-generated */

#include <stdint.h>
#include "spi_mcu_types.h"

#define SPI_CLOCK_HZ         10000000
#define SPI_MODE             0

#define SPI_CS_DAC_PIN      'PA8'
#define SPI_CS_ADC_EXT_PIN      'PA3'
#define SPI_CS_FLASH_PIN      'PA24'


#define ADC_INPUT_REG_DEVICE_ID                0x00
#define ADC_INPUT_REG_RST_PWRCTL               0x01
#define ADC_INPUT_REG_SDI_CTL                  0x02
#define ADC_INPUT_REG_SDO_CTL                  0x03
#define ADC_INPUT_REG_DATAOUT_CTL              0x04
#define ADC_INPUT_REG_RANGE_SEL                0x05
#define ADC_INPUT_REG_ALARM_H_TH               0x14
#define ADC_INPUT_REG_ALARM_L_TH               0x18

#define NOR_FLASH_CMD_READ_JEDEC_ID            0x9f
#define NOR_FLASH_CMD_READ_UNIQUE_ID           0x4b
#define NOR_FLASH_CMD_READ_STATUS_1            0x05
#define NOR_FLASH_CMD_READ_STATUS_2            0x35
#define NOR_FLASH_CMD_READ_STATUS_3            0x15
#define NOR_FLASH_CMD_WRITE_STATUS_1           0x01
#define NOR_FLASH_CMD_WRITE_ENABLE             0x06
#define NOR_FLASH_CMD_WRITE_DISABLE            0x04
#define NOR_FLASH_CMD_READ_DATA                0x03
#define NOR_FLASH_CMD_FAST_READ                0x0b
#define NOR_FLASH_CMD_PAGE_PROGRAM             0x02
#define NOR_FLASH_CMD_SECTOR_ERASE_4K          0x20
#define NOR_FLASH_CMD_BLOCK_ERASE_32K          0x52
#define NOR_FLASH_CMD_BLOCK_ERASE_64K          0xd8
#define NOR_FLASH_CMD_CHIP_ERASE               0xc7
#define NOR_FLASH_CMD_POWER_DOWN               0xb9
#define NOR_FLASH_CMD_RELEASE_POWER_DOWN       0xab


#endif /* LOCATOR_BASE_SPI_PERIPHERAL_BUS_INTERFAC_H */
