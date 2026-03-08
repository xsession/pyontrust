#!/usr/bin/env python3
"""
Launch helper for the Zephyr Pin Configurator.

Usage
-----
  python run.py                    # http://127.0.0.1:5100
  python run.py --port 8080        # custom port
  python run.py --debug            # Flask debug / hot-reload
  python run.py --open             # auto-open browser
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
import pathlib

# Make sure package modules are importable
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def main():
    parser = argparse.ArgumentParser(description="Zephyr Pin Configurator")
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--open", action="store_true",
                        help="Open browser automatically")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    print()
    print("  ┌─────────────────────────────────────────┐")
    print("  │  Zephyr Pin Configurator                 │")
    print(f"  │  {url:<38s} │")
    print("  │                                          │")
    print("  │  Ctrl+C to stop                          │")
    print("  └─────────────────────────────────────────┘")
    print()

    if args.open:
        webbrowser.open(url)

    from server import app
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
