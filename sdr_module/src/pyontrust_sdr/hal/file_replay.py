from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..errors import DriverError
from ..models import DeviceInfo, RxConfig
from .protocol import SdrHal


@dataclass
class FileReplayConfig:
    path: str = ""
    loop: bool = True
    rate_control: bool = True
    file_dtype: str = "complex64"  # complex64|cs16


class FileReplayHal(SdrHal):
    def __init__(self) -> None:
        self._cfg = RxConfig()
        self._streaming = False
        self._file = FileReplayConfig()
        self._data: Optional[np.ndarray] = None
        self._idx = 0
        self._t_last = 0.0

    def discover(self) -> list[DeviceInfo]:
        return [DeviceInfo(device_id="file0", driver="file", display_name="File replay", meta={})]

    def open(self, device_id: str) -> None:
        # device_id is ignored; configure via block params in v0.2
        self._idx = 0
        self._t_last = time.time()

    def close(self) -> None:
        self._streaming = False
        self._data = None

    def set_rx_config(self, cfg: RxConfig) -> None:
        self._cfg = cfg

    def start_stream(self) -> None:
        if not self._file.path:
            raise DriverError("FileReplayHal requires path")
        p = Path(self._file.path)
        if not p.exists():
            raise DriverError(f"IQ file not found: {p}")

        raw = np.fromfile(str(p), dtype=np.complex64)
        self._data = raw.astype(np.complex64, copy=False)
        self._idx = 0
        self._streaming = True
        self._t_last = time.time()

    def read_iq(self, num_samples: int, timeout_s: float) -> np.ndarray:
        if not self._streaming or self._data is None or len(self._data) == 0:
            return np.empty((0,), dtype=np.complex64)

        if self._file.rate_control:
            # simple wall-clock pacing
            now = time.time()
            elapsed = now - self._t_last
            target = num_samples / float(self._cfg.sample_rate_hz)
            if elapsed < target:
                time.sleep(max(0.0, target - elapsed))
            self._t_last = time.time()

        end = self._idx + num_samples
        if end <= len(self._data):
            out = self._data[self._idx : end]
            self._idx = end
            return out

        # wrap/loop
        if not self._file.loop:
            out = self._data[self._idx :]
            self._idx = len(self._data)
            return out

        first = self._data[self._idx :]
        remain = num_samples - len(first)
        loops = remain // len(self._data)
        tail = remain % len(self._data)
        parts = [first]
        if loops > 0:
            parts.append(np.tile(self._data, loops))
        if tail > 0:
            parts.append(self._data[:tail])
        out = np.concatenate(parts).astype(np.complex64, copy=False)
        self._idx = tail
        return out

    def stop_stream(self) -> None:
        self._streaming = False
