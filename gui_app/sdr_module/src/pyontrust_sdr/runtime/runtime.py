from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from ..config import RuntimeConfig
from ..errors import DriverError
from ..hal.protocol import SdrHal
from ..models import GraphSpec, RxConfig
from ..blocks.registry import BlockRegistry, default_block_registry
from .graph_validate import validate_graph
from .pubsub import PubSub


@dataclass
class Metrics:
    sample_rate_hz: float
    chunk_size: int
    dropped_chunks: int = 0
    processed_chunks: int = 0


class FlowgraphRuntime:
    """Push-based scheduler: source drives chunk flow.

    Execution strategy: pure Python + NumPy for vectorized DSP.
    - Latency: low (single DSP thread, bounded queues avoided by in-thread chaining)
    - Portability: high (no compiled extensions required for v0.1)
    - Packaging: simple (pip install)
    """

    def __init__(self, *, pubsub: PubSub, config: RuntimeConfig, registry: BlockRegistry | None = None) -> None:
        self._pubsub = pubsub
        self._cfg = config
        self._registry = registry or default_block_registry()

        self._hal: Optional[SdrHal] = None
        self._hal_device_id: Optional[str] = None
        self._rx = RxConfig()

        self._graph: Optional[GraphSpec] = None
        self._stop = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None
        self._dsp_thread: Optional[threading.Thread] = None

        self._q = deque(maxlen=max(1, int(self._cfg.ring_chunks)))
        self._q_cv = threading.Condition()

        self._metrics = Metrics(sample_rate_hz=self._rx.sample_rate_hz, chunk_size=self._cfg.chunk_size)

        # compiled pipeline
        self._source: Optional[tuple[str, object]] = None
        self._ordered_blocks = []
        self._edges = []

    def connect_hal(self, hal: SdrHal, device_id: str) -> None:
        self.stop()
        self._hal = hal
        self._hal_device_id = device_id
        self._hal.open(device_id)
        self._hal.set_rx_config(self._rx)

    def set_rx_config(self, rx: RxConfig) -> None:
        self._rx = rx
        self._metrics.sample_rate_hz = rx.sample_rate_hz
        if self._hal:
            self._hal.set_rx_config(rx)

    def load_graph(self, spec: GraphSpec) -> None:
        self.stop()
        validate_graph(spec, registry=self._registry)
        self._graph = spec
        self._compile(spec)

    def export_graph(self) -> dict:
        if not self._graph:
            return GraphSpec().model_dump()
        return self._graph.model_dump()

    def import_graph(self, data: dict) -> None:
        spec = GraphSpec.model_validate(data)
        self.load_graph(spec)

    def start(self) -> None:
        if self._dsp_thread and self._dsp_thread.is_alive():
            return
        if not self._graph:
            # default minimal graph: SDR/sim source -> FFT + waterfall + IQ scope sinks
            from ..presets import default_graph

            self.load_graph(default_graph())

        if not self._source:
            raise DriverError("Graph not compiled")

        source_block = self._source[1]
        needs_hal = bool(getattr(source_block, "requires_hal", False))
        if needs_hal and not self._hal:
            from ..hal.simulated import SimulatedHal

            self.connect_hal(SimulatedHal(), "sim0")

        self._stop.clear()
        self._rx_thread = threading.Thread(target=self._rx_loop, name="pyontrust_sdr_rx", daemon=True)
        self._dsp_thread = threading.Thread(target=self._dsp_loop, name="pyontrust_sdr_dsp", daemon=True)
        self._rx_thread.start()
        self._dsp_thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._q_cv:
            self._q_cv.notify_all()
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=2.0)
        if self._dsp_thread and self._dsp_thread.is_alive():
            self._dsp_thread.join(timeout=2.0)
        self._rx_thread = None
        self._dsp_thread = None
        # stop blocks
        for _, blk in list(self._ordered_blocks):
            try:
                blk.stop()
            except Exception:
                pass
        if self._source is not None:
            try:
                self._source[1].stop()
            except Exception:
                pass
        if self._hal:
            try:
                self._hal.stop_stream()
            except Exception:
                pass

    def _compile(self, spec: GraphSpec) -> None:
        # v0.1: topological order on blocks; instantiate block objects
        from collections import defaultdict, deque

        indeg = defaultdict(int)
        out = defaultdict(list)
        for b in spec.blocks:
            indeg[b.id] = 0
        for e in spec.edges:
            indeg[e.dst_block] += 1
            out[e.src_block].append(e.dst_block)

        q = deque([b.id for b in spec.blocks if indeg[b.id] == 0])
        order = []
        while q:
            n = q.popleft()
            order.append(n)
            for m in out[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    q.append(m)

        id_to_spec = {b.id: b for b in spec.blocks}
        self._ordered_blocks = []
        self._source = None
        for bid in order:
            bs = id_to_spec[bid]
            block = self._registry.get(bs.type)()
            block.configure(bs.params)

            if bool(getattr(block, "is_source", False)):
                self._source = (bid, block)
            else:
                self._ordered_blocks.append((bid, block))
        self._edges = list(spec.edges)

    def _rx_loop(self) -> None:
        if not self._source:
            raise DriverError("No source block compiled")

        source_id, source = self._source
        needs_hal = bool(getattr(source, "requires_hal", False))
        if needs_hal:
            if not self._hal:
                raise DriverError("HAL not connected")
            # bind HAL to source if it supports it
            if hasattr(source, "bind_hal"):
                source.bind_hal(self._hal)
            self._hal.start_stream()

        # start source and blocks
        try:
            if hasattr(source, "start"):
                source.start(sample_rate_hz=float(self._rx.sample_rate_hz), pubsub=self._pubsub)
        except Exception as e:
            raise DriverError(f"Source start failed: {e}")
        for _, blk in list(self._ordered_blocks):
            try:
                blk.start(sample_rate_hz=float(self._rx.sample_rate_hz), pubsub=self._pubsub)
            except Exception:
                pass

        self._metrics.dropped_chunks = 0
        self._metrics.processed_chunks = 0

        while not self._stop.is_set():
            if not hasattr(source, "produce"):
                raise DriverError("Source block does not implement produce()")

            try:
                out = source.produce(
                    chunk_size=int(self._cfg.chunk_size),
                    sample_rate_hz=float(self._rx.sample_rate_hz),
                    pubsub=self._pubsub,
                )
            except EOFError:
                self._stop.set()
                break
            iq = out.get("iq") if isinstance(out, dict) else None
            if iq is None:
                continue
            if isinstance(iq, np.ndarray) and iq.size == 0:
                continue
            if not isinstance(iq, np.ndarray):
                continue
            if iq.dtype != np.complex64:
                iq = iq.astype(np.complex64)

            with self._q_cv:
                if len(self._q) == self._q.maxlen:
                    # drop oldest to keep latency bounded
                    self._q.popleft()
                    self._metrics.dropped_chunks += 1
                self._q.append(iq)
                self._q_cv.notify()

        if needs_hal and self._hal:
            try:
                self._hal.stop_stream()
            except Exception:
                pass

    def _dsp_loop(self) -> None:
        if not self._source:
            raise DriverError("No source block compiled")

        # pre-build routing maps
        dst_inputs = {(e.dst_block, e.dst_port): (e.src_block, e.src_port) for e in self._edges}
        by_id = {bid: blk for bid, blk in self._ordered_blocks}

        source_id, _ = self._source

        while not self._stop.is_set():
            with self._q_cv:
                while not self._stop.is_set() and len(self._q) == 0:
                    self._q_cv.wait(timeout=0.25)
                if self._stop.is_set():
                    break
                iq = self._q.popleft()

            frame = {(source_id, "iq"): iq}

            for bid, blk in self._ordered_blocks:
                inputs = {}
                for in_name in blk.input_ports().keys():
                    src = dst_inputs.get((bid, in_name))
                    if src is None:
                        continue
                    inputs[in_name] = frame.get(src)
                outputs = blk.process(inputs, sample_rate_hz=float(self._rx.sample_rate_hz), pubsub=self._pubsub)
                for oname, oval in outputs.items():
                    frame[(bid, oname)] = oval

            self._metrics.processed_chunks += 1
            if self._metrics.processed_chunks % 10 == 0:
                self._pubsub.publish("metrics", self._metrics)
