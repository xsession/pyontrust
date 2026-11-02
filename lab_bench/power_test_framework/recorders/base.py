from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core import TestContext


@runtime_checkable
class Recorder(Protocol):
    """A long-running capture started/stopped around a test run.

    Examples:
    - Wireshark/tshark capture to pcapng
    - HackRF IQ recording
    - ffmpeg webcam recording
    - J-Link RTT console log
    - PEAK-CAN bus logging
    """

    name: str

    def start(self, ctx: "TestContext") -> None:
        ...

    def stop(self, ctx: "TestContext") -> None:
        ...


@dataclass(frozen=True)
class RecorderOutput:
    files: list[str]
    notes: dict[str, Any] | None = None
