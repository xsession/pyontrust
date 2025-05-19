import os
import subprocess
import shutil


def build_installer():
    # Define paths
    app_name = "YourAppName"  # Replace with your app name
    main_script = "main.py"  # Replace with your main script
    dist_folder = "dist"
    build_folder = "build"
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
        "--windowed",  # Hide the console window (useful for GUI apps)
        f"--name={app_name}",  # Set the name of the executable
        "--add-data=web;web",  # Add your Eel web directory (adjust as needed)
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
    build_installer()
