import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

from power_test_framework.instruments.ad3_dwf import Ad3DwfPowerMeter  # noqa: E402


class _FakeDwf:
    def __init__(self) -> None:
        self.closed = False

    def FDwfGetLastErrorMsg(self, buf):
        # buf is a ctypes string buffer
        try:
            buf.value = b""
        except Exception:
            pass
        return 1

    def FDwfDeviceOpen(self, idx, phdwf):
        # phdwf is byref(c_int)
        phdwf._obj.value = 1
        return 1

    def FDwfDeviceClose(self, hdwf):
        self.closed = True
        return 1

    def FDwfAnalogInChannelEnableSet(self, hdwf, ch, en):
        return 1

    def FDwfAnalogInChannelRangeSet(self, hdwf, ch, rng):
        return 1

    def FDwfAnalogInFrequencySet(self, hdwf, hz):
        return 1

    def FDwfAnalogInConfigure(self, hdwf, reconfig, start):
        return 1

    def FDwfAnalogInStatus(self, hdwf, read_data, status):
        return 1

    def FDwfAnalogInStatusSample(self, hdwf, ch, pval):
        # Return distinct voltages per channel: ch0=0.1V, ch1=3.3V
        c = int(getattr(ch, "value", ch))
        v = 0.1 if c == 0 else 3.3
        pval._obj.value = v
        return 1


class TestAd3DwfPowerMeter(unittest.TestCase):
    def test_capture_uses_scaling(self):
        meter = Ad3DwfPowerMeter(
            sample_rate_hz=50.0,
            current_channel=0,
            voltage_channel=1,
            current_a_per_v=2.0,
            voltage_v_per_v=1.0,
            dwf=_FakeDwf(),
        )
        meter.open()
        samples = list(meter.capture(duration_s=0.05))
        meter.close()

        self.assertTrue(samples)
        # first sample should be derived from fake voltages
        self.assertAlmostEqual(samples[0].current_a, 0.1 * 2.0, places=6)
        self.assertAlmostEqual(samples[0].voltage_v, 3.3, places=6)


if __name__ == "__main__":
    unittest.main()
