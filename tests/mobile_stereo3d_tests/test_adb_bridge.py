"""ADB/Termux bridge against the real connected device (MWS7N17623000254)."""
import pytest
from mobile_stereo3d import ADBManager, TermuxBridge


@pytest.fixture(scope="module")
def adb():
    return ADBManager()


def test_device_discovery(adb):
    devs = adb.get_connected_devices()
    assert len(devs) >= 1
    d = devs[0]
    assert d.serial and d.transport in ("usb", "tcpip")


def test_shell_roundtrip(adb):
    out = adb.shell("echo", "hello_from_device")
    assert "hello_from_device" in out


def test_push_pull_roundtrip(adb, tmp_path):
    src = tmp_path / "probe.txt"
    src.write_text("pyontrust-mobile-stereo3d-probe")
    remote = "/sdcard/Download/pyontrust_probe.txt"
    adb.push(str(src), remote)
    out = adb.shell("cat", remote)
    assert "probe" in out
    back = tmp_path / "back.txt"
    adb.pull(remote, str(back))
    assert back.read_text() == "pyontrust-mobile-stereo3d-probe"


def test_termux_bridge_probe(adb):
    tb = TermuxBridge(adb)
    avail = tb.termux_available()
    assert isinstance(avail, bool)
