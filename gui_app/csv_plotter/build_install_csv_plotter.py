import os
from pathlib import Path

import os
import sys
from pathlib import Path
import subprocess

# Check if running in a PyInstaller bundle
if hasattr(sys, '_MEIPASS'):
    # Running from a PyInstaller executable
    package_dir = os.path.join(sys._MEIPASS, "mediso_packages")
else:
    # Running locally
    if "MEDISO_PACKAGE_DIR" not in os.environ or not os.path.isdir(os.environ["MEDISO_PACKAGE_DIR"]):
        os.environ["MEDISO_PACKAGE_DIR"] = os.path.join(Path(__file__).parent.parent.parent, "mediso_packages")
    package_dir = os.environ["MEDISO_PACKAGE_DIR"]
    print(f'Mediso_packages_path: {package_dir}')

# Add the package directory to sys.path if not already included
if package_dir not in sys.path:
    sys.path.insert(0,package_dir)

import build_install

if __name__ == "__main__":
    app_builder = build_install.AppBuilder(app_name="CSV_Plotter",
                                           build_folder=str(Path(__file__).parent.joinpath("build")),
                                           dist_folder=str(Path(__file__).parent.joinpath("dist")), 
                                           main_script=str(Path(__file__).parent.joinpath("csv_plotter.py")))
    app_builder.dependency_dirs = [
        (os.path.join(Path(__file__).parent.parent.parent, "mediso_packages"), "mediso_packages"),
        (os.path.join(Path(__file__).parent, "core"), "core"),
        (os.path.join(Path(__file__).parent, "persistence"), "persistence"),
        (os.path.join(Path(__file__).parent, "plots"), "plots"),
        (os.path.join(Path(__file__).parent, "ui"), "ui"),
        (os.path.join(Path(__file__).parent, "data.py"), "."),
        (os.path.join(Path(__file__).parent, "lang.py"), "."),
        (os.path.join(Path(__file__).parent, "metrics.py"), "."),
        # (os.path.join(Path(__file__).parent, "layout.json"), "."),
        (os.path.join(Path(__file__).parent, "strings.json"), ".")
    ]
    app_builder.build_installer()
    