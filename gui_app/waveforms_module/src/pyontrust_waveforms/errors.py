from __future__ import annotations

from dataclasses import dataclass


class WaveformsError(Exception):
    """Base exception for the module."""


@dataclass(frozen=True)
class ErrorDetails:
    message: str
    hint: str | None = None


class DeviceNotFound(WaveformsError):
    pass


class FfiCallFailed(WaveformsError):
    pass


class Timeout(WaveformsError):
    pass


class BufferOverrun(WaveformsError):
    pass


class UnsupportedCapability(WaveformsError):
    pass
