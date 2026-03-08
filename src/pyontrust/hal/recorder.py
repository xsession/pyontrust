"""Recorder protocol — long-running background captures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pyontrust.core.models import TestContext


@runtime_checkable
class Recorder(Protocol):
    """A long-running capture started/stopped around a test run.

    Examples: Wireshark capture, HackRF IQ recording, ffmpeg webcam,
    J-Link RTT console, PEAK-CAN bus logging.
    """

    name: str

    def start(self, ctx: "TestContext") -> None:
        ...  # pragma: no cover

    def stop(self, ctx: "TestContext") -> None:
        ...  # pragma: no cover


@dataclass(frozen=True)
class RecorderOutput:
    """Structured output from a recorder run."""

    files: list[str]
    notes: dict[str, Any] | None = None
