# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the sensor datasheet parser module."""

import sys
import pathlib
import pytest

_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from sensor_parser import (
    SensorDatasheetInfo,
    SensorSummary,
    SensorAddress,
    RegisterMap,
    SensorRegister,
    RegisterField,
    detect_sensor_vendor,
    detect_sensor_type,
    identify_sensor,
    sensor_info_to_json,
    sensor_info_from_json,
    generate_register_header,
    generate_register_defines,
    _norm_access,
    _parse_hex,
    _is_register_table,
    _extract_registers_from_table,
    _extract_bitfields_from_table,
    _extract_registers_from_text,
    extract_addresses,
)


# ═══════════════════════════════════════════════════════════════════════
#  Data model tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataModels:
    """Verify sensor data model classes."""

    def test_register_field(self):
        f = RegisterField(
            name="ODR", bits="7:4", bit_high=7, bit_low=4,
            access="RW", reset_value=0, description="Output data rate",
        )
        assert f.name == "ODR"
        assert f.bit_high == 7
        assert f.bit_low == 4
        assert f.bits == "7:4"

    def test_sensor_register(self):
        r = SensorRegister(
            address=0x0F, name="WHO_AM_I", size=1,
            access="RO", reset_value=0x33, description="Device ID",
        )
        assert r.address == 0x0F
        assert r.c_name == "WHO_AM_I"
        assert r.reset_value == 0x33

    def test_sensor_register_c_name_normalisation(self):
        r = SensorRegister(address=0x20, name="CTRL-REG 1", access="RW")
        assert r.c_name == "CTRL_REG_1"

    def test_register_map_lookup(self):
        rm = RegisterMap(registers=[
            SensorRegister(address=0x0F, name="WHO_AM_I", access="RO"),
            SensorRegister(address=0x20, name="CTRL_REG1", access="RW"),
            SensorRegister(address=0x28, name="OUT_X_L", access="RO"),
        ])
        assert rm.by_address(0x0F).name == "WHO_AM_I"
        assert rm.by_address(0xFF) is None
        assert rm.by_name("CTRL_REG1").address == 0x20
        assert rm.by_name("nonexistent") is None

    def test_sensor_address(self):
        a = SensorAddress(
            protocol="i2c+spi",
            i2c_addresses=[0x76, 0x77],
            i2c_address_pin="SDO",
            spi_max_freq_hz=10_000_000,
            spi_mode=3,
        )
        assert a.protocol == "i2c+spi"
        assert 0x76 in a.i2c_addresses
        assert a.spi_mode == 3

    def test_sensor_summary(self):
        s = SensorSummary(
            part_number="BME280",
            vendor="bosch",
            vendor_name="Bosch Sensortec",
            sensor_type="environmental",
            who_am_i_value=0x60,
            who_am_i_reg=0xD0,
        )
        assert s.part_number == "BME280"
        assert s.who_am_i_value == 0x60

    def test_sensor_datasheet_info(self):
        info = SensorDatasheetInfo(
            summary=SensorSummary(part_number="TEST"),
            address=SensorAddress(protocol="i2c"),
            register_map=RegisterMap(registers=[
                SensorRegister(address=0x00, name="REG0", access="RO"),
            ]),
        )
        assert info.summary.part_number == "TEST"
        assert len(info.register_map.registers) == 1


# ═══════════════════════════════════════════════════════════════════════
#  Helper function tests
# ═══════════════════════════════════════════════════════════════════════

class TestHelpers:
    """Test internal helper functions."""

    @pytest.mark.parametrize("raw,expected", [
        ("RW", "RW"),
        ("R/W", "RW"),
        ("RO", "RO"),
        ("WO", "WO"),
        ("Read-only", "RO"),
        ("Write-only", "WO"),
        ("Read/Write", "RW"),
        ("W1C", "W1C"),
        ("RW1C", "W1C"),
        ("RC", "RC"),
        ("R", "RO"),
        ("W", "WO"),
    ])
    def test_norm_access(self, raw, expected):
        assert _norm_access(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("0x0F", 0x0F),
        ("0X0f", 0x0F),
        ("0Fh", 0x0F),
        ("0FH", 0x0F),
        ("0F", 0x0F),
        ("15", 0x15),   # parsed as hex
        ("FF", 0xFF),
        ("bad", 0xBAD), # valid hex
        ("", -1),
    ])
    def test_parse_hex(self, raw, expected):
        assert _parse_hex(raw) == expected


# ═══════════════════════════════════════════════════════════════════════
#  Vendor & type detection tests
# ═══════════════════════════════════════════════════════════════════════

class TestVendorDetection:
    """Test sensor vendor identification."""

    @pytest.mark.parametrize("part,expected_vendor", [
        ("BME280", "bosch"),
        ("BMP390", "bosch"),
        ("BMA456", "bosch"),
        ("LIS2DH12", "st"),
        ("LSM6DSO", "st"),
        ("LPS22HH", "st"),
        ("ICM-20948", "tdk"),
        ("MPU-6050", "tdk"),
        ("ADXL345", "adi"),
        ("MAX31875", "adi"),
        ("TMP117", "ti"),
        ("INA219", "ti"),
        ("FXOS8700", "nxp"),
        ("SHT40", "sensirion"),
        ("DPS310", "infineon"),
        ("AS7341", "ams"),
        ("MCP9808", "microchip"),
    ])
    def test_identify_sensor(self, part, expected_vendor):
        result = identify_sensor(part)
        assert result is not None, f"Failed to identify {part}"
        assert result[0] == expected_vendor

    def test_identify_unknown_sensor(self):
        assert identify_sensor("UNKNOWN_CHIP_999") is None

    @pytest.mark.parametrize("text,expected_vendor", [
        ("BME280 Combined humidity and pressure sensor", "bosch"),
        ("LIS2DH12 MEMS digital output motion sensor", "st"),
        ("ICM-42688-P 6-Axis MEMS MotionTracking Device", "tdk"),
        ("ADXL345 Digital Accelerometer", "adi"),
    ])
    def test_detect_sensor_vendor(self, text, expected_vendor):
        vid, vname, pn = detect_sensor_vendor([text])
        assert vid == expected_vendor


class TestSensorTypeDetection:
    """Test sensor type classification."""

    @pytest.mark.parametrize("text,expected_type", [
        ("3-axis digital accelerometer", "accelerometer"),
        ("MEMS gyroscope", "gyroscope"),
        ("6-axis IMU inertial measurement unit", "imu"),
        ("digital barometric pressure sensor", "pressure"),
        ("high-accuracy digital temperature sensor", "temperature"),
        ("capacitive humidity sensor", "humidity"),
        ("ambient light sensor", "light"),
        ("time-of-flight ranging sensor", "proximity"),
        ("current shunt monitor", "current"),
        ("16-bit analog-to-digital converter", "adc"),
    ])
    def test_detect_sensor_type(self, text, expected_type):
        assert detect_sensor_type([text]) == expected_type


# ═══════════════════════════════════════════════════════════════════════
#  Register table extraction tests
# ═══════════════════════════════════════════════════════════════════════

class TestRegisterTableDetection:
    """Test register table heuristics."""

    def test_standard_header(self):
        header = ["Address", "Name", "Type", "Reset", "Description"]
        is_reg, cols = _is_register_table(header)
        assert is_reg
        assert "addr" in cols
        assert "name" in cols

    def test_offset_mnemonic_header(self):
        header = ["Offset", "Mnemonic", "R/W", "Default", "Function"]
        is_reg, cols = _is_register_table(header)
        assert is_reg
        assert "addr" in cols
        assert "name" in cols

    def test_non_register_header(self):
        header = ["Pin Number", "Pin Name", "Type", "Description"]
        is_reg, cols = _is_register_table(header)
        assert not is_reg

    def test_extract_registers_from_table(self):
        tbl = [
            ["Address", "Register Name", "Type", "Reset", "Description"],
            ["0x0F", "WHO_AM_I", "RO", "0x33", "Device identification"],
            ["0x20", "CTRL_REG1", "RW", "0x00", "Control register 1"],
            ["0x21", "CTRL_REG2", "RW", "0x00", "Control register 2"],
            ["0x27", "STATUS_REG", "RO", "0x00", "Status register"],
            ["0x28", "OUT_X_L", "RO", "0x00", "X-axis output low byte"],
            ["0x29", "OUT_X_H", "RO", "0x00", "X-axis output high byte"],
        ]
        cols = {"addr": 0, "name": 1, "access": 2, "reset": 3, "desc": 4}
        regs = _extract_registers_from_table(tbl, cols)
        assert len(regs) == 6
        assert regs[0].address == 0x0F
        assert regs[0].name == "WHO_AM_I"
        assert regs[0].access == "RO"
        assert regs[0].reset_value == 0x33

    def test_extract_skips_reserved(self):
        tbl = [
            ["Address", "Name", "Type"],
            ["0x0F", "WHO_AM_I", "RO"],
            ["0x10", "Reserved", "RO"],  # reserved → kept as RESERVED_10
            ["0x11", "—", ""],           # dash → mapped to RESERVED_11
        ]
        cols = {"addr": 0, "name": 1, "access": 2}
        regs = _extract_registers_from_table(tbl, cols)
        assert len(regs) == 3
        assert regs[0].name == "WHO_AM_I"
        assert regs[1].name == "RESERVED_10"
        assert regs[2].name == "RESERVED_11"

    def test_extract_skips_invalid_addresses(self):
        tbl = [
            ["Address", "Name"],
            ["xyz", "REG1"],       # truly invalid hex
            ["—", "REG2"],         # dash → skipped
            ["0x0F", "WHO_AM_I"],
        ]
        cols = {"addr": 0, "name": 1}
        regs = _extract_registers_from_table(tbl, cols)
        assert len(regs) == 1
        assert regs[0].address == 0x0F


class TestBitFieldExtraction:
    """Test bit-field parsing from detail tables."""

    def test_standard_bitfield_table(self):
        tbl = [
            ["Bit", "Name", "Access", "Reset", "Description"],
            ["7:4", "ODR", "RW", "0", "Output data rate selection"],
            ["3", "LPen", "RW", "0", "Low-power mode enable"],
            ["2", "Zen", "RW", "1", "Z-axis enable"],
            ["1", "Yen", "RW", "1", "Y-axis enable"],
            ["0", "Xen", "RW", "1", "X-axis enable"],
        ]
        fields = _extract_bitfields_from_table(tbl, "CTRL_REG1")
        assert len(fields) == 5
        assert fields[0].name == "ODR"
        assert fields[0].bit_high == 7
        assert fields[0].bit_low == 4
        assert fields[0].bits == "7:4"
        assert fields[4].name == "XEN"
        assert fields[4].bit_high == 0
        assert fields[4].bit_low == 0

    def test_skips_reserved_fields(self):
        tbl = [
            ["Bit", "Field", "Type"],
            ["7", "BOOT", "RW"],
            ["6:4", "Reserved", "RO"],
            ["3:0", "ODR", "RW"],
        ]
        fields = _extract_bitfields_from_table(tbl, "CTRL_REG4")
        assert len(fields) == 2  # BOOT + ODR, not Reserved


class TestTextFallback:
    """Test text-based register extraction."""

    def test_hex_addr_name_pattern(self):
        texts = [
            "Register Map\n"
            "0x0F WHO_AM_I R Device identification register\n"
            "0x20 CTRL_REG1 RW Control register 1\n"
            "0x21 CTRL_REG2 RW Control register 2\n"
        ]
        regs = _extract_registers_from_text(texts)
        assert len(regs) >= 3
        names = {r.name for r in regs}
        assert "WHO_AM_I" in names
        assert "CTRL_REG1" in names

    def test_register_keyword_pattern(self):
        texts = [
            "Register 0x0F: WHO_AM_I\n"
            "Register 0x20: CTRL_REG1\n"
        ]
        regs = _extract_registers_from_text(texts)
        assert len(regs) >= 2

    def test_parenthesised_address(self):
        texts = [
            "WHO_AM_I (address 0x0F) - Device ID\n"
            "CTRL_REG1 (addr 0x20) - Control\n"
        ]
        regs = _extract_registers_from_text(texts)
        assert len(regs) >= 2


# ═══════════════════════════════════════════════════════════════════════
#  Address extraction tests
# ═══════════════════════════════════════════════════════════════════════

class TestAddressExtraction:
    """Test I2C/SPI address detection."""

    def test_i2c_address_detection(self):
        texts = [
            "The device supports I2C and SPI interfaces.\n"
            "The I2C slave address is 0x76 when SDO is connected to GND,\n"
            "and 0x77 when SDO is connected to VDDIO.\n"
            "SPI clock frequency up to 10 MHz.\n"
        ] + [""] * 29  # pad to 30 pages
        addr = extract_addresses(texts)
        assert addr.protocol == "i2c+spi"
        assert 0x76 in addr.i2c_addresses
        assert 0x77 in addr.i2c_addresses

    def test_i2c_only(self):
        texts = [
            "Communication via I2C bus.\n"
            "7-bit address = 0x48\n"
        ] + [""] * 29
        addr = extract_addresses(texts)
        assert addr.protocol == "i2c"
        assert 0x48 in addr.i2c_addresses

    def test_spi_only(self):
        texts = [
            "Serial Peripheral Interface (SPI) up to 8 MHz.\n"
            "SPI mode 3, CPOL=1, CPHA=1.\n"
        ] + [""] * 29
        addr = extract_addresses(texts)
        assert addr.protocol == "spi"
        assert addr.spi_max_freq_hz == 8_000_000
        assert addr.spi_mode == 3

    def test_address_pin_detection(self):
        texts = [
            "I2C interface.\n"
            "pin SDO selects the I2C address.\n"
            "SDO = GND → 0x76\n"
            "SDO = VDD → 0x77\n"
        ] + [""] * 29
        addr = extract_addresses(texts)
        assert addr.i2c_address_pin == "SDO"


# ═══════════════════════════════════════════════════════════════════════
#  C code generation tests
# ═══════════════════════════════════════════════════════════════════════

class TestCodeGeneration:
    """Test C header and define generation."""

    @pytest.fixture
    def sample_info(self):
        return SensorDatasheetInfo(
            summary=SensorSummary(
                part_number="BME280",
                vendor="bosch",
                vendor_name="Bosch Sensortec",
                sensor_type="environmental",
                description="Combined humidity and pressure sensor",
                who_am_i_reg=0xD0,
                who_am_i_value=0x60,
            ),
            address=SensorAddress(
                protocol="i2c+spi",
                i2c_addresses=[0x76, 0x77],
                i2c_address_pin="SDO",
            ),
            register_map=RegisterMap(registers=[
                SensorRegister(address=0xD0, name="CHIP_ID", access="RO",
                               reset_value=0x60, description="Chip ID"),
                SensorRegister(address=0xE0, name="RESET", access="WO",
                               description="Soft reset"),
                SensorRegister(address=0xF3, name="STATUS", access="RO",
                               description="Status register"),
                SensorRegister(address=0xF4, name="CTRL_MEAS", access="RW",
                               reset_value=0x00, description="Measurement control",
                               fields=[
                                   RegisterField("OSRS_T", "7:5", 7, 5, "RW", 0, "Temperature oversampling"),
                                   RegisterField("OSRS_P", "4:2", 4, 2, "RW", 0, "Pressure oversampling"),
                                   RegisterField("MODE", "1:0", 1, 0, "RW", 0, "Power mode"),
                               ]),
            ]),
        )

    def test_header_contains_guard(self, sample_info):
        h = generate_register_header(sample_info)
        assert "#ifndef __BME280_REGS_H__" in h
        assert "#define __BME280_REGS_H__" in h
        assert "#endif" in h

    def test_header_contains_i2c_addresses(self, sample_info):
        h = generate_register_header(sample_info)
        assert "BME280_I2C_ADDR_0" in h
        assert "0x76" in h.lower() or "0x76u" in h.lower()
        assert "0x77" in h.lower() or "0x77u" in h.lower()

    def test_header_contains_who_am_i(self, sample_info):
        h = generate_register_header(sample_info)
        assert "BME280_WHO_AM_I_REG" in h
        assert "0xD0" in h
        assert "BME280_WHO_AM_I_VAL" in h
        assert "0x60" in h

    def test_header_contains_registers(self, sample_info):
        h = generate_register_header(sample_info)
        assert "BME280_REG_CHIP_ID" in h
        assert "BME280_REG_RESET" in h
        assert "BME280_REG_STATUS" in h
        assert "BME280_REG_CTRL_MEAS" in h

    def test_header_contains_bitfields(self, sample_info):
        h = generate_register_header(sample_info)
        assert "BME280_CTRL_MEAS_OSRS_T_SHIFT" in h
        assert "BME280_CTRL_MEAS_OSRS_T_MASK" in h
        assert "BME280_CTRL_MEAS_MODE_SHIFT" in h
        assert "BME280_CTRL_MEAS_MODE_MASK" in h

    def test_header_custom_prefix(self, sample_info):
        h = generate_register_header(sample_info, guard_prefix="MY_SENSOR")
        assert "#ifndef __MY_SENSOR_REGS_H__" in h
        assert "MY_SENSOR_REG_CHIP_ID" in h

    def test_register_defines(self, sample_info):
        d = generate_register_defines(sample_info)
        assert "REG_CHIP_ID" in d
        assert "0xD0" in d
        assert "EXPECTED_WHO_AM_I" in d
        assert "0x60" in d


# ═══════════════════════════════════════════════════════════════════════
#  JSON serialisation tests
# ═══════════════════════════════════════════════════════════════════════

class TestJsonSerialisation:
    """Test round-trip JSON conversion."""

    def test_round_trip(self):
        original = SensorDatasheetInfo(
            summary=SensorSummary(
                part_number="LIS2DH12",
                vendor="st",
                vendor_name="STMicroelectronics",
                sensor_type="accelerometer",
                who_am_i_reg=0x0F,
                who_am_i_value=0x33,
            ),
            address=SensorAddress(
                protocol="i2c+spi",
                i2c_addresses=[0x18, 0x19],
                i2c_address_pin="SA0",
                spi_max_freq_hz=10_000_000,
                spi_mode=3,
            ),
            register_map=RegisterMap(registers=[
                SensorRegister(address=0x0F, name="WHO_AM_I", access="RO",
                               reset_value=0x33),
                SensorRegister(address=0x20, name="CTRL_REG1", access="RW",
                               reset_value=0x07, fields=[
                                   RegisterField("ODR", "7:4", 7, 4, "RW", 0, "Data rate"),
                                   RegisterField("LPen", "3", 3, 3, "RW", 0, "Low power"),
                               ]),
            ]),
        )

        j = sensor_info_to_json(original)
        restored = sensor_info_from_json(j)

        assert restored.summary.part_number == "LIS2DH12"
        assert restored.summary.who_am_i_value == 0x33
        assert restored.address.i2c_addresses == [0x18, 0x19]
        assert restored.address.spi_mode == 3
        assert len(restored.register_map.registers) == 2
        assert restored.register_map.registers[0].name == "WHO_AM_I"
        assert restored.register_map.registers[0].reset_value == 0x33
        assert len(restored.register_map.registers[1].fields) == 2

    def test_json_structure(self):
        info = SensorDatasheetInfo(
            summary=SensorSummary(part_number="TEST"),
            address=SensorAddress(protocol="i2c", i2c_addresses=[0x48]),
            register_map=RegisterMap(registers=[
                SensorRegister(address=0x00, name="TEMP", access="RO"),
            ]),
        )
        j = sensor_info_to_json(info)
        assert "summary" in j
        assert "address" in j
        assert "register_map" in j
        assert j["register_map"]["register_count"] == 1
        assert j["address"]["i2c_addresses"] == ["0x48"]


# ═══════════════════════════════════════════════════════════════════════
#  API endpoint tests
# ═══════════════════════════════════════════════════════════════════════

class TestSensorAPI:
    """Test sensor-related Flask endpoints."""

    @pytest.fixture
    def client(self):
        sys.path.insert(0, str(_PKG_DIR))
        from server import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_identify_known_sensor(self, client):
        resp = client.post(
            "/api/identify-sensor",
            data='{"part_number": "BME280"}',
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["known"] is True
        assert data["vendor"] == "bosch"

    def test_identify_unknown_sensor(self, client):
        resp = client.post(
            "/api/identify-sensor",
            data='{"part_number": "UNKNOWN_XYZ_999"}',
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["known"] is False

    def test_identify_sensor_missing_body(self, client):
        resp = client.post(
            "/api/identify-sensor",
            data='{}',
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_sensor_jobs_empty(self, client):
        resp = client.get("/api/sensor-jobs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_sensor_job_not_found(self, client):
        resp = client.get("/api/sensor-job/nonexistent")
        assert resp.status_code == 404

    def test_parse_sensor_pdf_no_file(self, client):
        resp = client.post("/api/parse-sensor-pdf")
        assert resp.status_code == 400

    def test_sensor_header_not_found(self, client):
        resp = client.get("/api/sensor-job/nonexistent/header")
        assert resp.status_code == 404
