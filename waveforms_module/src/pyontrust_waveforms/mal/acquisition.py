from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from ..config import WaveformsConfig
from ..errors import BufferOverrun, WaveformsError
from ..hal.base import InstrumentHal
from ..models import AwgConfig, ChannelConfig, DeviceInfo, ScopeConfig, TriggerConfig
from .pipeline import DspEngine, Spectrum


@dataclass(frozen=True)
class Frame:
    t0_s: float
    sample_rate_hz: float
    channels: dict[int, np.ndarray]  # float32 volts


@dataclass(frozen=True)
class UiFrame:
    t0_s: float
    sample_rate_hz: float
    x_s: np.ndarray  # float32
    y: np.ndarray  # float32 (raw or decimated)
    env_min: np.ndarray  # float32
    env_max: np.ndarray  # float32
    fft_freq_hz: np.ndarray  # float32
    fft_mag: np.ndarray  # float32
    measurements: dict[str, float | None]
    trigger_index: int | None


class AcquisitionManager:
    def __init__(self, *, hal: InstrumentHal, config: WaveformsConfig):
        self._hal = hal
        self._config = config
        self._device_id: Optional[str] = None

        self._scope_cfg = ScopeConfig(sample_rate_hz=1_000_000.0, record_length=4096, mode="realtime")
        self._trigger_cfg = TriggerConfig(source="ch0", level=0.0, edge="rising", pretrigger=0.1, holdoff=0.0, hysteresis=0.02)
        self._channel_cfg: dict[int, ChannelConfig] = {
            0: ChannelConfig(ch=0, enabled=True),
        }
        self._awg_cfg: dict[int, AwgConfig] = {}

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._ring = deque(maxlen=config.mal.ring_frames)
        self._ring_lock = threading.Lock()

        self._dsp = DspEngine()

        self._subscribers: list[tuple[Callable[[UiFrame], Any], float, float]] = []
        self._err_subscribers: list[Callable[[Exception], Any]] = []
        self._subs_lock = threading.Lock()
        self._last_error: Exception | None = None
        self._latest_ui: UiFrame | None = None

    def discover(self) -> list[DeviceInfo]:
        return self._hal.discover()

    def connect(self, device_id: str) -> None:
        if self._device_id is not None:
            self.disconnect()
        self._hal.open(device_id)
        self._device_id = device_id
        self._apply_config_to_hal()

    def disconnect(self) -> None:
        self.stop()
        if self._device_id is not None:
            try:
                self._hal.close()
            finally:
                self._device_id = None

    def configure_scope(self, cfg: ScopeConfig) -> None:
        self._scope_cfg = cfg
        if self._device_id is not None:
            self._hal.configure_scope(cfg)

    def configure_trigger(self, cfg: TriggerConfig) -> None:
        self._trigger_cfg = cfg
        if self._device_id is not None:
            self._hal.configure_trigger(cfg)

    def configure_channel(self, cfg: ChannelConfig) -> None:
        self._channel_cfg[cfg.ch] = cfg
        if self._device_id is not None:
            self._hal.configure_channel(cfg)

    def configure_awg(self, cfg: AwgConfig) -> None:
        self._awg_cfg[cfg.ch] = cfg
        if self._device_id is not None:
            self._hal.configure_awg(cfg)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if self._device_id is None:
            devices = self.discover()
            if devices:
                self.connect(devices[0].device_id)
            else:
                self.connect("sim0")

        self._stop_evt.clear()
        self._hal.start_streaming()
        self._thread = threading.Thread(target=self._run_loop, name="waveforms-acq", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
        self._thread = None
        try:
            self._hal.stop_streaming()
        except Exception:
            pass

    def subscribe(self, callback: Callable[[Frame], Any], *, fps_limit: int = 60) -> None:
        period_s = 1.0 / max(1, fps_limit)
        now = time.monotonic()
        with self._subs_lock:
            self._subscribers.append((callback, period_s, now))

    def subscribe_errors(self, callback: Callable[[Exception], Any]) -> None:
        with self._subs_lock:
            self._err_subscribers.append(callback)

    def latest_frame(self) -> Optional[Frame]:
        with self._ring_lock:
            if not self._ring:
                return None
            return self._ring[-1]

    def latest_ui_frame(self) -> Optional[UiFrame]:
        return self._latest_ui

    def _apply_config_to_hal(self) -> None:
        self._hal.configure_scope(self._scope_cfg)
        self._hal.configure_trigger(self._trigger_cfg)
        for cfg in self._channel_cfg.values():
            self._hal.configure_channel(cfg)
        for cfg in self._awg_cfg.values():
            self._hal.configure_awg(cfg)

    def _push_frame(self, frame: Frame) -> None:
        with self._ring_lock:
            if len(self._ring) == self._ring.maxlen and self._config.mal.drop_policy == "drop_new":
                return
            self._ring.append(frame)

    def _dispatch(self, frame: Frame) -> None:
        now = time.monotonic()
        with self._subs_lock:
            subs = list(self._subscribers)
            err_subs = list(self._err_subscribers)

        ui_frame = self._to_ui_frame(frame)
        self._latest_ui = ui_frame
        updated: list[tuple[Callable[[Frame], Any], float, float]] = []
        for cb, period_s, next_due in subs:
            if now >= next_due:
                try:
                    cb(ui_frame)
                except Exception:
                    pass
                updated.append((cb, period_s, now + period_s))
            else:
                updated.append((cb, period_s, next_due))
        with self._subs_lock:
            self._subscribers = updated

        if self._last_error is not None:
            e = self._last_error
            self._last_error = None
            for cb in err_subs:
                try:
                    cb(e)
                except Exception:
                    pass

    def _to_ui_frame(self, frame: Frame) -> UiFrame:
        y = frame.channels.get(0)
        if y is None:
            y = np.zeros(1, np.float32)
        y = np.asarray(y, dtype=np.float32)
        n = len(y)

        # Display decimation: envelope min/max per display column
        out_len = int(self._config.ui.display_points)
        env_min, env_max = self._dsp.decimate_envelope(y, out_len)
        m = self._dsp.measure_basic(y, frame.sample_rate_hz)
        spec = self._dsp.fft_spectrum(y, frame.sample_rate_hz, window="hann")

        trig_idx = self._dsp.find_edge_trigger(y, level=self._trigger_cfg.level, hysteresis=self._trigger_cfg.hysteresis, edge=self._trigger_cfg.edge)

        x_s = np.linspace(0.0, max(0.0, (n - 1) / frame.sample_rate_hz), len(env_min), dtype=np.float32)

        return UiFrame(
            t0_s=frame.t0_s,
            sample_rate_hz=frame.sample_rate_hz,
            x_s=x_s,
            y=y,
            env_min=env_min,
            env_max=env_max,
            fft_freq_hz=spec.freq_hz,
            fft_mag=spec.mag,
            measurements={
                "vpp": m.vpp,
                "vmin": m.vmin,
                "vmax": m.vmax,
                "mean": m.mean,
                "vrms": m.vrms,
                "frequency_hz": m.frequency_hz,
            },
            trigger_index=trig_idx,
        )

    def _run_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                samples = self._hal.read_samples(self._scope_cfg.record_length, timeout_s=0.25)
                frame = Frame(
                    t0_s=time.time(),
                    sample_rate_hz=float(self._scope_cfg.sample_rate_hz),
                    channels={k: np.asarray(v, dtype=np.float32) for k, v in samples.items()},
                )
                self._push_frame(frame)
                self._dispatch(frame)
            except Exception as e:
                self._last_error = e
                time.sleep(0.05)

