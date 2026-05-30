"""Convenience launcher for the packaged pyontrust MCP server."""

from __future__ import annotations

import pathlib
import sys


_ROOT = pathlib.Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pyontrust.mcp_server import main


if __name__ == "__main__":
    main()