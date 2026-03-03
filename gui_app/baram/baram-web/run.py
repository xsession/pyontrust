#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BaramFlow Web — CLI entry point.

Usage:
    python run.py                       # default port 5100
    python run.py --port 8080 --open    # custom port + auto-open browser
    python run.py --debug               # Flask hot-reload
    python run.py --project /path/to/my.bf  # auto-open project on start
"""

import argparse
import logging
import sys
import types
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# PySide6 shim — must run BEFORE any baramFlow import
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_BARAM_ROOT = _HERE.parent
_SHIM_DIR = _HERE / "_pyside6_shim"

# Ensure baram root and shim are on sys.path
for _p in (str(_BARAM_ROOT), str(_SHIM_DIR), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import PySide6  # noqa: already installed → use it
except ImportError:
    import _pyside6_shim
    sys.modules["PySide6"] = _pyside6_shim
    _qtcore = types.ModuleType("PySide6.QtCore")
    for _a in ("QCoreApplication", "QObject", "QLocale", "QRect", "Signal"):
        setattr(_qtcore, _a, getattr(_pyside6_shim, _a))
    _qtcore.qRegisterResourceData = _pyside6_shim._QtCore.qRegisterResourceData
    _qtcore.qUnregisterResourceData = _pyside6_shim._QtCore.qUnregisterResourceData
    sys.modules["PySide6.QtCore"] = _qtcore
    logging.getLogger("baram-web").info("PySide6 shim installed (headless mode)")


def main():
    parser = argparse.ArgumentParser(
        description="BaramFlow Web — browser-based CFD case setup & solver control",
    )
    parser.add_argument("--port", type=int, default=5100, help="HTTP port (default 5100)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug/hot-reload")
    parser.add_argument("--open", action="store_true", help="Open browser on start")
    parser.add_argument(
        "--project", type=str, default=None,
        help="Auto-open this project directory on start",
    )
    args = parser.parse_args()

    # Optionally pre-load a project into the global ProjectManager
    if args.project:
        from domain.project_manager import project_manager
        try:
            project_manager.open(args.project)
            print(f"[run] Auto-opened project: {args.project}")
        except Exception as exc:
            print(f"[run] WARNING: Could not auto-open project: {exc}", file=sys.stderr)

    if args.open:
        webbrowser.open(f"http://{args.host}:{args.port}")

    from server import app
    print(f"[run] BaramFlow Web → http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
