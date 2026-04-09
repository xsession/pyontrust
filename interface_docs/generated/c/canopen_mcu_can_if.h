#ifndef LOCATOR_CAN_IF_H
#define LOCATOR_CAN_IF_H

/* Locator Base CANopen MCU Interface — auto-generated */

#include <stdint.h>
#include "canopen_mcu_types.h"

#define INFO_DEVICE_NAME_MLX                                    0x100800
#define INFO_HW_VERSION_MLX                                     0x100900
#define INFO_FW_VERSION_MLX                                     0x100a00

#define STORE_PARAMETERS_SAVE_ALL_PARAMETERS_MLX                0x101001
#define STORE_PARAMETERS_SAVE_COMM_PARAMETERS_MLX               0x101002
#define STORE_PARAMETERS_SAVE_APP_PARAMETERS_MLX                0x101003

#define SERVICE_INFO_STORED_NODE_ID_MLX                         0x100b00
#define SERVICE_INFO_STORED_CAN_SPEED_MLX                       0x314420
#define SERVICE_INFO_SERIAL_NUM_MLX                             0x312301
#define SERVICE_INFO_LSS_VID_MLX                                0x312302
#define SERVICE_INFO_LSS_PID_MLX                                0x312303
#define SERVICE_INFO_LSS_REV_MLX                                0x312304
#define SERVICE_INFO_LSS_SN_MLX                                 0x312305

#define CONFIG_NICK_NAME_MLX                                    0x312c00
#define CONFIG_CAL_DATE_MLX                                     0x312c01

#define DIGITAL_OUTPUTS_LED_CONTROL_MLX                         0x620001

#define DIGITAL_INPUTS_BUTTON_STATE_MLX                         0x600001

#define STATUS_DEVICE_STATUS_MLX                                0x400001
#define STATUS_BOARD_TEMPERATURE_MLX                            0x400002
#define STATUS_SUPPLY_VOLTAGE_MLX                               0x400003

#define INFO_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.device_name_ac, INFO_DEVICE_NAME_MLX                                    SDO_READ, SDO_NOWRITE ), \
    MLX_DEF_MACRO( STRUCT.hw_version_ac, INFO_HW_VERSION_MLX                                     SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.fw_version_ac, INFO_FW_VERSION_MLX                                     SDO_READ, SDO_NOWRITE )

#define STORE_PARAMETERS_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.save_all_parameters_u32, STORE_PARAMETERS_SAVE_ALL_PARAMETERS_MLX                SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.save_comm_parameters_u32, STORE_PARAMETERS_SAVE_COMM_PARAMETERS_MLX               SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.save_app_parameters_u32, STORE_PARAMETERS_SAVE_APP_PARAMETERS_MLX                SDO_READ, SDO_WRITE )

#define SERVICE_INFO_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.stored_node_id_u16, SERVICE_INFO_STORED_NODE_ID_MLX                         SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.stored_can_speed_u16, SERVICE_INFO_STORED_CAN_SPEED_MLX                       SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.serial_num_ac, SERVICE_INFO_SERIAL_NUM_MLX                             SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.lss_vid_u32, SERVICE_INFO_LSS_VID_MLX                                SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.lss_pid_u32, SERVICE_INFO_LSS_PID_MLX                                SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.lss_rev_u32, SERVICE_INFO_LSS_REV_MLX                                SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.lss_sn_u32, SERVICE_INFO_LSS_SN_MLX                                 SDO_READ, SDO_WRITE )

#define CONFIG_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.nick_name_ac, CONFIG_NICK_NAME_MLX                                    SDO_READ, SDO_WRITE ), \
    MLX_DEF_MACRO( STRUCT.cal_date_ac, CONFIG_CAL_DATE_MLX                                     SDO_READ, SDO_WRITE )

#define DIGITAL_OUTPUTS_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.led_control_un, DIGITAL_OUTPUTS_LED_CONTROL_MLX                         SDO_READ, SDO_WRITE )

#define DIGITAL_INPUTS_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.button_state_un, DIGITAL_INPUTS_BUTTON_STATE_MLX                         SDO_READ, SDO_NOWRITE )

#define STATUS_MLX( STRUCT )\
    MLX_DEF_MACRO( STRUCT.device_status_un, STATUS_DEVICE_STATUS_MLX                                SDO_READ, SDO_NOWRITE ), \
    MLX_DEF_MACRO( STRUCT.board_temperature_i16, STATUS_BOARD_TEMPERATURE_MLX                            SDO_READ, SDO_NOWRITE ), \
    MLX_DEF_MACRO( STRUCT.supply_voltage_u16, STATUS_SUPPLY_VOLTAGE_MLX                               SDO_READ, SDO_NOWRITE )

#endif /* LOCATOR_CAN_IF_H */
