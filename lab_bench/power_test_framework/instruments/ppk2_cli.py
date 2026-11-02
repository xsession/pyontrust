from __future__ import annotations

"""PPK2 adapter placeholder.

This repo doesn't currently vendor a PPK2 Python API. In practice you can implement this adapter using:

- Nordic tooling (nRF Connect / nrfutil) if it exposes a CLI stream, or
- a Python PPK2 library (if you already use one internally), or
- a small gRPC/serial bridge.

The framework only requires `capture(duration_s)` to yield `PowerSample` values.
"""

from dataclasses import dataclass
from typing import Iterable

from ..core import PowerSample


@dataclass
class Ppk2CliPowerMeter:
    tool_path: str = "ppk2"

    def open(self) -> None:
        raise NotImplementedError("Wire this adapter to your PPK2 tooling")

    def close(self) -> None:
        return

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        raise NotImplementedError("Wire this adapter to your PPK2 tooling")
