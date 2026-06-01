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
import pathlib
import sys
import webbrowser


# Make sure package modules are importable
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _print_banner(url: str, ui_path: str) -> None:
    banner_lines = [
        "+-----------------------------------------+",
        "|  Zephyr Pin Configurator                |",
        f"|  {url:<38s}|",
        f"|  UI {ui_path:<35s}|",
        "|                                         |",
        "|  Ctrl+C to stop                         |",
        "+-----------------------------------------+",
    ]
    print()
    for line in banner_lines:
        print(f"  {line}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Zephyr Pin Configurator")
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open browser automatically",
    )
    parser.add_argument(
        "--ui-path",
        default=os.environ.get("PIN_CONFIGURATOR_UI_PATH", "/"),
        help="UI path to open in the browser (default: /)",
    )
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    ui_path = args.ui_path if str(args.ui_path).startswith("/") else f"/{args.ui_path}"
    open_url = f"{url}{ui_path}"

    _print_banner(url, ui_path)

    if args.open:
        webbrowser.open(open_url)

    from server import app

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
