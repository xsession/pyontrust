"""Camera / webcam protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Camera(Protocol):
    """Hardware abstraction for cameras."""

    def open(self) -> None:
        ...  # pragma: no cover

    def close(self) -> None:
        ...  # pragma: no cover

    def snapshot(self, output_path: str) -> None:
        """Capture a single frame to the given path (JPEG/PNG)."""
        ...  # pragma: no cover

    def start_recording(self, output_path: str) -> None:
        ...  # pragma: no cover

    def stop_recording(self) -> str:
        """Stop recording and return path to recorded file."""
        ...  # pragma: no cover


@runtime_checkable
class StreamingCamera(Camera, Protocol):
    """Extension for cameras that support frame-by-frame streaming."""

    def read_frame(self) -> bytes:
        """Read one JPEG frame."""
        ...  # pragma: no cover
