#!/usr/bin/env python3
"""CLI entry point for the CSV Plotter web application.

Usage:
    python run.py [--port PORT] [--host HOST] [--debug] [--open]
"""
from __future__ import annotations

import argparse
import sys
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV Plotter — Flask + Plotly.js SPA")
    parser.add_argument("--port", type=int, default=5200, help="HTTP port (default 5200)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug / hot-reload")
    parser.add_argument("--open", action="store_true", help="Open browser on startup")
    args = parser.parse_args()

    if args.open:
        webbrowser.open(f"http://{args.host}:{args.port}")

    from server import app  # noqa: E402

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
