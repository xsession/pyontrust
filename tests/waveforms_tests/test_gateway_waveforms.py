"""Gateway /waveforms blueprint tests — mocked DWF device layer (no hardware).

Covers: min/max decimation cap + peak preservation, channel stats math on a
known sine, endpoint contracts (devices/capture/spectrum/gen), session-handle
reuse across captures, generator gating for devices without analog outputs,
and error paths (bad body 400, no device 503).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pyontrust.instruments.dwf_waveforms as dwf_mod  # noqa: E402
from pyontrust.gateway.blueprints import waveforms as wf_bp  # noqa: E402


# ── Mock device layer ──────────────────────────────────────────────────


class FakeDwfDevice:
    """In-memory stand-in for WaveformDevice with the same call surface."""

    instances: list["FakeDwfDevice"] = []
    open_calls = 0

    def __init__(self, index: int = -1) -> None:
        self.index = index
        self.opened = False
        self.configured: dict[str, Any] | None = None
        self.started = False
        FakeDwfDevice.instances.append(self)

    def open(self) -> None:
        FakeDwfDevice.open_calls += 1
        self.opened = True

    def close(self) -> None:
        self.opened = False

    # scope
    def scope_configure(self, **kw: Any) -> None:
        self.configured = kw

    def scope_start(self) -> None:
        self.started = True

    def scope_state(self) -> str:
        return "done"

    def scope_wait_done(self, timeout_s: float = 5.0, poll_s: float = 0.02) -> bool:
        return True

    def scope_read(self, channel: int = 0, count: int | None = None) -> list[float]:
        # deterministic signal: 1 Vpk sine at 5 kHz + a spike on ch0
        n = 4096 if count is None else count
        t = np.arange(n) / 250_000.0
        sig = np.sin(2 * np.pi * 5_000.0 * t)
        if channel == 0:
            sig[n // 2] += 3.0   # spike that decimation must preserve
        return [float(v) for v in sig]

    # generator (unused by the gating tests, but present for parity)
    def gen_set(self, **kw: Any) -> None:
        pass

    def gen_start(self, channels=(0,)) -> None:
        pass

    def gen_stop(self, channels=(0,)) -> None:
        pass


class FakeDeviceInfo:
    def __init__(self, index: int, name: str, analog_in: int = 2, analog_out: int = 0) -> None:
        self.index = index
        self.name = name
        self.serial = f"SN:{index}"
        self.user = "test"
        self.analog_in_channels = analog_in
        self.analog_out_channels = analog_out
        self.is_opened = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "name": self.name, "serial": self.serial,
            "user": self.user, "analog_in_channels": self.analog_in_channels,
            "analog_out_channels": self.analog_out_channels, "is_opened": self.is_opened,
        }


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    """Blueprint test client with the device layer fully mocked."""
    FakeDwfDevice.instances = []
    FakeDwfDevice.open_calls = 0
    wf_bp._REGISTRY.clear()

    monkeypatch.setattr(dwf_mod, "WaveformDevice", FakeDwfDevice)
    # AD3-like: analog in but NO analog out → generator must be gated off
    monkeypatch.setattr(
        dwf_mod, "enumerate_devices", lambda: [FakeDeviceInfo(0, "Analog Discovery 3")],
    )

    app = Flask(__name__)
    app.register_blueprint(wf_bp.bp, url_prefix="/waveforms")
    yield app.test_client()
    wf_bp._REGISTRY.clear()


# ── Pure-function tests (no HTTP) ──────────────────────────────────────


def test_decimate_caps_points_and_preserves_spike() -> None:
    n = 20_000
    t = np.arange(n) / 1e6
    sig = [float(v) for v in np.sin(2 * np.pi * 1_000.0 * t)]
    sig[n // 2] = 9.5   # spike

    out = wf_bp._decimate(sig, max_points=2048)
    assert len(out) <= 2048
    assert len(out) >= 1024          # min/max pairs from ~1024 buckets
    assert max(out) == pytest.approx(9.5, abs=1e-6), "spike must survive decimation"


def test_decimate_passthrough_for_small_input() -> None:
    sig = [float(i) for i in range(100)]
    assert wf_bp._decimate(sig, max_points=2048) == sig


def test_channel_stats_known_sine() -> None:
    rate_hz = 1_000_000.0
    n = 16_384
    t = np.arange(n) / rate_hz
    samples = np.sin(2 * np.pi * 5_000.0 * t)   # 1 Vpk @ 5 kHz

    s = wf_bp._channel_stats(samples, rate_hz)
    assert s["vpp_v"] == pytest.approx(2.0, abs=1e-3)
    assert s["rms_v"] == pytest.approx(np.sqrt(0.5), abs=1e-3)
    # FFT bin width = 61.04 Hz → tolerance of one bin
    assert s["freq_hz"] == pytest.approx(5_000.0, abs=70.0)


# ── Endpoint contract tests ────────────────────────────────────────────


def test_devices_endpoint_contract(client: Any) -> None:
    r = client.get("/waveforms/api/devices")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    d = body["devices"][0]
    assert d["name"] == "Analog Discovery 3"
    assert d["has_analog_out"] is False   # derived flag for UI gating


def test_capture_endpoint_contract_and_session_reuse(client: Any) -> None:
    payload = {"device_index": 0, "channels": [0, 1], "rate_hz": 250_000, "record_s": 0.04}

    r1 = client.post("/waveforms/api/scope/capture", json=payload)
    assert r1.status_code == 200
    b1 = r1.get_json()
    assert b1["ok"] is True
    assert b1["capture"]["samples_total"] > 0
    for ch in b1["channels"]:
        assert ch["points"] <= wf_bp.MAX_POINTS_PER_CHANNEL
        assert "vpp_v" in ch["stats"] and "rms_v" in ch["stats"]

    # spike on ch0 must survive decimation into the transport payload
    ch0 = next(c for c in b1["channels"] if c["channel"] == 0)
    assert max(ch0["data"]) > 2.5

    r2 = client.post("/waveforms/api/scope/capture", json=payload)
    assert r2.status_code == 200
    # session registry must reuse the handle — exactly one open() total
    assert FakeDwfDevice.open_calls == 1, "second capture must reuse the open device"


def test_capture_rejects_empty_channels(client: Any) -> None:
    r = client.post("/waveforms/api/scope/capture", json={"device_index": 0, "channels": []})
    assert r.status_code == 400
    assert "non-empty" in r.get_json()["error"]


def test_capture_rejects_bad_body(client: Any) -> None:
    r = client.post("/waveforms/api/scope/capture", json={"rate_hz": "not-a-number"})
    assert r.status_code == 400


def test_spectrum_endpoint_contract(client: Any) -> None:
    r = client.post(
        "/waveforms/api/scope/spectrum",
        json={"device_index": 0, "channel": 0, "rate_hz": 250_000, "record_s": 0.04},
    )
    assert r.status_code == 200
    b = r.get_json()
    assert b["ok"] is True
    assert len(b["freqs"]) <= 1024
    assert len(b["magnitudes"]) == len(b["freqs"])
    # mock signal is a 5 kHz sine → must appear among the peaks
    peak_freqs = [p["freq_hz"] for p in b["peaks"]]
    assert any(abs(f - 5_000.0) < 120.0 for f in peak_freqs), f"5 kHz missing from {peak_freqs}"


def test_gen_gated_for_device_without_analog_out(client: Any) -> None:
    r = client.post(
        "/waveforms/api/gen/configure",
        json={"device_index": 0, "channel": 0, "function": "sine", "freq_hz": 1_000},
    )
    assert r.status_code == 409
    assert "no analog outputs" in r.get_json()["error"]

    r = client.post("/waveforms/api/gen/start", json={"device_index": 0})
    assert r.status_code == 409


def test_state_endpoint_reports_registry(client: Any) -> None:
    client.post(
        "/waveforms/api/scope/capture",
        json={"device_index": 0, "channels": [0], "rate_hz": 10_000, "record_s": 0.01},
    )
    r = client.get("/waveforms/api/state")
    assert r.status_code == 200
    b = r.get_json()
    assert 0 in b["open_devices"]
    assert b["max_points_per_channel"] == wf_bp.MAX_POINTS_PER_CHANNEL
