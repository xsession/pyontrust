import unittest

import numpy as np

from pyontrust_sdr.blocks.processing import FmDemod
from pyontrust_sdr.dsp_core.fir import design_lowpass
from pyontrust_sdr.runtime.pubsub import PubSub


class TestDspVectors(unittest.TestCase):
    def test_lowpass_impulse_sums_to_one(self) -> None:
        h = design_lowpass(cutoff_hz=10_000, sample_rate_hz=200_000, taps=101)
        self.assertAlmostEqual(float(np.sum(h)), 1.0, places=3)

    def test_fm_demod_constant_tone(self) -> None:
        # x[n] = exp(j*w*n) => angle(x[n]*conj(x[n-1])) ~ w
        sr = 200_000
        f = 10_000
        w = 2.0 * np.pi * f / sr
        n = np.arange(4096, dtype=np.float32)
        x = np.exp(1j * w * n).astype(np.complex64)

        fm = FmDemod(); fm.configure({})
        y = fm.process({"iq": x}, sample_rate_hz=float(sr), pubsub=PubSub())
        audio = y["audio"]
        # mean should be near w
        self.assertAlmostEqual(float(np.mean(audio[100:])), float(w), places=2)


if __name__ == "__main__":
    unittest.main()
