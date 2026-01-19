"""Install repo-local deps into the current interpreter.

- Copies `python_packages.pth` into site-packages
- Installs `requirements.txt`

This needs to work on both Windows and Linux.
"""

import pathlib
import shutil
import sys
import sysconfig


def _site_packages_dir() -> pathlib.Path:
    # Cross-platform: sysconfig knows the active interpreter layout.
    purelib = sysconfig.get_paths().get("purelib")
    if purelib:
        return pathlib.Path(purelib)

    # Fallbacks (older/odd environments)
    try:
        import site

        for p in site.getsitepackages():
            return pathlib.Path(p)
    except Exception:
        pass

    # Last resort: common layout.
    return pathlib.Path(sys.prefix) / "lib" / "python" / sys.version[:3] / "site-packages"


def install_dependencies() -> None:
    current_script_path = pathlib.Path(__file__).parent

    source_path = current_script_path / "python_packages.pth"
    site_packages_path = _site_packages_dir()
    site_packages_path.mkdir(parents=True, exist_ok=True)

    shutil.copy(source_path, site_packages_path)
    print(f"Copied {source_path} to {site_packages_path}")
    
# install requirements.txt
def install_requirements():
    import subprocess
    import sys

    # Get the path to the current script
    current_script_path = pathlib.Path(__file__).parent

    # Define the path to requirements.txt
    requirements_path = current_script_path / "requirements.txt"

    # Install the requirements using pip
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_path)])
    print(f"Installed requirements from {requirements_path}")   