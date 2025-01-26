import os
import shutil
import site
from pathlib import Path
import sys

# Check if running in a PyInstaller bundle
if hasattr(sys, '_MEIPASS'):
    # Running from a PyInstaller executable
    package_dir = os.path.join(sys._MEIPASS, "pyontrust_packages")
else:
    # Running locally
    package_dir = os.getenv(
        'PYONTRUST_PACKAGE_DIR',
        os.path.join(Path(__file__).parent.parent.parent, "pyontrust_packages")
    )

# Add the package directory to sys.path if not already included
if package_dir not in sys.path:
    sys.path.append(package_dir)

# Import required modules after updating sys.path
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
    g = greeting.Greeting()
    print(g.greet())
    eel.start('index.html', size=(400, 300))  # Launch the HTML file
