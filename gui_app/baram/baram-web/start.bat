@echo off
REM ── Baram-Web Quick Start (Windows) ──────────────────────────────────
REM This script creates a venv, installs deps, and launches the server.

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
