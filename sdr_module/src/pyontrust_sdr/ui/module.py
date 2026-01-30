from __future__ import annotations

from typing import Optional

import numpy as np
from nicegui import ui

from ..config import SdrConfig
from ..models import GraphSpec
from ..blocks.registry import default_block_registry


class SdrView:
    """NiceGUI UI: device panel + minimal flowgraph editor + plots."""

    def __init__(self, *, handle, config: SdrConfig):
        self._handle = handle
        self._config = config
        self._block_reg = default_block_registry()

        self._syncing_driver = False

        self._fft_latest: Optional[dict] = None
        self._wf_latest: Optional[dict] = None
        self._iq_latest: Optional[dict] = None

        self._graph = GraphSpec.model_validate(self._handle.export_graph())

        # subscriptions (throttled by PubSub)
        self._handle.subscribe("fft", self._on_fft, fps_limit=config.ui.fps_limit)
        self._handle.subscribe("waterfall", self._on_wf, fps_limit=config.ui.fps_limit)
        self._handle.subscribe("iq_scope", self._on_iq, fps_limit=config.ui.fps_limit)

        with ui.row().classes("w-full"):
            with ui.column().classes("w-96"):
                ui.label("SDR").classes("text-lg")

                self._driver = ui.select(
                    options={"sim": "sim", "hackrf": "hackrf", "file": "file"},
                    value=config.default_driver,
                    label="Driver",
                )
                self._driver.on_value_change(lambda _: self._on_source_mode_changed())

                # HackRF (HAL) controls
                self._hal_controls = ui.column().classes("w-full")
                with self._hal_controls:
                    self._device = ui.select(options={}, label="Device")
                    with ui.row().classes("w-full"):
                        ui.button("Discover", on_click=self._discover)
                        ui.button("Connect", on_click=self._connect)

                # Sim source params
                self._sim_controls = ui.column().classes("w-full")
                with self._sim_controls:
                    self._sim_tone = ui.number(label="Tone (Hz)", value=100e3, format="%.0f")
                    self._sim_amp = ui.number(label="Amplitude", value=0.7, format="%.3f")
                    self._sim_noise = ui.number(label="Noise", value=0.02, format="%.4f")
                    ui.button("Apply source", on_click=self._apply_source_params).props("dense")

                # File source params
                self._file_controls = ui.column().classes("w-full")
                with self._file_controls:
                    self._file_path = ui.input(label="IQ file path (complex64 raw)", value="").classes("w-full")
                    with ui.row().classes("w-full"):
                        self._file_loop = ui.checkbox("Loop", value=False)
                        self._file_pace = ui.checkbox("Pace", value=True)
                    ui.button("Apply source", on_click=self._apply_source_params).props("dense")

                self._refresh_source_visibility()
                self._ensure_source_block_for_mode(initial=True)

                ui.separator()
                self._cf = ui.number(label="Center freq (Hz)", value=float(self._handle.rx.center_freq_hz), format="%.0f")
                self._sr = ui.number(label="Sample rate (Hz)", value=float(self._handle.rx.sample_rate_hz), format="%.0f")
                self._gain = ui.number(label="Gain (dB)", value=float(self._handle.rx.gain_db), format="%.1f")
                self._bw = ui.number(label="Bandwidth (Hz)", value=float(self._handle.rx.bandwidth_hz or 0.0), format="%.0f")
                ui.button("Apply RX", on_click=self._apply_rx).props("dense")

                ui.separator()
                with ui.row().classes("w-full"):
                    ui.button("Start", on_click=self._handle.start)
                    ui.button("Stop", on_click=self._handle.stop)

                ui.separator()
                ui.label("Flowgraph (v0.1)")
                ui.label("Add blocks and connect ports; Apply loads runtime.")

                self._blocks_col = ui.column().classes("w-full")
                self._edges_col = ui.column().classes("w-full")
                self._render_graph_editor()

                ui.separator()
                with ui.row().classes("w-full"):
                    ui.button("Apply graph", on_click=self._apply_graph)
                    ui.button("Export graph", on_click=self._export_graph).props("dense")

            with ui.column().classes("grow"):
                self._fft_chart = ui.echart(self._empty_fft()).classes("w-full h-72")
                self._wf_chart = ui.echart(self._empty_waterfall()).classes("w-full h-72")
                self._iq_chart = ui.echart(self._empty_iq()).classes("w-full h-72")

        ui.timer(1.0 / max(1, config.ui.fps_limit), self._tick)

    def _discover(self) -> None:
        if str(self._driver.value) != "hackrf":
            ui.notify("Discover is only used for hackrf", type="warning")
            return
        infos = self._handle.discover_devices()
        # filter by selected driver
        drv = str(self._driver.value)
        filt = [d for d in infos if d.driver == drv] if drv else infos
        self._device.options = {d.device_id: d.display_name for d in filt}
        if filt:
            self._device.value = filt[0].device_id
        ui.notify(f"Found {len(filt)} device(s) for {drv}")

    def _connect(self) -> None:
        drv = str(self._driver.value)
        if drv != "hackrf":
            ui.notify("Connect is only needed for hackrf (HAL)", type="warning")
            return
        did = str(self._device.value or "")
        if not did:
            ui.notify("Select a device first", type="warning")
            return
        self._handle.connect(did, driver=drv)
        ui.notify(f"Connected {drv}:{did}")

    def _apply_rx(self) -> None:
        bw = float(self._bw.value or 0.0)
        self._handle.set_rx(
            center_freq_hz=float(self._cf.value),
            sample_rate_hz=float(self._sr.value),
            gain_db=float(self._gain.value),
            bandwidth_hz=None if bw <= 0 else bw,
        )

    def _export_graph(self) -> None:
        data = self._handle.export_graph()
        ui.notify("Graph exported to clipboard")
        ui.clipboard.write(str(data))

    def _apply_graph(self) -> None:
        try:
            self._ensure_source_block_for_mode(initial=False)
            self._handle.load_graph(self._graph)
            ui.notify("Graph applied")
        except Exception as e:
            ui.notify(f"Graph error: {e}", type="negative")

    def _on_source_mode_changed(self) -> None:
        if self._syncing_driver:
            return
        self._refresh_source_visibility()
        try:
            self._handle.stop()
        except Exception:
            pass
        self._ensure_source_block_for_mode(initial=False)

    def _sync_driver_from_graph(self) -> None:
        src = self._get_source_block()
        if src is None:
            return
        desired = {"hal_rx_source": "hackrf", "sim_iq_source": "sim", "file_iq_source": "file"}.get(str(src.type))
        if not desired:
            return
        if str(self._driver.value) == desired:
            return
        self._syncing_driver = True
        try:
            self._driver.value = desired
        finally:
            self._syncing_driver = False

    def _refresh_source_visibility(self) -> None:
        mode = str(self._driver.value)
        self._hal_controls.set_visibility(mode == "hackrf")
        self._sim_controls.set_visibility(mode == "sim")
        self._file_controls.set_visibility(mode == "file")

    def _apply_source_params(self) -> None:
        mode = str(self._driver.value)
        src = self._get_source_block()
        if src is None:
            ui.notify("No source block in graph", type="warning")
            return

        if mode == "sim":
            src.params = {
                "tone_hz": float(self._sim_tone.value or 0.0),
                "amp": float(self._sim_amp.value or 0.0),
                "noise": float(self._sim_noise.value or 0.0),
            }
        elif mode == "file":
            src.params = {
                "path": str(self._file_path.value or "").strip(),
                "loop": bool(self._file_loop.value),
                "pace": bool(self._file_pace.value),
            }
        self._render_graph_editor()
        ui.notify("Source params updated")

    def _is_source_type(self, block_type: str) -> bool:
        try:
            inst = self._block_reg.get(block_type)()
        except Exception:
            return False
        return bool(getattr(inst, "is_source", False))

    def _get_source_block(self):
        for b in self._graph.blocks:
            if self._is_source_type(b.type):
                return b
        return None

    def _ensure_source_block_for_mode(self, *, initial: bool) -> None:
        mode = str(self._driver.value)
        desired_type = {"hackrf": "hal_rx_source", "sim": "sim_iq_source", "file": "file_iq_source"}.get(mode)
        if not desired_type:
            return

        # Prefer an existing source block; otherwise, fall back to block id "src".
        src = self._get_source_block()
        if src is None:
            src = next((b for b in self._graph.blocks if b.id == "src"), None)

        if src is None:
            from ..models import BlockSpec

            src = BlockSpec(id="src", type=desired_type, params={})
            self._graph.blocks.insert(0, src)

        # Enforce exactly one source in the graph model (UI-level guard).
        self._graph.blocks = [b for b in self._graph.blocks if b is src or not self._is_source_type(b.type)]

        if src.type != desired_type:
            src.type = desired_type
            src.params = {}  # reset when switching modes

        # Seed defaults into controls from graph on first render, or when switching.
        if src.type == "sim_iq_source":
            p = dict(src.params or {})
            if initial and not p:
                p = {"tone_hz": 100e3, "amp": 0.7, "noise": 0.02}
                src.params = dict(p)
            self._sim_tone.value = float(p.get("tone_hz", 100e3))
            self._sim_amp.value = float(p.get("amp", 0.7))
            self._sim_noise.value = float(p.get("noise", 0.02))
        elif src.type == "file_iq_source":
            p = dict(src.params or {})
            self._file_path.value = str(p.get("path", ""))
            self._file_loop.value = bool(p.get("loop", False))
            self._file_pace.value = bool(p.get("pace", True))

        self._render_graph_editor()

    def _render_graph_editor(self) -> None:
        self._blocks_col.clear()
        self._edges_col.clear()

        # If the graph was changed externally (e.g. import), keep the Driver selector in sync.
        self._sync_driver_from_graph()

        with self._blocks_col:
            ui.label("Blocks")
            for b in list(self._graph.blocks):
                with ui.row().classes("w-full items-center"):
                    is_src = self._is_source_type(b.type)
                    ui.label(f"{b.id}: {b.type}" + (" (source)" if is_src else "")).classes("grow")
                    if is_src:
                        ui.button("Pinned", on_click=lambda: ui.notify("Source block is pinned", type="warning")).props(
                            "dense outline"
                        )
                    else:
                        ui.button("Remove", on_click=lambda bid=b.id: self._remove_block(bid)).props("dense")

            with ui.row().classes("w-full"):
                self._new_block_type = ui.select(
                    options={k: k for k in self._block_reg.list_blocks()},
                    value="dc_blocker",
                    label="Type",
                ).classes("grow")
                self._new_block_id = ui.input(label="ID", value="b1").classes("w-32")
                ui.button("Add", on_click=self._add_block)

        with self._edges_col:
            ui.separator()
            ui.label("Edges")
            for e in list(self._graph.edges):
                with ui.row().classes("w-full items-center"):
                    ui.label(f"{e.src_block}.{e.src_port} -> {e.dst_block}.{e.dst_port}").classes("grow")
                    ui.button("Remove", on_click=lambda ee=e: self._remove_edge(ee)).props("dense")

            # New edge controls
            block_ids = [b.id for b in self._graph.blocks]
            self._edge_src_block = ui.select(options={bid: bid for bid in block_ids}, label="Src block")
            self._edge_src_port = ui.select(options={}, label="Src port")
            self._edge_dst_block = ui.select(options={bid: bid for bid in block_ids}, label="Dst block")
            self._edge_dst_port = ui.select(options={}, label="Dst port")

            def _refresh_ports() -> None:
                sb = str(self._edge_src_block.value or "")
                db = str(self._edge_dst_block.value or "")
                s = next((b for b in self._graph.blocks if b.id == sb), None)
                d = next((b for b in self._graph.blocks if b.id == db), None)
                if s:
                    ports = self._block_reg.get(s.type)().output_ports().keys()
                    self._edge_src_port.options = {p: p for p in ports}
                if d:
                    ports = self._block_reg.get(d.type)().input_ports().keys()
                    self._edge_dst_port.options = {p: p for p in ports}

            self._edge_src_block.on_value_change(lambda _: _refresh_ports())
            self._edge_dst_block.on_value_change(lambda _: _refresh_ports())
            _refresh_ports()

            ui.button("Add edge", on_click=self._add_edge)

    def _remove_block(self, block_id: str) -> None:
        b = next((bb for bb in self._graph.blocks if bb.id == block_id), None)
        if b is not None and self._is_source_type(b.type):
            ui.notify("Source block is pinned", type="warning")
            return
        self._graph.blocks = [b for b in self._graph.blocks if b.id != block_id]
        self._graph.edges = [e for e in self._graph.edges if e.src_block != block_id and e.dst_block != block_id]
        self._render_graph_editor()

    def _add_block(self) -> None:
        bid = str(self._new_block_id.value).strip()
        btype = str(self._new_block_type.value)
        if not bid:
            ui.notify("Block ID required", type="warning")
            return
        if any(b.id == bid for b in self._graph.blocks):
            ui.notify("Duplicate block ID", type="warning")
            return
        if self._is_source_type(btype) and self._get_source_block() is not None:
            ui.notify("Graph already has a source block", type="warning")
            return
        from ..models import BlockSpec

        self._graph.blocks.append(BlockSpec(id=bid, type=btype, params={}))
        self._render_graph_editor()

    def _remove_edge(self, edge) -> None:
        self._graph.edges = [e for e in self._graph.edges if e != edge]
        self._render_graph_editor()

    def _add_edge(self) -> None:
        sb = str(self._edge_src_block.value or "")
        sp = str(self._edge_src_port.value or "")
        db = str(self._edge_dst_block.value or "")
        dp = str(self._edge_dst_port.value or "")
        if not (sb and sp and db and dp):
            ui.notify("Select src/dst and ports", type="warning")
            return

        src = self._get_source_block()
        if src is not None and db == str(src.id):
            ui.notify("Edges into the source block are not supported", type="warning")
            return
        from ..models import EdgeSpec

        self._graph.edges.append(EdgeSpec(src_block=sb, src_port=sp, dst_block=db, dst_port=dp))
        self._render_graph_editor()

    def _on_fft(self, msg: dict) -> None:
        self._fft_latest = msg

    def _on_wf(self, msg: dict) -> None:
        self._wf_latest = msg

    def _on_iq(self, msg: dict) -> None:
        self._iq_latest = msg

    def _tick(self) -> None:
        if self._fft_latest is not None:
            f = self._fft_latest["freq_hz"].tolist()
            p = self._fft_latest["power_db"].tolist()
            self._fft_chart.options["xAxis"]["data"] = f
            self._fft_chart.options["series"][0]["data"] = p
            self._fft_chart.update()

        if self._wf_latest is not None:
            m = self._wf_latest["power_db"]
            if isinstance(m, np.ndarray):
                m = m.astype(np.float32)
                rows, cols = m.shape
                # ECharts heatmap wants triples [x,y,val]
                data = []
                # throttle payload: downsample rows if needed
                step = max(1, rows // 120)
                for y in range(0, rows, step):
                    row = m[y]
                    for x in range(cols):
                        data.append([x, y // step, float(row[x])])
                self._wf_chart.options["series"][0]["data"] = data
                self._wf_chart.options["yAxis"]["max"] = (rows // step) - 1
                self._wf_chart.update()

        if self._iq_latest is not None:
            i = self._iq_latest["i"].tolist()
            q = self._iq_latest["q"].tolist()
            pts = [[i[k], q[k]] for k in range(min(len(i), len(q)))]
            self._iq_chart.options["series"][0]["data"] = pts
            self._iq_chart.update()

    @staticmethod
    def _empty_fft() -> dict:
        return {
            "animation": False,
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "showSymbol": False, "data": []}],
            "grid": {"left": 50, "right": 20, "top": 20, "bottom": 30},
        }

    @staticmethod
    def _empty_waterfall() -> dict:
        return {
            "animation": False,
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value", "min": 0, "max": 199},
            "visualMap": {
                "min": -120,
                "max": 0,
                "orient": "horizontal",
                "left": "center",
                "bottom": 0,
            },
            "series": [
                {
                    "type": "heatmap",
                    "data": [],
                    "progressive": 0,
                    "animation": False,
                }
            ],
            "grid": {"left": 50, "right": 20, "top": 20, "bottom": 50},
        }

    @staticmethod
    def _empty_iq() -> dict:
        return {
            "animation": False,
            "xAxis": {"type": "value"},
            "yAxis": {"type": "value"},
            "series": [{"type": "scatter", "symbolSize": 3, "data": []}],
            "grid": {"left": 50, "right": 20, "top": 20, "bottom": 30},
        }
