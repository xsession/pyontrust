@echo off
:: ═══════════════════════════════════════════════════════════════
:: pyontrust Lab Bench — Quick Launcher
:: ═══════════════════════════════════════════════════════════════
title pyontrust Lab Bench
setlocal

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
echo   ╔══════════════════════════════════════════════════╗
echo   ║  pyontrust Lab Bench                            ║
echo   ║  http://%HOST%:%PORT%/                    ║
echo   ╚══════════════════════════════════════════════════╝
echo.

:: Try to open browser after a short delay
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start http://%HOST%:%PORT%/"

:: Run the gateway
python -m pyontrust.gateway.app --host %HOST% --port %PORT%

if %ERRORLEVEL% neq 0 (
    echo.
    echo   [ERROR] Gateway failed to start.
    echo   Make sure pyontrust is installed:  pip install -e ".[gui]"
    echo.
    pause
)
