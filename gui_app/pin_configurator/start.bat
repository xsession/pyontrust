@echo off
REM Launch Zephyr Pin Configurator
REM Uses the locator_base venv (which has Flask installed)

set VENV=C:\GIT\WORK\codelayer\locator_base\.venv\Scripts\python.exe
set APP=%~dp0run.py

echo.
echo Starting Zephyr Pin Configurator...
echo.

"%VENV%" "%APP%" --open %*
