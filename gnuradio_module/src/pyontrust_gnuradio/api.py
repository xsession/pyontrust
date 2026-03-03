from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

from .config import GnuradioConfig
from .runner import ManagedProcess


@dataclass
class GnuradioHandle:
    config: GnuradioConfig
    _proc: Optional[ManagedProcess] = None

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
        finally:
            self._proc = None


class GnuradioModule:
    @staticmethod
    def mount(container, *, config: Optional[GnuradioConfig] = None) -> GnuradioHandle:
        cfg = config or GnuradioConfig()
        handle = GnuradioHandle(config=cfg)

        from .ui.module import GnuradioView

        GnuradioView(handle=handle, config=cfg).mount(container)
        return handle
