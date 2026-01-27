# NiceGUI Instrument Control

NiceGUI replacement for the legacy GUIs:
- `gui_app/reflex_control` (Reflex)
- `gui_app/power_test_gui` (Tkinter)

## Dev run (recommended venv)

```powershell
Set-Location C:\GIT\pyontrust
python -m venv .venv-nicegui
.\.venv-nicegui\Scripts\python -m pip install -U pip
.\.venv-nicegui\Scripts\python -m pip install -r scripts\requirements.txt
.\.venv-nicegui\Scripts\python -m pip install -e gui_app\nicegui_control
.\.venv-nicegui\Scripts\python -m pyontrust_gui
```

NiceGUI will print the local URL (default `http://localhost:8080`).

## Optional ML (object detection)

If you enable **object detection** in the UI:
- If `ultralytics` is installed in the venv, it will be used.
- Otherwise, the UI can auto-bootstrap it (venv only).

Manual install:
```powershell
.\.venv-nicegui\Scripts\python -m pip install ultralytics
```

## Packaging (Briefcase)

From `gui_app/nicegui_control`:

```powershell
Set-Location C:\GIT\pyontrust\gui_app\nicegui_control
..\..\.venv-nicegui\Scripts\python -m pip install -U briefcase
..\..\.venv-nicegui\Scripts\briefcase create windows app
..\..\.venv-nicegui\Scripts\briefcase build windows app
..\..\.venv-nicegui\Scripts\briefcase package windows app -p msi
```

Notes:
- MSI creation depends on Windows toolchains; typically you will need Visual Studio Build Tools and the WiX Toolset installed.
- The Briefcase project includes `pyontrust_packages/` and `scripts/` as sources so the GUI can run without a separate repo checkout.
