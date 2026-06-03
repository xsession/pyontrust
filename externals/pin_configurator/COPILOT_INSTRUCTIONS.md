# Copilot Instructions For Pin Configurator

Use this file as a practical instruction sheet for GitHub Copilot, Copilot Chat,
or any similar coding assistant working in this folder.

## Goal

Help maintain and extend the Zephyr Pin Configurator as a Windows-friendly,
desktop-capable embedded tooling app with:

- a Flask backend
- a React frontend under `frontend/`
- a legacy static frontend under `web/`
- optional Electron desktop shell under `electron/`

## Priorities

1. Preserve working behavior before refactoring.
2. Prefer small targeted fixes over broad rewrites.
3. Keep Windows usability in mind.
4. Reuse existing project patterns instead of introducing parallel architectures.
5. Validate changes with targeted checks when possible.

## Key Project Areas

### Backend

- `server.py` is the main Flask backend.
- `run.py` launches the backend and browser flow.
- `boards/` contains board definitions and registry-driven data.
- Generated/export features depend on runtime folders like `demo/`, `testbench/`, and `frontend/dist`.

### Frontend

- `frontend/` is the modern React app served at `/app`.
- `web/` is the legacy frontend served at `/`.
- Do not assume the legacy UI is unused. Fixes may still be needed there.

### Desktop Shell

- `electron/` contains the Electron wrapper.
- `start_electron.bat` is the Windows desktop launcher.
- The Electron shell should feel native, but it should reuse the existing backend and `/app` frontend.

## Implementation Guidance

### When editing backend code

- Preserve route compatibility unless a change is intentional.
- Prefer explicit filesystem paths rooted from the current app folder.
- Keep startup behavior friendly on Windows consoles.
- Avoid adding dependencies unless they materially improve the workflow.

### When editing React frontend code

- Keep the app loadable from Flask under `/app`.
- Prefer simple state flow and stable rendering over clever abstractions.
- If tabs or dock content misrender, first check layout constraints, mounted state, and bundle routing.

### When editing legacy `web/main.js`

- Be careful: it is large, stateful, and still active.
- Fix runtime errors surgically.
- Preserve global state names used across the file.
- If a refactor is needed, isolate it instead of rewriting unrelated areas.

### When editing Electron code

- Start the Python backend in the background and wait for readiness before opening the window.
- Clean up child processes on exit.
- Prefer a secure BrowserWindow configuration:
  - `contextIsolation: true`
  - `nodeIntegration: false`
  - `sandbox: true`
- Open external URLs in the system browser, not inside the app.

## Windows Expectations

- Batch launchers should prefer `.venv\Scripts\python.exe` when available.
- Fallback to system `python` only if needed.
- Console encoding issues are common; avoid Unicode-only console output in launch scripts.
- Desktop launch flows should be one-command when possible.

## Build And Packaging Expectations

- `build_install.py` should keep using `pyontrust.build_install.AppBuilder`.
- `build_install.bat` should be easy to run from PowerShell or `cmd`.
- Include required runtime folders when packaging.
- Avoid breaking the existing Python packaging flow while adding Electron support.

## Suggested Validation

After changes, prefer a small targeted check such as:

- `python -m py_compile <file>.py`
- `node --check <file>.cjs`
- `npm run build` in `frontend/`
- launch script smoke checks when relevant

If a full runtime test cannot be done, say so clearly.

## Style

- Keep code readable and direct.
- Prefer ASCII in scripts and launchers.
- Add short comments only where the code is not obvious.
- Do not add noisy boilerplate.

## Avoid

- large speculative rewrites
- changing both legacy and React frontend architecture at once unless necessary
- destructive git commands
- hidden assumptions about Linux-only paths or tooling
- adding duplicate launch systems without a reason
