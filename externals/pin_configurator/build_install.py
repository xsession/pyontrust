from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pyontrust.build_install import AppBuilder


if __name__ == "__main__":
    app_root = Path(__file__).parent
    app_builder = AppBuilder(
        app_name="Zephyr Pin Configurator",
        app_path=str(app_root),
        build_folder=str(app_root / "build"),
        dist_folder=str(app_root / "dist"),
        main_script=str(app_root / "run.py"),
        backend="pyinstaller",
    )
    app_builder.dependency_dirs = [
        (str(app_root / "web"), "web"),
        (str(app_root / "frontend" / "dist"), "frontend/dist"),
        (str(app_root / "boards"), "boards"),
        (str(app_root / "testbench"), "testbench"),
        (str(app_root / "demo"), "demo"),
    ]
    app_builder.build_installer()
