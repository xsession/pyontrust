"""Unit tests: thermal live services (camera arbitration, job, zone stats)."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

import numpy as np
import pytest

from pyontrust.services.thermal_job import MeasurementJob
from pyontrust.services.thermal_live import (CameraArbiter, FrameError, LiveCamera, LiveFeed,
                                             zone_stats)


class FakeCam:
    def __init__(self, value=25.0):
        self.value, self.opened, self.closed = value, 0, 0

    def open(self):
        self.opened += 1

    def close(self):
        self.closed += 1

    def grab_temperature_frame(self):
        return np.full((154, 206), self.value, np.float32)


class FakeTracking:
    def __init__(self, cam=None):
        self.camera = cam
        self.running = cam is not None
        self.lock = threading.Lock()

    @contextmanager
    def exclusive_camera(self):
        if self.camera is None:
            raise RuntimeError("No tracking session active")
        with self.lock:
            yield self.camera


def _live(cams):
    it = iter(cams)
    return LiveCamera(factory=lambda cfg: next(it))


def test_live_camera_reused_and_reopened_after_failure():
    a, b = FakeCam(20), FakeCam(30)
    live = _live([a, b])
    assert live.grab("seek")[0, 0] == 20
    assert live.grab("seek")[0, 0] == 20 and a.opened == 1     # held open
    with pytest.raises(ZeroDivisionError):
        with live.exclusive("seek"):
            raise ZeroDivisionError                             # device-level failure
    assert a.closed == 1 and not live.is_open                    # dropped …
    assert live.grab("seek")[0, 0] == 30                         # … and re-opened
    live.release()
    assert b.closed == 1


def test_arbiter_measurement_owns_camera():
    arb = CameraArbiter(_live([FakeCam()]), FakeTracking(), lambda: True)
    with pytest.raises(FrameError) as ei:
        arb.display_frame()
    assert ei.value.status == 409 and ei.value.busy


def test_arbiter_lends_tracking_camera():
    tcam = FakeCam(42)
    arb = CameraArbiter(_live([]), FakeTracking(tcam), lambda: False)
    frame, source = arb.display_frame()
    assert source == "tracking" and frame[0, 0] == 42


def test_arbiter_translates_open_failure_but_not_caller_errors():
    def boom(cfg):
        raise OSError("usb gone")

    arb = CameraArbiter(LiveCamera(factory=boom), FakeTracking(), lambda: False)
    with pytest.raises(FrameError) as ei:
        arb.display_frame()
    assert ei.value.status == 502 and "usb gone" in str(ei.value)

    arb2 = CameraArbiter(_live([FakeCam()]), FakeTracking(), lambda: False)
    with pytest.raises(KeyError):            # the caller's own bug is not masked
        with arb2.exclusive() as (_cam, _src):
            raise KeyError("route bug")


def test_zone_stats_clipping_and_aliases():
    f = np.zeros((10, 20), np.float32)
    f[2:4, 5:9] = 50.0
    out = zone_stats(f, [
        {"name": "hot", "x": 5, "y": 2, "w": 4, "h": 2},
        {"name": "alias", "x": 5, "y": 2, "width": 4, "height": 2},
        {"name": "edge", "x": 18, "y": 8, "w": 10, "h": 10},   # clipped to 2x2
        {"name": "outside", "x": 50, "y": 50, "w": 3, "h": 3},
        {"name": "bad", "x": "?"},
    ])
    by = {z["name"]: z for z in out}
    assert by["hot"]["mean_c"] == 50.0 and by["alias"] == {**by["hot"], "name": "alias"}
    assert by["edge"]["pixels"] == 4
    assert by["outside"]["pixels"] == 0 and "max_c" not in by["outside"]
    assert "bad" not in by


def test_live_feed_freshness():
    feed = LiveFeed()
    assert feed.frame() is None and not feed.meta()["active"]
    feed.update(np.ones((2, 2)), {"width": 2})
    assert feed.frame() is not None and feed.meta()["ok"]
    feed.set_error("unplugged")
    m = feed.meta()
    assert m["active"] and not m["ok"] and m["error"] == "unplugged"


def test_job_rejects_second_start_and_rolls_back_on_launch_failure(monkeypatch):
    job = MeasurementJob()
    gate = threading.Event()
    monkeypatch.setattr(job, "_run", lambda cfg: (gate.wait(5), setattr(job, "running", False)))
    job.start({"mode": "continuous"})
    assert job.running
    with pytest.raises(RuntimeError):
        job.start({})
    gate.set()
    for _ in range(50):
        if not job.running:
            break
        time.sleep(0.02)
    assert not job.running

    def fail():
        raise OSError("camera busy")

    with pytest.raises(OSError):
        job.start({}, before_launch=fail)
    assert not job.running, "a failed launch must not leave the job marked running"
    assert job.stop() is False


def test_handover_blocks_live_reopen():
    cams = [FakeCam(), FakeCam()]
    live = _live(cams)
    arb = CameraArbiter(live, FakeTracking(), lambda: False)
    arb.display_frame()
    assert live.is_open
    with arb.handover():
        assert not live.is_open, "live camera released for the new owner"
        with pytest.raises(FrameError) as ei:
            arb.display_frame()           # a running stream must not grab it back
        assert ei.value.status == 409 and ei.value.busy
        assert not live.is_open
    arb.display_frame()                   # after the handover the live view works again
    assert live.is_open
