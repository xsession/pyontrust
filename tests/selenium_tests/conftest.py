"""Shared fixtures for FlowLab / Lab-Bench Selenium tests.

Starts the gateway in a background thread so every test module can
drive a *real* browser against it.
"""
from __future__ import annotations

import socket
import threading
import time
import os
import unittest

# ---------------------------------------------------------------------------
# Find a free port
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Gateway fixture — one per test-run
# ---------------------------------------------------------------------------

_server_thread: threading.Thread | None = None
_port: int = 0


def get_gateway_url() -> str:
    """Return the base URL of the running gateway."""
    global _server_thread, _port
    if _server_thread is None:
        _port = _free_port()
        _server_thread = threading.Thread(target=_run_server, daemon=True)
        _server_thread.start()
        _wait_for_server(_port)
    return f"http://127.0.0.1:{_port}"


def _run_server() -> None:
    from pyontrust.gateway.app import create_app

    app = create_app()
    app.run(host="127.0.0.1", port=_port, use_reloader=False, threaded=True)


def _wait_for_server(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"Gateway did not start on port {port} within {timeout}s")


# ---------------------------------------------------------------------------
# WebDriver helpers
# ---------------------------------------------------------------------------

def create_driver():
    """Create a headless Chrome WebDriver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    # Suppress logging noise
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(3)
    return driver
