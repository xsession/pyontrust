"""
Zephyr RTOS Kconfig module definitions for the Pin Configurator.
Auto-generated from Zephyr 3.7 Kconfig sources.

Each module contains:
  - id: short lowercase identifier
  - name: display name
  - version: Zephyr version string
  - icon: emoji icon
  - desc: one-line description
  - categories: list of option categories, each with:
      - id: category id
      - title: display title
      - options: list of Kconfig options with key, type, default, help, and optional choices
"""

ZEPHYR_KCONFIG_MODULES = [
    # =========================================================================
    # 1. BLUETOOTH
    # =========================================================================
    {
        "id": "bluetooth",
        "name": "Bluetooth",
        "version": "3.7",
        "icon": "📶",
        "desc": "Bluetooth Low Energy and Classic support",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_BT", "type": "bool", "default": False, "help": "Enable Bluetooth support"},
                    {
                        "key": "CONFIG_BT_STACK_SELECTION",
                        "type": "choice",
                        "default": "CONFIG_BT_HCI",
                        "help": "Bluetooth Stack Selection",
                        "choices": [
                            {"key": "CONFIG_BT_HCI", "help": "HCI-based stack with optional host & controller"},
                            {"key": "CONFIG_BT_CUSTOM", "help": "Custom, non-HCI based stack"},
                        ],
                    },
                    {"key": "CONFIG_BT_PERIPHERAL", "type": "bool", "default": False, "help": "LE Peripheral role support"},
                    {"key": "CONFIG_BT_CENTRAL", "type": "bool", "default": False, "help": "LE Central role support"},
                    {"key": "CONFIG_BT_BROADCASTER", "type": "bool", "default": True, "help": "LE Broadcaster role support"},
                    {"key": "CONFIG_BT_OBSERVER", "type": "bool", "default": False, "help": "LE Observer role support"},
                    {"key": "CONFIG_BT_MAX_CONN", "type": "int", "default": 1, "help": "Maximum number of simultaneous connections (1-250)"},
                    {"key": "CONFIG_BT_DEVICE_NAME", "type": "string", "default": "Zephyr", "help": "Bluetooth device name"},
                ],
            },
            {
                "id": "features",
                "title": "Features",
                "options": [
                    {"key": "CONFIG_BT_PHY_UPDATE", "type": "bool", "default": True, "help": "Bluetooth 5.0 PHY Update Procedure"},
                    {"key": "CONFIG_BT_DATA_LEN_UPDATE", "type": "bool", "default": False, "help": "Bluetooth 4.2 LE Data Length Update"},
                    {"key": "CONFIG_BT_SMP", "type": "bool", "default": False, "help": "Security Manager Protocol (pairing/bonding)"},
                    {"key": "CONFIG_BT_PRIVACY", "type": "bool", "default": False, "help": "Privacy Feature (RPA addresses)"},
                    {"key": "CONFIG_BT_GATT_CLIENT", "type": "bool", "default": False, "help": "GATT Client support"},
                    {"key": "CONFIG_BT_GATT_DYNAMIC_DB", "type": "bool", "default": False, "help": "GATT dynamic database support"},
                    {"key": "CONFIG_BT_SETTINGS", "type": "bool", "default": False, "help": "Store Bluetooth state and config persistently"},
                    {"key": "CONFIG_BT_SHELL", "type": "bool", "default": False, "help": "Bluetooth shell commands"},
                ],
            },
            {
                "id": "mesh",
                "title": "Mesh",
                "options": [
                    {"key": "CONFIG_BT_MESH", "type": "bool", "default": False, "help": "Bluetooth Mesh support"},
                    {"key": "CONFIG_BT_MESH_RELAY", "type": "bool", "default": False, "help": "Relay support for Mesh"},
                    {"key": "CONFIG_BT_MESH_FRIEND", "type": "bool", "default": False, "help": "Friend feature support"},
                    {"key": "CONFIG_BT_MESH_LOW_POWER", "type": "bool", "default": False, "help": "Low Power Node support"},
                    {"key": "CONFIG_BT_MESH_PROXY", "type": "bool", "default": False, "help": "GATT Proxy support"},
                    {"key": "CONFIG_BT_MESH_PB_GATT", "type": "bool", "default": False, "help": "GATT Provisioning Bearer"},
                    {"key": "CONFIG_BT_MESH_PB_ADV", "type": "bool", "default": True, "help": "Advertising Provisioning Bearer"},
                    {"key": "CONFIG_BT_MESH_GATT_PROXY", "type": "bool", "default": False, "help": "GATT Proxy feature"},
                ],
            },
        ],
    },
    # =========================================================================
    # 2. NETWORKING
    # =========================================================================
    {
        "id": "networking",
        "name": "Networking",
        "version": "3.7",
        "icon": "🌐",
        "desc": "TCP/IP networking stack, protocols, and socket API",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_NETWORKING", "type": "bool", "default": False, "help": "Enable link layer and networking (including IP)"},
                    {"key": "CONFIG_NET_IPV4", "type": "bool", "default": False, "help": "Enable IPv4 support"},
                    {"key": "CONFIG_NET_IPV6", "type": "bool", "default": True, "help": "Enable IPv6 support"},
                    {"key": "CONFIG_NET_TCP", "type": "bool", "default": False, "help": "Enable TCP protocol"},
                    {"key": "CONFIG_NET_UDP", "type": "bool", "default": True, "help": "Enable UDP protocol"},
                    {"key": "CONFIG_NET_SOCKETS", "type": "bool", "default": False, "help": "BSD Sockets compatible API"},
                    {"key": "CONFIG_NET_MAX_CONN", "type": "int", "default": 4, "help": "Max network connections (UDP + TCP)"},
                    {"key": "CONFIG_NET_MAX_CONTEXTS", "type": "int", "default": 6, "help": "Number of network contexts to allocate"},
                    {"key": "CONFIG_NET_DHCPV4", "type": "bool", "default": False, "help": "DHCPv4 client"},
                    {"key": "CONFIG_DNS_RESOLVER", "type": "bool", "default": False, "help": "DNS resolver"},
                ],
            },
            {
                "id": "protocols",
                "title": "Protocols",
                "options": [
                    {"key": "CONFIG_MQTT_LIB", "type": "bool", "default": False, "help": "Socket MQTT Library Support"},
                    {"key": "CONFIG_MQTT_KEEPALIVE", "type": "int", "default": 60, "help": "MQTT keep alive time in seconds"},
                    {"key": "CONFIG_MQTT_LIB_TLS", "type": "bool", "default": False, "help": "TLS support for MQTT"},
                    {"key": "CONFIG_HTTP_CLIENT", "type": "bool", "default": False, "help": "HTTP client API"},
                    {"key": "CONFIG_HTTP_SERVER", "type": "bool", "default": False, "help": "HTTP/1 and HTTP/2 server support"},
                    {"key": "CONFIG_HTTP_SERVER_MAX_CLIENTS", "type": "int", "default": 3, "help": "Max number of HTTP/2 clients"},
                    {"key": "CONFIG_COAP", "type": "bool", "default": False, "help": "CoAP protocol support"},
                    {"key": "CONFIG_COAP_INIT_ACK_TIMEOUT_MS", "type": "int", "default": 2000, "help": "Base CoAP ACK timeout in ms"},
                    {"key": "CONFIG_WEBSOCKET_CLIENT", "type": "bool", "default": False, "help": "WebSocket client support"},
                ],
            },
            {
                "id": "tls",
                "title": "TLS / Security",
                "options": [
                    {"key": "CONFIG_NET_SOCKETS_SOCKOPT_TLS", "type": "bool", "default": False, "help": "TCP TLS socket option support"},
                    {"key": "CONFIG_NET_SOCKETS_TLS_CONNECT_TIMEOUT", "type": "int", "default": 10000, "help": "TLS handshake timeout in ms"},
                    {"key": "CONFIG_TLS_CREDENTIALS", "type": "bool", "default": False, "help": "TLS credentials management"},
                    {"key": "CONFIG_TLS_MAX_CREDENTIALS_NUMBER", "type": "int", "default": 4, "help": "Maximum number of TLS credentials"},
                ],
            },
            {
                "id": "tcp",
                "title": "TCP Settings",
                "options": [
                    {"key": "CONFIG_NET_TCP_TIME_WAIT_DELAY", "type": "int", "default": 1500, "help": "TIME_WAIT state duration in ms (0=disabled)"},
                    {"key": "CONFIG_NET_TCP_INIT_RETRANSMISSION_TIMEOUT", "type": "int", "default": 200, "help": "Initial RTO in ms (100-60000)"},
                    {"key": "CONFIG_NET_TCP_RANDOMIZED_RTO", "type": "bool", "default": True, "help": "Randomize retransmission timeout"},
                ],
            },
        ],
    },
    # =========================================================================
    # 3. USB
    # =========================================================================
    {
        "id": "usb",
        "name": "USB",
        "version": "3.7",
        "icon": "🔌",
        "desc": "USB Device and Host stack support",
        "categories": [
            {
                "id": "device_legacy",
                "title": "USB Device Stack (Legacy)",
                "options": [
                    {"key": "CONFIG_USB_DEVICE_STACK", "type": "bool", "default": False, "help": "Enable USB device stack (legacy)"},
                    {"key": "CONFIG_USB_DEVICE_VID", "type": "hex", "default": "0x2FE3", "help": "USB Vendor ID"},
                    {"key": "CONFIG_USB_DEVICE_PID", "type": "hex", "default": "0x0100", "help": "USB Product ID"},
                    {"key": "CONFIG_USB_DEVICE_MANUFACTURER", "type": "string", "default": "ZEPHYR", "help": "USB manufacturer name"},
                    {"key": "CONFIG_USB_DEVICE_PRODUCT", "type": "string", "default": "USB-DEV", "help": "USB product name"},
                    {"key": "CONFIG_USB_DEVICE_SN", "type": "string", "default": "0123456789ABCDEF", "help": "USB Serial Number String"},
                    {"key": "CONFIG_USB_SELF_POWERED", "type": "bool", "default": True, "help": "Self-powered characteristic"},
                    {"key": "CONFIG_USB_MAX_POWER", "type": "int", "default": 50, "help": "bMaxPower value (result = 2mA * value)"},
                    {"key": "CONFIG_USB_DEVICE_INITIALIZE_AT_BOOT", "type": "bool", "default": False, "help": "Initialize USB device at boot"},
                ],
            },
            {
                "id": "device_next",
                "title": "USB Device Stack (New)",
                "options": [
                    {"key": "CONFIG_USB_DEVICE_STACK_NEXT", "type": "bool", "default": False, "help": "Enable new USB device stack"},
                    {
                        "key": "CONFIG_USBD_MAX_SPEED",
                        "type": "choice",
                        "default": "CONFIG_USBD_MAX_SPEED_FULL",
                        "help": "Max supported connection speed",
                        "choices": [
                            {"key": "CONFIG_USBD_MAX_SPEED_HIGH", "help": "High-Speed"},
                            {"key": "CONFIG_USBD_MAX_SPEED_FULL", "help": "Full-Speed"},
                        ],
                    },
                    {"key": "CONFIG_USBD_SHELL", "type": "bool", "default": False, "help": "USB device shell commands"},
                    {"key": "CONFIG_USBD_THREAD_STACK_SIZE", "type": "int", "default": 1024, "help": "USB device stack thread stack size"},
                    {"key": "CONFIG_USBD_MAX_UDC_MSG", "type": "int", "default": 10, "help": "Maximum number of UDC events"},
                ],
            },
            {
                "id": "classes",
                "title": "USB Classes",
                "options": [
                    {"key": "CONFIG_USB_CDC_ACM", "type": "bool", "default": False, "help": "USB CDC ACM (serial port) class"},
                    {"key": "CONFIG_USB_DEVICE_HID", "type": "bool", "default": False, "help": "USB HID Device class"},
                    {"key": "CONFIG_USB_MASS_STORAGE", "type": "bool", "default": False, "help": "USB Mass Storage class"},
                    {"key": "CONFIG_USB_DEVICE_BLUETOOTH", "type": "bool", "default": False, "help": "USB Bluetooth HCI class"},
                    {"key": "CONFIG_USB_DEVICE_NETWORK_RNDIS", "type": "bool", "default": False, "help": "USB RNDIS network class"},
                    {"key": "CONFIG_USB_DEVICE_AUDIO", "type": "bool", "default": False, "help": "USB Audio class"},
                ],
            },
        ],
    },
    # =========================================================================
    # 4. SHELL
    # =========================================================================
    {
        "id": "shell",
        "name": "Shell",
        "version": "3.7",
        "icon": "🖥️",
        "desc": "Interactive command shell over UART, RTT, Telnet, etc.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SHELL", "type": "bool", "default": False, "help": "Enable Shell support"},
                    {"key": "CONFIG_SHELL_MINIMAL", "type": "bool", "default": False, "help": "Reduce flash/memory requirements"},
                    {"key": "CONFIG_SHELL_STACK_SIZE", "type": "int", "default": 2048, "help": "Shell thread stack size"},
                    {"key": "CONFIG_SHELL_CMD_BUFF_SIZE", "type": "int", "default": 256, "help": "Shell command buffer size"},
                    {"key": "CONFIG_SHELL_ARGC_MAX", "type": "int", "default": 20, "help": "Maximum arguments in shell command"},
                    {"key": "CONFIG_SHELL_TAB", "type": "bool", "default": True, "help": "Tab button support"},
                    {"key": "CONFIG_SHELL_TAB_AUTOCOMPLETION", "type": "bool", "default": True, "help": "Autocompletion with Tab key"},
                    {"key": "CONFIG_SHELL_HISTORY", "type": "bool", "default": True, "help": "Command history support"},
                    {"key": "CONFIG_SHELL_HISTORY_BUFFER", "type": "int", "default": 512, "help": "History buffer in bytes"},
                    {"key": "CONFIG_SHELL_WILDCARD", "type": "bool", "default": True, "help": "Wildcard support (* and ?)"},
                    {"key": "CONFIG_SHELL_VT100_COLORS", "type": "bool", "default": True, "help": "VT100 colors in shell"},
                    {"key": "CONFIG_SHELL_METAKEYS", "type": "bool", "default": True, "help": "Meta keys (Ctrl+a, Ctrl+c, etc.)"},
                    {"key": "CONFIG_SHELL_HELP", "type": "bool", "default": True, "help": "Help message support"},
                    {"key": "CONFIG_SHELL_CMDS", "type": "bool", "default": True, "help": "Built-in commands (clear, history, etc.)"},
                    {"key": "CONFIG_SHELL_LOG_BACKEND", "type": "bool", "default": True, "help": "Shell as logging backend"},
                    {"key": "CONFIG_SHELL_AUTOSTART", "type": "bool", "default": True, "help": "Auto-start shell at boot"},
                ],
            },
            {
                "id": "backends",
                "title": "Backends",
                "options": [
                    {"key": "CONFIG_SHELL_BACKEND_SERIAL", "type": "bool", "default": True, "help": "Serial (UART) backend"},
                    {"key": "CONFIG_SHELL_BACKEND_SERIAL_INTERRUPT_DRIVEN", "type": "bool", "default": True, "help": "Interrupt-driven UART backend"},
                    {"key": "CONFIG_SHELL_BACKEND_SERIAL_RX_RING_BUFFER_SIZE", "type": "int", "default": 64, "help": "RX ring buffer size"},
                    {"key": "CONFIG_SHELL_BACKEND_RTT", "type": "bool", "default": False, "help": "SEGGER RTT backend"},
                    {"key": "CONFIG_SHELL_BACKEND_TELNET", "type": "bool", "default": False, "help": "Telnet backend"},
                    {"key": "CONFIG_SHELL_BACKEND_WEBSOCKET", "type": "bool", "default": False, "help": "WebSocket backend"},
                    {"key": "CONFIG_SHELL_BACKEND_DUMMY", "type": "bool", "default": False, "help": "Dummy backend"},
                ],
            },
        ],
    },
    # =========================================================================
    # 5. LOGGING
    # =========================================================================
    {
        "id": "logging",
        "name": "Logging",
        "version": "3.7",
        "icon": "📝",
        "desc": "Logging subsystem with multiple backends and filtering",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_LOG", "type": "bool", "default": False, "help": "Enable Logging subsystem"},
                    {
                        "key": "CONFIG_LOG_MODE",
                        "type": "choice",
                        "default": "CONFIG_LOG_MODE_DEFERRED",
                        "help": "Logging mode",
                        "choices": [
                            {"key": "CONFIG_LOG_MODE_DEFERRED", "help": "Deferred logging — buffered, processed later"},
                            {"key": "CONFIG_LOG_MODE_IMMEDIATE", "help": "Synchronous — processed in calling context"},
                            {"key": "CONFIG_LOG_MODE_MINIMAL", "help": "Minimal footprint — printk-based"},
                        ],
                    },
                    {"key": "CONFIG_LOG_PRINTK", "type": "bool", "default": True, "help": "Redirect printk messages to logging"},
                    {"key": "CONFIG_LOG_MODE_OVERFLOW", "type": "bool", "default": True, "help": "Drop oldest message when buffer is full"},
                ],
            },
            {
                "id": "filtering",
                "title": "Filtering",
                "options": [
                    {"key": "CONFIG_LOG_DEFAULT_LEVEL", "type": "int", "default": 3, "help": "Default log level (0=OFF, 1=ERR, 2=WRN, 3=INF, 4=DBG)"},
                    {"key": "CONFIG_LOG_MAX_LEVEL", "type": "int", "default": 4, "help": "Max compiled-in log level (0-4)"},
                    {"key": "CONFIG_LOG_OVERRIDE_LEVEL", "type": "int", "default": 0, "help": "Override min log level for all modules (0=OFF)"},
                    {"key": "CONFIG_LOG_RUNTIME_FILTERING", "type": "bool", "default": False, "help": "Allow runtime filtering reconfiguration"},
                ],
            },
            {
                "id": "processing",
                "title": "Processing",
                "options": [
                    {"key": "CONFIG_LOG_PROCESS_THREAD", "type": "bool", "default": True, "help": "Use internal thread for log processing"},
                    {"key": "CONFIG_LOG_PROCESS_THREAD_SLEEP_MS", "type": "int", "default": 1000, "help": "Log processing thread sleep period (ms)"},
                    {"key": "CONFIG_LOG_PROCESS_THREAD_STACK_SIZE", "type": "int", "default": 768, "help": "Log processing thread stack size"},
                    {"key": "CONFIG_LOG_PROCESS_TRIGGER_THRESHOLD", "type": "int", "default": 10, "help": "Buffered messages before flushing"},
                    {"key": "CONFIG_LOG_BLOCK_IN_THREAD", "type": "bool", "default": False, "help": "Block thread when buffer is full"},
                ],
            },
            {
                "id": "backends",
                "title": "Backends",
                "options": [
                    {"key": "CONFIG_LOG_BACKEND_UART", "type": "bool", "default": True, "help": "UART logging backend"},
                    {"key": "CONFIG_LOG_BACKEND_UART_AUTOSTART", "type": "bool", "default": True, "help": "Auto-start UART backend"},
                    {"key": "CONFIG_LOG_BACKEND_UART_BUFFER_SIZE", "type": "int", "default": 1, "help": "UART backend buffer size (bytes)"},
                    {"key": "CONFIG_LOG_BACKEND_RTT", "type": "bool", "default": False, "help": "SEGGER RTT logging backend"},
                    {"key": "CONFIG_LOG_BACKEND_NET", "type": "bool", "default": False, "help": "Networking logging backend (syslog)"},
                    {"key": "CONFIG_LOG_BACKEND_FS", "type": "bool", "default": False, "help": "File system logging backend"},
                ],
            },
        ],
    },
    # =========================================================================
    # 6. SETTINGS / NVS / FLASH STORAGE
    # =========================================================================
    {
        "id": "settings",
        "name": "Settings",
        "version": "3.7",
        "icon": "💾",
        "desc": "Persistent settings storage (NVS, FCB, ZMS, File)",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SETTINGS", "type": "bool", "default": False, "help": "Enable Settings subsystem for persistent storage"},
                    {
                        "key": "CONFIG_SETTINGS_BACKEND",
                        "type": "choice",
                        "default": "CONFIG_SETTINGS_NVS",
                        "help": "Storage back-end",
                        "choices": [
                            {"key": "CONFIG_SETTINGS_ZMS", "help": "ZMS (Zephyr Memory Storage)"},
                            {"key": "CONFIG_SETTINGS_NVS", "help": "NVS non-volatile storage"},
                            {"key": "CONFIG_SETTINGS_FCB", "help": "FCB (Flash Circular Buffer)"},
                            {"key": "CONFIG_SETTINGS_FILE", "help": "File system based storage"},
                            {"key": "CONFIG_SETTINGS_NONE", "help": "No storage back-end"},
                        ],
                    },
                    {"key": "CONFIG_SETTINGS_RUNTIME", "type": "bool", "default": False, "help": "Runtime storage back-end"},
                    {"key": "CONFIG_SETTINGS_DYNAMIC_HANDLERS", "type": "bool", "default": True, "help": "Dynamic settings handlers"},
                    {"key": "CONFIG_SETTINGS_SHELL", "type": "bool", "default": False, "help": "Settings shell commands"},
                ],
            },
            {
                "id": "nvs",
                "title": "NVS Settings",
                "options": [
                    {"key": "CONFIG_SETTINGS_NVS_SECTOR_SIZE_MULT", "type": "int", "default": 1, "help": "NVS sector size multiplier"},
                    {"key": "CONFIG_SETTINGS_NVS_SECTOR_COUNT", "type": "int", "default": 8, "help": "Number of NVS sectors"},
                    {"key": "CONFIG_SETTINGS_NVS_NAME_CACHE", "type": "bool", "default": False, "help": "NVS name lookup cache"},
                    {"key": "CONFIG_SETTINGS_NVS_NAME_CACHE_SIZE", "type": "int", "default": 128, "help": "NVS name cache entries"},
                ],
            },
            {
                "id": "fcb",
                "title": "FCB Settings",
                "options": [
                    {"key": "CONFIG_SETTINGS_FCB_NUM_AREAS", "type": "int", "default": 8, "help": "Number of flash areas for FCB"},
                    {"key": "CONFIG_SETTINGS_FCB_MAGIC", "type": "hex", "default": "0xc0ffeeee", "help": "FCB magic word for settings area"},
                ],
            },
            {
                "id": "file",
                "title": "File Settings",
                "options": [
                    {"key": "CONFIG_SETTINGS_FILE_PATH", "type": "string", "default": "/settings/run", "help": "Default settings file path"},
                    {"key": "CONFIG_SETTINGS_FILE_MAX_LINES", "type": "int", "default": 32, "help": "Compression threshold (max items before compacting)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 7. FILE SYSTEMS
    # =========================================================================
    {
        "id": "filesystem",
        "name": "File Systems",
        "version": "3.7",
        "icon": "📁",
        "desc": "File system support (LittleFS, FAT, ext2)",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_FILE_SYSTEM", "type": "bool", "default": False, "help": "Enable file system support"},
                    {"key": "CONFIG_FILE_SYSTEM_MAX_TYPES", "type": "int", "default": 2, "help": "Maximum distinct file system types"},
                    {"key": "CONFIG_FILE_SYSTEM_MAX_FILE_NAME", "type": "int", "default": -1, "help": "Max file name length (-1 = auto)"},
                    {"key": "CONFIG_FILE_SYSTEM_SHELL", "type": "bool", "default": False, "help": "File system shell commands"},
                    {"key": "CONFIG_FILE_SYSTEM_MKFS", "type": "bool", "default": False, "help": "Allow formatting file system"},
                ],
            },
            {
                "id": "littlefs",
                "title": "LittleFS",
                "options": [
                    {"key": "CONFIG_FILE_SYSTEM_LITTLEFS", "type": "bool", "default": False, "help": "Enable LittleFS support"},
                    {"key": "CONFIG_FS_LITTLEFS_NUM_FILES", "type": "int", "default": 4, "help": "Maximum opened files"},
                    {"key": "CONFIG_FS_LITTLEFS_NUM_DIRS", "type": "int", "default": 4, "help": "Maximum opened directories"},
                    {"key": "CONFIG_FS_LITTLEFS_READ_SIZE", "type": "int", "default": 16, "help": "Minimum block read size"},
                    {"key": "CONFIG_FS_LITTLEFS_PROG_SIZE", "type": "int", "default": 16, "help": "Minimum block program size"},
                    {"key": "CONFIG_FS_LITTLEFS_CACHE_SIZE", "type": "int", "default": 64, "help": "Block cache size in bytes"},
                    {"key": "CONFIG_FS_LITTLEFS_LOOKAHEAD_SIZE", "type": "int", "default": 32, "help": "Lookahead buffer size in bytes"},
                ],
            },
            {
                "id": "fatfs",
                "title": "FAT File System",
                "options": [
                    {"key": "CONFIG_FAT_FILESYSTEM_ELM", "type": "bool", "default": False, "help": "ELM FAT file system support"},
                    {"key": "CONFIG_FS_FATFS_READ_ONLY", "type": "bool", "default": False, "help": "Read-only support for all volumes"},
                    {"key": "CONFIG_FS_FATFS_MKFS", "type": "bool", "default": False, "help": "mkfs support for FAT FS"},
                    {"key": "CONFIG_FS_FATFS_MOUNT_MKFS", "type": "bool", "default": True, "help": "Format volume when mounting fails"},
                    {"key": "CONFIG_FS_FATFS_EXFAT", "type": "bool", "default": False, "help": "exFAT format support"},
                    {"key": "CONFIG_FS_FATFS_NUM_FILES", "type": "int", "default": 4, "help": "Maximum opened files"},
                    {"key": "CONFIG_FS_FATFS_NUM_DIRS", "type": "int", "default": 4, "help": "Maximum opened directories"},
                    {"key": "CONFIG_FS_FATFS_LFN", "type": "bool", "default": False, "help": "Long File Names (LFN) support"},
                ],
            },
        ],
    },
    # =========================================================================
    # 8. POWER MANAGEMENT
    # =========================================================================
    {
        "id": "power_management",
        "name": "Power Management",
        "version": "3.7",
        "icon": "🔋",
        "desc": "System and device power management",
        "categories": [
            {
                "id": "system",
                "title": "System PM",
                "options": [
                    {"key": "CONFIG_PM", "type": "bool", "default": False, "help": "Enable System Power Management"},
                    {"key": "CONFIG_PM_STATS", "type": "bool", "default": False, "help": "System Power Management Stats"},
                    {"key": "CONFIG_PM_S2RAM", "type": "bool", "default": False, "help": "Suspend-to-RAM support"},
                    {"key": "CONFIG_PM_NEED_ALL_DEVICES_IDLE", "type": "bool", "default": False, "help": "Require all devices idle for low power"},
                ],
            },
            {
                "id": "device",
                "title": "Device PM",
                "options": [
                    {"key": "CONFIG_PM_DEVICE", "type": "bool", "default": False, "help": "Enable Device Power Management interface"},
                    {"key": "CONFIG_PM_DEVICE_RUNTIME", "type": "bool", "default": False, "help": "Runtime Device Power Management"},
                    {"key": "CONFIG_PM_DEVICE_RUNTIME_ASYNC", "type": "bool", "default": True, "help": "Asynchronous device runtime PM"},
                    {"key": "CONFIG_PM_DEVICE_RUNTIME_DEFAULT_ENABLE", "type": "bool", "default": False, "help": "Enable PM runtime by default for all devices"},
                    {"key": "CONFIG_PM_DEVICE_POWER_DOMAIN", "type": "bool", "default": True, "help": "Power domain support"},
                    {"key": "CONFIG_PM_DEVICE_SYSTEM_MANAGED", "type": "bool", "default": True, "help": "System-managed device PM (suspend/resume)"},
                    {"key": "CONFIG_PM_DEVICE_SHELL", "type": "bool", "default": False, "help": "Device PM shell commands"},
                ],
            },
        ],
    },
    # =========================================================================
    # 9. DISPLAY
    # =========================================================================
    {
        "id": "display",
        "name": "Display",
        "version": "3.7",
        "icon": "🖥️",
        "desc": "Display controller drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_DISPLAY", "type": "bool", "default": False, "help": "Enable display controller drivers"},
                    {"key": "CONFIG_DISPLAY_INIT_PRIORITY", "type": "int", "default": 85, "help": "Display device init priority"},
                ],
            },
            {
                "id": "drivers",
                "title": "Common Display Drivers",
                "options": [
                    {"key": "CONFIG_SSD1306", "type": "bool", "default": False, "help": "SSD1306 OLED display driver"},
                    {"key": "CONFIG_ILI9XXX", "type": "bool", "default": False, "help": "ILI9xxx TFT display driver"},
                    {"key": "CONFIG_ST7789V", "type": "bool", "default": False, "help": "ST7789V TFT display driver"},
                    {"key": "CONFIG_ST7735R", "type": "bool", "default": False, "help": "ST7735R TFT display driver"},
                    {"key": "CONFIG_GC9X01X", "type": "bool", "default": False, "help": "GC9x01x round display driver"},
                    {"key": "CONFIG_SSD16XX", "type": "bool", "default": False, "help": "SSD16xx e-paper display driver"},
                    {"key": "CONFIG_SDL_DISPLAY", "type": "bool", "default": False, "help": "SDL display (for native_posix simulation)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 10. DEBUG
    # =========================================================================
    {
        "id": "debug",
        "name": "Debug",
        "version": "3.7",
        "icon": "🐛",
        "desc": "Debugging, thread analysis, core dump, and assertions",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_DEBUG", "type": "bool", "default": False, "help": "Build kernel with debugging enabled (disables optimization)"},
                    {"key": "CONFIG_PRINTK", "type": "bool", "default": True, "help": "Send printk() to console"},
                    {"key": "CONFIG_ASSERT", "type": "bool", "default": False, "help": "Enable __ASSERT() macro"},
                    {"key": "CONFIG_ASSERT_LEVEL", "type": "int", "default": 2, "help": "__ASSERT() level (0=OFF, 1=on+warn, 2=on)"},
                    {"key": "CONFIG_ASSERT_VERBOSE", "type": "bool", "default": True, "help": "Verbose assertions with location info"},
                    {"key": "CONFIG_STACK_SENTINEL", "type": "bool", "default": False, "help": "Stack sentinel (magic value check)"},
                    {"key": "CONFIG_EXCEPTION_STACK_TRACE", "type": "bool", "default": True, "help": "Print stack traces upon exceptions"},
                    {"key": "CONFIG_DEBUG_THREAD_INFO", "type": "bool", "default": False, "help": "Thread awareness for debugger RTOS plugins"},
                ],
            },
            {
                "id": "thread_analyzer",
                "title": "Thread Analyzer",
                "options": [
                    {"key": "CONFIG_THREAD_ANALYZER", "type": "bool", "default": False, "help": "Enable thread analyzer"},
                    {
                        "key": "CONFIG_THREAD_ANALYZER_PRINT_MODE",
                        "type": "choice",
                        "default": "CONFIG_THREAD_ANALYZER_USE_PRINTK",
                        "help": "Thread analysis print mode",
                        "choices": [
                            {"key": "CONFIG_THREAD_ANALYZER_USE_LOG", "help": "Use logger output"},
                            {"key": "CONFIG_THREAD_ANALYZER_USE_PRINTK", "help": "Use printk function"},
                        ],
                    },
                    {"key": "CONFIG_THREAD_ANALYZER_AUTO", "type": "bool", "default": False, "help": "Run periodic thread analysis automatically"},
                    {"key": "CONFIG_THREAD_ANALYZER_AUTO_INTERVAL", "type": "int", "default": 60, "help": "Thread analysis interval (seconds)"},
                    {"key": "CONFIG_THREAD_ANALYZER_ISR_STACK_USAGE", "type": "bool", "default": True, "help": "Analyze interrupt stack usage"},
                ],
            },
            {
                "id": "coredump",
                "title": "Core Dump",
                "options": [
                    {"key": "CONFIG_DEBUG_COREDUMP", "type": "bool", "default": False, "help": "Enable core dump for offline debugging"},
                    {
                        "key": "CONFIG_DEBUG_COREDUMP_BACKEND",
                        "type": "choice",
                        "default": "CONFIG_DEBUG_COREDUMP_BACKEND_LOGGING",
                        "help": "Coredump backend",
                        "choices": [
                            {"key": "CONFIG_DEBUG_COREDUMP_BACKEND_LOGGING", "help": "Use Logging subsystem"},
                            {"key": "CONFIG_DEBUG_COREDUMP_BACKEND_FLASH_PARTITION", "help": "Use flash partition"},
                            {"key": "CONFIG_DEBUG_COREDUMP_BACKEND_IN_MEMORY", "help": "Use memory buffer"},
                        ],
                    },
                    {
                        "key": "CONFIG_DEBUG_COREDUMP_MEMORY_DUMP",
                        "type": "choice",
                        "default": "CONFIG_DEBUG_COREDUMP_MEMORY_DUMP_LINKER_RAM",
                        "help": "Memory dump scope",
                        "choices": [
                            {"key": "CONFIG_DEBUG_COREDUMP_MEMORY_DUMP_MIN", "help": "Minimal (exception thread only)"},
                            {"key": "CONFIG_DEBUG_COREDUMP_MEMORY_DUMP_THREADS", "help": "All threads"},
                            {"key": "CONFIG_DEBUG_COREDUMP_MEMORY_DUMP_LINKER_RAM", "help": "Entire RAM (linker defined)"},
                        ],
                    },
                ],
            },
            {
                "id": "cpu_load",
                "title": "CPU Load",
                "options": [
                    {"key": "CONFIG_CPU_LOAD", "type": "bool", "default": False, "help": "CPU load measurement"},
                    {"key": "CONFIG_CPU_LOAD_LOG_PERIODICALLY", "type": "int", "default": 0, "help": "Report period in ms (0=disabled)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 11. CRYPTO / TLS (mbedTLS)
    # =========================================================================
    {
        "id": "crypto",
        "name": "Crypto / TLS",
        "version": "3.7",
        "icon": "🔐",
        "desc": "Cryptography (mbedTLS / PSA Crypto) and TLS support",
        "categories": [
            {
                "id": "mbedtls",
                "title": "mbed TLS",
                "options": [
                    {"key": "CONFIG_MBEDTLS", "type": "bool", "default": False, "help": "Enable mbed TLS cryptography library"},
                    {
                        "key": "CONFIG_MBEDTLS_IMPLEMENTATION",
                        "type": "choice",
                        "default": "CONFIG_MBEDTLS_BUILTIN",
                        "help": "mbed TLS implementation",
                        "choices": [
                            {"key": "CONFIG_MBEDTLS_BUILTIN", "help": "Use Zephyr in-tree mbedTLS version"},
                            {"key": "CONFIG_MBEDTLS_LIBRARY", "help": "Use external prebuilt mbedTLS library"},
                        ],
                    },
                    {"key": "CONFIG_MBEDTLS_SSL_MAX_CONTENT_LEN", "type": "int", "default": 1500, "help": "Max payload size for TLS message"},
                    {"key": "CONFIG_MBEDTLS_ENABLE_HEAP", "type": "bool", "default": False, "help": "Global heap for mbed TLS"},
                    {"key": "CONFIG_MBEDTLS_HEAP_SIZE", "type": "int", "default": 512, "help": "Heap size for mbed TLS"},
                    {"key": "CONFIG_MBEDTLS_DEBUG", "type": "bool", "default": False, "help": "mbed TLS debug activation"},
                    {"key": "CONFIG_MBEDTLS_INIT", "type": "bool", "default": True, "help": "Initialize mbed TLS at boot"},
                    {"key": "CONFIG_MBEDTLS_SHELL", "type": "bool", "default": False, "help": "mbed TLS shell (heap usage info)"},
                ],
            },
            {
                "id": "hw_crypto",
                "title": "Hardware Crypto",
                "options": [
                    {"key": "CONFIG_CRYPTO", "type": "bool", "default": False, "help": "Enable hardware crypto drivers"},
                    {"key": "CONFIG_CRYPTO_INIT_PRIORITY", "type": "int", "default": 90, "help": "Crypto device init priority"},
                    {"key": "CONFIG_CRYPTO_MBEDTLS_SHIM", "type": "bool", "default": False, "help": "mbedTLS shim driver for crypto API"},
                ],
            },
        ],
    },
    # =========================================================================
    # 12. DFU / MCUBOOT
    # =========================================================================
    {
        "id": "dfu",
        "name": "DFU / MCUboot",
        "version": "3.7",
        "icon": "⬆️",
        "desc": "Device Firmware Update and MCUboot bootloader integration",
        "categories": [
            {
                "id": "mcuboot",
                "title": "MCUboot Bootloader",
                "options": [
                    {"key": "CONFIG_BOOTLOADER_MCUBOOT", "type": "bool", "default": False, "help": "MCUboot bootloader support (chain-loaded image)"},
                    {"key": "CONFIG_MCUBOOT_SIGNATURE_KEY_FILE", "type": "string", "default": "", "help": "Path to MCUboot signing key file (PEM)"},
                    {"key": "CONFIG_MCUBOOT_ENCRYPTION_KEY_FILE", "type": "string", "default": "", "help": "Path to MCUboot encryption key file (PEM)"},
                    {"key": "CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION", "type": "string", "default": "0.0.0+0", "help": "Version for imgtool signing"},
                    {"key": "CONFIG_MCUBOOT_IMGTOOL_OVERWRITE_ONLY", "type": "bool", "default": False, "help": "Use overwrite-only instead of swap"},
                    {"key": "CONFIG_MCUBOOT_GENERATE_UNSIGNED_IMAGE", "type": "bool", "default": False, "help": "Generate unsigned bootable image"},
                    {"key": "CONFIG_MCUBOOT_GENERATE_CONFIRMED_IMAGE", "type": "bool", "default": False, "help": "Generate padded confirmed image"},
                    {"key": "CONFIG_MCUBOOT_EXTRA_IMGTOOL_ARGS", "type": "string", "default": "", "help": "Extra arguments for imgtool"},
                ],
            },
            {
                "id": "img_manager",
                "title": "Image Manager",
                "options": [
                    {"key": "CONFIG_IMG_MANAGER", "type": "bool", "default": False, "help": "DFU image manager"},
                    {"key": "CONFIG_MCUBOOT_IMG_MANAGER", "type": "bool", "default": False, "help": "Image manager for MCUboot"},
                    {"key": "CONFIG_MCUBOOT_SHELL", "type": "bool", "default": False, "help": "MCUboot shell commands"},
                    {"key": "CONFIG_MCUBOOT_TRAILER_SWAP_TYPE", "type": "bool", "default": True, "help": "Use trailer swap_type field"},
                    {"key": "CONFIG_IMG_BLOCK_BUF_SIZE", "type": "int", "default": 512, "help": "Image writer buffer size (bytes)"},
                    {"key": "CONFIG_IMG_ERASE_PROGRESSIVELY", "type": "bool", "default": False, "help": "Erase flash progressively during DFU"},
                    {"key": "CONFIG_IMG_ENABLE_IMAGE_CHECK", "type": "bool", "default": False, "help": "Image integrity check functions"},
                    {"key": "CONFIG_UPDATEABLE_IMAGE_NUMBER", "type": "int", "default": 1, "help": "Number of updateable images"},
                ],
            },
        ],
    },
    # =========================================================================
    # 13. SENSOR
    # =========================================================================
    {
        "id": "sensor",
        "name": "Sensor",
        "version": "3.7",
        "icon": "🌡️",
        "desc": "Sensor driver subsystem",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SENSOR", "type": "bool", "default": False, "help": "Enable sensor drivers"},
                    {"key": "CONFIG_SENSOR_INIT_PRIORITY", "type": "int", "default": 90, "help": "Sensor init priority"},
                    {"key": "CONFIG_SENSOR_ASYNC_API", "type": "bool", "default": False, "help": "Async Sensor API (RTIO-based)"},
                    {"key": "CONFIG_SENSOR_SHELL", "type": "bool", "default": False, "help": "Sensor shell commands"},
                    {"key": "CONFIG_SENSOR_SHELL_STREAM", "type": "bool", "default": False, "help": "Sensor shell stream command (FIFO)"},
                    {"key": "CONFIG_SENSOR_SHELL_BATTERY", "type": "bool", "default": False, "help": "Sensor shell battery command"},
                    {"key": "CONFIG_SENSOR_INFO", "type": "bool", "default": False, "help": "Sensor info iterable section"},
                ],
            },
        ],
    },
    # =========================================================================
    # 14. WATCHDOG
    # =========================================================================
    {
        "id": "watchdog",
        "name": "Watchdog",
        "version": "3.7",
        "icon": "🐕",
        "desc": "Watchdog timer drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_WATCHDOG", "type": "bool", "default": False, "help": "Enable watchdog drivers"},
                    {"key": "CONFIG_WDT_DISABLE_AT_BOOT", "type": "bool", "default": False, "help": "Disable watchdog timers at boot"},
                    {"key": "CONFIG_WDT_MULTISTAGE", "type": "bool", "default": False, "help": "Multistage timeout support"},
                    {"key": "CONFIG_WDT_COUNTER", "type": "bool", "default": False, "help": "Counter-based watchdog emulation"},
                    {"key": "CONFIG_WDT_COUNTER_CH_COUNT", "type": "int", "default": 4, "help": "Max supported counter WDT channels"},
                ],
            },
        ],
    },
    # =========================================================================
    # 15. CAN BUS
    # =========================================================================
    {
        "id": "can",
        "name": "CAN Bus",
        "version": "3.7",
        "icon": "🚗",
        "desc": "Controller Area Network (CAN) drivers and protocols",
        "categories": [
            {
                "id": "driver",
                "title": "CAN Driver",
                "options": [
                    {"key": "CONFIG_CAN", "type": "bool", "default": False, "help": "Enable CAN driver"},
                    {"key": "CONFIG_CAN_INIT_PRIORITY", "type": "int", "default": 80, "help": "CAN driver init priority"},
                    {"key": "CONFIG_CAN_DEFAULT_BITRATE", "type": "int", "default": 125000, "help": "Default CAN bitrate (bits/s)"},
                    {"key": "CONFIG_CAN_FD_MODE", "type": "bool", "default": False, "help": "CAN FD support"},
                    {"key": "CONFIG_CAN_DEFAULT_BITRATE_DATA", "type": "int", "default": 1000000, "help": "Default CAN FD data phase bitrate"},
                    {"key": "CONFIG_CAN_SHELL", "type": "bool", "default": False, "help": "CAN shell commands"},
                    {"key": "CONFIG_CAN_STATS", "type": "bool", "default": False, "help": "CAN controller statistics"},
                    {"key": "CONFIG_CAN_ACCEPT_RTR", "type": "bool", "default": False, "help": "Accept Remote Transmission Request frames"},
                ],
            },
            {
                "id": "protocols",
                "title": "CAN Protocols",
                "options": [
                    {"key": "CONFIG_ISOTP", "type": "bool", "default": False, "help": "ISO-TP Transport (ISO 15765-2)"},
                    {"key": "CONFIG_ISOTP_ENABLE_TX_PADDING", "type": "bool", "default": False, "help": "Padding for transmitted ISO-TP messages"},
                    {"key": "CONFIG_ISOTP_RX_BUF_COUNT", "type": "int", "default": 4, "help": "Number of ISO-TP RX data buffers"},
                    {"key": "CONFIG_CANOPEN", "type": "bool", "default": False, "help": "CANopen protocol support (CiA 301)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 16. I2C
    # =========================================================================
    {
        "id": "i2c",
        "name": "I2C",
        "version": "3.7",
        "icon": "🔗",
        "desc": "Inter-Integrated Circuit (I2C) bus drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_I2C", "type": "bool", "default": False, "help": "Enable I2C bus drivers"},
                    {"key": "CONFIG_I2C_SHELL", "type": "bool", "default": False, "help": "I2C shell (scan, read, write)"},
                    {"key": "CONFIG_I2C_SHELL_BUFFER_SIZE", "type": "int", "default": 16, "help": "I2C shell buffer size"},
                    {"key": "CONFIG_I2C_STATS", "type": "bool", "default": False, "help": "I2C device statistics"},
                    {"key": "CONFIG_I2C_DUMP_MESSAGES", "type": "bool", "default": False, "help": "Log every I2C transaction"},
                    {"key": "CONFIG_I2C_CALLBACK", "type": "bool", "default": False, "help": "I2C asynchronous callback API"},
                    {"key": "CONFIG_I2C_RTIO", "type": "bool", "default": False, "help": "I2C RTIO API (experimental)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 17. SPI
    # =========================================================================
    {
        "id": "spi",
        "name": "SPI",
        "version": "3.7",
        "icon": "🔄",
        "desc": "Serial Peripheral Interface (SPI) bus drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SPI", "type": "bool", "default": False, "help": "Enable SPI bus drivers"},
                    {"key": "CONFIG_SPI_SHELL", "type": "bool", "default": False, "help": "SPI shell commands"},
                    {"key": "CONFIG_SPI_ASYNC", "type": "bool", "default": False, "help": "Asynchronous SPI API"},
                    {"key": "CONFIG_SPI_RTIO", "type": "bool", "default": False, "help": "SPI RTIO support (experimental)"},
                    {"key": "CONFIG_SPI_SLAVE", "type": "bool", "default": False, "help": "SPI slave support (experimental)"},
                    {"key": "CONFIG_SPI_EXTENDED_MODES", "type": "bool", "default": False, "help": "Extended modes (dual/quad/octal)"},
                    {"key": "CONFIG_SPI_INIT_PRIORITY", "type": "int", "default": 70, "help": "SPI init priority"},
                    {"key": "CONFIG_SPI_COMPLETION_TIMEOUT_TOLERANCE", "type": "int", "default": 200, "help": "Completion timeout tolerance (ms)"},
                    {"key": "CONFIG_SPI_STATS", "type": "bool", "default": False, "help": "SPI device statistics"},
                ],
            },
        ],
    },
    # =========================================================================
    # 18. UART / SERIAL
    # =========================================================================
    {
        "id": "uart",
        "name": "UART / Serial",
        "version": "3.7",
        "icon": "📡",
        "desc": "UART serial driver configuration",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SERIAL", "type": "bool", "default": False, "help": "Enable serial drivers"},
                    {"key": "CONFIG_SERIAL_INIT_PRIORITY", "type": "int", "default": 55, "help": "Serial init priority"},
                    {"key": "CONFIG_UART_USE_RUNTIME_CONFIGURE", "type": "bool", "default": True, "help": "Runtime UART configuration (uart_configure())"},
                    {"key": "CONFIG_UART_ASYNC_API", "type": "bool", "default": False, "help": "Asynchronous UART API"},
                    {"key": "CONFIG_UART_INTERRUPT_DRIVEN", "type": "bool", "default": False, "help": "UART interrupt support"},
                    {"key": "CONFIG_UART_LINE_CTRL", "type": "bool", "default": False, "help": "Serial line control API (baud, CTS, RTS)"},
                    {"key": "CONFIG_UART_EXCLUSIVE_API_CALLBACKS", "type": "bool", "default": True, "help": "Exclusive callbacks for multiple APIs"},
                ],
            },
        ],
    },
    # =========================================================================
    # 19. ADC
    # =========================================================================
    {
        "id": "adc",
        "name": "ADC",
        "version": "3.7",
        "icon": "📊",
        "desc": "Analog-to-Digital Converter drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_ADC", "type": "bool", "default": False, "help": "Enable ADC drivers"},
                    {"key": "CONFIG_ADC_SHELL", "type": "bool", "default": False, "help": "ADC shell commands"},
                    {"key": "CONFIG_ADC_ASYNC", "type": "bool", "default": False, "help": "Asynchronous ADC API"},
                    {"key": "CONFIG_ADC_INIT_PRIORITY", "type": "int", "default": 55, "help": "ADC init priority"},
                    {"key": "CONFIG_ADC_STREAM", "type": "bool", "default": False, "help": "ADC stream support (RTIO)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 20. PWM
    # =========================================================================
    {
        "id": "pwm",
        "name": "PWM",
        "version": "3.7",
        "icon": "〰️",
        "desc": "Pulse Width Modulation drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_PWM", "type": "bool", "default": False, "help": "Enable PWM drivers"},
                    {"key": "CONFIG_PWM_INIT_PRIORITY", "type": "int", "default": 55, "help": "PWM init priority"},
                    {"key": "CONFIG_PWM_SHELL", "type": "bool", "default": False, "help": "PWM shell commands"},
                    {"key": "CONFIG_PWM_CAPTURE", "type": "bool", "default": False, "help": "PWM capture API"},
                ],
            },
        ],
    },
    # =========================================================================
    # 21. GPIO
    # =========================================================================
    {
        "id": "gpio",
        "name": "GPIO",
        "version": "3.7",
        "icon": "📌",
        "desc": "General-Purpose Input/Output drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_GPIO", "type": "bool", "default": False, "help": "Enable GPIO drivers"},
                    {"key": "CONFIG_GPIO_SHELL", "type": "bool", "default": False, "help": "GPIO shell commands"},
                    {"key": "CONFIG_GPIO_SHELL_INFO_CMD", "type": "bool", "default": True, "help": "GPIO shell info command"},
                    {"key": "CONFIG_GPIO_SHELL_BLINK_CMD", "type": "bool", "default": True, "help": "GPIO shell blink command"},
                    {"key": "CONFIG_GPIO_INIT_PRIORITY", "type": "int", "default": 40, "help": "GPIO init priority"},
                    {"key": "CONFIG_GPIO_GET_DIRECTION", "type": "bool", "default": False, "help": "Support querying GPIO direction"},
                    {"key": "CONFIG_GPIO_GET_CONFIG", "type": "bool", "default": False, "help": "Support getting GPIO configuration"},
                    {"key": "CONFIG_GPIO_HOGS", "type": "bool", "default": False, "help": "GPIO hogs (auto-config via devicetree)"},
                    {"key": "CONFIG_GPIO_ENABLE_DISABLE_INTERRUPT", "type": "bool", "default": False, "help": "Enable/disable interrupt without re-config"},
                ],
            },
        ],
    },
    # =========================================================================
    # 22. FLASH
    # =========================================================================
    {
        "id": "flash",
        "name": "Flash",
        "version": "3.7",
        "icon": "💿",
        "desc": "Flash memory drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_FLASH", "type": "bool", "default": False, "help": "Enable flash hardware support"},
                    {"key": "CONFIG_FLASH_SHELL", "type": "bool", "default": False, "help": "Flash shell commands"},
                    {"key": "CONFIG_FLASH_PAGE_LAYOUT", "type": "bool", "default": True, "help": "API for retrieving page layout"},
                    {"key": "CONFIG_FLASH_JESD216_API", "type": "bool", "default": False, "help": "API for JESD216 flash parameters"},
                    {"key": "CONFIG_FLASH_EX_OP_ENABLED", "type": "bool", "default": False, "help": "Extended flash operations API"},
                    {"key": "CONFIG_FLASH_INIT_PRIORITY", "type": "int", "default": 50, "help": "Flash init priority"},
                    {"key": "CONFIG_FLASH_MAP", "type": "bool", "default": False, "help": "Flash map (partition table support)"},
                    {"key": "CONFIG_NVS", "type": "bool", "default": False, "help": "Non-Volatile Storage (NVS)"},
                ],
            },
        ],
    },
    # =========================================================================
    # 23. TIMER / COUNTER
    # =========================================================================
    {
        "id": "counter",
        "name": "Timer / Counter",
        "version": "3.7",
        "icon": "⏱️",
        "desc": "Counter and timer drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_COUNTER", "type": "bool", "default": False, "help": "Enable counter/timer drivers"},
                    {"key": "CONFIG_COUNTER_INIT_PRIORITY", "type": "int", "default": 60, "help": "Counter init priority"},
                    {"key": "CONFIG_COUNTER_SHELL", "type": "bool", "default": False, "help": "Counter shell commands"},
                ],
            },
        ],
    },
    # =========================================================================
    # 24. DMA
    # =========================================================================
    {
        "id": "dma",
        "name": "DMA",
        "version": "3.7",
        "icon": "🔀",
        "desc": "Direct Memory Access drivers",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_DMA", "type": "bool", "default": False, "help": "Enable DMA drivers"},
                    {"key": "CONFIG_DMA_64BIT", "type": "bool", "default": False, "help": "DMA 64-bit address support"},
                    {"key": "CONFIG_DMA_INIT_PRIORITY", "type": "int", "default": 40, "help": "DMA init priority"},
                ],
            },
        ],
    },
    # =========================================================================
    # 25. CONSOLE
    # =========================================================================
    {
        "id": "console",
        "name": "Console",
        "version": "3.7",
        "icon": "🖨️",
        "desc": "Console subsystem and helper functions",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_CONSOLE_SUBSYS", "type": "bool", "default": False, "help": "Enable console subsystem"},
                    {
                        "key": "CONFIG_CONSOLE_INPUT_MODE",
                        "type": "choice",
                        "default": "CONFIG_CONSOLE_GETCHAR",
                        "help": "Console get function selection",
                        "choices": [
                            {"key": "CONFIG_CONSOLE_GETCHAR", "help": "Character by character input/output"},
                            {"key": "CONFIG_CONSOLE_GETLINE", "help": "Line by line input"},
                        ],
                    },
                    {"key": "CONFIG_CONSOLE_GETCHAR_BUFSIZE", "type": "int", "default": 16, "help": "console_getchar() buffer size"},
                    {"key": "CONFIG_CONSOLE_PUTCHAR_BUFSIZE", "type": "int", "default": 16, "help": "console_putchar() buffer size"},
                    {"key": "CONFIG_UART_CONSOLE", "type": "bool", "default": False, "help": "UART-based console"},
                    {"key": "CONFIG_RTT_CONSOLE", "type": "bool", "default": False, "help": "SEGGER RTT console"},
                ],
            },
        ],
    },
]
