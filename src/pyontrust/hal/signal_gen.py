"""Signal generator protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SignalGenerator(Protocol):
    """Hardware abstraction for signal / waveform generators."""

    def open(self) -> None:
        ...  # pragma: no cover

    def close(self) -> None:
        ...  # pragma: no cover

    def set_waveform(self, channel: int, shape: str, freq_hz: float, amplitude_v: float) -> None:
        """Configure a waveform output.

        shape: 'sine', 'square', 'triangle', 'sawtooth', 'dc'
        """
        ...  # pragma: no cover

    def enable_output(self, channel: int, on: bool) -> None:
        ...  # pragma: no cover
