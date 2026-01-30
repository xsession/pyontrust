from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


WindowKind = Literal["hann", "blackman", "flattop"]


@dataclass(frozen=True)
class Measurements:
    vpp: float
    vmin: float
    vmax: float
    mean: float
    vrms: float
    frequency_hz: float | None = None


@dataclass(frozen=True)
class Spectrum:
    freq_hz: np.ndarray  # float32
    mag: np.ndarray  # float32 (linear)


class DspEngine:
    def __init__(self) -> None:
        self._core = None
        try:
            import pyontrust_waveforms_core as core  # built by maturin

            self._core = core
        except Exception:
            self._core = None

    @property
    def has_rust_core(self) -> bool:
        return self._core is not None

    def decimate_envelope(self, samples: np.ndarray, out_len: int) -> tuple[np.ndarray, np.ndarray]:
        s = np.asarray(samples, dtype=np.float32)
        if self._core is not None:
            lo, hi = self._core.decimate_envelope(s, int(out_len))
            return np.asarray(lo, dtype=np.float32), np.asarray(hi, dtype=np.float32)

        # NumPy fallback
        n = len(s)
        out_len = max(1, int(out_len))
        if n == 0:
            return np.zeros(out_len, np.float32), np.zeros(out_len, np.float32)
        edges = np.linspace(0, n, out_len + 1, dtype=np.int64)
        lo = np.empty(out_len, np.float32)
        hi = np.empty(out_len, np.float32)
        for i in range(out_len):
            a, b = int(edges[i]), int(edges[i + 1])
            seg = s[a:b] if b > a else s[a : a + 1]
            lo[i] = float(np.min(seg))
            hi[i] = float(np.max(seg))
        return lo, hi

    def measure_basic(self, samples: np.ndarray, sample_rate_hz: float) -> Measurements:
        s = np.asarray(samples, dtype=np.float32)
        sr = float(sample_rate_hz)
        if self._core is not None:
            m = self._core.measure_basic(s, sr)
            return Measurements(**m)

        if len(s) == 0:
            return Measurements(vpp=0.0, vmin=0.0, vmax=0.0, mean=0.0, vrms=0.0, frequency_hz=None)
        vmin = float(np.min(s))
        vmax = float(np.max(s))
        mean = float(np.mean(s))
        vrms = float(np.sqrt(np.mean(np.square(s))))
        vpp = vmax - vmin
        return Measurements(vpp=vpp, vmin=vmin, vmax=vmax, mean=mean, vrms=vrms, frequency_hz=None)

    def fft_spectrum(self, samples: np.ndarray, sample_rate_hz: float, window: WindowKind = "hann") -> Spectrum:
        s = np.asarray(samples, dtype=np.float32)
        sr = float(sample_rate_hz)
        if self._core is not None:
            spec = self._core.fft_spectrum(s, sr, window)
            return Spectrum(freq_hz=np.asarray(spec["freq_hz"], dtype=np.float32), mag=np.asarray(spec["mag"], dtype=np.float32))

        n = len(s)
        if n <= 1:
            return Spectrum(freq_hz=np.zeros(1, np.float32), mag=np.zeros(1, np.float32))
        if window == "blackman":
            w = np.blackman(n)
        elif window == "flattop":
            # Simple flat-top approximation (fallback)
            w = 1 - 1.93 * np.cos(2 * np.pi * np.arange(n) / (n - 1)) + 1.29 * np.cos(4 * np.pi * np.arange(n) / (n - 1))
        else:
            w = np.hanning(n)
        yf = np.fft.rfft(s * w.astype(np.float32))
        mag = (np.abs(yf) / max(1.0, n)).astype(np.float32)
        freq = np.fft.rfftfreq(n, d=1.0 / sr).astype(np.float32)
        return Spectrum(freq_hz=freq, mag=mag)

    def find_edge_trigger(self, samples: np.ndarray, level: float, hysteresis: float, edge: str) -> int | None:
        s = np.asarray(samples, dtype=np.float32)
        if self._core is not None:
            return self._core.find_edge_trigger(s, float(level), float(hysteresis), str(edge))

        # NumPy fallback
        if len(s) < 2:
            return None
        h = max(1e-9, float(abs(hysteresis)))
        lo = float(level) - h
        hi = float(level) + h
        if edge == "rising":
            armed = False
            for i in range(1, len(s)):
                prev = float(s[i - 1])
                cur = float(s[i])
                if not armed:
                    if prev <= lo:
                        armed = True
                    continue
                if prev < hi and cur >= hi:
                    return i
            return None
        if edge == "falling":
            armed = False
            for i in range(1, len(s)):
                prev = float(s[i - 1])
                cur = float(s[i])
                if not armed:
                    if prev >= hi:
                        armed = True
                    continue
                if prev > lo and cur <= lo:
                    return i
            return None
        return None
