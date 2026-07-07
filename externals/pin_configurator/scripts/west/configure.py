# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2025 Pyontrust Contributors
"""
Custom west command: `west configure`

Launches the Pyontrust Pin Configurator GUI from within a Zephyr west workspace.
Inspired by the Swedish Embedded SDK's `west simulate` pattern.

Usage:
    west configure                        # Open GUI in default browser
    west configure --port 5200            # Custom port
    west configure --headless             # API-only mode (no browser)
    west configure --board lp_mspm0g3507  # Pre-select a board

Registration (add to your workspace west.yml):
    manifest:
      self:
        west-commands: path/to/scripts/west/west-commands.yml
"""

import os
import sys
import webbrowser
import threading
from pathlib import Path
from textwrap import dedent

from west.commands import WestCommand
from west import log


class Configure(WestCommand):
    """West command to launch the Pyontrust Pin Configurator."""

    def __init__(self):
        super(Configure, self).__init__(
            "configure",
            "launch the Pyontrust pin configurator web GUI",
            dedent("""\
                Starts the Flask-based pin configurator server and opens
                the web interface in your default browser. The configurator
                provides interactive pin assignment, clock configuration,
                peripheral setup, and DTS/Kconfig generation for Zephyr
                RTOS projects.

                The server runs in the foreground. Press Ctrl+C to stop."""),
        )

    def do_add_parser(self, parser_adder):
        parser = parser_adder.add_parser(
            self.name,
            help=self.help,
            description=self.description,
        )

        parser.add_argument(
            "-p", "--port",
            type=int,
            default=5100,
            help="port to run the server on (default: 5100)",
        )
        parser.add_argument(
            "-b", "--board",
            default="",
            help="pre-select a board package on startup",
        )
        parser.add_argument(
            "--headless",
            action="store_true",
            help="start server without opening browser",
        )
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="host to bind to (default: 127.0.0.1)",
        )
        parser.add_argument(
            "--zephyr-base",
            default="",
            help="override ZEPHYR_BASE path",
        )
        parser.add_argument(
            "--ui-path",
            default=os.environ.get("PIN_CONFIGURATOR_UI_PATH", "/"),
            help="UI path to open in the browser (default: /)",
        )
        return parser

    def do_run(self, args, unknown_args):
        # Resolve the pin_configurator package directory
        script_dir = Path(__file__).resolve().parent
        pkg_dir = script_dir.parent.parent  # scripts/west/ -> pin_configurator/
        
        # Ensure the package is importable
        if str(pkg_dir) not in sys.path:
            sys.path.insert(0, str(pkg_dir))

        # Set ZEPHYR_BASE if provided or detect from west workspace
        if args.zephyr_base:
            os.environ["ZEPHYR_BASE"] = args.zephyr_base
        elif "ZEPHYR_BASE" not in os.environ:
            try:
                from west.configuration import config
                topdir = config.get("manifest", "path")
                zephyr_base = Path(self.topdir) / "zephyr"
                if zephyr_base.is_dir():
                    os.environ["ZEPHYR_BASE"] = str(zephyr_base)
                    log.inf(f"Auto-detected ZEPHYR_BASE: {zephyr_base}")
            except Exception:
                log.wrn("Could not auto-detect ZEPHYR_BASE")

        # Pass the pre-selected board as an environment variable
        if args.board:
            os.environ["PYONTRUST_DEFAULT_BOARD"] = args.board

        log.inf(f"Starting Pyontrust Pin Configurator on "
                f"http://{args.host}:{args.port}")

        # Import the Flask app
        try:
            from server import app
        except ImportError as e:
            log.die(f"Failed to import pin_configurator server: {e}\n"
                    f"Package directory: {pkg_dir}")

        # Open browser in a separate thread (unless headless)
        if not args.headless:
            base_url = f"http://{args.host}:{args.port}"
            ui_path = args.ui_path if str(args.ui_path).startswith("/") else f"/{args.ui_path}"
            url = f"{base_url}{ui_path}"
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
            log.inf(f"Opening browser at {url}")

        # Run the Flask server (blocking)
        try:
            app.run(
                host=args.host,
                port=args.port,
                debug=False,
                use_reloader=False,
            )
        except KeyboardInterrupt:
            log.inf("Configurator stopped.")
