# copy python_packages.pth to the actual python interpreter site-packages directory
import shutil
import pathlib
import sys
def install_dependencies():
    # Get the path to the current script
    current_script_path = pathlib.Path(__file__).parent

    # Define the source and destination paths
    source_path = current_script_path / "python_packages.pth"
    site_packages_path = pathlib.Path(sys.prefix) / "lib" / "python" / sys.version[:3] / "site-packages"

    # Copy the .pth file to the site-packages directory
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