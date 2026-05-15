# SPDX-License-Identifier: Apache-2.0
"""Detailed tests for generated Zephyr artifacts, including optional compile validation."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest


_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
_DEMO_APP = _PKG_DIR / "demo" / "zephyr_compile_demo"


def _generate(client, payload: dict) -> dict:
    response = client.post(
        "/api/generate",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _mspm0_compile_payload() -> dict:
    return {
        "board": "lp_mspm0g3507",
        "board_id": "lp_mspm0g3507",
        "targets": ["zephyr"],
        "assignments": [
            {
                "pin_name": "PA10",
                "pincm": 21,
                "function_id": 2,
                "af_name": "UART0_TX",
                "peripheral": "uart0",
                "signal": "tx",
                "direction": "out",
            },
            {
                "pin_name": "PA11",
                "pincm": 22,
                "function_id": 2,
                "af_name": "UART0_RX",
                "peripheral": "uart0",
                "signal": "rx",
                "direction": "in",
                "input_enable": True,
                "bias_pull_up": True,
            },
            {
                "pin_name": "PA25",
                "pincm": 33,
                "function_id": 5,
                "af_name": "I2C0_SCL",
                "peripheral": "i2c0",
                "signal": "scl",
                "direction": "io",
                "drive_open_drain": True,
            },
            {
                "pin_name": "PA26",
                "pincm": 34,
                "function_id": 5,
                "af_name": "I2C0_SDA",
                "peripheral": "i2c0",
                "signal": "sda",
                "direction": "io",
                "drive_open_drain": True,
                "input_enable": True,
            },
        ],
        "peripherals": [
            {
                "name": "uart0",
                "dts_node": "&uart0",
                "compatible": "ti,mspm0-uart",
                "enabled": True,
            },
            {
                "name": "i2c0",
                "dts_node": "&i2c0",
                "compatible": "ti,mspm0-i2c",
                "enabled": True,
            },
            {
                "name": "gpioa",
                "dts_node": "&gpioa",
                "compatible": "ti,mspm0-gpio",
                "enabled": True,
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
                "frameworks": ["zephyr"],
                "notes": "Compile-validation sensor node.",
            }
        ],
    }


def _config_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def _zephyr_workspace() -> pathlib.Path:
    workspace = os.environ.get("PIN_CONFIGURATOR_ZEPHYR_WORKSPACE")
    if not workspace:
        pytest.skip("Set PIN_CONFIGURATOR_ZEPHYR_WORKSPACE to run the compile-backed Zephyr test")

    root = pathlib.Path(workspace).expanduser().resolve()
    for candidate in (root, *root.parents):
        if (candidate / ".west").exists():
            return candidate

    pytest.skip(f"Zephyr workspace not found at or above {root}")


class TestZephyrGeneratedArtifacts:
    def test_overlay_contains_real_pinctrl_nodes_and_bus_blocks(self, client):
        data = _generate(client, _mspm0_compile_payload())
        overlay = data["overlay"]

        assert "#include <zephyr/dt-bindings/pinctrl/mspm0-pinctrl.h>" in overlay
        assert "uart0_tx_pa10" in overlay
        assert "uart0_rx_pa11" in overlay
        assert "i2c0_scl_pa25" in overlay
        assert "i2c0_sda_pa26" in overlay
        assert "pinmux = <MSP_PINMUX(21,MSPM0_PIN_FUNCTION_2)>;" in overlay
        assert "pinmux = <MSP_PINMUX(33,MSPM0_PIN_FUNCTION_5)>;" in overlay
        assert '&uart0 {' in overlay
        assert '&i2c0 {' in overlay
        assert 'current-speed = <115200>;' in overlay
        assert 'clock-frequency = <I2C_BITRATE_STANDARD>;' in overlay
        assert 'pinctrl-0 = <&uart0_tx_pa10 &uart0_rx_pa11>;' in overlay
        assert 'pinctrl-0 = <&i2c0_scl_pa25 &i2c0_sda_pa26>;' in overlay

    def test_overlay_emits_requested_pin_flags_and_external_device(self, client):
        data = _generate(client, _mspm0_compile_payload())
        overlay = data["overlay"]

        assert overlay.count("input-enable;") >= 2
        assert "bias-pull-up;" in overlay
        assert overlay.count("drive-open-drain;") == 2
        assert 'compatible = "bosch,bme280";' in overlay
        assert 'reg = <0x76>;' in overlay
        assert 'label = "Bosch BME280";' in overlay
        assert "Compile-validation sensor node." in overlay

    def test_prj_conf_contains_deduplicated_required_symbols(self, client):
        data = _generate(client, _mspm0_compile_payload())
        conf_lines = _config_lines(data["prj_conf"])

        assert conf_lines == sorted(conf_lines)
        assert conf_lines.count("CONFIG_CLOCK_CONTROL=y") == 1
        assert conf_lines.count("CONFIG_GPIO=y") == 1
        assert conf_lines.count("CONFIG_I2C=y") == 1
        assert conf_lines.count("CONFIG_SERIAL=y") == 1
        assert conf_lines.count("CONFIG_UART_CONSOLE=y") == 1
        assert conf_lines.count("CONFIG_SENSOR=y") == 1
        assert conf_lines.count("CONFIG_BME280=y") == 1


@pytest.mark.slow
def test_generated_zephyr_artifacts_compile_for_mspm0_board(client, tmp_path):
    workspace = _zephyr_workspace()
    generated = _generate(client, _mspm0_compile_payload())
    app_dir = tmp_path / "zephyr_compile_demo"
    build_dir = tmp_path / "build"
    build_env = os.environ.copy()
    west_python_override = build_env.get("PIN_CONFIGURATOR_WEST_PYTHON", "").strip()
    cmake_python_override = build_env.get("PIN_CONFIGURATOR_CMAKE_PYTHON", "").strip()
    cmake_pythonpath_override = build_env.get("PIN_CONFIGURATOR_CMAKE_PYTHONPATH", "").strip()

    shutil.copytree(_DEMO_APP, app_dir)
    (app_dir / "app.overlay").write_text(generated["overlay"], encoding="utf-8")
    (app_dir / "prj.conf").write_text(generated["prj_conf"], encoding="utf-8")

    command = [
        os.environ.get("PIN_CONFIGURATOR_WEST", "west"),
        "build",
        "-p",
        "auto",
        "-b",
        "lp_mspm0g3507",
        "-s",
        str(app_dir),
        "-d",
        str(build_dir),
    ]
    cmake_args: list[str] = []
    if west_python_override:
        build_env["WEST_PYTHON"] = west_python_override
        cmake_args.append(f"-DWEST_PYTHON={west_python_override}")
    if cmake_python_override:
        cmake_args.append(f"-DPython3_EXECUTABLE={cmake_python_override}")
    if cmake_pythonpath_override:
        existing_pythonpath = build_env.get("PYTHONPATH", "")
        build_env["PYTHONPATH"] = (
            cmake_pythonpath_override
            if not existing_pythonpath
            else cmake_pythonpath_override + os.pathsep + existing_pythonpath
        )
    if cmake_args:
        command.extend(["--", *cmake_args])

    result = subprocess.run(
        command,
        cwd=workspace,
        env=build_env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "west build failed\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert (build_dir / "zephyr" / "zephyr.elf").is_file()