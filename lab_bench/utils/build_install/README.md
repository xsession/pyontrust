# build_install (Nuitka)

This folder contains helpers to build Windows executables from the Python apps in this repo.

## Prerequisites

- Python (CPython)
- A C/C++ toolchain for Nuitka (Windows):
  - Visual Studio 2022 Build Tools (recommended), or
  - another supported compiler as per Nuitka docs.

## Install build dependency

```powershell
python -m pip install nuitka
```

## Usage

`build_install_.py` builds a **onefile** executable via `python -m nuitka`.

- By default it writes into a timestamped folder under this directory.
- `hide_console=True` maps to `--windows-console-mode=disable`.
- `dependency_dirs` entries are included using Nuitka data-file options.

If a build fails due to missing imports or data files, enable `debug_info=True` to get a Nuitka XML report in the build directory.
