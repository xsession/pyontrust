"""
Zephyr Module / Subsystem Kconfig Registry.

Defines the configurable options for every major Zephyr subsystem and driver
category, structured for the Module Configurator UI.

Each module dict has:
    id        – short lowercase slug
    name      – display name
    version   – Zephyr version the data was sourced from
    icon      – emoji for sidebar
    desc      – one-line description
    categories – list of { id, title, options[] }
        options: { key, type, default, help, [choices] }
"""

ZEPHYR_MODULES: list[dict] = [

    # ── LVGL ──────────────────────────────────────────────────────────
    {
        "id": "lvgl",
        "name": "LVGL",
        "version": "9.2",
        "icon": "\U0001f3a8",   # 🎨
        "desc": "Light and Versatile Graphics Library – embedded GUI with advanced visual effects and low memory footprint.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_LVGL", "type": "bool", "default": True, "help": "Enable LVGL library"},
                    {"key": "CONFIG_LV_Z_MEM_POOL_SIZE", "type": "int", "default": 16384, "help": "LVGL memory pool size in bytes"},
                    {"key": "CONFIG_LV_COLOR_DEPTH", "type": "choice", "choices": ["1", "8", "16", "32"], "default": "16", "help": "Color depth (bits per pixel)"},
                    {"key": "CONFIG_LV_DPI_DEF", "type": "int", "default": 130, "help": "Default display DPI"},
                ]
            },
            {
                "id": "display",
                "title": "Display",
                "options": [
                    {"key": "CONFIG_LV_HOR_RES_MAX", "type": "int", "default": 320, "help": "Maximum horizontal resolution"},
                    {"key": "CONFIG_LV_VER_RES_MAX", "type": "int", "default": 240, "help": "Maximum vertical resolution"},
                    {"key": "CONFIG_LV_Z_FLUSH_THREAD", "type": "bool", "default": False, "help": "Use a dedicated flush thread for display"},
                    {"key": "CONFIG_LV_Z_FULL_REFRESH", "type": "bool", "default": False, "help": "Always redraw the whole screen"},
                    {"key": "CONFIG_LV_Z_VDB_SIZE", "type": "int", "default": 100, "help": "Display buffer size (% of screen)"},
                    {"key": "CONFIG_LV_Z_DOUBLE_VDB", "type": "bool", "default": False, "help": "Use double display buffering"},
                    {"key": "CONFIG_LV_Z_VBD_CUSTOM_SECTION", "type": "bool", "default": False, "help": "Place VDB in custom linker section"},
                ]
            },
            {
                "id": "input",
                "title": "Input Devices",
                "options": [
                    {"key": "CONFIG_LV_Z_POINTER_INPUT", "type": "bool", "default": False, "help": "Enable pointer (touch) input device"},
                    {"key": "CONFIG_LV_Z_POINTER_INPUT_MSGQ_COUNT", "type": "int", "default": 10, "help": "Pointer input message queue depth"},
                    {"key": "CONFIG_LV_Z_BUTTON_INPUT", "type": "bool", "default": False, "help": "Enable button input device"},
                    {"key": "CONFIG_LV_Z_ENCODER_INPUT", "type": "bool", "default": False, "help": "Enable rotary encoder input device"},
                    {"key": "CONFIG_LV_Z_KEYPAD_INPUT", "type": "bool", "default": False, "help": "Enable keypad input device"},
                ]
            },
            {
                "id": "fonts",
                "title": "Fonts",
                "options": [
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_8", "type": "bool", "default": False, "help": "Montserrat 8px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_10", "type": "bool", "default": False, "help": "Montserrat 10px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_12", "type": "bool", "default": False, "help": "Montserrat 12px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_14", "type": "bool", "default": True, "help": "Montserrat 14px font (default)"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_16", "type": "bool", "default": False, "help": "Montserrat 16px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_18", "type": "bool", "default": False, "help": "Montserrat 18px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_20", "type": "bool", "default": False, "help": "Montserrat 20px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_22", "type": "bool", "default": False, "help": "Montserrat 22px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_24", "type": "bool", "default": False, "help": "Montserrat 24px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_28", "type": "bool", "default": False, "help": "Montserrat 28px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_32", "type": "bool", "default": False, "help": "Montserrat 32px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_36", "type": "bool", "default": False, "help": "Montserrat 36px font"},
                    {"key": "CONFIG_LV_FONT_MONTSERRAT_48", "type": "bool", "default": False, "help": "Montserrat 48px font"},
                    {"key": "CONFIG_LV_FONT_DEFAULT_MONTSERRAT_14", "type": "bool", "default": True, "help": "Use Montserrat 14 as default font"},
                ]
            },
            {
                "id": "themes",
                "title": "Themes & Styles",
                "options": [
                    {"key": "CONFIG_LV_USE_THEME_DEFAULT", "type": "bool", "default": True, "help": "Enable default theme"},
                    {"key": "CONFIG_LV_THEME_DEFAULT_DARK", "type": "bool", "default": False, "help": "Use dark variant of default theme"},
                    {"key": "CONFIG_LV_USE_THEME_BASIC", "type": "bool", "default": False, "help": "Enable basic minimal theme"},
                    {"key": "CONFIG_LV_USE_THEME_MONO", "type": "bool", "default": False, "help": "Enable monochrome theme"},
                ]
            },
            {
                "id": "widgets",
                "title": "Widgets",
                "options": [
                    {"key": "CONFIG_LV_USE_ARC", "type": "bool", "default": True, "help": "Arc / circular gauge widget"},
                    {"key": "CONFIG_LV_USE_BAR", "type": "bool", "default": True, "help": "Progress bar widget"},
                    {"key": "CONFIG_LV_USE_BTN", "type": "bool", "default": True, "help": "Button widget"},
                    {"key": "CONFIG_LV_USE_BTNMATRIX", "type": "bool", "default": True, "help": "Button matrix widget"},
                    {"key": "CONFIG_LV_USE_CALENDAR", "type": "bool", "default": False, "help": "Calendar widget"},
                    {"key": "CONFIG_LV_USE_CANVAS", "type": "bool", "default": False, "help": "Canvas / draw widget"},
                    {"key": "CONFIG_LV_USE_CHART", "type": "bool", "default": False, "help": "Chart widget"},
                    {"key": "CONFIG_LV_USE_CHECKBOX", "type": "bool", "default": True, "help": "Checkbox widget"},
                    {"key": "CONFIG_LV_USE_DROPDOWN", "type": "bool", "default": True, "help": "Dropdown list widget"},
                    {"key": "CONFIG_LV_USE_IMG", "type": "bool", "default": True, "help": "Image widget"},
                    {"key": "CONFIG_LV_USE_IMGBTN", "type": "bool", "default": False, "help": "Image button widget"},
                    {"key": "CONFIG_LV_USE_KEYBOARD", "type": "bool", "default": False, "help": "Virtual keyboard widget"},
                    {"key": "CONFIG_LV_USE_LABEL", "type": "bool", "default": True, "help": "Label / text widget"},
                    {"key": "CONFIG_LV_USE_LED", "type": "bool", "default": False, "help": "LED indicator widget"},
                    {"key": "CONFIG_LV_USE_LINE", "type": "bool", "default": True, "help": "Line drawing widget"},
                    {"key": "CONFIG_LV_USE_LIST", "type": "bool", "default": False, "help": "List widget"},
                    {"key": "CONFIG_LV_USE_MENU", "type": "bool", "default": False, "help": "Menu widget"},
                    {"key": "CONFIG_LV_USE_METER", "type": "bool", "default": False, "help": "Meter / gauge widget"},
                    {"key": "CONFIG_LV_USE_MSGBOX", "type": "bool", "default": False, "help": "Message box widget"},
                    {"key": "CONFIG_LV_USE_ROLLER", "type": "bool", "default": True, "help": "Roller (scrollable list) widget"},
                    {"key": "CONFIG_LV_USE_SLIDER", "type": "bool", "default": True, "help": "Slider widget"},
                    {"key": "CONFIG_LV_USE_SPAN", "type": "bool", "default": False, "help": "Rich text span widget"},
                    {"key": "CONFIG_LV_USE_SPINBOX", "type": "bool", "default": False, "help": "Spinbox / number input widget"},
                    {"key": "CONFIG_LV_USE_SPINNER", "type": "bool", "default": False, "help": "Spinner / loading widget"},
                    {"key": "CONFIG_LV_USE_SWITCH", "type": "bool", "default": True, "help": "Toggle switch widget"},
                    {"key": "CONFIG_LV_USE_TABLE", "type": "bool", "default": False, "help": "Table widget"},
                    {"key": "CONFIG_LV_USE_TABVIEW", "type": "bool", "default": False, "help": "Tab view container widget"},
                    {"key": "CONFIG_LV_USE_TEXTAREA", "type": "bool", "default": True, "help": "Text area / input widget"},
                    {"key": "CONFIG_LV_USE_TILEVIEW", "type": "bool", "default": False, "help": "Tile view (swipeable pages)"},
                    {"key": "CONFIG_LV_USE_WIN", "type": "bool", "default": False, "help": "Window widget"},
                ]
            },
            {
                "id": "memory",
                "title": "Memory & Performance",
                "options": [
                    {"key": "CONFIG_LV_Z_MEM_POOL_NUMBER_BLOCKS", "type": "int", "default": 8, "help": "Number of memory pool blocks"},
                    {"key": "CONFIG_LV_MEM_CUSTOM", "type": "bool", "default": False, "help": "Use custom memory allocator"},
                    {"key": "CONFIG_LV_MEM_SIZE_KILOBYTES", "type": "int", "default": 32, "help": "Internal memory size (KB) when not using pool"},
                    {"key": "CONFIG_LV_DRAW_BUF_ALIGN", "type": "int", "default": 4, "help": "Draw buffer alignment (bytes)"},
                    {"key": "CONFIG_LV_USE_GPU", "type": "bool", "default": False, "help": "Enable GPU accelerated rendering"},
                ]
            },
            {
                "id": "debug",
                "title": "Logging & Debug",
                "options": [
                    {"key": "CONFIG_LV_USE_LOG", "type": "bool", "default": False, "help": "Enable LVGL internal logging"},
                    {"key": "CONFIG_LV_LOG_LEVEL_TRACE", "type": "bool", "default": False, "help": "Trace-level logging (most verbose)"},
                    {"key": "CONFIG_LV_LOG_LEVEL_INFO", "type": "bool", "default": False, "help": "Info-level logging"},
                    {"key": "CONFIG_LV_LOG_LEVEL_WARN", "type": "bool", "default": True, "help": "Warning-level logging"},
                    {"key": "CONFIG_LV_LOG_LEVEL_ERROR", "type": "bool", "default": False, "help": "Error-only logging"},
                    {"key": "CONFIG_LV_USE_ASSERT_NULL", "type": "bool", "default": True, "help": "Assert on NULL pointer dereference"},
                    {"key": "CONFIG_LV_USE_ASSERT_MEM_INTEGRITY", "type": "bool", "default": False, "help": "Assert on memory integrity violation"},
                    {"key": "CONFIG_LV_USE_ASSERT_STYLE", "type": "bool", "default": False, "help": "Assert on invalid style usage"},
                    {"key": "CONFIG_LV_USE_PERF_MONITOR", "type": "bool", "default": False, "help": "Show FPS & CPU usage overlay"},
                    {"key": "CONFIG_LV_USE_MEM_MONITOR", "type": "bool", "default": False, "help": "Show memory usage overlay"},
                ]
            },
        ]
    },

    # ── Bluetooth ─────────────────────────────────────────────────────
    {
        "id": "bluetooth",
        "name": "Bluetooth",
        "version": "3.7",
        "icon": "\U0001f4f6",   # 📶
        "desc": "Bluetooth Low Energy (BLE) and Bluetooth Classic/Mesh support.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_BT", "type": "bool", "default": False, "help": "Enable Bluetooth subsystem"},
                    {"key": "CONFIG_BT_HCI", "type": "bool", "default": True, "help": "Enable HCI-based Bluetooth"},
                    {"key": "CONFIG_BT_PERIPHERAL", "type": "bool", "default": False, "help": "Enable Peripheral role"},
                    {"key": "CONFIG_BT_CENTRAL", "type": "bool", "default": False, "help": "Enable Central role"},
                    {"key": "CONFIG_BT_OBSERVER", "type": "bool", "default": False, "help": "Enable Observer role (scanning)"},
                    {"key": "CONFIG_BT_BROADCASTER", "type": "bool", "default": False, "help": "Enable Broadcaster role (advertising)"},
                    {"key": "CONFIG_BT_DEVICE_NAME", "type": "text", "default": "Zephyr", "help": "Bluetooth device name"},
                    {"key": "CONFIG_BT_MAX_CONN", "type": "int", "default": 1, "help": "Maximum number of simultaneous connections"},
                ]
            },
            {
                "id": "features",
                "title": "Features",
                "options": [
                    {"key": "CONFIG_BT_SMP", "type": "bool", "default": False, "help": "Enable Security Manager Protocol (pairing/bonding)"},
                    {"key": "CONFIG_BT_PRIVACY", "type": "bool", "default": False, "help": "Enable privacy (random addresses)"},
                    {"key": "CONFIG_BT_GATT_CLIENT", "type": "bool", "default": False, "help": "Enable GATT client role"},
                    {"key": "CONFIG_BT_GATT_DYNAMIC_DB", "type": "bool", "default": False, "help": "Enable dynamic GATT database"},
                    {"key": "CONFIG_BT_GATT_CACHING", "type": "bool", "default": True, "help": "Enable GATT caching"},
                    {"key": "CONFIG_BT_ATT_TX_COUNT", "type": "int", "default": 3, "help": "Number of ATT TX buffers"},
                    {"key": "CONFIG_BT_L2CAP_TX_BUF_COUNT", "type": "int", "default": 3, "help": "Number of L2CAP TX buffers"},
                    {"key": "CONFIG_BT_BUF_ACL_RX_SIZE", "type": "int", "default": 73, "help": "ACL RX buffer size"},
                    {"key": "CONFIG_BT_BUF_ACL_TX_SIZE", "type": "int", "default": 27, "help": "ACL TX buffer size"},
                    {"key": "CONFIG_BT_SETTINGS", "type": "bool", "default": False, "help": "Persist BT settings to flash"},
                    {"key": "CONFIG_BT_KEYS_OVERWRITE_OLDEST", "type": "bool", "default": False, "help": "Overwrite oldest keys when storage is full"},
                ]
            },
            {
                "id": "extended",
                "title": "Extended / LE Audio",
                "options": [
                    {"key": "CONFIG_BT_EXT_ADV", "type": "bool", "default": False, "help": "Enable extended advertising"},
                    {"key": "CONFIG_BT_PER_ADV", "type": "bool", "default": False, "help": "Enable periodic advertising"},
                    {"key": "CONFIG_BT_ISO", "type": "bool", "default": False, "help": "Enable ISO channels (LE Audio)"},
                    {"key": "CONFIG_BT_AUDIO", "type": "bool", "default": False, "help": "Enable Bluetooth LE Audio"},
                    {"key": "CONFIG_BT_PHY_UPDATE", "type": "bool", "default": True, "help": "Enable PHY update procedure"},
                    {"key": "CONFIG_BT_DATA_LEN_UPDATE", "type": "bool", "default": True, "help": "Enable Data Length Extension"},
                ]
            },
            {
                "id": "mesh",
                "title": "Bluetooth Mesh",
                "options": [
                    {"key": "CONFIG_BT_MESH", "type": "bool", "default": False, "help": "Enable Bluetooth Mesh support"},
                    {"key": "CONFIG_BT_MESH_RELAY", "type": "bool", "default": False, "help": "Enable Mesh relay feature"},
                    {"key": "CONFIG_BT_MESH_PROXY", "type": "bool", "default": False, "help": "Enable Mesh GATT proxy"},
                    {"key": "CONFIG_BT_MESH_PB_GATT", "type": "bool", "default": False, "help": "Enable PB-GATT provisioning"},
                    {"key": "CONFIG_BT_MESH_PB_ADV", "type": "bool", "default": True, "help": "Enable PB-ADV provisioning"},
                    {"key": "CONFIG_BT_MESH_FRIEND", "type": "bool", "default": False, "help": "Enable Mesh Friend feature"},
                    {"key": "CONFIG_BT_MESH_LOW_POWER", "type": "bool", "default": False, "help": "Enable Mesh Low Power Node"},
                    {"key": "CONFIG_BT_MESH_MSG_CACHE_SIZE", "type": "int", "default": 10, "help": "Message cache size"},
                    {"key": "CONFIG_BT_MESH_ADV_BUF_COUNT", "type": "int", "default": 6, "help": "Advertising buffer count"},
                ]
            },
        ]
    },

    # ── Networking ────────────────────────────────────────────────────
    {
        "id": "networking",
        "name": "Networking",
        "version": "3.7",
        "icon": "\U0001f310",   # 🌐
        "desc": "TCP/IP networking stack with IPv4/IPv6, MQTT, HTTP, CoAP, WebSocket and more.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_NETWORKING", "type": "bool", "default": False, "help": "Enable networking subsystem"},
                    {"key": "CONFIG_NET_IPV4", "type": "bool", "default": False, "help": "Enable IPv4 support"},
                    {"key": "CONFIG_NET_IPV6", "type": "bool", "default": False, "help": "Enable IPv6 support"},
                    {"key": "CONFIG_NET_TCP", "type": "bool", "default": False, "help": "Enable TCP protocol"},
                    {"key": "CONFIG_NET_UDP", "type": "bool", "default": False, "help": "Enable UDP protocol"},
                    {"key": "CONFIG_NET_DHCPV4", "type": "bool", "default": False, "help": "Enable DHCPv4 client"},
                    {"key": "CONFIG_NET_SOCKETS", "type": "bool", "default": False, "help": "Enable BSD socket API"},
                    {"key": "CONFIG_DNS_RESOLVER", "type": "bool", "default": False, "help": "Enable DNS resolver"},
                    {"key": "CONFIG_NET_BUF_DATA_SIZE", "type": "int", "default": 128, "help": "Network buffer data fragment size"},
                    {"key": "CONFIG_NET_PKT_RX_COUNT", "type": "int", "default": 4, "help": "RX packet count"},
                    {"key": "CONFIG_NET_PKT_TX_COUNT", "type": "int", "default": 4, "help": "TX packet count"},
                    {"key": "CONFIG_NET_MAX_CONN", "type": "int", "default": 4, "help": "Maximum number of net connections"},
                ]
            },
            {
                "id": "protocols",
                "title": "Application Protocols",
                "options": [
                    {"key": "CONFIG_MQTT_LIB", "type": "bool", "default": False, "help": "Enable MQTT client library"},
                    {"key": "CONFIG_MQTT_LIB_TLS", "type": "bool", "default": False, "help": "Enable MQTT over TLS"},
                    {"key": "CONFIG_MQTT_LIB_WEBSOCKET", "type": "bool", "default": False, "help": "Enable MQTT over WebSocket"},
                    {"key": "CONFIG_HTTP_CLIENT", "type": "bool", "default": False, "help": "Enable HTTP client"},
                    {"key": "CONFIG_HTTP_SERVER", "type": "bool", "default": False, "help": "Enable HTTP server"},
                    {"key": "CONFIG_COAP", "type": "bool", "default": False, "help": "Enable CoAP protocol"},
                    {"key": "CONFIG_LWM2M", "type": "bool", "default": False, "help": "Enable LwM2M protocol"},
                    {"key": "CONFIG_WEBSOCKET_CLIENT", "type": "bool", "default": False, "help": "Enable WebSocket client"},
                    {"key": "CONFIG_NET_SOCKETS_SOCKOPT_TLS", "type": "bool", "default": False, "help": "Enable TLS socket options"},
                    {"key": "CONFIG_SNTP", "type": "bool", "default": False, "help": "Enable SNTP (time sync) client"},
                ]
            },
            {
                "id": "wifi",
                "title": "WiFi",
                "options": [
                    {"key": "CONFIG_WIFI", "type": "bool", "default": False, "help": "Enable WiFi support"},
                    {"key": "CONFIG_WIFI_NM", "type": "bool", "default": False, "help": "Enable WiFi network manager"},
                    {"key": "CONFIG_NET_L2_WIFI_SHELL", "type": "bool", "default": False, "help": "Enable WiFi shell commands"},
                    {"key": "CONFIG_NET_L2_WIFI_MGMT", "type": "bool", "default": False, "help": "Enable WiFi management API"},
                ]
            },
            {
                "id": "link_layer",
                "title": "Link Layer / Interface",
                "options": [
                    {"key": "CONFIG_NET_L2_ETHERNET", "type": "bool", "default": False, "help": "Enable Ethernet L2"},
                    {"key": "CONFIG_NET_ARP", "type": "bool", "default": False, "help": "Enable ARP protocol"},
                    {"key": "CONFIG_NET_L2_IEEE802154", "type": "bool", "default": False, "help": "Enable IEEE 802.15.4 L2"},
                    {"key": "CONFIG_NET_L2_OPENTHREAD", "type": "bool", "default": False, "help": "Enable OpenThread L2"},
                    {"key": "CONFIG_NET_LOOPBACK", "type": "bool", "default": False, "help": "Enable loopback interface"},
                ]
            },
        ]
    },

    # ── USB ───────────────────────────────────────────────────────────
    {
        "id": "usb",
        "name": "USB",
        "version": "3.7",
        "icon": "\U0001f50c",   # 🔌
        "desc": "USB device stack with CDC-ACM, HID, Mass Storage, and DFU device classes.",
        "categories": [
            {
                "id": "device",
                "title": "USB Device (new stack)",
                "options": [
                    {"key": "CONFIG_USB_DEVICE_STACK", "type": "bool", "default": False, "help": "Enable USB device stack"},
                    {"key": "CONFIG_USB_DEVICE_VID", "type": "int", "default": 0x2FE3, "help": "USB Vendor ID (hex)"},
                    {"key": "CONFIG_USB_DEVICE_PID", "type": "int", "default": 0x0100, "help": "USB Product ID (hex)"},
                    {"key": "CONFIG_USB_DEVICE_MANUFACTURER", "type": "text", "default": "ZEPHYR", "help": "Manufacturer string"},
                    {"key": "CONFIG_USB_DEVICE_PRODUCT", "type": "text", "default": "Zephyr USB Device", "help": "Product string"},
                    {"key": "CONFIG_USB_DEVICE_SN", "type": "text", "default": "0123456789ABCDEF", "help": "Serial number string"},
                    {"key": "CONFIG_USBD_MAX_SPEED", "type": "choice", "choices": ["full-speed", "high-speed"], "default": "full-speed", "help": "Maximum USB speed"},
                ]
            },
            {
                "id": "classes",
                "title": "Device Classes",
                "options": [
                    {"key": "CONFIG_USB_CDC_ACM", "type": "bool", "default": False, "help": "Enable CDC-ACM (virtual serial port)"},
                    {"key": "CONFIG_USB_CDC_ACM_RINGBUF_SIZE", "type": "int", "default": 1024, "help": "CDC-ACM ring buffer size"},
                    {"key": "CONFIG_USB_DEVICE_HID", "type": "bool", "default": False, "help": "Enable HID device class"},
                    {"key": "CONFIG_USB_MASS_STORAGE", "type": "bool", "default": False, "help": "Enable Mass Storage class"},
                    {"key": "CONFIG_USB_DFU_CLASS", "type": "bool", "default": False, "help": "Enable DFU (firmware update) class"},
                    {"key": "CONFIG_USB_DEVICE_BLUETOOTH", "type": "bool", "default": False, "help": "Enable USB Bluetooth (HCI) class"},
                    {"key": "CONFIG_USB_DEVICE_NETWORK_ECM", "type": "bool", "default": False, "help": "Enable USB ECM networking"},
                    {"key": "CONFIG_USB_DEVICE_NETWORK_RNDIS", "type": "bool", "default": False, "help": "Enable USB RNDIS networking"},
                ]
            },
            {
                "id": "console",
                "title": "USB Console",
                "options": [
                    {"key": "CONFIG_USB_DEVICE_LOG_LEVEL_DBG", "type": "bool", "default": False, "help": "Enable USB debug logging"},
                    {"key": "CONFIG_UART_CONSOLE_ON_DEV_NAME", "type": "text", "default": "CDC_ACM_0", "help": "UART console device name when using CDC-ACM"},
                    {"key": "CONFIG_USB_DEVICE_INITIALIZE_AT_BOOT", "type": "bool", "default": True, "help": "Initialize USB at boot"},
                ]
            },
        ]
    },

    # ── Shell ─────────────────────────────────────────────────────────
    {
        "id": "shell",
        "name": "Shell",
        "version": "3.7",
        "icon": "\U0001f5a5\ufe0f",  # 🖥️
        "desc": "Interactive command shell with UART, RTT, Telnet, and USB backends.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SHELL", "type": "bool", "default": False, "help": "Enable shell subsystem"},
                    {"key": "CONFIG_SHELL_PROMPT_UART", "type": "text", "default": "uart:~$ ", "help": "Shell prompt string"},
                    {"key": "CONFIG_SHELL_CMD_BUFF_SIZE", "type": "int", "default": 256, "help": "Command buffer size"},
                    {"key": "CONFIG_SHELL_PRINTF_BUFF_SIZE", "type": "int", "default": 30, "help": "Printf buffer size"},
                    {"key": "CONFIG_SHELL_ARGC_MAX", "type": "int", "default": 12, "help": "Maximum number of command arguments"},
                    {"key": "CONFIG_SHELL_HISTORY", "type": "bool", "default": True, "help": "Enable command history"},
                    {"key": "CONFIG_SHELL_HISTORY_BUFFER", "type": "int", "default": 512, "help": "History buffer size in bytes"},
                    {"key": "CONFIG_SHELL_TAB", "type": "bool", "default": True, "help": "Enable Tab auto-completion"},
                    {"key": "CONFIG_SHELL_TAB_AUTOCOMPLETION", "type": "bool", "default": True, "help": "Enable Tab auto-complete with candidates"},
                    {"key": "CONFIG_SHELL_WILDCARD", "type": "bool", "default": False, "help": "Enable wildcard expansion"},
                    {"key": "CONFIG_SHELL_HELP", "type": "bool", "default": True, "help": "Enable built-in help command"},
                    {"key": "CONFIG_SHELL_VT100_COLORS", "type": "bool", "default": True, "help": "Enable VT100 color codes"},
                ]
            },
            {
                "id": "backends",
                "title": "Backends",
                "options": [
                    {"key": "CONFIG_SHELL_BACKEND_SERIAL", "type": "bool", "default": True, "help": "Enable UART serial backend"},
                    {"key": "CONFIG_SHELL_BACKEND_RTT", "type": "bool", "default": False, "help": "Enable SEGGER RTT backend"},
                    {"key": "CONFIG_SHELL_BACKEND_TELNET", "type": "bool", "default": False, "help": "Enable Telnet backend"},
                    {"key": "CONFIG_SHELL_BACKEND_DUMMY", "type": "bool", "default": False, "help": "Enable dummy backend (testing)"},
                ]
            },
            {
                "id": "modules",
                "title": "Shell Modules",
                "options": [
                    {"key": "CONFIG_KERNEL_SHELL", "type": "bool", "default": False, "help": "Enable kernel shell commands"},
                    {"key": "CONFIG_DEVICE_SHELL", "type": "bool", "default": False, "help": "Enable device shell commands"},
                    {"key": "CONFIG_DEVMEM_SHELL", "type": "bool", "default": False, "help": "Enable devmem read/write commands"},
                    {"key": "CONFIG_DATE_SHELL", "type": "bool", "default": False, "help": "Enable date shell command"},
                ]
            },
        ]
    },

    # ── Logging ───────────────────────────────────────────────────────
    {
        "id": "logging",
        "name": "Logging",
        "version": "3.7",
        "icon": "\U0001f4dd",   # 📝
        "desc": "Structured logging subsystem with multiple backends and filtering.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_LOG", "type": "bool", "default": False, "help": "Enable logging subsystem"},
                    {"key": "CONFIG_LOG_DEFAULT_LEVEL", "type": "choice", "choices": ["0", "1", "2", "3", "4"], "default": "3", "help": "Default log level (0=off,1=err,2=warn,3=info,4=dbg)"},
                    {"key": "CONFIG_LOG_MAX_LEVEL", "type": "choice", "choices": ["0", "1", "2", "3", "4"], "default": "4", "help": "Compile-time max log level"},
                    {"key": "CONFIG_LOG_PRINTK", "type": "bool", "default": True, "help": "Redirect printk to logging"},
                    {"key": "CONFIG_LOG_MODE_DEFERRED", "type": "bool", "default": True, "help": "Deferred logging mode"},
                    {"key": "CONFIG_LOG_MODE_IMMEDIATE", "type": "bool", "default": False, "help": "Immediate logging mode"},
                    {"key": "CONFIG_LOG_MODE_MINIMAL", "type": "bool", "default": False, "help": "Minimal logging mode (low footprint)"},
                    {"key": "CONFIG_LOG_BUFFER_SIZE", "type": "int", "default": 1024, "help": "Deferred log buffer size (bytes)"},
                    {"key": "CONFIG_LOG_PROCESS_THREAD_STACK_SIZE", "type": "int", "default": 768, "help": "Log processing thread stack size"},
                ]
            },
            {
                "id": "backends",
                "title": "Backends",
                "options": [
                    {"key": "CONFIG_LOG_BACKEND_UART", "type": "bool", "default": True, "help": "Enable UART log backend"},
                    {"key": "CONFIG_LOG_BACKEND_RTT", "type": "bool", "default": False, "help": "Enable SEGGER RTT log backend"},
                    {"key": "CONFIG_LOG_BACKEND_NET", "type": "bool", "default": False, "help": "Enable network (syslog) log backend"},
                    {"key": "CONFIG_LOG_BACKEND_FS", "type": "bool", "default": False, "help": "Enable filesystem log backend"},
                    {"key": "CONFIG_LOG_BACKEND_SWO", "type": "bool", "default": False, "help": "Enable SWO log backend"},
                ]
            },
            {
                "id": "formatting",
                "title": "Formatting",
                "options": [
                    {"key": "CONFIG_LOG_FUNC_NAME_PREFIX_ERR", "type": "bool", "default": False, "help": "Include function name on errors"},
                    {"key": "CONFIG_LOG_FUNC_NAME_PREFIX_WRN", "type": "bool", "default": False, "help": "Include function name on warnings"},
                    {"key": "CONFIG_LOG_FUNC_NAME_PREFIX_INF", "type": "bool", "default": False, "help": "Include function name on info"},
                    {"key": "CONFIG_LOG_FUNC_NAME_PREFIX_DBG", "type": "bool", "default": True, "help": "Include function name on debug"},
                    {"key": "CONFIG_LOG_OUTPUT_FORMAT_TIMESTAMP", "type": "bool", "default": True, "help": "Include timestamp in log output"},
                ]
            },
        ]
    },

    # ── Settings / NVS ────────────────────────────────────────────────
    {
        "id": "settings",
        "name": "Settings & NVS",
        "version": "3.7",
        "icon": "\U0001f4be",   # 💾
        "desc": "Persistent settings with NVS, ZMS, FCB, or file-system backends.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SETTINGS", "type": "bool", "default": False, "help": "Enable settings subsystem"},
                    {"key": "CONFIG_SETTINGS_RUNTIME", "type": "bool", "default": False, "help": "Enable runtime settings (RAM)"},
                ]
            },
            {
                "id": "backend",
                "title": "Backend",
                "options": [
                    {"key": "CONFIG_SETTINGS_NVS", "type": "bool", "default": False, "help": "Use NVS backend for settings"},
                    {"key": "CONFIG_SETTINGS_ZMS", "type": "bool", "default": False, "help": "Use ZMS backend for settings"},
                    {"key": "CONFIG_SETTINGS_FCB", "type": "bool", "default": False, "help": "Use Flash Circular Buffer backend"},
                    {"key": "CONFIG_SETTINGS_FILE", "type": "bool", "default": False, "help": "Use file system backend"},
                    {"key": "CONFIG_SETTINGS_SHELL", "type": "bool", "default": False, "help": "Enable settings shell commands"},
                ]
            },
            {
                "id": "nvs",
                "title": "NVS / ZMS Configuration",
                "options": [
                    {"key": "CONFIG_NVS", "type": "bool", "default": False, "help": "Enable NVS (Non-Volatile Storage)"},
                    {"key": "CONFIG_NVS_LOG_LEVEL_DBG", "type": "bool", "default": False, "help": "Enable NVS debug logging"},
                    {"key": "CONFIG_ZMS", "type": "bool", "default": False, "help": "Enable ZMS (Zephyr Memory Storage)"},
                    {"key": "CONFIG_FLASH_MAP", "type": "bool", "default": False, "help": "Enable flash area map"},
                ]
            },
        ]
    },

    # ── File Systems ──────────────────────────────────────────────────
    {
        "id": "filesystem",
        "name": "File Systems",
        "version": "3.7",
        "icon": "\U0001f4c1",   # 📁
        "desc": "File system support with LittleFS, FAT FS, and VFS layer.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_FILE_SYSTEM", "type": "bool", "default": False, "help": "Enable file system support"},
                    {"key": "CONFIG_FILE_SYSTEM_SHELL", "type": "bool", "default": False, "help": "Enable file system shell commands"},
                    {"key": "CONFIG_FILE_SYSTEM_MKFS", "type": "bool", "default": False, "help": "Enable mkfs (format) support"},
                    {"key": "CONFIG_FILE_SYSTEM_MAX_TYPES", "type": "int", "default": 2, "help": "Maximum number of registered FS types"},
                    {"key": "CONFIG_FILE_SYSTEM_MAX_FILE_NAME", "type": "int", "default": 12, "help": "Maximum file name length"},
                ]
            },
            {
                "id": "littlefs",
                "title": "LittleFS",
                "options": [
                    {"key": "CONFIG_FILE_SYSTEM_LITTLEFS", "type": "bool", "default": False, "help": "Enable LittleFS support"},
                    {"key": "CONFIG_FS_LITTLEFS_CACHE_SIZE", "type": "int", "default": 256, "help": "LittleFS cache size"},
                    {"key": "CONFIG_FS_LITTLEFS_LOOKAHEAD_SIZE", "type": "int", "default": 32, "help": "LittleFS lookahead size"},
                    {"key": "CONFIG_FS_LITTLEFS_READ_SIZE", "type": "int", "default": 16, "help": "Minimum read size"},
                    {"key": "CONFIG_FS_LITTLEFS_PROG_SIZE", "type": "int", "default": 16, "help": "Minimum program size"},
                ]
            },
            {
                "id": "fatfs",
                "title": "FAT FS",
                "options": [
                    {"key": "CONFIG_FAT_FILESYSTEM_ELM", "type": "bool", "default": False, "help": "Enable ELM FAT file system"},
                    {"key": "CONFIG_FS_FATFS_EXFAT", "type": "bool", "default": False, "help": "Enable exFAT support"},
                    {"key": "CONFIG_FS_FATFS_LFN", "type": "bool", "default": False, "help": "Enable Long File Name support"},
                    {"key": "CONFIG_FS_FATFS_MAX_LFN", "type": "int", "default": 255, "help": "Maximum LFN length"},
                    {"key": "CONFIG_FS_FATFS_CODEPAGE", "type": "int", "default": 437, "help": "OEM codepage for FAT (437=US)"},
                    {"key": "CONFIG_FS_FATFS_MAX_SS", "type": "int", "default": 512, "help": "Maximum sector size"},
                ]
            },
        ]
    },

    # ── Power Management ──────────────────────────────────────────────
    {
        "id": "power_management",
        "name": "Power Management",
        "version": "3.7",
        "icon": "\U0001f50b",   # 🔋
        "desc": "System and device power management with sleep states.",
        "categories": [
            {
                "id": "system",
                "title": "System PM",
                "options": [
                    {"key": "CONFIG_PM", "type": "bool", "default": False, "help": "Enable system power management"},
                    {"key": "CONFIG_PM_S2RAM", "type": "bool", "default": False, "help": "Enable Suspend-to-RAM state"},
                    {"key": "CONFIG_PM_POLICY_DEFAULT", "type": "bool", "default": True, "help": "Use default PM policy (residency-based)"},
                    {"key": "CONFIG_PM_POLICY_CUSTOM", "type": "bool", "default": False, "help": "Use custom PM policy"},
                ]
            },
            {
                "id": "device",
                "title": "Device PM",
                "options": [
                    {"key": "CONFIG_PM_DEVICE", "type": "bool", "default": False, "help": "Enable device power management"},
                    {"key": "CONFIG_PM_DEVICE_RUNTIME", "type": "bool", "default": False, "help": "Enable runtime device PM"},
                    {"key": "CONFIG_PM_DEVICE_POWER_DOMAIN", "type": "bool", "default": False, "help": "Enable power domain support"},
                    {"key": "CONFIG_PM_DEVICE_SHELL", "type": "bool", "default": False, "help": "Enable PM shell commands"},
                ]
            },
        ]
    },

    # ── Display Drivers ───────────────────────────────────────────────
    {
        "id": "display",
        "name": "Display Drivers",
        "version": "3.7",
        "icon": "\U0001f4fa",   # 📺
        "desc": "Display controller drivers – SSD1306, ILI9xxx, ST7789V, e-paper, and more.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_DISPLAY", "type": "bool", "default": False, "help": "Enable display driver subsystem"},
                    {"key": "CONFIG_DISPLAY_LOG_LEVEL_DBG", "type": "bool", "default": False, "help": "Enable display debug logging"},
                    {"key": "CONFIG_DISPLAY_INIT_PRIORITY", "type": "int", "default": 85, "help": "Display driver init priority"},
                ]
            },
            {
                "id": "drivers",
                "title": "Display Drivers",
                "options": [
                    {"key": "CONFIG_SSD1306", "type": "bool", "default": False, "help": "SSD1306 OLED driver (128×64 / 128×32)"},
                    {"key": "CONFIG_SSD16XX", "type": "bool", "default": False, "help": "SSD16xx e-paper driver"},
                    {"key": "CONFIG_ILI9XXX", "type": "bool", "default": False, "help": "ILI9340/9341/9488 TFT driver"},
                    {"key": "CONFIG_ST7789V", "type": "bool", "default": False, "help": "ST7789V TFT driver"},
                    {"key": "CONFIG_ST7735R", "type": "bool", "default": False, "help": "ST7735R TFT driver"},
                    {"key": "CONFIG_GC9A01", "type": "bool", "default": False, "help": "GC9A01 round TFT driver"},
                    {"key": "CONFIG_SDL_DISPLAY", "type": "bool", "default": False, "help": "SDL display emulation (native_sim)"},
                    {"key": "CONFIG_DUMMY_DISPLAY", "type": "bool", "default": False, "help": "Dummy display driver (testing)"},
                ]
            },
        ]
    },

    # ── Debug & Analysis ──────────────────────────────────────────────
    {
        "id": "debug",
        "name": "Debug & Analysis",
        "version": "3.7",
        "icon": "\U0001f41b",   # 🐛
        "desc": "Debug tools, thread analyzer, core dump, stack monitoring.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_DEBUG", "type": "bool", "default": False, "help": "Enable debug mode (no optimization)"},
                    {"key": "CONFIG_ASSERT", "type": "bool", "default": False, "help": "Enable __ASSERT macros"},
                    {"key": "CONFIG_STACK_SENTINEL", "type": "bool", "default": False, "help": "Enable stack sentinel (overflow check)"},
                    {"key": "CONFIG_STACK_CANARIES", "type": "bool", "default": False, "help": "Enable stack canaries (GCC -fstack-protector)"},
                    {"key": "CONFIG_STACK_POINTER_RANDOM", "type": "int", "default": 0, "help": "Stack pointer randomization size (0=off)"},
                    {"key": "CONFIG_BOOT_BANNER", "type": "bool", "default": True, "help": "Print Zephyr boot banner"},
                    {"key": "CONFIG_PRINTK", "type": "bool", "default": True, "help": "Enable printk output"},
                ]
            },
            {
                "id": "thread",
                "title": "Thread Analyzer",
                "options": [
                    {"key": "CONFIG_THREAD_ANALYZER", "type": "bool", "default": False, "help": "Enable thread analyzer"},
                    {"key": "CONFIG_THREAD_ANALYZER_AUTO", "type": "bool", "default": False, "help": "Enable periodic auto-printing"},
                    {"key": "CONFIG_THREAD_ANALYZER_AUTO_INTERVAL", "type": "int", "default": 60, "help": "Auto-print interval (seconds)"},
                    {"key": "CONFIG_THREAD_NAME", "type": "bool", "default": False, "help": "Store thread names (debug)"},
                    {"key": "CONFIG_THREAD_RUNTIME_STATS", "type": "bool", "default": False, "help": "Collect per-thread runtime stats"},
                ]
            },
            {
                "id": "coredump",
                "title": "Core Dump",
                "options": [
                    {"key": "CONFIG_DEBUG_COREDUMP", "type": "bool", "default": False, "help": "Enable core dump on fatal error"},
                    {"key": "CONFIG_DEBUG_COREDUMP_BACKEND_LOGGING", "type": "bool", "default": False, "help": "Output core dump via logging"},
                    {"key": "CONFIG_DEBUG_COREDUMP_BACKEND_FLASH_PARTITION", "type": "bool", "default": False, "help": "Store core dump in flash partition"},
                    {"key": "CONFIG_DEBUG_COREDUMP_MEMORY_DUMP_MIN", "type": "bool", "default": True, "help": "Minimal memory dump (registers only)"},
                ]
            },
        ]
    },

    # ── Crypto / TLS ──────────────────────────────────────────────────
    {
        "id": "crypto",
        "name": "Crypto & TLS",
        "version": "3.7",
        "icon": "\U0001f510",   # 🔐
        "desc": "Mbed TLS, hardware crypto, TLS sockets and certificate management.",
        "categories": [
            {
                "id": "mbedtls",
                "title": "Mbed TLS",
                "options": [
                    {"key": "CONFIG_MBEDTLS", "type": "bool", "default": False, "help": "Enable Mbed TLS library"},
                    {"key": "CONFIG_MBEDTLS_BUILTIN", "type": "bool", "default": True, "help": "Use Zephyr built-in Mbed TLS"},
                    {"key": "CONFIG_MBEDTLS_TLS_VERSION_1_2", "type": "bool", "default": True, "help": "Enable TLS 1.2 support"},
                    {"key": "CONFIG_MBEDTLS_DTLS", "type": "bool", "default": False, "help": "Enable DTLS support"},
                    {"key": "CONFIG_MBEDTLS_KEY_EXCHANGE_RSA_ENABLED", "type": "bool", "default": True, "help": "Enable RSA key exchange"},
                    {"key": "CONFIG_MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED", "type": "bool", "default": False, "help": "Enable ECDHE-ECDSA key exchange"},
                    {"key": "CONFIG_MBEDTLS_ECP_DP_SECP256R1_ENABLED", "type": "bool", "default": False, "help": "Enable secp256r1 elliptic curve"},
                    {"key": "CONFIG_MBEDTLS_HEAP_SIZE", "type": "int", "default": 15360, "help": "Mbed TLS heap size (bytes)"},
                    {"key": "CONFIG_MBEDTLS_SSL_MAX_CONTENT_LEN", "type": "int", "default": 1500, "help": "Max TLS content length"},
                    {"key": "CONFIG_MBEDTLS_DEBUG", "type": "bool", "default": False, "help": "Enable Mbed TLS debug logging"},
                    {"key": "CONFIG_MBEDTLS_DEBUG_LEVEL", "type": "int", "default": 0, "help": "Mbed TLS debug verbosity (0-4)"},
                ]
            },
            {
                "id": "hw_crypto",
                "title": "Hardware Crypto",
                "options": [
                    {"key": "CONFIG_CRYPTO", "type": "bool", "default": False, "help": "Enable crypto driver API"},
                    {"key": "CONFIG_CRYPTO_MBEDTLS_SHIM", "type": "bool", "default": False, "help": "Use Mbed TLS shim as crypto backend"},
                    {"key": "CONFIG_ENTROPY_GENERATOR", "type": "bool", "default": False, "help": "Enable hardware entropy generator"},
                    {"key": "CONFIG_HARDWARE_DEVICE_CS_GENERATOR", "type": "bool", "default": False, "help": "Enable HW random number generator"},
                ]
            },
        ]
    },

    # ── DFU / MCUboot ─────────────────────────────────────────────────
    {
        "id": "dfu",
        "name": "DFU & MCUboot",
        "version": "3.7",
        "icon": "\u2b06\ufe0f",  # ⬆️
        "desc": "Device firmware update via MCUboot, image manager and update protocols.",
        "categories": [
            {
                "id": "mcuboot",
                "title": "MCUboot Integration",
                "options": [
                    {"key": "CONFIG_BOOTLOADER_MCUBOOT", "type": "bool", "default": False, "help": "Application uses MCUboot as bootloader"},
                    {"key": "CONFIG_MCUBOOT_SIGNATURE_KEY_FILE", "type": "text", "default": "", "help": "Path to MCUboot signing key (.pem)"},
                    {"key": "CONFIG_MCUBOOT_EXTRA_IMGTOOL_ARGS", "type": "text", "default": "", "help": "Extra imgtool arguments"},
                    {"key": "CONFIG_MCUBOOT_GENERATE_CONFIRMED_IMAGE", "type": "bool", "default": False, "help": "Generate a confirmed (non-test) image"},
                ]
            },
            {
                "id": "image",
                "title": "Image Manager",
                "options": [
                    {"key": "CONFIG_IMG_MANAGER", "type": "bool", "default": False, "help": "Enable image manager (confirm/revert)"},
                    {"key": "CONFIG_IMG_ENABLE_IMAGE_CHECK", "type": "bool", "default": True, "help": "Validate image before boot"},
                    {"key": "CONFIG_IMG_ERASE_PROGRESSIVELY", "type": "bool", "default": False, "help": "Erase flash progressively during update"},
                    {"key": "CONFIG_UPDATEABLE_IMAGE_NUMBER", "type": "int", "default": 1, "help": "Number of updateable images"},
                ]
            },
            {
                "id": "smp",
                "title": "SMP / MCUmgr",
                "options": [
                    {"key": "CONFIG_MCUMGR", "type": "bool", "default": False, "help": "Enable MCU manager (SMP protocol)"},
                    {"key": "CONFIG_MCUMGR_TRANSPORT_BT", "type": "bool", "default": False, "help": "Enable SMP over Bluetooth"},
                    {"key": "CONFIG_MCUMGR_TRANSPORT_UART", "type": "bool", "default": False, "help": "Enable SMP over UART"},
                    {"key": "CONFIG_MCUMGR_TRANSPORT_UDP", "type": "bool", "default": False, "help": "Enable SMP over UDP"},
                    {"key": "CONFIG_MCUMGR_GRP_IMG", "type": "bool", "default": False, "help": "Enable image management group"},
                    {"key": "CONFIG_MCUMGR_GRP_OS", "type": "bool", "default": False, "help": "Enable OS management group"},
                    {"key": "CONFIG_MCUMGR_GRP_FS", "type": "bool", "default": False, "help": "Enable filesystem management group"},
                    {"key": "CONFIG_MCUMGR_GRP_SHELL", "type": "bool", "default": False, "help": "Enable shell management group"},
                ]
            },
        ]
    },

    # ── Sensor ────────────────────────────────────────────────────────
    {
        "id": "sensor",
        "name": "Sensor",
        "version": "3.7",
        "icon": "\U0001f321\ufe0f",  # 🌡️
        "desc": "Sensor driver subsystem with async API, streaming and shell.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SENSOR", "type": "bool", "default": False, "help": "Enable sensor driver subsystem"},
                    {"key": "CONFIG_SENSOR_ASYNC_API", "type": "bool", "default": False, "help": "Enable asynchronous sensor API"},
                    {"key": "CONFIG_SENSOR_SHELL", "type": "bool", "default": False, "help": "Enable sensor shell commands"},
                    {"key": "CONFIG_SENSOR_INFO", "type": "bool", "default": False, "help": "Enable sensor info queries"},
                    {"key": "CONFIG_SENSOR_INIT_PRIORITY", "type": "int", "default": 90, "help": "Sensor driver init priority"},
                ]
            },
        ]
    },

    # ── Watchdog ──────────────────────────────────────────────────────
    {
        "id": "watchdog",
        "name": "Watchdog",
        "version": "3.7",
        "icon": "\U0001f415",   # 🐕
        "desc": "Hardware watchdog timer drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_WATCHDOG", "type": "bool", "default": False, "help": "Enable watchdog timer driver"},
                    {"key": "CONFIG_WDT_DISABLE_AT_BOOT", "type": "bool", "default": False, "help": "Disable watchdog at boot"},
                    {"key": "CONFIG_WDT_MULTISTAGE", "type": "bool", "default": False, "help": "Enable multistage watchdog"},
                    {"key": "CONFIG_WDT_SHELL", "type": "bool", "default": False, "help": "Enable watchdog shell commands"},
                    {"key": "CONFIG_TASK_WDT", "type": "bool", "default": False, "help": "Enable task-level watchdog"},
                    {"key": "CONFIG_TASK_WDT_CHANNELS", "type": "int", "default": 5, "help": "Number of task WDT channels"},
                ]
            },
        ]
    },

    # ── CAN Bus ───────────────────────────────────────────────────────
    {
        "id": "can",
        "name": "CAN Bus",
        "version": "3.7",
        "icon": "\U0001f697",   # 🚗
        "desc": "CAN / CAN-FD bus drivers and higher-layer protocols (ISO-TP, CANopen).",
        "categories": [
            {
                "id": "driver",
                "title": "CAN Driver",
                "options": [
                    {"key": "CONFIG_CAN", "type": "bool", "default": False, "help": "Enable CAN bus driver"},
                    {"key": "CONFIG_CAN_FD_MODE", "type": "bool", "default": False, "help": "Enable CAN-FD support"},
                    {"key": "CONFIG_CAN_RX_TIMESTAMP", "type": "bool", "default": False, "help": "Enable RX timestamps"},
                    {"key": "CONFIG_CAN_SHELL", "type": "bool", "default": False, "help": "Enable CAN shell commands"},
                    {"key": "CONFIG_CAN_INIT_PRIORITY", "type": "int", "default": 80, "help": "CAN driver init priority"},
                    {"key": "CONFIG_CAN_MAX_FILTER", "type": "int", "default": 5, "help": "Maximum number of CAN filters"},
                ]
            },
            {
                "id": "protocols",
                "title": "CAN Protocols",
                "options": [
                    {"key": "CONFIG_ISOTP", "type": "bool", "default": False, "help": "Enable ISO-TP (ISO 15765-2) transport"},
                    {"key": "CONFIG_ISOTP_RX_BUF_COUNT", "type": "int", "default": 4, "help": "ISO-TP RX buffer count"},
                    {"key": "CONFIG_ISOTP_TX_BUF_COUNT", "type": "int", "default": 4, "help": "ISO-TP TX buffer count"},
                    {"key": "CONFIG_CANOPEN", "type": "bool", "default": False, "help": "Enable CANopen (CANopenNode) stack"},
                    {"key": "CONFIG_CANOPEN_STORAGE", "type": "bool", "default": False, "help": "Enable CANopen OD storage"},
                    {"key": "CONFIG_CANOPEN_LEDS", "type": "bool", "default": False, "help": "Enable CANopen LED indicators"},
                    {"key": "CONFIG_CANOPEN_SDO_BUFFER_SIZE", "type": "int", "default": 32, "help": "CANopen SDO buffer size"},
                    {"key": "CONFIG_CANOPEN_TX_WORKQUEUE_STACK_SIZE", "type": "int", "default": 320, "help": "CANopen TX workqueue stack size"},
                ]
            },
        ]
    },

    # ── I2C ───────────────────────────────────────────────────────────
    {
        "id": "i2c",
        "name": "I\u00b2C",
        "version": "3.7",
        "icon": "\U0001f517",   # 🔗
        "desc": "I\u00b2C bus drivers and utilities.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_I2C", "type": "bool", "default": False, "help": "Enable I\u00b2C driver"},
                    {"key": "CONFIG_I2C_SHELL", "type": "bool", "default": False, "help": "Enable I\u00b2C shell commands"},
                    {"key": "CONFIG_I2C_DUMP_MESSAGES", "type": "bool", "default": False, "help": "Dump I\u00b2C messages (debug)"},
                    {"key": "CONFIG_I2C_DUMP_MESSAGES_ALLOWLIST", "type": "bool", "default": False, "help": "Only dump from allowlisted devices"},
                    {"key": "CONFIG_I2C_INIT_PRIORITY", "type": "int", "default": 50, "help": "I\u00b2C driver init priority"},
                    {"key": "CONFIG_I2C_RTIO", "type": "bool", "default": False, "help": "Enable I\u00b2C RTIO support"},
                    {"key": "CONFIG_I2C_TARGET", "type": "bool", "default": False, "help": "Enable I\u00b2C target (slave) mode"},
                ]
            },
        ]
    },

    # ── SPI ───────────────────────────────────────────────────────────
    {
        "id": "spi",
        "name": "SPI",
        "version": "3.7",
        "icon": "\U0001f504",   # 🔄
        "desc": "SPI bus drivers with async, slave and extended mode support.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SPI", "type": "bool", "default": False, "help": "Enable SPI driver"},
                    {"key": "CONFIG_SPI_ASYNC", "type": "bool", "default": False, "help": "Enable asynchronous SPI API"},
                    {"key": "CONFIG_SPI_SLAVE", "type": "bool", "default": False, "help": "Enable SPI slave mode"},
                    {"key": "CONFIG_SPI_EXTENDED_MODES", "type": "bool", "default": False, "help": "Enable dual/quad/octal SPI modes"},
                    {"key": "CONFIG_SPI_INIT_PRIORITY", "type": "int", "default": 70, "help": "SPI driver init priority"},
                    {"key": "CONFIG_SPI_SHELL", "type": "bool", "default": False, "help": "Enable SPI shell commands"},
                    {"key": "CONFIG_SPI_RTIO", "type": "bool", "default": False, "help": "Enable SPI RTIO support"},
                ]
            },
        ]
    },

    # ── UART ──────────────────────────────────────────────────────────
    {
        "id": "uart",
        "name": "UART / Serial",
        "version": "3.7",
        "icon": "\U0001f4e1",   # 📡
        "desc": "UART serial drivers with async, interrupt-driven and polling modes.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_SERIAL", "type": "bool", "default": False, "help": "Enable serial (UART) driver"},
                    {"key": "CONFIG_UART_ASYNC_API", "type": "bool", "default": False, "help": "Enable asynchronous UART API"},
                    {"key": "CONFIG_UART_INTERRUPT_DRIVEN", "type": "bool", "default": False, "help": "Enable interrupt-driven UART"},
                    {"key": "CONFIG_UART_LINE_CTRL", "type": "bool", "default": False, "help": "Enable line control (baud, RTS/CTS)"},
                    {"key": "CONFIG_UART_PIPE", "type": "bool", "default": False, "help": "Enable UART pipe (transparent channel)"},
                    {"key": "CONFIG_UART_CONSOLE", "type": "bool", "default": True, "help": "Enable UART console"},
                    {"key": "CONFIG_UART_SHELL_ON_DEV_NAME", "type": "text", "default": "UART_0", "help": "UART device for shell backend"},
                ]
            },
        ]
    },

    # ── ADC ───────────────────────────────────────────────────────────
    {
        "id": "adc",
        "name": "ADC",
        "version": "3.7",
        "icon": "\U0001f4ca",   # 📊
        "desc": "Analog-to-digital converter drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_ADC", "type": "bool", "default": False, "help": "Enable ADC driver"},
                    {"key": "CONFIG_ADC_ASYNC", "type": "bool", "default": False, "help": "Enable asynchronous ADC API"},
                    {"key": "CONFIG_ADC_SHELL", "type": "bool", "default": False, "help": "Enable ADC shell commands"},
                    {"key": "CONFIG_ADC_INIT_PRIORITY", "type": "int", "default": 80, "help": "ADC driver init priority"},
                    {"key": "CONFIG_ADC_CONFIGURABLE_INPUTS", "type": "bool", "default": False, "help": "Allow reconfigurable ADC inputs"},
                ]
            },
        ]
    },

    # ── PWM ───────────────────────────────────────────────────────────
    {
        "id": "pwm",
        "name": "PWM",
        "version": "3.7",
        "icon": "\u3030\ufe0f",  # 〰️
        "desc": "Pulse-Width Modulation drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_PWM", "type": "bool", "default": False, "help": "Enable PWM driver"},
                    {"key": "CONFIG_PWM_SHELL", "type": "bool", "default": False, "help": "Enable PWM shell commands"},
                    {"key": "CONFIG_PWM_CAPTURE", "type": "bool", "default": False, "help": "Enable PWM capture mode"},
                    {"key": "CONFIG_PWM_INIT_PRIORITY", "type": "int", "default": 80, "help": "PWM driver init priority"},
                ]
            },
        ]
    },

    # ── GPIO ──────────────────────────────────────────────────────────
    {
        "id": "gpio",
        "name": "GPIO",
        "version": "3.7",
        "icon": "\U0001f4cc",   # 📌
        "desc": "General-purpose I/O pin drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_GPIO", "type": "bool", "default": False, "help": "Enable GPIO driver"},
                    {"key": "CONFIG_GPIO_SHELL", "type": "bool", "default": False, "help": "Enable GPIO shell commands"},
                    {"key": "CONFIG_GPIO_HOGS", "type": "bool", "default": False, "help": "Enable GPIO hogs (auto-configure pins at boot)"},
                    {"key": "CONFIG_GPIO_GET_DIRECTION", "type": "bool", "default": False, "help": "Enable runtime direction query"},
                    {"key": "CONFIG_GPIO_GET_CONFIG", "type": "bool", "default": False, "help": "Enable runtime pin config query"},
                    {"key": "CONFIG_GPIO_INIT_PRIORITY", "type": "int", "default": 40, "help": "GPIO driver init priority"},
                ]
            },
        ]
    },

    # ── Flash ─────────────────────────────────────────────────────────
    {
        "id": "flash",
        "name": "Flash",
        "version": "3.7",
        "icon": "\U0001f4bf",   # 💿
        "desc": "Internal and external flash memory drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_FLASH", "type": "bool", "default": False, "help": "Enable flash driver"},
                    {"key": "CONFIG_FLASH_MAP", "type": "bool", "default": False, "help": "Enable flash area map"},
                    {"key": "CONFIG_FLASH_PAGE_LAYOUT", "type": "bool", "default": False, "help": "Enable flash page layout API"},
                    {"key": "CONFIG_FLASH_SHELL", "type": "bool", "default": False, "help": "Enable flash shell commands"},
                    {"key": "CONFIG_FLASH_INIT_PRIORITY", "type": "int", "default": 50, "help": "Flash driver init priority"},
                ]
            },
            {
                "id": "external",
                "title": "External Flash",
                "options": [
                    {"key": "CONFIG_SPI_NOR", "type": "bool", "default": False, "help": "Enable SPI NOR flash driver"},
                    {"key": "CONFIG_SPI_NOR_SFDP_DEVICETREE", "type": "bool", "default": False, "help": "Get flash params from devicetree"},
                    {"key": "CONFIG_SPI_NOR_SFDP_RUNTIME", "type": "bool", "default": False, "help": "Read SFDP at runtime"},
                    {"key": "CONFIG_SPI_NOR_FLASH_LAYOUT_PAGE_SIZE", "type": "int", "default": 65536, "help": "Page size for SPI NOR layout"},
                    {"key": "CONFIG_FLASH_JESD216_API", "type": "bool", "default": False, "help": "Enable JESD216 SFDP read API"},
                ]
            },
        ]
    },

    # ── Timer / Counter ───────────────────────────────────────────────
    {
        "id": "counter",
        "name": "Timer & Counter",
        "version": "3.7",
        "icon": "\u23f1\ufe0f",  # ⏱️
        "desc": "Hardware counter/timer drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_COUNTER", "type": "bool", "default": False, "help": "Enable counter driver"},
                    {"key": "CONFIG_COUNTER_SHELL", "type": "bool", "default": False, "help": "Enable counter shell commands"},
                    {"key": "CONFIG_COUNTER_INIT_PRIORITY", "type": "int", "default": 60, "help": "Counter driver init priority"},
                ]
            },
            {
                "id": "system",
                "title": "System Timer",
                "options": [
                    {"key": "CONFIG_SYS_CLOCK_TICKS_PER_SEC", "type": "int", "default": 10000, "help": "System clock ticks per second"},
                    {"key": "CONFIG_TICKLESS_KERNEL", "type": "bool", "default": True, "help": "Enable tickless kernel"},
                    {"key": "CONFIG_SYSTEM_CLOCK_INIT_PRIORITY", "type": "int", "default": 0, "help": "System clock init priority"},
                ]
            },
        ]
    },

    # ── DMA ───────────────────────────────────────────────────────────
    {
        "id": "dma",
        "name": "DMA",
        "version": "3.7",
        "icon": "\U0001f500",   # 🔀
        "desc": "Direct Memory Access controller drivers.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_DMA", "type": "bool", "default": False, "help": "Enable DMA driver"},
                    {"key": "CONFIG_DMA_64BIT", "type": "bool", "default": False, "help": "Enable 64-bit DMA address support"},
                    {"key": "CONFIG_DMA_INIT_PRIORITY", "type": "int", "default": 40, "help": "DMA driver init priority"},
                    {"key": "CONFIG_DMA_SHELL", "type": "bool", "default": False, "help": "Enable DMA shell commands"},
                ]
            },
        ]
    },

    # ── Console ───────────────────────────────────────────────────────
    {
        "id": "console",
        "name": "Console",
        "version": "3.7",
        "icon": "\U0001f5a8\ufe0f",  # 🖨️
        "desc": "Console subsystem – UART/RTT console, getchar, getline.",
        "categories": [
            {
                "id": "general",
                "title": "General",
                "options": [
                    {"key": "CONFIG_CONSOLE", "type": "bool", "default": True, "help": "Enable console subsystem"},
                    {"key": "CONFIG_CONSOLE_SUBSYS", "type": "bool", "default": False, "help": "Enable console input subsystem"},
                    {"key": "CONFIG_CONSOLE_GETCHAR", "type": "bool", "default": False, "help": "Enable getchar() support"},
                    {"key": "CONFIG_CONSOLE_GETLINE", "type": "bool", "default": False, "help": "Enable getline() support"},
                    {"key": "CONFIG_UART_CONSOLE", "type": "bool", "default": True, "help": "Enable UART console output"},
                    {"key": "CONFIG_RTT_CONSOLE", "type": "bool", "default": False, "help": "Enable SEGGER RTT console"},
                    {"key": "CONFIG_RAM_CONSOLE", "type": "bool", "default": False, "help": "Enable RAM console (circular buffer)"},
                    {"key": "CONFIG_RAM_CONSOLE_BUFFER_SIZE", "type": "int", "default": 1024, "help": "RAM console buffer size"},
                ]
            },
        ]
    },

    # ── Kernel ────────────────────────────────────────────────────────
    {
        "id": "kernel",
        "name": "Kernel",
        "version": "3.7",
        "icon": "\u2699\ufe0f",  # ⚙️
        "desc": "Core Zephyr RTOS kernel configuration – threads, stacks, timers, memory.",
        "categories": [
            {
                "id": "threads",
                "title": "Threads & Scheduling",
                "options": [
                    {"key": "CONFIG_MAIN_STACK_SIZE", "type": "int", "default": 1024, "help": "Main thread stack size (bytes)"},
                    {"key": "CONFIG_IDLE_STACK_SIZE", "type": "int", "default": 256, "help": "Idle thread stack size (bytes)"},
                    {"key": "CONFIG_ISR_STACK_SIZE", "type": "int", "default": 2048, "help": "ISR stack size (bytes)"},
                    {"key": "CONFIG_NUM_PREEMPT_PRIORITIES", "type": "int", "default": 15, "help": "Number of preemptible priority levels"},
                    {"key": "CONFIG_NUM_COOP_PRIORITIES", "type": "int", "default": 16, "help": "Number of cooperative priority levels"},
                    {"key": "CONFIG_SCHED_MULTIQ", "type": "bool", "default": False, "help": "Use multi-queue scheduler"},
                    {"key": "CONFIG_TIMESLICING", "type": "bool", "default": True, "help": "Enable time-slicing for equal-priority threads"},
                    {"key": "CONFIG_TIMESLICE_SIZE", "type": "int", "default": 0, "help": "Time slice size in ms (0=disabled)"},
                ]
            },
            {
                "id": "memory",
                "title": "Memory",
                "options": [
                    {"key": "CONFIG_HEAP_MEM_POOL_SIZE", "type": "int", "default": 0, "help": "Kernel heap pool size (bytes, 0=disabled)"},
                    {"key": "CONFIG_KERNEL_MEM_POOL", "type": "bool", "default": False, "help": "Enable kernel memory pool"},
                    {"key": "CONFIG_SYS_HEAP_RUNTIME_STATS", "type": "bool", "default": False, "help": "Enable sys heap runtime statistics"},
                    {"key": "CONFIG_USERSPACE", "type": "bool", "default": False, "help": "Enable user-mode threads"},
                ]
            },
            {
                "id": "ipc",
                "title": "Synchronization & IPC",
                "options": [
                    {"key": "CONFIG_POLL", "type": "bool", "default": False, "help": "Enable poll API for async waiting"},
                    {"key": "CONFIG_EVENTS", "type": "bool", "default": False, "help": "Enable event objects"},
                    {"key": "CONFIG_PIPES", "type": "bool", "default": False, "help": "Enable pipe objects"},
                    {"key": "CONFIG_SYS_MEM_BLOCKS", "type": "bool", "default": False, "help": "Enable memory block allocator"},
                ]
            },
        ]
    },

]  # end ZEPHYR_MODULES


def get_all_modules() -> list[dict]:
    """Return the full list of module definitions."""
    return ZEPHYR_MODULES


def get_module(module_id: str) -> dict | None:
    """Look up a single module by id."""
    for m in ZEPHYR_MODULES:
        if m["id"] == module_id:
            return m
    return None
