from __future__ import annotations

"""J-Link adapter placeholder.

Intended responsibilities:
- flash firmware, reset target, set breakpoints (optional), start/stop RTT logging.

Keep it CLI-first to reduce Python dependencies in lab environments.
"""


class JLinkController:
    def __init__(self, jlink_path: str = "JLink.exe") -> None:
        self.jlink_path = jlink_path

    def open(self) -> None:
        return

    def close(self) -> None:
        return
