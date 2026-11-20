"""Real hardware only: simulators are test doubles, refused in the product."""
from __future__ import annotations

import struct
import threading

import pytest

from pyontrust.core import simulation_guard as sg


@pytest.fixture()
def product(monkeypatch):
    """Run as the product does (no test opt-in)."""
    monkeypatch.delenv(sg.ENV, raising=False)


def test_guard_switch(monkeypatch):
    assert sg.allowed()                                  # the suite opts in (conftest)
    monkeypatch.delenv(sg.ENV)
    assert not sg.allowed()
    with pytest.raises(sg.SimulationDisabled, match="real hardware only"):
        sg.require("X")


@pytest.mark.parametrize("factory", [
    lambda: __import__("pyontrust.instruments.simulated", fromlist=["x"]).SimulatedPowerMeter(),
    lambda: __import__("pyontrust.instruments.seek_thermal", fromlist=["x"]).SimulatedThermalCamera(),
    lambda: __import__("pyontrust.instruments.aoi_camera", fromlist=["x"]).SimulatedAOICamera(),
    lambda: __import__("pyontrust.instruments.android_sensors", fromlist=["x"]).SimulatedAndroidSensors(),
])
def test_simulators_refused_in_product(product, factory):
    with pytest.raises(sg.SimulationDisabled):
        factory()


def test_profiles_need_an_explicit_driver():
    from pyontrust.core.profiles import _build_instruments

    with pytest.raises(ValueError, match="no 'type'"):
        _build_instruments({"power_meter": {"vdd_mv": 3300}})
    assert _build_instruments({}) == {}


def test_hil_converter_defaults_to_real_drivers():
    from pyontrust.gateway import hil_flowlab_converter as hc

    assert hc._instrument_to_block("power_meter", "") == "ppk2_meter"
    assert hc._instrument_to_block("power_meter", "simulated") == "simulated_power"   # legacy only
    inst = hc._detect_instruments([{"type": "aoi_camera", "params": {}},
                                   {"type": "seek_thermal", "params": {}},
                                   {"type": "sleep_test", "params": {}}])
    assert inst["aoi_camera"]["type"] == "webcam" and inst["seek_thermal"]["type"] == "seek"
    assert inst["power_meter"]["type"] == "ppk2"
    assert hc._detect_instruments([]) == {}


# ── CAN ─────────────────────────────────────────────────────────────────

def test_can_without_adapter_reports_missing(product, monkeypatch):
    from pyontrust.services.can_service import CanDiagService

    monkeypatch.setattr(CanDiagService, "_pcan_userspace_available", classmethod(lambda cls: False))
    monkeypatch.setattr(CanDiagService, "_linux_can_interfaces", staticmethod(lambda: []))
    assert CanDiagService.detect_default() == ("none", "")
    svc = CanDiagService()
    assert "No CAN adapter found" in svc.start("auto")["error"]
    assert "simulation" in svc.start("virtual", "vcan0")["error"]


def test_canopen_master_shares_the_monitor_bus():
    """SDO read/NMT go through the running monitor (one adapter, one bus)."""
    can = pytest.importorskip("can")
    from pyontrust.services.can_service import CanDiagService
    from pyontrust.services.canopen_service import CanopenMaster

    chan = "pyontrust-test-canopen-transport"
    svc = CanDiagService()
    assert svc.start("virtual", chan)["ok"]
    node = can.Bus(interface="virtual", channel=chan)
    stop = threading.Event()

    def slave():                                         # node 5: 0x1000:00 = 0x00020192
        while not stop.is_set():
            m = node.recv(timeout=0.05)
            if m is not None and m.arbitration_id == 0x605 and m.data[0] == 0x40 and len(m.data) == 8:
                node.send(can.Message(arbitration_id=0x585, is_extended_id=False,
                                      data=bytes([0x43, 0x00, 0x10, 0x00]) + struct.pack("<I", 0x00020192)))

    t = threading.Thread(target=slave, daemon=True)
    t.start()
    master = CanopenMaster(transport=svc, timeout_s=1.0)
    try:
        assert master.start()["ok"]
        out = master.sdo_read(5, 0x1000, 0)
        assert out["ok"] and out["value"] == 0x00020192, out
        assert master.nmt_command(5, 0x01)["ok"]
    finally:
        master.stop()
        stop.set()
        t.join(1)
        node.shutdown()
        svc.stop()


def test_canopen_master_needs_a_running_monitor():
    from pyontrust.services.can_service import CanDiagService
    from pyontrust.services.canopen_service import CanopenMaster

    assert "not running" in CanopenMaster(transport=CanDiagService()).start()["error"]
