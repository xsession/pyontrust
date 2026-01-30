from __future__ import annotations

from typing import Optional

from nicegui import ui

from ..config import WaveformsConfig
from ..hal.registry import list_hals


class WaveformsView:
    def __init__(self, *, handle, config: WaveformsConfig):
        self._handle = handle
        self._config = config

        self._devices: list[tuple[str, str]] = []
        self._selected_device: Optional[str] = None

        with ui.row().classes("w-full"):
            with ui.column().classes("grow"):
                self._scope_chart = ui.echart(self._empty_scope_option()).classes("w-full h-80")
                self._fft_chart = ui.echart(self._empty_fft_option()).classes("w-full h-80")
            with ui.column().classes("w-80"):
                ui.label("Controls").classes("text-lg")

                self._hal_select = ui.select(options=list_hals(), value=config.hal.name, label="HAL")
                self._device_select = ui.select(options={}, label="Device")
                with ui.row().classes("w-full"):
                    ui.button("Discover", on_click=self._on_discover)
                    ui.button("Connect", on_click=self._on_connect_selected)
                with ui.row().classes("w-full"):
                    ui.button("Start", on_click=self._on_start)
                    ui.button("Stop", on_click=self._on_stop)

                ui.separator()
                ui.label("Measurements")
                self._m_vpp = ui.label("Vpp: -")
                self._m_mean = ui.label("Mean: -")
                self._m_vrms = ui.label("Vrms: -")
                self._m_vmin = ui.label("Vmin: -")
                self._m_vmax = ui.label("Vmax: -")

                ui.separator()
                ui.label("Cursors")
                self._c1 = ui.number(label="t1 (s)", value=0.0, format="%.6f")
                self._c2 = ui.number(label="t2 (s)", value=0.001, format="%.6f")
                self._cdt = ui.label("Δt: -")
                self._cf = ui.label("1/Δt: -")

                ui.separator()
                ui.label("Timebase")
                self._sr = ui.number(label="Sample rate (Hz)", value=1_000_000, format="%.0f")
                self._rl = ui.number(label="Record length", value=4096, format="%.0f")
                ui.button("Apply", on_click=self._apply_timebase).props("dense")

                ui.separator()
                ui.label("Trigger")
                self._trig_level = ui.number(label="Level (V)", value=0.0)
                self._trig_edge = ui.select(options={"rising": "rising", "falling": "falling"}, value="rising", label="Edge")
                ui.button("Apply", on_click=self._apply_trigger).props("dense")

                ui.separator()
                ui.label("Channel 0")
                self._ch0_en = ui.switch("Enabled", value=True)
                self._ch0_range = ui.number(label="Range (V)", value=5.0)
                self._ch0_offset = ui.number(label="Offset (V)", value=0.0)
                ui.button("Apply", on_click=self._apply_channel0).props("dense")

                ui.separator()
                ui.label("AWG 0")
                self._awg_wave = ui.select(options={"sine": "sine", "square": "square", "triangle": "triangle", "ramp": "ramp", "dc": "dc"}, value="sine", label="Waveform")
                self._awg_freq = ui.number(label="Freq (Hz)", value=1000.0)
                self._awg_amp = ui.number(label="Amp (Vpp)", value=1.0)
                self._awg_off = ui.number(label="Offset (V)", value=0.0)
                ui.button("Apply", on_click=self._apply_awg0).props("dense")

        ui.timer(1.0 / max(1, config.ui.fps_limit), self._tick)

    def attach_handle(self, handle) -> None:
        self._handle = handle
        try:
            self._handle._acq.subscribe_errors(lambda e: ui.notify(f"Acq error: {e}", type="negative"))
        except Exception:
            pass

    def _on_discover(self) -> None:
        if not self._handle:
            return
        # Switch HAL at runtime (disconnect/recreate handled in v0.2). For v0.1, only affects next mount.
        devices = self._handle.discover()
        self._devices = [(d.device_id, d.display_name) for d in devices]
        self._device_select.options = {did: name for did, name in self._devices}
        if self._devices:
            self._device_select.value = self._devices[0][0]
        ui.notify(f"Found {len(devices)} device(s)")

    def _on_connect_selected(self) -> None:
        if not self._handle:
            return
        did = self._device_select.value or "sim0"
        self._handle.connect(str(did))
        ui.notify(f"Connected: {did}")

    def _on_start(self) -> None:
        if self._handle:
            self._handle.start_acquisition()

    def _on_stop(self) -> None:
        if self._handle:
            self._handle.stop_acquisition()

    def _apply_timebase(self) -> None:
        if not self._handle:
            return
        self._handle.set_timebase(float(self._sr.value), int(self._rl.value), mode="realtime")

    def _apply_trigger(self) -> None:
        if not self._handle:
            return
        self._handle.set_trigger(
            source="ch0",
            level=float(self._trig_level.value),
            edge=str(self._trig_edge.value),
            pretrigger=0.1,
            holdoff=0.0,
            hysteresis=0.02,
        )

    def _apply_channel0(self) -> None:
        if not self._handle:
            return
        self._handle.set_channel(
            ch=0,
            enabled=bool(self._ch0_en.value),
            coupling="dc",
            range_v=float(self._ch0_range.value),
            offset_v=float(self._ch0_offset.value),
            bandwidth_hz=None,
        )

    def _apply_awg0(self) -> None:
        if not self._handle:
            return
        self._handle.set_awg(
            ch=0,
            waveform=str(self._awg_wave.value),
            freq_hz=float(self._awg_freq.value),
            amp_vpp=float(self._awg_amp.value),
            offset_v=float(self._awg_off.value),
            duty=0.5,
            symmetry=0.5,
        )

    def _tick(self) -> None:
        if not self._handle:
            return
        uif = self._handle._acq.latest_ui_frame()
        if uif is None:
            return

        # Scope: envelope min/max
        self._scope_chart.options["xAxis"]["data"] = uif.x_s.tolist()
        self._scope_chart.options["series"][0]["data"] = uif.env_min.tolist()
        self._scope_chart.options["series"][1]["data"] = uif.env_max.tolist()

        # Trigger marker
        if uif.trigger_index is not None and len(uif.y) > 0:
            t_trig = float(uif.trigger_index) / float(uif.sample_rate_hz)
            self._scope_chart.options["series"][0]["markLine"] = {
                "symbol": ["none", "none"],
                "data": [{"xAxis": t_trig}],
            }
        else:
            self._scope_chart.options["series"][0].pop("markLine", None)
        self._scope_chart.update()

        # FFT
        self._fft_chart.options["xAxis"]["data"] = uif.fft_freq_hz.tolist()
        self._fft_chart.options["series"][0]["data"] = uif.fft_mag.tolist()
        self._fft_chart.update()

        # Measurements
        m = uif.measurements
        self._m_vpp.text = f"Vpp: {m.get('vpp', None):.4g}" if m.get("vpp") is not None else "Vpp: -"
        self._m_mean.text = f"Mean: {m.get('mean', None):.4g}" if m.get("mean") is not None else "Mean: -"
        self._m_vrms.text = f"Vrms: {m.get('vrms', None):.4g}" if m.get("vrms") is not None else "Vrms: -"
        self._m_vmin.text = f"Vmin: {m.get('vmin', None):.4g}" if m.get("vmin") is not None else "Vmin: -"
        self._m_vmax.text = f"Vmax: {m.get('vmax', None):.4g}" if m.get("vmax") is not None else "Vmax: -"

        # Cursors
        t1 = float(self._c1.value or 0.0)
        t2 = float(self._c2.value or 0.0)
        dt = abs(t2 - t1)
        self._cdt.text = f"Δt: {dt:.6g} s"
        self._cf.text = f"1/Δt: {1.0/dt:.6g} Hz" if dt > 0 else "1/Δt: -"

    @staticmethod
    def _empty_scope_option() -> dict:
        return {
            "animation": False,
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value"},
            "series": [
                {"type": "line", "showSymbol": False, "data": [], "name": "min"},
                {"type": "line", "showSymbol": False, "data": [], "name": "max"},
            ],
            "grid": {"left": 40, "right": 20, "top": 20, "bottom": 30},
        }

    @staticmethod
    def _empty_fft_option() -> dict:
        return {
            "animation": False,
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "showSymbol": False, "data": []}],
            "grid": {"left": 40, "right": 20, "top": 20, "bottom": 30},
        }
