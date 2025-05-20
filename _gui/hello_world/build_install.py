import os
import subprocess
import shutil
from pathlib import Path
import importlib.util

def get_version(version_file="version.py"):
    """
    Dynamically fetch the app version from a version file.
    Args:
        version_file (str): Path to the version file.
    Returns:
        str: The application version.
    """
    version_path = Path(__file__).parent / version_file
    if version_path.exists():
        spec = importlib.util.spec_from_file_location("version", version_path)
        version_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(version_module)
        return getattr(version_module, "__version__", "unknown")
    return "unknown"

def build_installer(app_name="YourAppName", main_script="main.py", dist_folder="dist", build_folder="build"):
    
    
    # Get version from version.py
    version = get_version(version_file=main_script)
    
    # Define paths
    app_name = f"{app_name}_v{version}"
    spec_file = f"{app_name}.spec"

    # Step 1: Clean previous builds
    print("[INFO] Cleaning up previous builds...")
    folders_to_clean = [dist_folder, build_folder, spec_file]
    for folder in folders_to_clean:
        if os.path.exists(folder):
            if os.path.isfile(folder):
                os.remove(folder)
            else:
                shutil.rmtree(folder)

    # Step 2: Generate the PyInstaller command
    print("[INFO] Generating the PyInstaller command...")
    cmd = [
        "pyinstaller",
        "--noconfirm",  # Automatically confirm overwrites
        "--onefile",  # Create a single executable
        # "--windowed",  # Hide the console window (useful for GUI apps)
        f"--name={app_name}",  # Set the name of the executable
        f"--add-data={Path(__file__).parent}/web;web",  # Add your Eel web directory (adjust as needed)
        f"--add-data={Path(__file__).parent.parent.parent}/pyontrust_packages;pyontrust_packages",  # Add your PyOnTrust packages
        # f"--debug=imports",  # Print debug information about imports
        main_script,  # Main script to run the app
    ]

    # Step 3: Run PyInstaller
    print("[INFO] Building the installer...")
    result = subprocess.run(cmd, text=True)

    # Step 4: Handle success or failure
    if result.returncode == 0:
        print("[SUCCESS] Build completed successfully.")
        print(f"[INFO] Executable is in: {os.path.join(dist_folder, app_name)}")
    else:
        print("[ERROR] Build failed.")
        print(result.stderr)

    # Optional: Add logic to package the build into an installer (e.g., using NSIS or Inno Setup)


if __name__ == "__main__":
    build_installer(app_name="HelloWorldApp", main_script=f"{Path(__file__).parent}/hello_world.py")
