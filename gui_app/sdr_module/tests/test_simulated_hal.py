import unittest

import numpy as np

from pyontrust_sdr.hal.simulated import SimulatedHal
from pyontrust_sdr.models import RxConfig


class TestSimulatedHal(unittest.TestCase):
    def test_streams_complex64(self) -> None:
        hal = SimulatedHal()
        hal.open("sim0")
        hal.set_rx_config(RxConfig(sample_rate_hz=1e6))
        hal.start_stream()
        iq = hal.read_iq(4096, timeout_s=0.1)
        hal.stop_stream()
        self.assertEqual(iq.dtype, np.complex64)
        self.assertEqual(len(iq), 4096)


if __name__ == "__main__":
    unittest.main()
