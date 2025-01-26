import os
import subprocess
import shutil
from pathlib import Path


def build_installer(app_name="YourAppName", main_script="main.py", dist_folder="dist", build_folder="build"):
    # Define paths
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
        main_script,  # Main script to run the app
    ]

    # Step 3: Run PyInstaller
    print("[INFO] Building the installer...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
