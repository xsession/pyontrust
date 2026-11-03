"""Shared fixtures: simulated multi-phone microphone rig."""
import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def simulate(mics, source, fs=48000, c=343.0, dur_s=0.5, seed=11, snr_db=20.0):
    """Non-stationary chirp+noise source arriving at each mic with geometric delay."""
    rng = np.random.default_rng(seed)
    n = int(dur_s * fs)
    t = np.arange(n) / fs
    # broadband noise burst: the GCC-PHAT gold-standard test signal (real machine
    # noise is broadband/non-stationary; pure tones/chirps are worst-case ambiguous)
    sig = rng.standard_normal(n)
    wfs = []
    for m in mics:
        lag = int(round(float(np.linalg.norm(source - m)) / c * fs))
        w = np.zeros(n)
        noise = (10 ** (-snr_db / 20.0)) * rng.standard_normal(max(1, n - lag))
        w[lag:] = sig[:n - lag] + noise
        wfs.append(w)
    return wfs


@pytest.fixture(scope="session")
def rig():
    """4-phone array (3 in a plane + 1 lifted) — well-conditioned for 3-D TDOA."""
    mics = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.75, 1.2, 0.0], [0.75, 0.6, 0.8]])
    source = np.array([0.9, -0.6, 1.4])
    return {"mics": mics, "source": source}


@pytest.fixture(scope="session")
def waveforms(rig):
    return simulate(rig["mics"], rig["source"])
