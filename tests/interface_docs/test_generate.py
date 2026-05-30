from __future__ import annotations

import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DOCS_DIR = REPO_ROOT / "interface_docs"
if str(INTERFACE_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(INTERFACE_DOCS_DIR))


import generate  # noqa: E402


def test_process_target_generates_python_output(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text(
        """
interface:
  title: Demo Interface
  transport: canopen
  canopen:
    object dictionary:
      sensors:
        temperature:
          mlx: 3211265
          flags: [read]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/py/demo_driver.py",
            "format": "python",
            "od_name": "DemoBoard",
        },
        tmp_path,
    )

    output_path = tmp_path / "generated" / "py" / "demo_driver.py"
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Demo Interface" in content
    assert "class DemoBoard" in content


def test_process_target_skips_unknown_formats(tmp_path: Path, caplog) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text("interface: {}\n", encoding="utf-8")

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/unknown.out",
            "format": "does-not-exist",
        },
        tmp_path,
    )

    assert not (tmp_path / "generated" / "unknown.out").exists()
    assert "Unknown format" in caplog.text


def test_process_target_can_generate_python_package_init(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text(
        """
interface:
  title: Demo Interface
  transport: canopen
  canopen:
    object dictionary:
      sensors:
        temperature:
          mlx: 3211265
          flags: [read]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/py/demo_driver.py",
            "format": "python",
            "od_name": "DemoBoard",
            "generate_init": True,
        },
        tmp_path,
    )

    init_path = tmp_path / "generated" / "py" / "__init__.py"
    assert init_path.exists()
    assert init_path.read_text(encoding="utf-8") == "from .demo_driver import *\n"


def test_process_target_can_write_debug_output(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text(
        """
interface:
  title: Demo Interface
  transport: canopen
  canopen:
    object dictionary:
      sensors:
        temperature:
          mlx: 3211265
          flags: [read]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/py/demo_driver.py",
            "debug": "generated/debug/demo_driver.json",
            "format": "python",
            "od_name": "DemoBoard",
        },
        tmp_path,
    )

    debug_path = tmp_path / "generated" / "debug" / "demo_driver.json"
    assert debug_path.exists()
    assert '"format": "python"' in debug_path.read_text(encoding="utf-8")


def test_process_target_keeps_existing_python_package_init(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text(
        """
interface:
  title: Demo Interface
  transport: canopen
  canopen:
    object dictionary:
      sensors:
        temperature:
          mlx: 3211265
          flags: [read]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )
    init_path = tmp_path / "generated" / "py" / "__init__.py"
    init_path.parent.mkdir(parents=True, exist_ok=True)
    init_path.write_text("from .legacy import *\n", encoding="utf-8")

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/py/demo_driver.py",
            "format": "python",
            "od_name": "DemoBoard",
            "generate_init": True,
        },
        tmp_path,
    )

    assert init_path.read_text(encoding="utf-8") == "from .legacy import *\n"


def test_validate_target_rejects_missing_dependency(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text("interface: {}\n", encoding="utf-8")

    try:
        generate.validate_target(
            {
                "source": "demo.yaml",
                "output": "generated/out.py",
                "format": "python",
                "dependencies": ["missing.yaml"],
            },
            tmp_path,
        )
    except FileNotFoundError as exc:
        assert "missing.yaml" in str(exc)
    else:
        raise AssertionError("validate_target did not reject a missing dependency")


def test_register_formats_share_single_handler() -> None:
    register_handler = generate.FORMAT_HANDLERS["c-uart-protocol"]
    assert generate.FORMAT_HANDLERS["c-modbus-registers"] is register_handler
    assert generate.FORMAT_HANDLERS["c-i2c-registers"] is register_handler
    assert generate.FORMAT_HANDLERS["c-spi-devices"] is register_handler
    assert generate.FORMAT_HANDLERS["c-tcp-protocol"] is register_handler


def test_main_can_smoke_generate_python_targets_from_copied_batch_manifest(tmp_path: Path, monkeypatch) -> None:
    manifest_source = INTERFACE_DOCS_DIR / "mp.yaml"
    manifest_copy = tmp_path / "mp.yaml"
    manifest_copy.write_text(manifest_source.read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copytree(INTERFACE_DOCS_DIR / "locator_base", tmp_path / "locator_base")

    monkeypatch.setattr(
        sys,
        "argv",
        ["generate.py", str(manifest_copy), "--format", "python"],
    )

    generate.main()

    generated_dir = tmp_path / "generated" / "py"
    assert (generated_dir / "canopen_driver.py").exists()
    assert (generated_dir / "uart_driver.py").exists()
    assert (generated_dir / "rs485_driver.py").exists()
    assert (generated_dir / "tcp_udp_driver.py").exists()
    assert (generated_dir / "i2c_driver.py").exists()
    assert (generated_dir / "spi_driver.py").exists()
    assert "class LocatorBaseOD:" in (generated_dir / "canopen_driver.py").read_text(encoding="utf-8")
    assert "class LocatorBaseUARTDriver:" in (generated_dir / "uart_driver.py").read_text(encoding="utf-8")