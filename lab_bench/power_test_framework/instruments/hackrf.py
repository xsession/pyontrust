from __future__ import annotations

"""HackRF One adapter placeholder.

Typical output: IQ recording via `hackrf_transfer`.
"""


class HackRfRecorder:
    def __init__(self, tool_path: str = "hackrf_transfer") -> None:
        self.tool_path = tool_path

    def open(self) -> None:
        return

    def close(self) -> None:
        return
