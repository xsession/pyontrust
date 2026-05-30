@echo off
REM Launch Zephyr Pin Configurator
setlocal
set SCRIPT_DIR=%~dp0
set DEFAULT_PORT=4124
set PORT_ARG=
set VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
set VENV_PIP=%SCRIPT_DIR%.venv\Scripts\pip.exe

for %%I in (%*) do (
    if /I "%%~I"=="--port" set PORT_ARG=provided
)

if not exist "%SCRIPT_DIR%.venv" (
    echo [1/3] Creating virtual environment...
    python -m venv "%SCRIPT_DIR%.venv"
)

if not exist "%VENV_PYTHON%" (
    echo Virtual environment python not found at "%VENV_PYTHON%".
    exit /b 1
)

echo [2/3] Installing dependencies...
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment at "%SCRIPT_DIR%.venv".
    exit /b 1
)
"%VENV_PIP%" install -q -r "%SCRIPT_DIR%requirements.txt"
if errorlevel 1 (
    echo Failed to install Python dependencies.
    exit /b 1
)

echo [3/3] Starting Zephyr Pin Configurator...
if defined PORT_ARG (
    echo Launching with user-specified arguments: %*
    "%VENV_PYTHON%" "%SCRIPT_DIR%run.py" --open %*
) else (
    echo Launching on http://127.0.0.1:%DEFAULT_PORT% ...
    "%VENV_PYTHON%" "%SCRIPT_DIR%run.py" --port %DEFAULT_PORT% --open %*
)

