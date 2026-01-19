"""TestApp

########## ########## ##########

Commit hash: 23a0c8
Full commit hash: 23a0c803b68b0446ef4edc45b0f85754382912d6
Commit date: Mon Jan 19 10:07:35 2026 +0100
Branch: main
User name: Ivanyi Laszlo
User email: k9eqto@gmail.com
Logged-in user: Riko
        
This is a test application to demonstrate the use of docopt for command-line argument parsing.
Usage:
    test.py -h | --help
    test.py --version
    
Options:
    -h --help       Show this help message and exit.
    --version        Show version information and exit.

"""

import docopt
import os 

__version__ = "0.0.0"
__description__ = "Test App for testing purposes"

if __name__ == "__main__":
    print(__doc__)
    arguments = docopt.docopt(__doc__, version=__version__)
    print(arguments)

    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    print("Directory name:", script_dir)
    print("Hello world")
