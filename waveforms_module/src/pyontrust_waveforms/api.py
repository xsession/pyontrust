from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from nicegui import ui

from .config import WaveformsConfig
from .errors import WaveformsError
from .hal.registry import create_hal
from .mal.acquisition import AcquisitionManager
from .models import (
    AwgConfig,
    ChannelConfig,
    DeviceInfo,
    ScopeConfig,
    TriggerConfig,
)
from .ui.nicegui_module import WaveformsView


@dataclass
class WaveformsHandle:
    config: WaveformsConfig
    _acq: AcquisitionManager
    _view: Optional[WaveformsView] = None

    def discover(self) -> list[DeviceInfo]:
        return self._acq.discover()

    def connect(self, device_id: str) -> None:
        self._acq.connect(device_id)

    def disconnect(self) -> None:
        self._acq.disconnect()

    def start_acquisition(self) -> None:
        self._acq.start()

    def stop_acquisition(self) -> None:
        self._acq.stop()

    def set_timebase(
        self,
        sample_rate_hz: float,
        record_length: int,
        mode: Literal["realtime", "single"] = "realtime",
    ) -> None:
        self._acq.configure_scope(ScopeConfig(sample_rate_hz=sample_rate_hz, record_length=record_length, mode=mode))

    def set_trigger(
        self,
        source: str,
        level: float,
        edge: Literal["rising", "falling"],
        pretrigger: float,
        holdoff: float,
        hysteresis: float,
    ) -> None:
        self._acq.configure_trigger(
            TriggerConfig(
                source=source,
                level=level,
                edge=edge,
                pretrigger=pretrigger,
                holdoff=holdoff,
                hysteresis=hysteresis,
            )
        )

    def set_channel(
        self,
        ch: int,
        enabled: bool,
        coupling: Literal["dc", "ac"],
        range_v: float,
        offset_v: float,
        bandwidth_hz: float | None,
    ) -> None:
        self._acq.configure_channel(
            ChannelConfig(
                ch=ch,
                enabled=enabled,
                coupling=coupling,
                range_v=range_v,
                offset_v=offset_v,
                bandwidth_hz=bandwidth_hz,
            )
        )

    def set_awg(
        self,
        ch: int,
        waveform: Literal["sine", "square", "triangle", "ramp", "dc"],
        freq_hz: float,
        amp_vpp: float,
        offset_v: float,
        duty: float,
        symmetry: float,
    ) -> None:
        self._acq.configure_awg(
            AwgConfig(
                ch=ch,
                waveform=waveform,
                freq_hz=freq_hz,
                amp_vpp=amp_vpp,
                offset_v=offset_v,
                duty=duty,
                symmetry=symmetry,
            )
        )

    def subscribe(self, callback: Callable, *, fps_limit: int = 60) -> None:
        self._acq.subscribe(callback, fps_limit=fps_limit)


class WaveformsModule:
    @staticmethod
    def mount(container, *, config: WaveformsConfig) -> WaveformsHandle:
        # Register built-in HALs (simulated, file replay, dwf).
        from .hal import builtins as _builtins  # noqa: F401

        hal = create_hal(config.hal.name, config.hal.config)
        acq = AcquisitionManager(hal=hal, config=config)

        with container:
            view = WaveformsView(handle=None, config=config)
        handle = WaveformsHandle(config=config, _acq=acq, _view=view)
        view.attach_handle(handle)
        return handle
