@echo off
:: ===============================================================
:: pyontrust Lab Bench - Quick Launcher
:: ===============================================================
title pyontrust Lab Bench
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

:: Ensure local source tree is importable even when package is not installed.
if defined PYTHONPATH (
    set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%SCRIPT_DIR%src"
)

set "PYTHON_EXE=python"
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"

set PORT=5200
set HOST=127.0.0.1

:: Parse optional arguments
:parse_args
if "%~1"=="" goto :start
if /i "%~1"=="--port" (set PORT=%~2& shift& shift& goto :parse_args)
if /i "%~1"=="--host" (set HOST=%~2& shift& shift& goto :parse_args)
shift
goto :parse_args

:start
echo.
echo   +--------------------------------------------------+
echo   ^|  pyontrust Lab Bench                             ^|
echo   ^|  http://%HOST%:%PORT%/^|
echo   +--------------------------------------------------+
echo.

:: Try to open browser after a short delay
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start http://%HOST%:%PORT%/"

:: Run the gateway
"%PYTHON_EXE%" -m pyontrust.gateway.app --host %HOST% --port %PORT%

if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Gateway failed to start.
    echo   Install GUI dependencies if needed:
    echo     "%PYTHON_EXE%" -m pip install -e ".[gui]"
    echo.
    pause
)

popd
