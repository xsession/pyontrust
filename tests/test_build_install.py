from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from pyontrust.build_install import AppBuilder


def test_get_version_reads_literal_without_importing_main_script(tmp_path: Path) -> None:
    main_script = tmp_path / "main.py"
    main_script.write_text(
        """
__version__ = "2.4.6"

import definitely_missing_module
""".strip(),
        encoding="utf-8",
    )

    builder = AppBuilder(app_name="Demo", main_script=str(main_script))

    assert builder.get_version() == "2.4.6"


def test_generate_pyinstaller_command_includes_dependency_dirs(tmp_path: Path) -> None:
    main_script = tmp_path / "main.py"
    main_script.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    web_dir = tmp_path / "web"
    web_dir.mkdir()

    builder = AppBuilder(
        app_name="DemoDashboard",
        main_script=str(main_script),
        build_folder=str(tmp_path / "build"),
        dist_folder=str(tmp_path / "dist"),
        backend="pyinstaller",
    )
    builder.dependency_dirs = [(str(web_dir), "web")]

    command = builder.generate_pyinstaller_command()

    assert command[:3] == [builder.pyinstaller_cmd[0], "-m", "PyInstaller"]
    assert "--add-data" in command
    add_data_index = command.index("--add-data")
    assert command[add_data_index + 1].endswith("web")
    assert command[-1] == str(main_script)


def test_generate_nuitka_command_includes_report_and_data_dirs(tmp_path: Path) -> None:
    main_script = tmp_path / "main.py"
    main_script.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    icon_path = tmp_path / "demo.ico"
    icon_path.write_text("icon", encoding="utf-8")

    builder = AppBuilder(
        app_name="DemoDashboard",
        main_script=str(main_script),
        build_folder=str(tmp_path / "build"),
        dist_folder=str(tmp_path / "dist"),
        backend="nuitka",
        icon_path=str(icon_path),
    )
    builder.dependency_dirs = [(str(assets_dir), "assets")]

    command = builder.generate_nuitka_command()

    assert command[:3] == [builder.nuitka_cmd[0], "-m", "nuitka"]
    assert any(item.startswith("--report=") for item in command)
    assert f"--windows-icon-from-ico={icon_path}" in command
    assert any(item.endswith("=assets") for item in command if item.startswith("--include-data-dir="))
    assert command[-1] == str(main_script)


def test_run_command_dry_run_prints_json_payload(tmp_path: Path, capsys) -> None:
    main_script = tmp_path / "main.py"
    main_script.write_text('__version__ = "0.1.0"\n', encoding="utf-8")

    builder = AppBuilder(app_name="DemoDashboard", main_script=str(main_script), backend="pyinstaller")
    builder.dry_run = True

    assert builder.build_installer() is True

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["backend"] == "pyinstaller"
    assert payload["command"][1:3] == ["-m", "PyInstaller"]


def test_run_command_dry_run_prints_nuitka_json_payload(tmp_path: Path, capsys) -> None:
    main_script = tmp_path / "main.py"
    main_script.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    icon_path = tmp_path / "demo.ico"
    icon_path.write_text("icon", encoding="utf-8")

    builder = AppBuilder(
        app_name="DemoDashboard",
        main_script=str(main_script),
        backend="nuitka",
        icon_path=str(icon_path),
    )
    builder.dry_run = True

    assert builder.build_installer() is True

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["backend"] == "nuitka"
    assert payload["command"][1:3] == ["-m", "nuitka"]
    assert f"--windows-icon-from-ico={icon_path}" in payload["command"]