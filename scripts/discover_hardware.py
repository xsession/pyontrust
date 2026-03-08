#!/usr/bin/env python3
"""Discover available instruments and print a summary.

Usage::

    python scripts/discover_hardware.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pyontrust.instruments import discover_instruments  # noqa: E402


def main() -> None:
    instruments = discover_instruments()
    print(f"Found {len(instruments)} registered instrument type(s):\n")
    for name, ep in sorted(instruments.items()):
        print(f"  {name:20s}  →  {ep}")
    print()


if __name__ == "__main__":
    main()
