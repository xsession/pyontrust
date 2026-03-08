#!/usr/bin/env python
"""pyontrust Lab Bench — standalone launcher.

Usage::

    python start_lab_bench.py                  # defaults: localhost:5200
    python start_lab_bench.py --port 8080      # custom port
    python start_lab_bench.py --no-browser     # skip auto-open

Can also be frozen into an .exe via PyInstaller (see build_exe.py).
"""
from __future__ import annotations

import argparse
import logging
import os
import pathlib
import sys
import threading
import time
import webbrowser


def _open_browser(url: str, delay: float = 1.5) -> None:
    """Open the default browser after a short delay."""
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass  # non-critical


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pyontrust-lab-bench",
        description="Launch the pyontrust Lab Bench GUI (Flask gateway)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PYONTRUST_PORT", "5200")),
        help="TCP port (default: 5200)",
    )
    parser.add_argument(
        "--artifacts",
        default=os.environ.get("PYONTRUST_ARTIFACTS", "artifacts"),
        help="Artifacts storage directory",
    )
    parser.add_argument("--bench", default=os.environ.get("PYONTRUST_BENCH"), help="Default bench JSON")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open the browser")
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("PYONTRUST_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("pyontrust.launcher")

    # ── Banner ──────────────────────────────────────────────────
    url = f"http://{args.host}:{args.port}"
    print()
    print("  +--------------------------------------------------+")
    print("  |  pyontrust Lab Bench                              |")
    print(f"  |  {url:<49s}|")
    print("  +--------------------------------------------------+")
    print()
    print(f"  Artifacts : {args.artifacts}")
    if args.bench:
        print(f"  Bench     : {args.bench}")
    print(f"  Debug     : {'ON' if args.debug else 'OFF'}")
    print()
    print("  Press Ctrl+C to stop the server.")
    print()

    # ── Import and create app ───────────────────────────────────
    try:
        from pyontrust.gateway.app import create_app
    except ImportError as exc:
        logger.error("Cannot import pyontrust.gateway — is it installed?")
        logger.error("  pip install -e \".[gui]\"")
        logger.error("  Error: %s", exc)
        sys.exit(1)

    app = create_app(
        artifacts_root=args.artifacts,
        bench_path=args.bench,
    )

    # ── Auto-open browser ───────────────────────────────────────
    if not args.no_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    # ── Run ─────────────────────────────────────────────────────
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
