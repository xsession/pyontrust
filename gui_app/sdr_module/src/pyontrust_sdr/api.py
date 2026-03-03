from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from nicegui import ui

from .config import SdrConfig
from .errors import DriverError
from .hal.registry import HalRegistry, default_hal_registry
from .models import DeviceInfo, GraphSpec, RxConfig
from .runtime.pubsub import PubSub
from .runtime.runtime import FlowgraphRuntime
from .ui.module import SdrView


@dataclass
class SdrModule:
    """Embeddable module entrypoint."""

    @staticmethod
    def mount(container, *, config: Optional[SdrConfig] = None) -> "SdrHandle":
        cfg = config or SdrConfig()
        handle = SdrHandle(config=cfg)
        with container:
            view = SdrView(handle=handle, config=cfg)
            handle._attach_view(view)
        return handle


class SdrHandle:
    def __init__(self, *, config: SdrConfig, hal_registry: Optional[HalRegistry] = None) -> None:
        self._config = config
        self._pubsub = PubSub()
        self._hal_registry = hal_registry or default_hal_registry()
        self._runtime = FlowgraphRuntime(pubsub=self._pubsub, config=config.runtime)

        self._view: Optional[SdrView] = None
        self._rx = RxConfig()
        self._connected_driver = config.default_driver
        self._connected_device_id: Optional[str] = None

    # ---- UI integration ----

    def _attach_view(self, view: SdrView) -> None:
        self._view = view

    # ---- Device ----

    def discover_devices(self) -> list[DeviceInfo]:
        infos: list[DeviceInfo] = []
        for driver_name in self._hal_registry.list_drivers():
            hal_factory = self._hal_registry.get(driver_name)
            try:
                infos.extend(hal_factory().discover())
            except Exception:
                # discovery should be best-effort; show nothing for missing deps
                continue
        return infos

    def connect(self, device_id: str, *, driver: str = "hackrf") -> None:
        if driver not in self._hal_registry.list_drivers():
            raise DriverError(f"Unknown driver: {driver}")
        self._connected_driver = driver
        self._connected_device_id = device_id
        self._runtime.connect_hal(self._hal_registry.get(driver)(), device_id)

    def set_rx(
        self,
        center_freq_hz: float,
        sample_rate_hz: float,
        gain_db: float,
        bandwidth_hz: Optional[float] = None,
    ) -> None:
        self._rx = RxConfig(
            center_freq_hz=center_freq_hz,
            sample_rate_hz=sample_rate_hz,
            gain_db=gain_db,
            bandwidth_hz=bandwidth_hz,
        )
        self._runtime.set_rx_config(self._rx)

    # ---- Graph ----

    def load_graph(self, graph_spec: GraphSpec) -> None:
        self._runtime.load_graph(graph_spec)

    def export_graph(self) -> dict:
        return self._runtime.export_graph()

    def import_graph(self, data: dict) -> None:
        self._runtime.import_graph(data)

    # ---- Run control ----

    def start(self) -> None:
        self._runtime.start()

    def stop(self) -> None:
        self._runtime.stop()

    # ---- Subscriptions ----

    def subscribe(self, topic: str, callback: Callable[[Any], None], *, fps_limit: int = 30) -> Callable[[], None]:
        return self._pubsub.subscribe(topic, callback, fps_limit=fps_limit)

    # Convenience for UI
    @property
    def rx(self) -> RxConfig:
        return self._rx

    @property
    def connected(self) -> tuple[str, Optional[str]]:
        return self._connected_driver, self._connected_device_id
