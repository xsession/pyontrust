from __future__ import annotations

from pathlib import Path

from pyontrust.build_install import AppBuilder


if __name__ == "__main__":
    app_root = Path(__file__).parent
    app_builder = AppBuilder(
        app_name="Demo Dashboard",
        build_folder=str(app_root / "build"),
        dist_folder=str(app_root / "dist"),
        main_script=str(app_root / "main.py"),
        backend="pyinstaller",
    )
    app_builder.dependency_dirs = [
        (str(app_root / "web"), "web"),
    ]
    app_builder.build_installer()