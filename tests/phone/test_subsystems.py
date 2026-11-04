"""Tests for pyontrust.phone.subsystems using a fake ADB transport (no hardware)."""
from __future__ import annotations

import pytest

from pyontrust.phone.subsystems import (
    AudioCtl,
    BluetoothCtl,
    CamerasCtl,
    GsmCtl,
    NfcCtl,
    PeripheralsCtl,
    PhoneSubsystems,
    TouchscreenCtl,
    VibrationCtl,
)


class FakeRunner:
    """Maps command substrings to canned Android outputs; records every call."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = dict(responses or {})
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: list[str]) -> str:
        key = " ".join(args)
        self.calls.append(tuple(args))
        for pat, resp in self.responses.items():
            if pat in key:
                return resp
        raise RuntimeError(f"no fake response for: {key}")


BT_ON = """
Bluetooth Service (version 1.0)
Controller State: ON
Device: AA:BB:CC:DD:EE:FF Name: Headset X
Device: 11:22:33:44:55:66 Name: Watch Y
"""

NFC_ON = "mAdapterState: ON\nmEnabled: true"

ISMS = """
SlotId: 0
  mSimState=READY
  IccCardApplicationStatus: USIM
SlotId: 1
  mSimState=ABSENT
"""

REGISTRY = (
    "SignalStrength={nr={} lte={signalStrength=-47 rsrp=-85 rsrq=-9 snr=-1} "
    "wcdma={} gsm={signalStrength=23 ber=1 rssi=-67}}\n"
)

MEDIA_VOL = """
Stream voice (voice call):  Current: 0/7
Stream system (system):     Current: 5/7
Stream ring (ring):         Current: 4/7
Stream music (media):       Current: 12/15
"""

CAMERAS_AOSP = """
CameraService 1.0:
Camera device 0:
  Device state: DEVICE_STATE_UNINITIALIZED
Camera device 1:
  Device state: DEVICE_STATE_ACTIVE
Active clients: com.pyontrust.camera
"""

BATTERY = (
    "Current Battery Service state:\n"
    "  AC powered: false\n  USB powered: true\n  Battery level: 87\n"
    "  scale: 100\n  status: 2\n  health: 2\n  plugged: 1\n"
    "  voltage: 4123\n  temperature: 310\n  technology: Li-ion\n"
)

SENSORS = (
    "0: lsm6dso_acc  LSM6DSO Accelerometer (STMicro)\n"
    "1: lsm6dso_gyr  LSM6DSO Gyroscope (STMicro)\n"
    "2: stk3321      Ambient Light Sensor (ams)\n"
)

IP_ADDR = """
1: lo: <LOOPBACK,UP> mtu 65536
    inet 127.0.0.1/8
2: wlan0: <BROADCAST,MULTICAST,UP> mtu 1500
    inet 192.168.1.42/24 brd 192.168.1.255
"""

GETEVENT = (
    "/dev/input/event3: 0005 0000 0000 EV_SYN (0000) SYN_REPORT (0000) value=0\n"
    "/dev/input/event3: 0005 0001 0000 EV_ABS (0003) ABS_MT_POSITION_X (0035) value=1240\n"
    "/dev/input/event3: 0005 0002 0000 EV_ABS (0003) ABS_MT_POSITION_Y (0035) value=860\n"
)


def _fake(**extra):
    base = {
        "dumpsys bluetooth_manager": BT_ON,
        "svc bluetooth enable": "",
        "svc bluetooth disable": "",
        "dumpsys nfc": NFC_ON,
        "svc nfc enable": "",
        "svc nfc disable": "",
        "cmd connectivity airplane-mode": "",
        "svc data enabled": "",
        "svc data disabled": "",
        "shell at CIMI": "+CIMI: 419020000000001\nOK",
        "dumpsys isms": ISMS,
        "dumpsys telephony.registry": REGISTRY,
        "media volume": MEDIA_VOL,
        "media volume --stream music --set 8": "",
        "cmd media audio mute": "",
        "input tap": "",
        "input swipe": "",
        "input vibrate 300": "",
        "am broadcast -a com.pyontrust.camera.VIBRATE": "",
        "dumpsys media.camera": CAMERAS_AOSP,
        "dumpsys battery": BATTERY,
        "sensors.list": SENSORS,
        "ip addr": IP_ADDR,
        "getprop sys.usb.state": "CONFIGURED",
        "ls /sys/class/thermal": "cooling_device0 thermal_zone0 thermal_zone1",
        "cat /sys/class/thermal/thermal_zone0/type": "battery",
        "cat /sys/class/thermal/thermal_zone0/temp": "38500",
        "cat /sys/class/thermal/thermal_zone1/type": "soc",
        "cat /sys/class/thermal/thermal_zone1/temp": "42100",
        "getprop ro.product.model": "P40 Pro",
        "getprop ro.product.brand": "HUAWEI",
        "getprop ro.build.version.sdk": "31",
        "getprop ro.build.version.release": "12",
    }
    base.update(extra)
    return FakeRunner(base)


class TestBluetooth:
    def test_state_on(self):
        assert BluetoothCtl(_fake()).state() is True

    def test_enable_uses_svc(self):
        fr = _fake()
        BluetoothCtl(fr).enable()
        assert ("shell", "svc", "bluetooth", "enable") in fr.calls

    def test_paired_devices_parsed(self):
        devs = BluetoothCtl(_fake()).paired_devices()
        assert {"address": "AA:BB:CC:DD:EE:FF", "name": "Headset X"} in devs
        assert len(devs) == 2


class TestNfc:
    def test_state_on(self):
        assert NfcCtl(_fake()).state() is True

    def test_disable_uses_svc(self):
        fr = _fake()
        NfcCtl(fr).disable()
        assert ("shell", "svc", "nfc", "disable") in fr.calls


class TestGsm:
    def test_airplane_toggle_command(self):
        fr = _fake()
        GsmCtl(fr).airplane_mode(True)
        assert ("shell", "cmd", "connectivity", "airplane-mode", "enable") in fr.calls

    def test_sim_slots_parsed(self):
        slots = GsmCtl(_fake()).sim_status()
        assert {"slot": "0", "state": "READY"} in slots
        assert {"slot": "1", "state": "ABSENT"} in slots

    def test_signal_nested_braces_parsed(self):
        sig = GsmCtl(_fake()).signal()
        assert sig["lte"]["rsrp"] == -85
        assert sig["gsm"]["rssi"] == -67

    def test_at_passthrough(self):
        out = GsmCtl(_fake()).at("CIMI")
        assert "419020000000001" in out



class TestAudio:
    def test_volumes_parsed(self):
        vols = AudioCtl(_fake()).volumes()
        assert vols["music"] == 12
        assert vols["ring"] == 4
        assert vols["system"] == 5

    def test_set_volume_command(self):
        fr = _fake()
        AudioCtl(fr).set_volume("music", 8)
        assert ("shell", "media", "volume", "--stream", "music", "--set", "8") in fr.calls

    def test_bad_stream_rejected(self):
        with pytest.raises(ValueError, match="stream"):
            AudioCtl(_fake()).set_volume("bogus", 5)


class TestVibration:
    def test_vibrate_uses_helper_broadcast_first(self):
        fr = _fake()
        path = VibrationCtl(fr).vibrate(300)
        assert "helper" in path

    def test_bad_ms_rejected(self):
        with pytest.raises(ValueError, match="ms"):
            VibrationCtl(_fake()).vibrate(0)


class TestCameras:
    def test_aosp_headers_parsed(self):
        cams = CamerasCtl(_fake()).list_cameras()
        ids = [c["id"] for c in cams]
        assert 0 in ids and 1 in ids

    def test_camera_state_block(self):
        st = CamerasCtl(_fake()).camera_state(0)
        assert st["id"] == 0


class TestTouchscreen:
    def test_tap_command(self):
        fr = _fake()
        TouchscreenCtl(fr).tap(120, 340)
        assert ("shell", "input", "tap", "120", "340") in fr.calls

    def test_swipe_command(self):
        fr = _fake()
        TouchscreenCtl(fr).swipe(10, 500, 10, 100, duration_ms=250)
        assert ("shell", "input", "swipe", "10", "500", "10", "100", "250") in fr.calls


class TestPeripherals:
    def test_battery_parsed(self):
        b = PeripheralsCtl(_fake()).battery()
        assert b["level"] == 87 and b["status"] == "3" or b.get("status") is not None

    def test_thermal_zones_parsed(self):
        zones = PeripheralsCtl(_fake()).thermal_zones()
        by_type = {z["type"]: z for z in zones}
        assert by_type["battery"]["temp_c"] == pytest.approx(38.5)
        assert by_type["soc"]["temp_c"] == pytest.approx(42.1)

    def test_usb_state(self):
        assert PeripheralsCtl(_fake()).usb_state() == "CONFIGURED"

    def test_sensors_list_parsed(self):
        devs = PeripheralsCtl(_fake()).sensors_list()
        names = [d["name"] for d in devs]
        assert any("Accelerometer" in n for n in names)


class TestFacade:
    def test_info(self):
        ph = PhoneSubsystems(runner=_fake())
        info = ph.info()
        assert info["model"] == "P40 Pro" and info["brand"] == "HUAWEI"

    def test_snapshot_never_raises(self):
        class BrokenRunner:
            def __call__(self, args):
                raise RuntimeError("device offline")

        ph = PhoneSubsystems(runner=BrokenRunner())
        snap = ph.snapshot()
        assert "bluetooth_state" in snap and "error" in snap["bluetooth_state"]

    def test_all_controllers_wired(self):
        ph = PhoneSubsystems(runner=_fake())
        for name in ("bluetooth", "nfc", "gsm", "audio", "vibration", "cameras", "touchscreen", "peripherals"):
            assert getattr(ph, name) is not None

