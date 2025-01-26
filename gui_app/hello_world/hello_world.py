import os
import shutil
import site
from pathlib import Path
import sys

package_dir = os.getenv(
    'PYONTRUST_PACKAGE_DIR',
    os.path.join(Path(__file__).parent, "pyontrust_packages")
)
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
