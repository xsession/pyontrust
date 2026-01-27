"""Legacy GUI entrypoint.

This used to be a Tkinter GUI. The project now uses NiceGUI for long-term maintainability.

Run the NiceGUI app instead:

    python -m venv .venv-nicegui
    .\.venv-nicegui\Scripts\python -m pip install -U pip
    .\.venv-nicegui\Scripts\python -m pip install -r scripts\requirements.txt
    .\.venv-nicegui\Scripts\python -m pip install -e gui_app\nicegui_control
    .\.venv-nicegui\Scripts\python -m pyontrust_gui
"""

from pyontrust_gui.app import main


if __name__ == "__main__":
    main()
