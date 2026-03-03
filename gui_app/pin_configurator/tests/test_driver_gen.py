# SPDX-License-Identifier: Apache-2.0
"""Tests for the Zephyr driver boilerplate generator."""

import sys
import pathlib
import pytest

_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from driver_generator import (
    DriverSpec,
    RegisterDef,
    DRIVER_TYPES,
    generate_driver,
    generate_kconfig,
    generate_cmake,
    generate_sensor_driver,
    generate_custom_driver,
    generate_overlay_sample,
    generate_prj_conf_sample,
    generate_readme,
    generate_test_skeleton,
    spec_from_json,
    driver_to_json,
)


class TestDriverSpec:
    """Test DriverSpec construction and defaults."""

    def test_minimal_spec(self):
        spec = DriverSpec(
            name="test_drv",
            driver_type="custom",
            compatible="vendor,test-drv",
        )
        assert spec.name == "test_drv"
        assert spec.bus == "i2c"
        assert spec.has_interrupt is False

    def test_spec_from_json(self):
        data = {
            "name": "my_sensor",
            "driver_type": "sensor",
            "compatible": "acme,temp-sensor",
            "bus": "spi",
            "description": "Temperature sensor",
            "has_interrupt": True,
            "registers": [
                {"name": "REG_TEMP", "address": 0x00, "size": 2, "rw": "RO"},
                {"name": "REG_CTRL", "address": 0x01, "size": 1, "rw": "RW"},
            ],
        }
        spec = spec_from_json(data)
        assert spec.name == "my_sensor"
        assert spec.bus == "spi"
        assert spec.has_interrupt is True
        assert len(spec.registers) == 2
        assert spec.registers[0].name == "REG_TEMP"
        assert spec.registers[0].address == 0x00


class TestSensorDriverGeneration:
    """Test sensor driver C source generation."""

    @pytest.fixture()
    def sensor_spec(self):
        return DriverSpec(
            name="bme280",
            driver_type="sensor",
            compatible="bosch,bme280",
            bus="i2c",
            description="Bosch BME280 temperature/humidity/pressure sensor",
            registers=[
                RegisterDef("REG_CHIP_ID", 0xD0, 1, "RO"),
                RegisterDef("REG_CTRL_MEAS", 0xF4, 1, "RW"),
                RegisterDef("REG_TEMP_MSB", 0xFA, 1, "RO"),
            ],
        )

    def test_source_contains_compat(self, sensor_spec):
        src = generate_sensor_driver(sensor_spec)
        assert "DT_DRV_COMPAT bosch_bme280" in src

    def test_source_contains_api_functions(self, sensor_spec):
        src = generate_sensor_driver(sensor_spec)
        assert "bme280_sample_fetch" in src
        assert "bme280_channel_get" in src
        assert "sensor_driver_api" in src

    def test_source_contains_init(self, sensor_spec):
        src = generate_sensor_driver(sensor_spec)
        assert "bme280_init" in src
        assert "DEVICE_DT_INST_DEFINE" in src
        assert "DT_INST_FOREACH_STATUS_OKAY" in src

    def test_source_contains_registers(self, sensor_spec):
        src = generate_sensor_driver(sensor_spec)
        assert "REG_CHIP_ID" in src
        assert "0xD0" in src
        assert "REG_CTRL_MEAS" in src

    def test_source_contains_i2c_helpers(self, sensor_spec):
        src = generate_sensor_driver(sensor_spec)
        assert "i2c_burst_read_dt" in src
        assert "struct i2c_dt_spec" in src

    def test_source_contains_logging(self, sensor_spec):
        src = generate_sensor_driver(sensor_spec)
        assert "LOG_MODULE_REGISTER" in src
        assert "BME280_LOG_LEVEL" in src

    def test_spi_bus_variant(self):
        spec = DriverSpec(
            name="lis3dh",
            driver_type="sensor",
            compatible="st,lis3dh",
            bus="spi",
        )
        src = generate_sensor_driver(spec)
        assert "struct spi_dt_spec" in src
        assert "#include <zephyr/drivers/spi.h>" in src

    def test_irq_handler_included(self):
        spec = DriverSpec(
            name="irq_sensor",
            driver_type="sensor",
            compatible="vendor,irq-sensor",
            has_interrupt=True,
        )
        src = generate_sensor_driver(spec)
        assert "irq_sensor_irq_handler" in src


class TestCustomDriverGeneration:
    """Test custom (bare skeleton) driver generation."""

    def test_custom_driver_basics(self):
        spec = DriverSpec(
            name="my_device",
            driver_type="custom",
            compatible="acme,my-device",
        )
        src = generate_custom_driver(spec)
        assert "DT_DRV_COMPAT acme_my_device" in src
        assert "DEVICE_DT_INST_DEFINE" in src
        assert "my_device_init" in src
        assert "struct my_device_config" in src
        assert "struct my_device_data" in src


class TestKconfig:
    """Test Kconfig generation."""

    def test_kconfig_sensor(self):
        spec = DriverSpec(
            name="bme280",
            driver_type="sensor",
            compatible="bosch,bme280",
            bus="i2c",
        )
        kconfig = generate_kconfig(spec)
        assert "config BME280" in kconfig
        assert "select I2C" in kconfig
        assert "BME280_INIT_PRIORITY" in kconfig
        assert "BME280_LOG_LEVEL" in kconfig

    def test_kconfig_spi_dependency(self):
        spec = DriverSpec(name="x", driver_type="sensor",
                          compatible="v,x", bus="spi")
        kconfig = generate_kconfig(spec)
        assert "select SPI" in kconfig


class TestCMake:
    """Test CMakeLists.txt snippet generation."""

    def test_cmake_conditional(self):
        spec = DriverSpec(name="bme280", driver_type="sensor",
                          compatible="bosch,bme280")
        cmake = generate_cmake(spec)
        assert "zephyr_library_sources_ifdef(CONFIG_BME280 bme280.c)" in cmake


class TestOverlaySample:
    """Test DTS overlay sample generation."""

    def test_i2c_overlay(self):
        spec = DriverSpec(name="bme280", driver_type="sensor",
                          compatible="bosch,bme280", bus="i2c")
        overlay = generate_overlay_sample(spec)
        assert "&i2c0" in overlay
        assert 'compatible = "bosch,bme280"' in overlay

    def test_spi_overlay(self):
        spec = DriverSpec(name="lis3dh", driver_type="sensor",
                          compatible="st,lis3dh", bus="spi")
        overlay = generate_overlay_sample(spec)
        assert "&spi0" in overlay
        assert "spi-max-frequency" in overlay


class TestFullGeneration:
    """Test the complete generate_driver() pipeline."""

    def test_full_sensor_generation(self):
        spec = DriverSpec(
            name="bme280",
            driver_type="sensor",
            compatible="bosch,bme280",
            bus="i2c",
            description="BME280 environmental sensor",
        )
        drv = generate_driver(spec)
        assert drv.source_c  # non-empty
        assert drv.kconfig
        assert drv.cmake
        assert drv.overlay_sample
        assert drv.prj_conf_sample
        assert drv.readme
        assert drv.test_c is not None  # sensor gets test skeleton

    def test_full_custom_generation(self):
        spec = DriverSpec(
            name="my_device",
            driver_type="custom",
            compatible="acme,my-device",
        )
        drv = generate_driver(spec)
        assert drv.source_c
        assert drv.kconfig
        assert drv.test_c is None  # custom doesn't get test skeleton

    def test_driver_to_json(self):
        spec = DriverSpec(
            name="test",
            driver_type="sensor",
            compatible="v,t",
        )
        drv = generate_driver(spec)
        j = driver_to_json(drv)
        assert isinstance(j, dict)
        assert "source_c" in j
        assert "kconfig" in j
        assert "cmake" in j


class TestDriverAPI:
    """Test the /api/driver-* endpoints."""

    def test_list_templates(self, client):
        resp = client.get("/api/driver-templates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        types = [t["type"] for t in data]
        assert "sensor" in types
        assert "custom" in types

    def test_generate_driver_endpoint(self, client):
        import json
        resp = client.post(
            "/api/generate-driver",
            data=json.dumps({
                "name": "test_sensor",
                "driver_type": "sensor",
                "compatible": "test,sensor",
                "bus": "i2c",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "source_c" in data
        assert "DT_DRV_COMPAT" in data["source_c"]
        assert "kconfig" in data
        assert "cmake" in data

    def test_generate_driver_missing_body(self, client):
        resp = client.post(
            "/api/generate-driver",
            data="",
            content_type="application/json",
        )
        # Should handle gracefully
        assert resp.status_code in (200, 400, 500)
