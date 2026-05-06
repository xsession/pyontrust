from board_schema import BoardDef, ExternalDevice, board_to_frontend
from package_generator import generate_board_file
from pdf_parser import DatasheetInfo, DeviceSummary, PackageInfo, PackagePin, PinMuxEntry


def test_generate_board_file_with_external_devices():
    info = DatasheetInfo(
        device=DeviceSummary(
            soc="MSPM0G3507",
            vendor="ti",
            flash_size_kb=128,
            sram_size_kb=32,
            clock_hz=80_000_000,
        ),
        packages=[
            PackageInfo(
                name="QFP-4",
                pin_count=4,
                pins=[
                    PackagePin(number=1, name="PA0", port="A", gpio_num=0),
                    PackagePin(number=2, name="PA1", port="A", gpio_num=1),
                    PackagePin(number=3, name="VDD", kind="power"),
                    PackagePin(number=4, name="GND", kind="ground"),
                ],
            )
        ],
        pin_mux={
            "PA0": [PinMuxEntry("PA0", 1, 2, "I2C0_SCL", "i2c0", "scl", "io")],
            "PA1": [PinMuxEntry("PA1", 2, 2, "I2C0_SDA", "i2c0", "sda", "io")],
        },
    )

    source = generate_board_file(
        device=info.device,
        package=info.packages[0],
        pin_mux=info.pin_mux,
        external_devices=[
            {
                "id": "bme280_i2c",
                "display": "BME280 Sensor",
                "category": "sensor",
                "bus": "i2c0",
                "compatible": "bosch,bme280",
                "address": "0x76",
                "required_signals": ["scl", "sda"],
                "frameworks": ["zephyr", "arduino"],
                "notes": "Shared environmental sensor",
            }
        ],
    )

    assert "ExternalDevice" in source
    assert "id='bme280_i2c'" in source
    assert "frameworks=['zephyr', 'arduino']" in source
    assert "external_devices=external_devices" in source


def test_board_to_frontend_includes_external_devices():
    board = BoardDef(
        soc="RP2040",
        board="rpi_pico",
        external_devices=[
            ExternalDevice(
                id="ssd1306_i2c",
                display="SSD1306 OLED",
                category="display",
                bus="i2c1",
                compatible="solomon,ssd1306fb",
                address="0x3c",
                required_signals=["scl", "sda"],
                frameworks=["zephyr", "arduino"],
                notes="128x64 OLED",
            )
        ],
    )

    frontend = board_to_frontend(board)
    assert frontend["external_devices"][0]["id"] == "ssd1306_i2c"
    assert frontend["external_devices"][0]["category"] == "display"
    assert frontend["external_devices"][0]["frameworks"] == ["zephyr", "arduino"]