@echo off
REM Launch Zephyr Pin Configurator
REM Uses the locator_base venv (which has Flask installed)

@REM set VENV=C:\GIT\WORK\codelayer\locator_base\.venv\Scripts\python.exe
@REM set APP=%~dp0run.py

@REM echo.
@REM echo Starting Zephyr Pin Configurator...
@REM echo.

@REM "%VENV%" "%APP%" --open %*


setlocal
set SCRIPT_DIR=%~dp0

if not exist "%SCRIPT_DIR%.venv" (
    echo [1/3] Creating virtual environment...
    python -m venv "%SCRIPT_DIR%.venv"
)

echo [2/3] Installing dependencies...
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
pip install -q -r "%SCRIPT_DIR%requirements.txt"

echo [3/3] Starting Baram-Web...
python "%SCRIPT_DIR%run.py" --open %*