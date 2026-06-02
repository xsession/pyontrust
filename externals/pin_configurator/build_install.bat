@echo off
REM Build a packaged Zephyr Pin Configurator executable
setlocal
set SCRIPT_DIR=%~dp0
set VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
set VENV_PIP=%SCRIPT_DIR%.venv\Scripts\pip.exe

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
    if errorlevel 1 (
        echo [1/2] Installing PyInstaller into the local virtual environment...
        "%VENV_PIP%" install pyinstaller
        if errorlevel 1 (
            echo Failed to install PyInstaller into "%SCRIPT_DIR%.venv".
            exit /b 1
        )
    )
    echo [2/2] Building installer...
    "%VENV_PYTHON%" "%SCRIPT_DIR%build_install.py" %*
) else (
    echo Local virtual environment not found, falling back to system Python.
    python "%SCRIPT_DIR%build_install.py" %*
)

exit /b %ERRORLEVEL%
