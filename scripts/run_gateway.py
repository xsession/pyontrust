#!/usr/bin/env python3
"""Launch the pyontrust gateway server.

Usage::

    python scripts/run_gateway.py
    python scripts/run_gateway.py --port 8080 --debug
"""
from __future__ import annotations

import sys
import os

# Ensure src/ is importable during development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pyontrust.gateway.app import main  # noqa: E402

if __name__ == "__main__":
    main()
