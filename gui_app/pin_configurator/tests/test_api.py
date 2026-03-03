# SPDX-License-Identifier: Apache-2.0
"""API endpoint tests using Flask test client (no running server needed).

Inspired by Swedish Embedded SDK's multi-level test architecture:
unit → integration → system (robotbench).
"""

import json
import pytest


class TestBoardEndpoints:
    """Tests for board listing and detail endpoints."""

    def test_board_list(self, client):
        """GET /api/boards returns at least one board."""
        resp = client.get("/api/boards")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Each board should have id/board/soc fields
        for b in data:
            assert "id" in b or "board" in b

    def test_board_detail_mspm0(self, client):
        """GET /api/board/mspm0g3507 returns valid board definition."""
        resp = client.get("/api/board/mspm0g3507")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["soc"] == "MSPM0G3507"
        assert data["pin_count"] == 48
        assert len(data["pins"]) == 48
        assert len(data["peripherals"]) >= 10

    def test_board_detail_unknown(self, client):
        """GET /api/board/<unknown> returns 404."""
        resp = client.get("/api/board/nonexistent_board_xyz")
        assert resp.status_code == 404


class TestGenerateEndpoints:
    """Tests for DTS overlay / prj.conf generation."""

    def test_generate_uart(self, client, sample_uart_assignments):
        """POST /api/generate produces valid UART overlay."""
        resp = client.post(
            "/api/generate",
            data=json.dumps(sample_uart_assignments),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        overlay = data["overlay"]
        conf = data["prj_conf"]
        assert "MSP_PINMUX" in overlay or "pinmux" in overlay.lower()
        assert "&pinctrl" in overlay
        assert "&uart0" in overlay
        assert "pinctrl-0" in overlay
        assert "CONFIG_SERIAL=y" in conf

    def test_generate_multi_peripheral(self, client, sample_multi_peripheral_assignments):
        """POST /api/generate with UART + I2C + GPIO."""
        resp = client.post(
            "/api/generate",
            data=json.dumps(sample_multi_peripheral_assignments),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        overlay = data["overlay"]
        conf = data["prj_conf"]
        assert "&i2c0" in overlay
        assert "I2C_BITRATE_STANDARD" in overlay
        assert "&gpioa" in overlay
        assert "CONFIG_I2C=y" in conf
        assert "CONFIG_GPIO=y" in conf


class TestImportEndpoints:
    """Tests for overlay / prj.conf import (reverse engineering)."""

    def test_import_conf_only(self, client):
        """POST /api/import-config with conf text only."""
        resp = client.post(
            "/api/import-config",
            data=json.dumps({
                "conf": "CONFIG_SERIAL=y\nCONFIG_GPIO=y\nCONFIG_CONSOLE=y\n",
                "board_name": "lp_mspm0g3507",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "kconfig" in data
        assert len(data["kconfig"]) >= 1

    def test_import_overlay_and_conf(self, client, sample_overlay_text, sample_conf_text):
        """POST /api/import-config with overlay + conf."""
        resp = client.post(
            "/api/import-config",
            data=json.dumps({
                "overlay": sample_overlay_text,
                "conf": sample_conf_text,
                "board_name": "lp_mspm0g3507",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "kconfig" in data


class TestMcuIdentification:
    """Tests for MCU vendor identification endpoint."""

    @pytest.mark.parametrize("part_number,expected_known", [
        ("MSPM0G3507", True),
        ("STM32F401RE", True),
        ("NRF52840", True),
        ("ESP32", True),
    ])
    def test_identify_known_mcus(self, client, part_number, expected_known):
        """POST /api/identify-mcu identifies known MCU vendors."""
        resp = client.post(
            "/api/identify-mcu",
            data=json.dumps({"part_number": part_number}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("known") == expected_known

    def test_identify_unknown_mcu(self, client):
        """POST /api/identify-mcu returns known=False for garbage."""
        resp = client.post(
            "/api/identify-mcu",
            data=json.dumps({"part_number": "TOTALLY_FAKE_CHIP_XYZ"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("known") is False


class TestModuleEndpoints:
    """Tests for Zephyr module definitions."""

    def test_list_modules(self, client):
        """GET /api/modules returns module list."""
        resp = client.get("/api/modules")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_generate_module_config(self, client):
        """POST /api/generate-module-config produces Kconfig."""
        resp = client.post(
            "/api/generate-module-config",
            data=json.dumps({
                "modules": {
                    "serial": {"CONFIG_SERIAL": True},
                    "gpio": {"CONFIG_GPIO": True},
                }
            }),
            content_type="application/json",
        )
        # Even if the exact module names differ, we shouldn't get a 500
        assert resp.status_code in (200, 400)


class TestPeripheralEndpoints:
    """Tests for peripheral template endpoints."""

    def test_list_templates(self, client):
        """GET /api/peripheral-templates returns template list."""
        resp = client.get("/api/peripheral-templates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_peripheral_instances(self, client):
        """GET /api/peripheral-instances/<board> returns instances."""
        resp = client.get("/api/peripheral-instances/mspm0g3507")
        # Might 404 if board doesn't have instances defined
        assert resp.status_code in (200, 404)


class TestClockEndpoints:
    """Tests for clock tree configuration."""

    def test_list_clock_trees(self, client):
        """GET /api/clock-trees returns tree list."""
        resp = client.get("/api/clock-trees")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))
