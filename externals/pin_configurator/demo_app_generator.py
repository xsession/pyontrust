"""Generate a buildable Zephyr demo app from a normalized project document."""

from __future__ import annotations

import pathlib
import textwrap


def _write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _c_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _config_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").splitlines() if line.strip()]


def _merge_prj_conf(project: dict) -> str:
    required = [
        "CONFIG_CONSOLE=y",
        "CONFIG_GPIO=y",
        "CONFIG_PRINTK=y",
        "CONFIG_SERIAL=y",
        "CONFIG_UART_CONSOLE=y",
    ]
    merged: list[str] = []
    seen: set[str] = set()
    for line in [*_config_lines(project.get("generated_conf", "")), *required]:
        key = line.split("=", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        merged.append(line)
    return "\n".join(merged) + "\n"


def _enabled_peripherals(project: dict) -> list[str]:
    periph_states = project.get("periph_states") or {}
    return sorted(name for name, enabled in periph_states.items() if enabled)


def _selected_external_devices(project: dict) -> list[str]:
    devices = project.get("external_device_states") or {}
    return sorted(name for name, state in devices.items() if isinstance(state, dict) and state.get("selected"))


def _summary_header(project: dict) -> str:
    board_id = str(project.get("board_id") or "custom_board")
    enabled_peripherals = ", ".join(_enabled_peripherals(project)) or "none"
    selected_devices = ", ".join(_selected_external_devices(project)) or "none"
    pin_count = len(project.get("pin_states") or {})
    return textwrap.dedent(
        f"""\
        #pragma once

        #define PINCFG_DEMO_BOARD \"{_c_escape(board_id)}\"
        #define PINCFG_DEMO_PIN_COUNT {pin_count}
        #define PINCFG_DEMO_ENABLED_PERIPHERALS \"{_c_escape(enabled_peripherals)}\"
        #define PINCFG_DEMO_SELECTED_DEVICES \"{_c_escape(selected_devices)}\"
        """
    )


def _main_c() -> str:
    return textwrap.dedent(
        """\
        #include <zephyr/devicetree.h>
        #include <zephyr/drivers/gpio.h>
        #include <zephyr/kernel.h>
        #include <zephyr/sys/printk.h>

        #include \"generated_project_summary.h\"

        #define SLEEP_TIME_MS 1000
        #define LED0_NODE DT_ALIAS(led0)

        #if DT_NODE_HAS_STATUS(LED0_NODE, okay)
        static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED0_NODE, gpios);
        #endif

        int main(void)
        {
        	printk("Pin Configurator demo boot\\n");
        	printk("Board: %s\\n", PINCFG_DEMO_BOARD);
        	printk("Pins configured: %d\\n", PINCFG_DEMO_PIN_COUNT);
        	printk("Enabled peripherals: %s\\n", PINCFG_DEMO_ENABLED_PERIPHERALS);
        	printk("Selected external devices: %s\\n", PINCFG_DEMO_SELECTED_DEVICES);

        	#if DT_NODE_HAS_STATUS(LED0_NODE, okay)
        	if (!gpio_is_ready_dt(&led)) {
        		printk("LED0 not ready\\n");
        	} else if (gpio_pin_configure_dt(&led, GPIO_OUTPUT_ACTIVE) < 0) {
        		printk("LED0 configure failed\\n");
        	} else {
        		printk("LED0 ready\\n");
        	}
        	#else
        	printk("LED0 alias missing; running console-only blinky\\n");
        	#endif

        	while (1) {
        		#if DT_NODE_HAS_STATUS(LED0_NODE, okay)
        		gpio_pin_toggle_dt(&led);
        		#endif
        		printk("Blink\\n");
        		k_msleep(SLEEP_TIME_MS);
        	}

        	return 0;
        }
        """
    )


def _cmakelists() -> str:
    return textwrap.dedent(
        """\
        cmake_minimum_required(VERSION 3.20.0)

        find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
        project(pin_configurator_demo)

        target_sources(app PRIVATE src/main.c)
        target_include_directories(app PRIVATE include)

        include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/testbench.cmake)
        """
    )


def _resc(project: dict) -> str:
    renode = project.get("renode") or {}
    platform = renode.get("platform") or "platforms/boards/ti/lp_mspm0g3507.repl"
    uart = renode.get("uart") or "sysbus.uart0"
    board_id = project.get("board_id") or "custom_board"
    return textwrap.dedent(
        f"""\
        :name: Pin Configurator demo for {board_id}

        using sysbus
        mach create \"Pin Configurator demo\"

        machine LoadPlatformDescription @{platform}
        showAnalyzer {uart}

        macro reset
        \"\"\"
            sysbus LoadELF $bin
        \"\"\"

        runMacro $reset
        """
    )


def _sample_robot(project: dict) -> str:
    renode = project.get("renode") or {}
    uart = renode.get("uart") or "sysbus.uart0"
    boot_line = renode.get("boot_line") or "Pin Configurator demo boot"
    return textwrap.dedent(
        f"""\
        *** Settings ***
        Suite Setup                   Setup
        Suite Teardown                Teardown
        Test Setup                    Reset Emulation
        Test Teardown                 Test Teardown
        Resource                      ${{RENODEKEYWORDS}}

        *** Variables ***
        ${{APPLICATION_BINARY_DIR}}     %{{APPLICATION_BINARY_DIR}}
        ${{APPLICATION_SOURCE_DIR}}     %{{APPLICATION_SOURCE_DIR}}
        ${{BOARD}}                      %{{BOARD}}
        ${{UART}}                       {uart}

        *** Test Cases ***

        Firmware boots successfully
            Boot
            Wait For Line On Uart     {boot_line}    timeout=10

        Application prints configuration summary
            Boot
            Wait For Line On Uart     Enabled peripherals:    timeout=10

        *** Keywords ***

        Boot
            Execute Command           set bin @${{APPLICATION_BINARY_DIR}}/zephyr/zephyr.elf
            Execute Command           include @${{APPLICATION_SOURCE_DIR}}/boards/${{BOARD}}.resc
            Create Terminal Tester    ${{UART}}
            Start Emulation
        """
    )


def _demo_readme(project: dict) -> str:
    board_id = project.get("board_id") or "<board>"
    renode = project.get("renode") or {}
    appbench_target = renode.get("appbench_target") or "appbench"
    robot_target = renode.get("robot_target") or "robotbench"
    return textwrap.dedent(
        f"""\
        # Pin Configurator Demo App

        This app was materialized from a normalized Pin Configurator project document.

        It contains:
        - generated Zephyr overlay and `prj.conf`
        - a Zephyr-style blinky firmware entrypoint that also prints the collected configuration summary
        - a Renode appbench script in `boards/{board_id}.resc`
        - a RobotFramework smoke test in `sample.robot`
        - preserved generated source artifacts under `generated/`

        ## Build

        ```powershell
        west build -p auto -b {board_id} .
        ```

        ## Renode

        ```powershell
        west build -t {appbench_target}
        west build -t {robot_target}
        ```
        """
    )


def _generated_artifacts(project: dict) -> dict[str, str]:
    fragments = project.get("generated_fragments") or {}
    outputs: dict[str, str] = {}
    for group_name, entries in fragments.items():
        if not isinstance(entries, dict):
            continue
        for key, value in entries.items():
            text = str(value or "")
            if not text.strip():
                continue
            safe_group = str(group_name).replace("_", "-")
            safe_key = str(key).replace("_", "-")
            outputs[f"generated/{safe_group}-{safe_key}.txt"] = text
    outputs["generated/aggregated.overlay"] = str(project.get("generated_overlay") or "")
    outputs["generated/aggregated.prj.conf"] = str(project.get("generated_conf") or "")
    return outputs


def materialize_demo_app(project: dict, output_dir: pathlib.Path, *, testbench_cmake: str) -> dict:
    board_id = str(project.get("board_id") or "custom_board")
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "CMakeLists.txt": _cmakelists(),
        "prj.conf": _merge_prj_conf(project),
        "app.overlay": str(project.get("generated_overlay") or "/* No generated overlay available. */\n"),
        "src/main.c": _main_c(),
        "include/generated_project_summary.h": _summary_header(project),
        f"boards/{board_id}.resc": _resc(project),
        "sample.robot": _sample_robot(project),
        "README.md": _demo_readme(project),
        "cmake/testbench.cmake": testbench_cmake,
    }
    files.update(_generated_artifacts(project))

    for relative_path, content in files.items():
        _write_text(output_dir / relative_path, content)

    return {
        "output_dir": str(output_dir),
        "board_id": board_id,
        "files": sorted(files.keys()),
        "renode": project.get("renode") or {},
    }