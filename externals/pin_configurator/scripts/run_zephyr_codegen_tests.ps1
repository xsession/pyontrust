# SPDX-License-Identifier: Apache-2.0

param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [string]$Python312Path = "",
    [string]$AppPythonPath = "",
    [string]$ZephyrEnvDir = "",
    [string[]]$PytestArgs = @("tests/test_zephyr_codegen.py", "-v"),
    [switch]$RecreateZephyrEnv,
    [switch]$RecreateAppEnv
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-ExecutablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseDir,

        [Parameter(Mandatory = $true)]
        [string[]]$RelativeCandidates
    )

    foreach ($candidate in $RelativeCandidates) {
        $fullPath = Join-Path $BaseDir $candidate
        if (Test-Path $fullPath) {
            return (Resolve-Path $fullPath).Path
        }
    }

    throw "Could not find executable under '$BaseDir'. Tried: $($RelativeCandidates -join ', ')"
}

function Convert-ToForwardSlashPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    return $PathValue.Replace("\", "/")
}

function Resolve-Python312 {
    param([string]$PreferredPath)

    if ($PreferredPath) {
        if (-not (Test-Path $PreferredPath)) {
            throw "Python 3.12 path does not exist: $PreferredPath"
        }
        return (Resolve-Path $PreferredPath).Path
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $resolved = & $pyLauncher.Source -3.12 -c "import sys; print(sys.executable)"
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                return $resolved.Trim()
            }
        }
        catch {
        }
    }

    foreach ($candidate in @("python3.12", "python")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        try {
            $version = & $command.Source -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"
            if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq "3.12") {
                $resolved = & $command.Source -c "import sys; print(sys.executable)"
                if ($LASTEXITCODE -eq 0 -and $resolved) {
                    return $resolved.Trim()
                }
            }
        }
        catch {
        }
    }

    throw "Unable to locate a Python 3.12 interpreter. Pass -Python312Path explicitly."
}

function Resolve-AppPython {
    param([string]$PreferredPath)

    if ($PreferredPath) {
        if (-not (Test-Path $PreferredPath)) {
            throw "Application Python path does not exist: $PreferredPath"
        }
        return (Resolve-Path $PreferredPath).Path
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($version in @("3.12", "3.11", "3.10")) {
            try {
                $resolved = & $pyLauncher.Source -$version -c "import sys; print(sys.executable)"
                if ($LASTEXITCODE -eq 0 -and $resolved) {
                    return $resolved.Trim()
                }
            }
            catch {
            }
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Unable to locate a Python interpreter for the pin configurator test venv. Pass -AppPythonPath explicitly."
}

function Ensure-Venv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,

        [Parameter(Mandatory = $true)]
        [string]$VenvDir,

        [switch]$Recreate
    )

    if ($Recreate -and (Test-Path $VenvDir)) {
        Remove-Item $VenvDir -Recurse -Force
    }

    if (-not (Test-Path $VenvDir)) {
        & $PythonExe -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment at $VenvDir"
        }
    }
}

function Install-Packages {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,

        [Parameter(Mandatory = $true)]
        [string[]]$Packages
    )

    & $PythonExe -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip tooling for $PythonExe"
    }

    & $PythonExe -m pip install @Packages
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install packages for $PythonExe"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$requirementsFile = Join-Path $projectRoot "requirements.txt"
$workspacePath = (Resolve-Path $Workspace).Path

$workspaceRoot = $null
$probe = [System.IO.DirectoryInfo]::new($workspacePath)
while ($probe) {
    if (Test-Path (Join-Path $probe.FullName ".west")) {
        $workspaceRoot = $probe.FullName
        break
    }
    $probe = $probe.Parent
}

if (-not $workspaceRoot) {
    throw "No west workspace found at or above '$workspacePath'."
}

$appVenvDir = Join-Path $projectRoot ".venv"
$resolvedAppPython = Resolve-AppPython -PreferredPath $AppPythonPath
Ensure-Venv -PythonExe $resolvedAppPython -VenvDir $appVenvDir -Recreate:$RecreateAppEnv
$appVenvPython = Resolve-ExecutablePath -BaseDir $appVenvDir -RelativeCandidates @(
    "Scripts/python.exe",
    "bin/python.exe",
    "bin/python"
)
Install-Packages -PythonExe $appVenvPython -Packages @("-r", $requirementsFile)

$resolvedPython312 = Resolve-Python312 -PreferredPath $Python312Path
if (-not $ZephyrEnvDir) {
    $ZephyrEnvDir = Join-Path $env:LOCALAPPDATA "Pyontrust\pinconfig-zephyr-test-py312"
}
if (-not (Test-Path (Split-Path $ZephyrEnvDir -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $ZephyrEnvDir -Parent) -Force | Out-Null
}
Ensure-Venv -PythonExe $resolvedPython312 -VenvDir $ZephyrEnvDir -Recreate:$RecreateZephyrEnv
$zephyrPython = Resolve-ExecutablePath -BaseDir $ZephyrEnvDir -RelativeCandidates @(
    "Scripts/python.exe",
    "bin/python.exe",
    "bin/python"
)

Install-Packages -PythonExe $zephyrPython -Packages @(
    "west",
    "pyelftools",
    "PyYAML",
    "pykwalify",
    "jsonschema==4.17.3",
    "requests",
    "semver",
    "tqdm",
    "anytree",
    "intelhex",
    "pyserial",
    "patool",
    "colorama",
    "python-dateutil",
    "docopt",
    "ruamel.yaml"
)
$zephyrWest = Resolve-ExecutablePath -BaseDir $ZephyrEnvDir -RelativeCandidates @(
    "Scripts/west.exe",
    "bin/west.exe",
    "bin/west"
)

$env:PIN_CONFIGURATOR_ZEPHYR_WORKSPACE = Convert-ToForwardSlashPath $workspacePath
$env:PIN_CONFIGURATOR_WEST = Convert-ToForwardSlashPath $zephyrWest
$env:PIN_CONFIGURATOR_WEST_PYTHON = Convert-ToForwardSlashPath $zephyrPython
$env:PIN_CONFIGURATOR_CMAKE_PYTHON = Convert-ToForwardSlashPath $zephyrPython
if (Test-Path Env:PIN_CONFIGURATOR_CMAKE_PYTHONPATH) {
    Remove-Item Env:PIN_CONFIGURATOR_CMAKE_PYTHONPATH
}

Push-Location $projectRoot
try {
    & $appVenvPython -m pytest @PytestArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}