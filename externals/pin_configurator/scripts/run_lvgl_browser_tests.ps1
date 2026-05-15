param(
    [string[]]$PytestArgs = @("tests/test_lvgl_browser_integration.py", "-v")
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& ".\.venv\Scripts\python.exe" -m pytest @PytestArgs