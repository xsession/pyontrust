@echo off
REM Launch the Zephyr Pin Configurator inside an Electron desktop shell
setlocal
set SCRIPT_DIR=%~dp0
set ELECTRON_DIR=%SCRIPT_DIR%electron

if not exist "%ELECTRON_DIR%\package.json" (
    echo Electron shell package not found at "%ELECTRON_DIR%".
    exit /b 1
)

if not exist "%ELECTRON_DIR%\node_modules\electron\package.json" (
    echo [1/2] Installing Electron desktop shell dependencies...
    pushd "%ELECTRON_DIR%"
    call npm install
    if errorlevel 1 (
        popd
        echo Failed to install Electron dependencies.
        exit /b 1
    )
    popd
)

echo [2/2] Starting Electron desktop shell...
pushd "%ELECTRON_DIR%"
call npm start
set EXIT_CODE=%ERRORLEVEL%
popd
exit /b %EXIT_CODE%
