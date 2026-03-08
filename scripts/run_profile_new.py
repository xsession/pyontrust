#!/usr/bin/env python3
"""Run a test profile from the CLI.

Usage::

    python scripts/run_profile.py profiles/sleep_current.json
    python scripts/run_profile.py profiles/tx_burst.json --artifacts ./results
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pyontrust.core.profiles import run_profile  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a pyontrust test profile")
    parser.add_argument("profile", help="Path to profile JSON file")
    parser.add_argument("--artifacts", default="artifacts", help="Artifacts output dir")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    result = run_profile(args.profile, artifacts_root=args.artifacts)
    print(f"✅ Artifacts written to: {result}")


if __name__ == "__main__":
    main()
