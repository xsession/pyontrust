from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Type

from .protocol import SdrHal
from .simulated import SimulatedHal
from .file_replay import FileReplayHal
from .soapy_hackrf import SoapyHackrfHal


HalFactory = Callable[[], SdrHal]


@dataclass
class HalRegistry:
    _drivers: Dict[str, HalFactory]

    def list_drivers(self) -> List[str]:
        return sorted(self._drivers.keys())

    def get(self, name: str) -> HalFactory:
        return self._drivers[name]


def default_hal_registry() -> HalRegistry:
    return HalRegistry(
        _drivers={
            "hackrf": SoapyHackrfHal,
            "sim": SimulatedHal,
            "file": FileReplayHal,
        }
    )
