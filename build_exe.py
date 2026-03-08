#!/usr/bin/env python
"""Build a standalone .exe for the pyontrust Lab Bench.

Usage::

    python build_exe.py           # build one-dir bundle (fast, recommended)
    python build_exe.py --onefile  # build single .exe (slower startup)

Output lands in  dist/pyontrust_lab_bench/  (or dist/pyontrust_lab_bench.exe).
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

_ROOT = pathlib.Path(__file__).resolve().parent
_SRC = _ROOT / "src"
_GATEWAY = _SRC / "pyontrust" / "gateway"
_WEB = _GATEWAY / "web"

# Icon — only use if it's a valid .ico file (header: 00 00 01 00)
_ICON = _WEB / "shell" / "favicon.ico"


def _icon_is_valid() -> bool:
    """Check the favicon is a real ICO (not a placeholder text file)."""
    try:
        with open(_ICON, "rb") as f:
            header = f.read(4)
        return header[:4] == b'\x00\x00\x01\x00'
    except Exception:
        return False


def _collect_web_data() -> list[str]:
    """Build --add-data flags for every web asset folder."""
    data: list[str] = []
    sep = ";"  # Windows path separator for PyInstaller
    for subdir in _WEB.iterdir():
        if subdir.is_dir():
            # Map:  <source_dir> → pyontrust/gateway/web/<name>
            dest = f"pyontrust/gateway/web/{subdir.name}"
            data.append(f"--add-data={subdir}{sep}{dest}")
    return data


def _collect_hidden_imports() -> list[str]:
    """Imports that PyInstaller cannot auto-detect."""
    return [
        "--hidden-import=pyontrust.gateway.app",
        "--hidden-import=pyontrust.gateway.blueprints.shell",
        "--hidden-import=pyontrust.gateway.blueprints.hil",
        "--hidden-import=pyontrust.gateway.blueprints.csv_plotter",
        "--hidden-import=pyontrust.gateway.blueprints.bench",
        "--hidden-import=pyontrust.gateway.blueprints.artifacts",
        "--hidden-import=pyontrust.gateway.blueprints.config",
        "--hidden-import=pyontrust.gateway.blueprints.flowlab",
        "--hidden-import=pyontrust.gateway.flowlab_engine",
        "--hidden-import=pyontrust.gateway.middleware",
        "--hidden-import=pyontrust.gateway.ws",
        "--hidden-import=pyontrust.services",
        "--hidden-import=pyontrust.services.artifact_service",
        "--hidden-import=pyontrust.services.bench_service",
        "--hidden-import=pyontrust.services.config_service",
        "--hidden-import=pyontrust.services.log_service",
        "--hidden-import=pyontrust.services.test_service",
        "--hidden-import=pyontrust.instruments",
        "--hidden-import=pyontrust.instruments.simulated",
        "--hidden-import=pyontrust.core",
        # Flask internals PyInstaller sometimes misses
        "--hidden-import=flask.json",
        "--hidden-import=jinja2",
        "--hidden-import=jinja2.ext",
        "--hidden-import=werkzeug",
        "--hidden-import=markupsafe",
        # Optional but useful if installed
        "--hidden-import=numpy",
        "--hidden-import=scipy",
        "--hidden-import=scipy.signal",
    ]


def build(*, onefile: bool = False) -> None:
    """Run PyInstaller to create the Lab Bench executable."""
    entry = str(_ROOT / "start_lab_bench.py")

    cmd: list[str] = [
        sys.executable, "-m", "PyInstaller",
        "--name=pyontrust_lab_bench",
        f"--distpath={_ROOT / 'dist'}",
        f"--workpath={_ROOT / 'build'}",
        f"--specpath={_ROOT / 'build'}",
        "--noconfirm",
        "--clean",
        "--console",  # keep console for logs; use --windowed for GUI-only
    ]

    if _icon_is_valid():
        cmd.append(f"--icon={_ICON}")

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Add all web assets
    cmd.extend(_collect_web_data())

    # Add hidden imports
    cmd.extend(_collect_hidden_imports())

    # Add the src directory to the Python path
    cmd.extend([
        f"--paths={_SRC}",
        f"--paths={_GATEWAY}",
    ])

    cmd.append(entry)

    print()
    print("  +------------------------------------------------------+")
    print("  |  Building pyontrust Lab Bench executable              |")
    print(f"  |  Mode: {'single .exe' if onefile else 'one-directory bundle':<45s}|")
    print("  +------------------------------------------------------+")
    print()
    print("  Command:")
    print(f"    {' '.join(cmd[:6])}")
    print(f"      ... +{len(cmd) - 6} flags")
    print()

    result = subprocess.run(cmd, cwd=str(_ROOT))

    if result.returncode == 0:
        if onefile:
            exe = _ROOT / "dist" / "pyontrust_lab_bench.exe"
        else:
            exe = _ROOT / "dist" / "pyontrust_lab_bench" / "pyontrust_lab_bench.exe"
        print()
        print("  [OK] Build succeeded!")
        print(f"  Output: {exe}")
        print()
        print("  Run it:")
        print(f"    {exe}")
        print(f"    {exe} --port 8080")
        print(f"    {exe} --no-browser")
        print()
    else:
        print()
        print("  [FAIL] Build FAILED -- check output above.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pyontrust Lab Bench .exe")
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Pack everything into a single .exe (slower startup, easier to distribute)",
    )
    args = parser.parse_args()
    build(onefile=args.onefile)


if __name__ == "__main__":
    main()
