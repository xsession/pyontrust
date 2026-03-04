from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from ..errors import DeviceNotFound
from ..models import AwgConfig, Capabilities, ChannelConfig, DeviceInfo, ScopeConfig, TriggerConfig
from .registry import register_hal


class FileReplayHal:
    """Offline replay HAL.

    Input format: `.npz` (schema v1) with keys:
    - `schema_version` (scalar int, optional; default=1)
    - `sample_rate_hz` (scalar float)
    - `t0_s` (scalar float, optional)
    - `ch0` (1D float32)
    Optional: `ch1`, `ch2`, ...
    """

    def __init__(self, config: dict[str, Any]):
        self._path = str(config.get("path", ""))
        self._opened = False
        self._scope = ScopeConfig(sample_rate_hz=1_000_000.0, record_length=4096, mode="realtime")
        self._data: dict[int, np.ndarray] = {}
        self._sr = 1_000_000.0
        self._idx = 0

    def discover(self) -> list[DeviceInfo]:
        return [DeviceInfo(device_id="replay0", display_name=f"Replay: {self._path or '<unset>'}", vendor="pyontrust", product="replay")]

    def open(self, device_id: str) -> None:
        if not self._path:
            raise DeviceNotFound("FileReplayHal requires config.path")
        npz = np.load(self._path)
        _schema = int(npz["schema_version"]) if "schema_version" in npz else 1
        self._sr = float(npz["sample_rate_hz"]) if "sample_rate_hz" in npz else self._sr
        self._data = {}
        for k in npz.files:
            if k.startswith("ch") and k[2:].isdigit():
                self._data[int(k[2:])] = np.asarray(npz[k], dtype=np.float32)
        if not self._data:
            raise DeviceNotFound(f"No channels found in {self._path}")
        self._idx = 0
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def capabilities(self) -> Capabilities:
        return Capabilities(
            analog_in_channels=max(self._data.keys()) + 1 if self._data else 1,
            analog_out_channels=0,
            max_sample_rate_hz=self._sr,
            has_hw_trigger=False,
            has_awg=False,
        )

    def configure_scope(self, cfg: ScopeConfig) -> None:
        self._scope = cfg

    def configure_trigger(self, cfg: TriggerConfig) -> None:
        pass

    def configure_channel(self, cfg: ChannelConfig) -> None:
        pass

    def configure_awg(self, cfg: AwgConfig) -> None:
        pass

    def start_streaming(self) -> None:
        pass

    def stop_streaming(self) -> None:
        pass

    def read_samples(self, max_n: int, timeout_s: float) -> dict[int, np.ndarray]:
        n = int(max_n)
        out: dict[int, np.ndarray] = {}
        for ch, arr in self._data.items():
            if self._idx >= len(arr):
                self._idx = 0
            end = min(self._idx + n, len(arr))
            seg = arr[self._idx : end]
            if len(seg) < n:
                seg = np.pad(seg, (0, n - len(seg)), mode="constant")
            out[ch] = seg.astype(np.float32, copy=False)
        self._idx += n

        # Best-effort real-time pacing
        sr = float(self._scope.sample_rate_hz or self._sr)
        time.sleep(min(timeout_s, n / max(1.0, sr)))
        return out


register_hal("file_replay", lambda cfg: FileReplayHal(cfg))
