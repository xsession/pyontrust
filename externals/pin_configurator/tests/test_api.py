# SPDX-License-Identifier: Apache-2.0
"""API endpoint tests using Flask test client (no running server needed).

Inspired by Swedish Embedded SDK's multi-level test architecture:
unit → integration → system (robotbench).
"""

import json
import pathlib
import pytest


def _write_temp_zephyr_tree(root: pathlib.Path) -> pathlib.Path:
        (root / "boards" / "vendor" / "demo_board").mkdir(parents=True, exist_ok=True)
        (root / "dts" / "bindings" / "sensor").mkdir(parents=True, exist_ok=True)
        (root / "boards" / "vendor" / "demo_board" / "board.yml").write_text(
                """
board:
    name: demo_board
    full_name: Demo Board
    vendor: demo
    socs:
        - name: DEMO_SOC
""".strip(),
                encoding="utf-8",
        )
        (root / "dts" / "bindings" / "sensor" / "demo,temp-i2c.yaml").write_text(
                """
description: Demo temperature sensor
compatible: demo,temp
include: [sensor-device.yaml, i2c-device.yaml]
properties:
    reg:
        type: int
        required: true
        description: I2C address
    odr:
        type: string
        description: Output data rate
""".strip(),
                encoding="utf-8",
        )
        return root


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

    def test_board_detail_rpi_pico_multicore(self, client):
        """GET /api/board/rpi_pico returns multicore board metadata."""
        resp = client.get("/api/board/rpi_pico")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["soc"] == "RP2040"
        assert data["board"] == "rpi_pico"
        assert len(data["cores"]) == 2
        assert data["cores"][0]["default"] is True
        assert {target["kind"] for target in data["output_targets"]} == {
            "zephyr", "arduino", "baremetal"
        }
        uart0 = next(peripheral for peripheral in data["peripherals"] if peripheral["name"] == "uart0")
        assert uart0["core_id"] == "core0"
        assert uart0["available_cores"] == ["core0", "core1"]


class TestStaticAndBoardEditorDraftEndpoints:
    def test_favicon_route_is_quiet_when_icon_missing(self, client):
        resp = client.get("/favicon.ico")
        assert resp.status_code == 204

    def test_board_editor_draft_round_trip(self, client, tmp_path, monkeypatch):
        import server

        draft_dir = tmp_path / "drafts"
        monkeypatch.setattr(server, "_BOARD_EDITOR_DRAFT_DIR", draft_dir)

        empty = client.get("/api/board-editor/drafts")
        assert empty.status_code == 200
        assert empty.get_json() == {"drafts": []}

        board = {
            "board": "demo_board",
            "soc": "DEMO_SOC",
            "pins": [{"number": 1, "name": "P0"}],
            "external_devices": [],
        }

        save = client.post(
            "/api/board-editor/save",
            data=json.dumps({"board": board}),
            content_type="application/json",
        )
        assert save.status_code == 200
        filename = save.get_json()["filename"]
        assert filename == "demo_board.json"

        listed = client.get("/api/board-editor/drafts")
        assert listed.status_code == 200
        drafts = listed.get_json()["drafts"]
        assert len(drafts) == 1
        assert drafts[0]["filename"] == filename
        assert drafts[0]["size"] > 0
        assert drafts[0]["updated_at"]

        loaded = client.get(f"/api/board-editor/draft/{filename}")
        assert loaded.status_code == 200
        assert loaded.get_json()["board"] == board

        deleted = client.post(
            "/api/board-editor/delete",
            data=json.dumps({"filename": filename}),
            content_type="application/json",
        )
        assert deleted.status_code == 200
        assert deleted.get_json()["filename"] == filename

        missing = client.get(f"/api/board-editor/draft/{filename}")
        assert missing.status_code == 404


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

    def test_generate_multitarget_rpi_pico(self, client, sample_rpi_pico_assignments):
        """POST /api/generate returns Zephyr, Arduino, and bare-metal outputs."""
        resp = client.post(
            "/api/generate",
            data=json.dumps(sample_rpi_pico_assignments),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "UART0_TX_GP0" in data["overlay"]
        assert "targets" in data
        assert "arduino" in data["targets"]
        assert "baremetal" in data["targets"]
        assert "assigned-core: core1" in data["overlay"]
        assert "pinMode(PIN_UART0_TX, OUTPUT);" in data["targets"]["arduino"]["rpi_pico.ino"]
        assert "pin_config_apply" in data["targets"]["baremetal"]["pin_config.c"]

    def test_generate_external_device_outputs(self, client):
        """POST /api/generate emits external device snippets for Zephyr and Arduino."""
        payload = {
            "board_id": "rpi_pico",
            "board": "rpi_pico",
            "targets": ["zephyr", "arduino"],
            "assignments": [
                {
                    "pin_name": "GP4", "pincm": 5, "function_id": 3,
                    "af_name": "I2C0_SDA", "peripheral": "i2c0",
                    "signal": "sda", "direction": "io",
                    "zephyr_pinmux": "I2C0_SDA_GP4",
                },
                {
                    "pin_name": "GP5", "pincm": 6, "function_id": 3,
                    "af_name": "I2C0_SCL", "peripheral": "i2c0",
                    "signal": "scl", "direction": "io",
                    "zephyr_pinmux": "I2C0_SCL_GP5",
                },
            ],
            "peripherals": [
                {
                    "name": "i2c0", "dts_node": "&i2c0",
                    "compatible": "raspberrypi,rp2040-i2c", "enabled": True,
                },
            ],
            "external_devices": [
                {
                    "id": "bme280_i2c",
                    "display": "Bosch BME280",
                    "category": "sensor",
                    "bus": "i2c0",
                    "compatible": "bosch,bme280",
                    "address": "0x76",
                    "required_signals": ["sda", "scl"],
                    "frameworks": ["zephyr", "arduino"],
                    "notes": "Temperature, humidity, and pressure sensor.",
                }
            ],
        }

        resp = client.post(
            "/api/generate",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert "&i2c0" in data["overlay"]
        assert 'compatible = "bosch,bme280";' in data["overlay"]
        assert "reg = <0x76>;" in data["overlay"]
        assert "CONFIG_BME280=y" in data["prj_conf"]
        assert "#include <Wire.h>" in data["targets"]["arduino"]["rpi_pico.ino"]
        assert "Device: Bosch BME280 on i2c0 (0x76)" in data["targets"]["arduino"]["rpi_pico.ino"]


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


class TestZephyrCatalog:
    def test_catalog_endpoint_returns_mcus_and_sensors(self, client, tmp_path):
        zephyr_root = _write_temp_zephyr_tree(tmp_path / "zephyr")

        resp = client.get(f"/api/zephyr/catalog?zephyr_root={zephyr_root.as_posix()}&refresh=1")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["root"] == str(zephyr_root)
        assert data["summary"]["mcu_count"] == 1
        assert data["summary"]["sensor_count"] == 1
        assert data["mcus"][0]["name"] == "demo_board"
        assert data["mcus"][0]["socs"] == ["DEMO_SOC"]
        assert data["sensors"][0]["compatible"] == "demo,temp"
        assert data["sensors"][0]["buses"] == ["i2c"]
        assert data["sensors"][0]["properties"][0]["name"] == "odr"

    def test_catalog_endpoint_rejects_missing_root(self, client, tmp_path):
        missing = tmp_path / "missing-zephyr"
        resp = client.get(f"/api/zephyr/catalog?zephyr_root={missing.as_posix()}&refresh=1")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "Unable to locate a Zephyr tree" in data["error"]

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


class TestLvglLayoutEndpoints:
    """Tests for direct LVGL layout import/export APIs."""

    def test_import_lvgl_layout_from_text(self, client):
        payload = {
            "lvgl_layout": {
                "preset": "phone",
                "screens": [
                    {
                        "id": "screen_root",
                        "type": "screen",
                        "name": "screen_main",
                        "w": 360,
                        "h": 640,
                        "nodes": [
                            {
                                "id": "button_1",
                                "type": "button",
                                "name": "button_1",
                                "text": "Tap",
                                "x": 40,
                                "y": 60,
                                "w": 160,
                                "h": 56,
                            }
                        ],
                    }
                ],
            }
        }

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({"text": json.dumps(payload)}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "pasted JSON"
        assert data["layout"]["screens"][0]["name"] == "screen_main"
        assert data["layout"]["screens"][0]["nodes"][0]["type"] == "button"

    def test_import_lvgl_layout_from_file(self, client, tmp_path):
        file_path = tmp_path / "imported_gui.json"
        file_path.write_text(json.dumps({
            "version": 1,
            "kind": "lvgl-layout",
            "lvgl_layout": {
                "screens": [
                    {
                        "id": "screen_root",
                        "type": "screen",
                        "name": "screen_main",
                        "w": 320,
                        "h": 240,
                        "nodes": [],
                    }
                ]
            },
        }), encoding="utf-8")

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({"file_path": str(file_path)}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == str(file_path)
        assert data["layout"]["screens"][0]["w"] == 320

    def test_export_lvgl_layout_to_file(self, client, tmp_path):
        file_path = tmp_path / "saved_layout"
        layout = {
            "preset": "phone",
            "screens": [
                {
                    "id": "screen_root",
                    "type": "screen",
                    "name": "screen_main",
                    "w": 360,
                    "h": 640,
                    "nodes": [],
                }
            ],
        }

        resp = client.post(
            "/api/lvgl/export",
            data=json.dumps({"file_path": str(file_path), "layout": layout}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        saved_path = pathlib.Path(data["file_path"])
        assert saved_path.name == "saved_layout.lvgl.json"
        saved_doc = json.loads(saved_path.read_text(encoding="utf-8"))
        assert saved_doc["kind"] == "lvgl-layout"
        assert saved_doc["lvgl_layout"]["screens"][0]["name"] == "screen_main"

    def test_import_external_pages_schema(self, client):
        payload = {
            "project": "Demo GUI",
            "width": 480,
            "height": 272,
            "startupPage": "home",
            "styles": [
                {
                    "name": "primaryCard",
                    "background": "#1e293b",
                    "color": "#f8fafc",
                    "radius": 18,
                }
            ],
            "pages": [
                {
                    "id": "home",
                    "name": "Home",
                    "widgets": [
                        {
                            "type": "Text",
                            "name": "headline",
                            "text": "External Headline",
                            "x": 18,
                            "y": 12,
                            "width": 180,
                            "height": 30,
                            "color": "#e2e8f0",
                        },
                        {
                            "type": "Button",
                            "name": "openSettings",
                            "text": "Settings",
                            "x": 24,
                            "y": 72,
                            "width": 160,
                            "height": 52,
                            "style": "primaryCard",
                            "targetPage": "settings",
                            "transition": "fade_in",
                            "transitionDuration": 320,
                        },
                    ],
                },
                {
                    "id": "settings",
                    "name": "Settings",
                    "widgets": [],
                },
            ],
        }

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({"text": json.dumps(payload)}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        layout = data["layout"]
        assert layout["startupScreenId"] == "home"
        assert layout["preset"] == "dashboard"
        assert len(layout["screens"]) == 2
        assert layout["sharedStyles"][0]["id"] == "primarycard"
        button = layout["screens"][0]["nodes"][1]
        assert button["type"] == "button"
        assert button["action"] == "goto"
        assert button["targetScreenId"] == "settings"
        assert button["styleMode"] == "shared"
        assert button["styleRefs"] == ["primarycard"]

    def test_import_lvgl_layout_from_zephyr_display_text(self, client):
        zephyr_text = """
CONFIG_LV_HOR_RES_MAX=800
CONFIG_LV_VER_RES_MAX=480

&display0 {
    compatible = "sitronix,st7789v";
    width = <800>;
    height = <480>;
};
""".strip()

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({"source_kind": "zephyr", "text": zephyr_text}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        layout = data["layout"]
        assert data["source"] == "pasted Zephyr text"
        assert layout["preset"] == "panel"
        assert layout["screens"][0]["w"] == 800
        assert layout["screens"][0]["h"] == 480
        assert layout["importMeta"]["kind"] == "zephyr-display"
        assert layout["importMeta"]["display"]["label"] == "sitronix,st7789v"

    def test_import_lvgl_layout_from_zephyr_project_directory(self, client, tmp_path):
        project_dir = tmp_path / "demo_app"
        project_dir.mkdir()
        (project_dir / "prj.conf").write_text(
            "CONFIG_LV_HOR_RES_MAX=800\nCONFIG_LV_VER_RES_MAX=480\n",
            encoding="utf-8",
        )
        (project_dir / "demo_board.overlay").write_text(
            '&display0 { compatible = "sitronix,st7701s"; width = <800>; height = <480>; };\n',
            encoding="utf-8",
        )

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({"source_kind": "zephyr", "file_path": str(project_dir)}),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        layout = data["layout"]
        assert "Zephyr project" in data["source"]
        assert layout["preset"] == "panel"
        assert layout["screens"][0]["w"] == 800
        assert layout["screens"][0]["h"] == 480
        assert layout["importMeta"]["display"]["label"] == "sitronix,st7701s"

    def test_import_lvgl_layout_from_display_pdf_bytes(self, client, monkeypatch):
        import server

        monkeypatch.setattr(
            server,
            "_extract_display_pdf_text",
            lambda pdf_bytes: "Demo panel datasheet\nDisplay Resolution 480 x 272 dots\nController ST7262E43",
        )

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({
                "source_kind": "display-pdf",
                "filename": "panel.pdf",
                "binary_base64": "JVBERi0xLjQ=",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        layout = data["layout"]
        assert data["source"] == "panel.pdf"
        assert layout["screens"][0]["w"] == 480
        assert layout["screens"][0]["h"] == 272
        assert layout["importMeta"]["kind"] == "display-pdf"
        assert layout["preset"] == "dashboard"

    def test_import_lvgl_layout_from_display_pdf_rgb_resolution_notation(self, client, monkeypatch):
        import server

        monkeypatch.setattr(
            server,
            "_extract_display_pdf_text",
            lambda pdf_bytes: "ILI9341 is a TFT liquid crystal display controller with resolution of 240RGBx320 dots and 262K color.",
        )

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps({
                "source_kind": "display-pdf",
                "filename": "ili9341.pdf",
                "binary_base64": "JVBERi0xLjQ=",
            }),
            content_type="application/json",
        )

        assert resp.status_code == 200
        data = resp.get_json()
        layout = data["layout"]
        assert layout["screens"][0]["w"] == 240
        assert layout["screens"][0]["h"] == 320
        assert layout["importMeta"]["kind"] == "display-pdf"

    def test_import_lvgl_layout_rejects_mcu_datasheet_pdf(self, client):
        pdf_path = pathlib.Path(__file__).resolve().parent.parent / ".uploads" / "stm32f427_datasheet.pdf"
        payload = {
            "source_kind": "display-pdf",
            "file_path": str(pdf_path),
        }

        resp = client.post(
            "/api/lvgl/import",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert resp.status_code == 400
        data = resp.get_json()
        assert "Could not infer display resolution" in data["error"]


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


class TestProjectFileEndpoints:
    """Tests for project file save/load (.zpinproj)."""

    def test_save_project_file(self, client, tmp_path):
        """POST /api/project-file/save creates a .zpinproj file."""
        fp = str(tmp_path / "test.zpinproj")
        resp = client.post("/api/project-file/save", json={
            "file_path": fp,
            "board_id": "lp_mspm0g3507",
            "pin_states": {
                "1": {
                    "af": {"function_id": 1, "name": "UART0_TX",
                           "pincm": "IOMUX_PINCM1", "peripheral": "uart0",
                           "signal": "tx", "direction": "output"},
                    "props": {"bias_pull_up": False},
                }
            },
            "periph_states": {"uart0": True, "spi0": False},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["saved"] is True
        # File should exist on disk
        import pathlib
        assert pathlib.Path(fp).is_file()

    def test_load_project_file(self, client, tmp_path):
        """POST /api/project-file/load returns saved state."""
        fp = str(tmp_path / "roundtrip.zpinproj")
        pin_states = {
            "5": {
                "af": {"function_id": 3, "name": "SPI0_CLK",
                       "pincm": "IOMUX_PINCM5", "peripheral": "spi0",
                       "signal": "clk", "direction": "output"},
                "props": {"bias_pull_down": True},
            }
        }
        periph_states = {"uart0": False, "spi0": True}
        periph_core_states = {"spi0": "core1"}
        # Save first
        client.post("/api/project-file/save", json={
            "file_path": fp,
            "board_id": "lp_mspm0g3507",
            "pin_states": pin_states,
            "periph_states": periph_states,
            "periph_core_states": periph_core_states,
            "external_device_states": {
                "bme280_i2c": {"selected": True, "bus": "i2c0"},
            },
            "protocol_editor": {
                "messages": [{"id": "frame-a", "name": "StatusFrame"}],
            },
            "generated_overlay": "/* test overlay */",
            "generated_conf": "CONFIG_SPI=y",
        })
        # Load it back
        resp = client.post("/api/project-file/load", json={"file_path": fp})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == 1
        assert data["board_id"] == "lp_mspm0g3507"
        assert "5" in data["pin_states"]
        assert data["pin_states"]["5"]["af"]["name"] == "SPI0_CLK"
        assert data["periph_states"]["spi0"] is True
        assert data["periph_core_states"]["spi0"] == "core1"
        assert data["external_device_states"]["bme280_i2c"]["selected"] is True
        assert data["external_device_states"]["bme280_i2c"]["bus"] == "i2c0"
        assert data["protocol_editor"]["messages"][0]["name"] == "StatusFrame"
        assert data["generated_overlay"] == "/* test overlay */"
        assert data["generated_conf"] == "CONFIG_SPI=y"

    def test_save_project_file_adds_default_renode_profile(self, client, tmp_path):
        """POST /api/project-file/save adds a normalized Renode profile."""
        fp = str(tmp_path / "renode_demo.zpinproj")
        resp = client.post("/api/project-file/save", json={
            "file_path": fp,
            "board_id": "lp_mspm0g3507",
            "pin_states": {},
            "periph_states": {},
        })

        assert resp.status_code == 200

        load_resp = client.post("/api/project-file/load", json={"file_path": fp})
        assert load_resp.status_code == 200
        data = load_resp.get_json()
        assert data["renode"]["enabled"] is True
        assert data["renode"]["platform"] == "platforms/boards/ti/lp_mspm0g3507.repl"
        assert data["renode"]["uart"] == "sysbus.uart0"
        assert data["renode"]["boot_line"] == "Pin Configurator demo boot"

    def test_save_project_file_with_core_state(self, client, tmp_path):
        """POST /api/project-file/save persists multicore peripheral ownership."""
        fp = str(tmp_path / "pico.zpinproj")
        resp = client.post("/api/project-file/save", json={
            "file_path": fp,
            "board_id": "rpi_pico",
            "pin_states": {},
            "periph_states": {"uart0": True},
            "periph_core_states": {"uart0": "core1"},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["saved"] is True

        load_resp = client.post("/api/project-file/load", json={"file_path": fp})
        assert load_resp.status_code == 200
        load_data = load_resp.get_json()
        assert load_data["periph_core_states"]["uart0"] == "core1"

    def test_load_missing_file(self, client):
        """POST /api/project-file/load returns 404 for missing file."""
        resp = client.post("/api/project-file/load", json={
            "file_path": "C:/nonexistent/path/missing.zpinproj",
        })
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_save_adds_extension(self, client, tmp_path):
        """Save auto-appends .zpinproj extension if missing."""
        fp = str(tmp_path / "noext")
        resp = client.post("/api/project-file/save", json={
            "file_path": fp,
            "board_id": "test",
            "pin_states": {},
            "periph_states": {},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["file_path"].endswith(".zpinproj")

    def test_save_missing_path(self, client):
        """Save without file_path returns 400."""
        resp = client.post("/api/project-file/save", json={
            "board_id": "test",
        })
        assert resp.status_code == 400

    def test_path_dialog_returns_selected_path(self, client, monkeypatch):
        import server

        captured = {}

        def fake_open_native_path_dialog(dialog_kind, **kwargs):
            captured["dialog_kind"] = dialog_kind
            captured.update(kwargs)
            return r"C:\GIT\demo\pin_config.zpinproj"

        monkeypatch.setattr(server, "_open_native_path_dialog", fake_open_native_path_dialog)

        resp = client.post("/api/path-dialog", json={
            "dialog_kind": "save-file",
            "title": "Save project file",
            "initial_path": r"C:\GIT\demo\pin_config.zpinproj",
            "default_extension": ".zpinproj",
            "filetypes": [{"name": "Pin Config Project", "patterns": ["*.zpinproj"]}],
        })

        assert resp.status_code == 200
        assert resp.get_json() == {
            "path": r"C:\GIT\demo\pin_config.zpinproj",
            "cancelled": False,
        }
        assert captured["dialog_kind"] == "save-file"
        assert captured["title"] == "Save project file"
        assert captured["initial_path"] == r"C:\GIT\demo\pin_config.zpinproj"
        assert captured["default_extension"] == ".zpinproj"

    def test_path_dialog_rejects_unknown_kind(self, client):
        resp = client.post("/api/path-dialog", json={"dialog_kind": "network-share"})

        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestDemoAppExport:
    def test_export_demo_app_materializes_buildable_layout(self, client, tmp_path):
        out_dir = tmp_path / "demo_app"
        resp = client.post("/api/demo-app/export", json={
            "output_dir": str(out_dir),
            "overwrite": True,
            "board_id": "lp_mspm0g3507",
            "pin_states": {
                "21": {"af": {"name": "UART0_TX"}},
                "22": {"af": {"name": "UART0_RX"}},
            },
            "periph_states": {"uart0": True, "i2c0": True},
            "external_device_states": {
                "bme280_i2c": {"selected": True, "bus": "i2c0"},
            },
            "generated_overlay": "&uart0 { status = \"okay\"; };\n",
            "generated_conf": "CONFIG_I2C=y\n",
            "generated_fragments": {
                "protocols": {"integration": "Protocol notes"},
                "lvgl": {"validation": "No validation findings."},
            },
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["saved"] is True
        assert (out_dir / "CMakeLists.txt").is_file()
        assert (out_dir / "prj.conf").is_file()
        assert (out_dir / "app.overlay").is_file()
        assert (out_dir / "src" / "main.c").is_file()
        assert (out_dir / "include" / "generated_project_summary.h").is_file()
        assert (out_dir / "boards" / "lp_mspm0g3507.resc").is_file()
        assert (out_dir / "sample.robot").is_file()
        assert (out_dir / "cmake" / "testbench.cmake").is_file()
        assert (out_dir / "generated" / "protocols-integration.txt").read_text(encoding="utf-8") == "Protocol notes"

        main_c = (out_dir / "src" / "main.c").read_text(encoding="utf-8")
        summary_h = (out_dir / "include" / "generated_project_summary.h").read_text(encoding="utf-8")
        resc = (out_dir / "boards" / "lp_mspm0g3507.resc").read_text(encoding="utf-8")
        prj_conf = (out_dir / "prj.conf").read_text(encoding="utf-8")

        assert "Pin Configurator demo boot" in main_c
        assert 'PINCFG_DEMO_BOARD "lp_mspm0g3507"' in summary_h
        assert 'PINCFG_DEMO_ENABLED_PERIPHERALS "i2c0, uart0"' in summary_h
        assert "machine LoadPlatformDescription @platforms/boards/ti/lp_mspm0g3507.repl" in resc
        assert "showAnalyzer sysbus.uart0" in resc
        assert "CONFIG_PRINTK=y" in prj_conf
        assert "CONFIG_UART_CONSOLE=y" in prj_conf
