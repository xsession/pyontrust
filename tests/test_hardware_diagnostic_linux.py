"""Hardware Diagnostic on Linux: USB devices found from sysfs, quick tests and live readers.

Uses a fake sysfs tree — no hardware needed.
"""
from __future__ import annotations

import json
import types

import pytest

import pyontrust.services.hardware_discovery as hd


def _usb(root, name, vid, pid, product="", serial="", busnum=1, devnum=5):
    d = root / name
    d.mkdir(parents=True)
    for k, v in {"idVendor": f"{vid:04x}", "idProduct": f"{pid:04x}", "product": product,
                 "serial": serial, "manufacturer": "", "busnum": str(busnum), "devnum": str(devnum)}.items():
        (d / k).write_text(v + "\n")


@pytest.fixture()
def sysfs(tmp_path, monkeypatch):
    usb = tmp_path / "usb"
    usb.mkdir()
    _usb(usb, "1-2.1", 0x1366, 0x0101, "J-Link", "000260118149", devnum=16)
    _usb(usb, "1-2.2", 0x1D50, 0x6089, "HackRF One", "0000000000000000a06063c82255075f", devnum=12)
    _usb(usb, "1-2.3", 0x0C72, 0x000C, "PCAN-USB", "", devnum=9)
    (usb / "1-2.1:1.0").mkdir()                       # interfaces are skipped
    monkeypatch.setattr(hd, "_SYS_USB", str(usb))
    writable = {"/dev/bus/usb/001/016"}               # J-Link yes, HackRF no
    monkeypatch.setattr(hd.os, "access", lambda p, m: p in writable)
    return tmp_path


def test_usb_devices_from_sysfs(sysfs):
    devs = {d["path"]: d for d in hd._usb_devices()}
    assert set(devs) == {"1-2.1", "1-2.2", "1-2.3"}
    assert devs["1-2.1"]["node"] == "/dev/bus/usb/001/016" and devs["1-2.1"]["writable"] is True
    assert devs["1-2.2"]["writable"] is False


def test_jlink_and_hackrf_found_without_vendor_tools(sysfs, monkeypatch):
    monkeypatch.setattr(hd.shutil, "which", lambda name: None)
    jl = hd._probe_jlink()
    assert jl[0]["status"] == "ok" and jl[0]["details"]["serial"] == "260118149"
    rf = hd._probe_hackrf()
    assert rf[0]["status"] == "error" and "udev" in rf[0]["error"]
    assert rf[0]["details"]["vid_pid"] == "1D50:6089"          # still identified
    assert hd._test_hackrf(rf[0])["passed"] is False


def test_pcan_via_socketcan(sysfs, monkeypatch, tmp_path):
    net = tmp_path / "net" / "can0"
    (net / "statistics").mkdir(parents=True)
    (net / "type").write_text("280\n")
    (net / "operstate").write_text("down\n")
    for k in ("rx_packets", "tx_packets", "rx_errors", "tx_errors"):
        (net / "statistics" / k).write_text("0\n")
    drv = tmp_path / "drivers" / "peak_usb"
    drv.mkdir(parents=True)
    dev = tmp_path / "usbif" / "1-2.3:1.0"
    dev.mkdir(parents=True)
    (dev / "driver").symlink_to(drv)
    (net / "device").symlink_to(dev)
    monkeypatch.setattr(hd, "_SYS_NET", str(tmp_path / "net"))
    monkeypatch.setattr(hd, "_IS_WINDOWS", False)

    r = hd._probe_pcan()[0]
    assert r["status"] == "ok" and r["details"]["channel"] == "can0" and r["details"]["model"] == "PCAN-USB"
    t = hd._test_pcan(r)
    assert t["passed"] and "ip link set can0 up" in t["message"]

    from pyontrust.services import diag_live
    reader = diag_live.open_reader("pcan", "bus", r["details"])
    (net / "statistics" / "rx_packets").write_text("50\n")
    out = reader.read()
    assert out["rx_fps"] > 0 and out["state"] == "down" and "note" in out


def test_legacy_ttyS_slots_are_hidden(monkeypatch):
    import serial.tools.list_ports as lp

    fake = [types.SimpleNamespace(device="/dev/ttyS4", description="n/a", hwid="n/a", vid=None, pid=None,
                                  manufacturer=None, product=None, serial_number=None),
            types.SimpleNamespace(device="/dev/ttyACM0", description="PPK2", hwid="USB VID:PID=1915:C00A",
                                  vid=0x1915, pid=0xC00A, manufacturer="Nordic", product="PPK2",
                                  serial_number="X")]
    monkeypatch.setattr(lp, "comports", lambda: fake)
    monkeypatch.setattr(hd, "_IS_WINDOWS", False)
    names = [r["name"] for r in hd._probe_serial_ports()]
    assert names == ["PPK2 (/dev/ttyACM0)"]


def test_ppk2_data_port_is_the_lower_usb_interface(monkeypatch):
    import serial.tools.list_ports as lp

    mk = lambda dev, loc: types.SimpleNamespace(device=dev, location=loc, vid=0x1915, pid=0xC00A,  # noqa: E731
                                               serial_number="SN", description="PPK2", product="PPK2")
    monkeypatch.setattr(lp, "comports", lambda: [mk("/dev/ttyACM0", "1-2.2:1.3"), mk("/dev/ttyACM1", "1-2.2:1.1")])
    d = hd._probe_ppk2()[0]["details"]
    assert d["port"] == "/dev/ttyACM1" and d["control_port"] == "/dev/ttyACM0"


def test_jlink_quick_test_reports_firmware_and_target(monkeypatch):
    import pyontrust.instruments.jlink_usb as ju

    class Fake:
        def __init__(self, serial=""):
            self.serial = serial

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def firmware(self):
            return "J-Link V10 compiled Jan 30 2023"

        def hw_status(self):
            return {"vtarget_v": 3.31}

    monkeypatch.setattr(ju, "JLinkUsb", Fake)
    r = hd._test_jlink({"details": {"vid_pid": "1366:0101", "serial": "260118149"}})
    assert r["passed"] and "V10" in r["message"] and "3.31 V" in r["message"]


@pytest.fixture()
def client():
    from flask import Flask

    import pyontrust.gateway.blueprints.diagnostic as diag

    app = Flask(__name__)
    app.register_blueprint(diag.bp, url_prefix="/diag")
    with app.test_client() as c:
        yield c, diag


def _first_event(resp):
    chunk = next(iter(resp.response))
    return json.loads((chunk.decode() if isinstance(chunk, bytes) else chunk).split("data: ", 1)[1])


def test_channels_cover_every_streamable_device(client):
    c, _ = client
    ch = c.get("/diag/api/live/channels").get_json()
    for t in ("android_sensors", "webcam", "ad3_dwf", "ppk2", "seek_thermal", "jlink", "pcan"):
        assert ch[t] and all({"id", "label", "axes"} <= set(x) for x in ch[t])


def test_webcam_stream_uses_the_card_device(client, monkeypatch):
    import numpy as np

    c, diag = client
    seen = []

    def frame(index):
        seen.append(index)
        return np.full((4, 6, 3), 100, np.uint8)

    monkeypatch.setattr(hd, "webcam_frame", frame)
    resp = c.get("/diag/api/live/stream?hw_type=webcam&sensor=frame&rate_ms=100&dev="
                 + json.dumps({"index": 4, "device": "/dev/video4"}), buffered=False)
    msg = _first_event(resp)
    for stop in list(diag._active_streams.values()):
        stop.set()
    resp.close()
    assert seen == [4] and msg["data"]["brightness"] == 100.0 and msg["data"]["width"] == 6


def test_device_that_cannot_open_ends_the_stream_with_the_reason(client, monkeypatch):
    c, _ = client
    from pyontrust.services import diag_live

    def boom(details):
        raise diag_live.LiveError("J-Link is in use by another program")

    monkeypatch.setattr(diag_live, "_JLink", boom)
    resp = c.get("/diag/api/live/stream?hw_type=jlink&sensor=vtarget&dev={}", buffered=False)
    msg = _first_event(resp)
    resp.close()
    assert msg["fatal"] is True and "in use" in msg["data"]["error"]


def test_ppk2_is_left_alone_while_a_hil_run_uses_it(client, monkeypatch):
    c, diag = client
    from flask import current_app  # noqa: F401

    class Svc:
        def status(self):
            return {"state": "running"}

    c.application.extensions["test_service"] = Svc()
    called = []
    monkeypatch.setattr(hd, "run_quick_test", lambda hw: called.append(hw) or {"passed": True})
    r = c.post("/diag/api/test", json={"type": "ppk2", "details": {"port": "/dev/ttyACM0"}}).get_json()
    assert r["passed"] is False and "HIL" in r["message"] and called == []
    resp = c.get("/diag/api/live/stream?hw_type=ppk2&sensor=current", buffered=False)
    msg = _first_event(resp)
    resp.close()
    assert msg["fatal"] and "HIL" in msg["data"]["error"]
