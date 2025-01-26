import os
import shutil
import site
from pathlib import Path

def copy_pth_to_site_packages(source_pth_file):
    site_packages_dir = site.getsitepackages()[0]
    destination_path = os.path.join(site_packages_dir, os.path.basename(source_pth_file))
    try:
        shutil.copy(source_pth_file, destination_path)
        print(f"Successfully copied {source_pth_file} to {destination_path}")
    except Exception as e:
        print(f"Failed to copy {source_pth_file} to {destination_path}: {e}")

copy_pth_to_site_packages(f"{Path(__file__).parent}/../../scripts/python_packages.pth")

import eel
import greeting

# Initialize Eel with the 'web' folder
eel.init(f'{Path(__file__).parent}/web')


@eel.expose
def say_hello_py(name):
    print(f"Hello from Python, {name}!")
    return f"Hello, {name}! This message is from Python."


# Start the app
if __name__ == "__main__":
    eel.start('index.html', size=(400, 300))  # Launch the HTML file
