from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DOCS_DIR = REPO_ROOT / "interface_docs"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
if str(INTERFACE_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(INTERFACE_DOCS_DIR))


import generate  # noqa: E402


def _assert_matches_fixture(output_root: Path, fixture_root: Path) -> None:
    actual_files = sorted(
        str(path.relative_to(output_root)).replace("\\", "/")
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "driver.py" and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    fixture_files = sorted(
        str(path.relative_to(fixture_root)).replace("\\", "/")
        for path in fixture_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    assert actual_files == fixture_files

    for relative_path in fixture_files:
        actual = (output_root / relative_path).read_text(encoding="utf-8")
        expected = (fixture_root / relative_path).read_text(encoding="utf-8")
        assert actual == expected, relative_path


def _write_canopen_source(path: Path) -> None:
    path.write_text(
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
          doc: Board temperature
          unit: C
        status:
          mlx: 3211266
          flags: [read, write]
          type:
            format: uint
            size: 8
          doc: Device status
""".strip(),
        encoding="utf-8",
    )


def test_process_target_generates_gui_app_scaffold(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/gui/demo_dashboard",
            "format": "gui-app",
            "od_name": "DemoBoard",
            "app_name": "Demo Dashboard",
            "route_prefix": "/demo-dashboard",
            "port": 5410,
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "gui" / "demo_dashboard"
    assert sorted(
        str(path.relative_to(output_root)).replace("\\", "/")
        for path in output_root.rglob("*")
        if path.is_file()
    ) == [
        "README.md",
        "app_factory.py",
        "build_install.py",
        "driver.py",
        "main.py",
        "web/index.html",
    ]
    assert (output_root / "driver.py").exists()
    assert (output_root / "main.py").exists()
    assert (output_root / "app_factory.py").exists()
    assert (output_root / "build_install.py").exists()
    assert (output_root / "web" / "index.html").exists()
    assert "Demo Dashboard" in (output_root / "README.md").read_text(encoding="utf-8")
    assert "class DemoBoardOD" in (output_root / "driver.py").read_text(encoding="utf-8")
    assert "create_gateway_app" in (output_root / "app_factory.py").read_text(encoding="utf-8")
    assert "from pyontrust.build_install import AppBuilder" in (output_root / "build_install.py").read_text(encoding="utf-8")
    assert '__version__ = "0.1.0"' in (output_root / "main.py").read_text(encoding="utf-8")
    assert "/demo-dashboard/api/summary" in (output_root / "web" / "index.html").read_text(encoding="utf-8")
    _assert_matches_fixture(output_root, FIXTURES_DIR / "gui_app_demo")


def test_process_target_generates_test_sequence_scaffold(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/tests/demo_sequence",
            "format": "test-sequence",
            "od_name": "DemoBoard",
            "sequence_class_name": "DemoBoardSequence",
            "device_key": "demo_board",
            "device_label": "Demo Board",
            "hil_app_path": "samples/basic/blink",
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "tests" / "demo_sequence"
    assert sorted(
        str(path.relative_to(output_root)).replace("\\", "/")
        for path in output_root.rglob("*")
        if path.is_file()
    ) == [
        "README.md",
        "conftest.py",
        "driver.py",
        "pytest.ini",
        "sequence.py",
        "tests/test_hil_sequence.py",
        "tests/test_metadata.py",
    ]
    assert (output_root / "driver.py").exists()
    assert (output_root / "sequence.py").exists()
    assert (output_root / "conftest.py").exists()
    assert (output_root / "tests" / "test_metadata.py").exists()
    assert (output_root / "tests" / "test_hil_sequence.py").exists()
    assert "DemoBoardSequence" in (output_root / "sequence.py").read_text(encoding="utf-8")
    assert "HILTestFixture" in (output_root / "conftest.py").read_text(encoding="utf-8")
    _assert_matches_fixture(output_root, FIXTURES_DIR / "test_sequence_demo")


def test_scaffold_generation_loads_context_file_relative_to_batch_dir(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)
    context_path = tmp_path / "gui_context.json"
    context_path.write_text(
        json.dumps(
            {
                "app_name": "Context Driven App",
                "page_title": "Context Driven App Home",
                "route_prefix": "/context-driven",
                "api_prefix": "/context-driven/custom-api",
            }
        ),
        encoding="utf-8",
    )

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/gui/context_dashboard",
            "format": "gui-app",
            "od_name": "DemoBoard",
            "context_file": "gui_context.json",
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "gui" / "context_dashboard"
    assert "Context Driven App" in (output_root / "README.md").read_text(encoding="utf-8")
    html = (output_root / "web" / "index.html").read_text(encoding="utf-8")
    assert "Context Driven App Home" in html
    assert "/context-driven/custom-api/metadata" in html


def test_gui_scaffold_can_override_build_backend_version_and_icon(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/gui/demo_dashboard",
            "format": "gui-app",
            "od_name": "DemoBoard",
            "build_backend": "nuitka",
            "app_version": "1.2.3",
            "build_icon_path": "assets/demo.ico",
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "gui" / "demo_dashboard"
    build_helper = (output_root / "build_install.py").read_text(encoding="utf-8")
    assert 'backend="nuitka"' in build_helper
    assert 'icon_path=str("assets/demo.ico")' in build_helper
    assert '__version__ = "1.2.3"' in (output_root / "main.py").read_text(encoding="utf-8")


def test_gui_scaffold_emitted_build_helper_runs_in_dry_run_mode(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/gui/demo_dashboard",
            "format": "gui-app",
            "od_name": "DemoBoard",
            "app_name": "Demo Dashboard",
            "route_prefix": "/demo-dashboard",
            "port": 5410,
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "gui" / "demo_dashboard"
    env = os.environ.copy()
    env["PYONTRUST_BUILD_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, str(output_root / "build_install.py")],
        cwd=output_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout.strip())
    assert payload["backend"] == "pyinstaller"
    assert payload["command"][1:3] == ["-m", "PyInstaller"]
    assert any("web" in part for part in payload["command"])


def test_gui_scaffold_emitted_build_helper_passes_icon_path_to_backend(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/gui/demo_dashboard",
            "format": "gui-app",
            "od_name": "DemoBoard",
            "build_icon_path": "assets/demo.ico",
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "gui" / "demo_dashboard"
    env = os.environ.copy()
    env["PYONTRUST_BUILD_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, str(output_root / "build_install.py")],
        cwd=output_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout.strip())
    assert payload["backend"] == "pyinstaller"
    assert "--icon" in payload["command"]
    icon_index = payload["command"].index("--icon")
    assert payload["command"][icon_index + 1].endswith("assets\\demo.ico") or payload["command"][icon_index + 1].endswith("assets/demo.ico")


def test_gui_scaffold_emitted_build_helper_passes_icon_path_to_nuitka_backend(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "generated/gui/demo_dashboard",
            "format": "gui-app",
            "od_name": "DemoBoard",
            "build_backend": "nuitka",
            "build_icon_path": "assets/demo.ico",
        },
        tmp_path,
    )

    output_root = tmp_path / "generated" / "gui" / "demo_dashboard"
    env = os.environ.copy()
    env["PYONTRUST_BUILD_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, str(output_root / "build_install.py")],
        cwd=output_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout.strip())
    assert payload["backend"] == "nuitka"
    assert any(part.startswith("--windows-icon-from-ico=") for part in payload["command"])
    assert any(
        part.endswith("assets\\demo.ico") or part.endswith("assets/demo.ico")
        for part in payload["command"]
        if part.startswith("--windows-icon-from-ico=")
    )


def test_scaffold_generation_rejects_existing_output_without_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    _write_canopen_source(source_path)

    output_root = tmp_path / "generated" / "gui" / "demo_dashboard"
    output_root.mkdir(parents=True, exist_ok=True)

    try:
        generate.process_target(
            {
                "source": "demo.yaml",
                "output": "generated/gui/demo_dashboard",
                "format": "gui-app",
                "od_name": "DemoBoard",
            },
            tmp_path,
        )
    except FileExistsError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected gui-app generation to reject an existing output directory")