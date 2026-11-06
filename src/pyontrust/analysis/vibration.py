"""Vibration analysis for motors and rolling-element bearings.

Time-domain severity metrics, Welch PSD (pure-numpy), dominant-peak picking,
bearing defect-line computation (BPFO / BPFI / FTF) from bearing geometry,
defect-line energy detection with harmonics, envelope (demodulation) spectrum
for early-stage fault signatures, and ISO 20816-style RMS-velocity zone
classification.

Requires numpy (``pyontrust[analysis]``). No scipy needed — the Welch PSD and
Hilbert transform are implemented directly on top of numpy FFTs so the module
works in minimal environments.

Typical use::

    from pyontrust.analysis.vibration import (
        BearingGeometry, bearing_defect_lines, analyze_vibration)

    geo = BearingGeometry("6204", d_ball_mm=8.5, pitch_dia_mm=33.5, n_balls=9)
    report = analyze_vibration(x, fs=10240.0, shaft_rpm=1800.0, geometry=geo)
    print(report["fault_lines"], report["zone"])

Bearing defect frequency formulas (outer race stationary, classic rigid-ring
model; see e.g. Randall, *Vibration-Based Condition Monitoring*):

    gamma = (d / Dp) * cos(alpha)
    BPFO  = (N/2) * f_r * (1 - gamma)     outer-race defect
    BPFI  = (N/2) * f_r * (1 + gamma)     inner-race defect
    FTF   =      f_r * (1 - gamma) / 2    cage / ball-pass frequency

where ``f_r`` is shaft rotational frequency, ``N`` the number of balls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

__all__ = [
    "BearingGeometry",
    "bearing_defect_lines",
    "time_metrics",
    "psd_welch",
    "dominant_peaks",
    "envelope_spectrum",
    "detect_bearing_faults",
    "iso20816_zone",
    "analyze_vibration",
]


# ── bearing geometry ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BearingGeometry:
    """Rolling-element bearing dimensions (SI-adjacent, mm).

    Parameters
    ----------
    name:
        Free-form label (e.g. ``"6204"``).
    d_ball_mm:
        Rolling element (ball/roller) diameter.
    pitch_dia_mm:
        Pitch circle diameter (center-to-center of the rolling elements).
    n_balls:
        Number of rolling elements.
    contact_angle_deg:
        Contact angle; 0 for deep-groove radial bearings.
    """

    name: str
    d_ball_mm: float
    pitch_dia_mm: float
    n_balls: int
    contact_angle_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.d_ball_mm <= 0 or self.pitch_dia_mm <= 0 or self.n_balls < 2:
            raise ValueError("bearing geometry must be positive with n_balls >= 2")

    @property
    def gamma(self) -> float:
        """Dimensionless ratio (d/Dp)*cos(alpha)."""
        return (self.d_ball_mm / self.pitch_dia_mm) * math.cos(
            math.radians(self.contact_angle_deg))


#: Common lab/motor bearings. Ball diameters are typical catalog values and
#: vary slightly between manufacturers — treat defect lines as ±5 % unless you
#: have the exact datasheet geometry (override with your own BearingGeometry).
COMMON_BEARINGS: dict[str, BearingGeometry] = {
    "608":  BearingGeometry("608", d_ball_mm=3.175, pitch_dia_mm=15.0, n_balls=9),
    "6204": BearingGeometry("6204", d_ball_mm=8.5,   pitch_dia_mm=33.5, n_balls=9),
    "6305": BearingGeometry("6305", d_ball_mm=10.16, pitch_dia_mm=41.0, n_balls=8),
}


def bearing_defect_lines(geo: BearingGeometry, shaft_rpm: float) -> dict[str, float]:
    """Defect frequencies (Hz) for a given shaft speed.

    Returns ``{"BPFO": ..., "BPFI": ..., "FTF": ...}``.
    """
    if shaft_rpm < 0:
        raise ValueError("shaft_rpm must be >= 0")
    f_r = shaft_rpm / 60.0
    g = geo.gamma
    return {
        "shaft_hz": f_r,
        "BPFO": (geo.n_balls / 2.0) * f_r * (1.0 - g),
        "BPFI": (geo.n_balls / 2.0) * f_r * (1.0 + g),
        "FTF":  f_r * (1.0 - g) / 2.0,
    }


# ── time-domain metrics ─────────────────────────────────────────────────────

def _as_1d(x: Sequence[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("x must be a 1-D signal")
    if arr.size < 4:
        raise ValueError("need at least 4 samples")
    if arr.size < 8:
        raise ValueError("need at least 8 samples")
    return arr


def time_metrics(x: Sequence[float] | np.ndarray, fs: float) -> dict[str, float]:
    """Basic severity metrics of a vibration signal.

    Returns rms / peak / p2p (in input units), crest factor and kurtosis
    (Gaussian reference = 3). ``fs`` is accepted for API symmetry with the
    frequency-domain helpers; it does not affect these statistics.
    """
    if fs <= 0:
        raise ValueError("fs must be > 0")
    x0 = _as_1d(x)
    a = x0 - float(np.mean(x0))
    rms = math.sqrt(float(np.mean(a ** 2)))
    peak = float(np.max(np.abs(a)))
    p2p = float(np.max(a) - np.min(a))
    m4 = float(np.mean(a ** 4)) / (rms ** 4) if rms > 0 else float("nan")
    return {
        "rms": rms,
        "peak": peak,
        "p2p": p2p,
        "crest_factor": peak / rms if rms > 0 else float("inf"),
        "kurtosis": m4,
        "n_samples": int(a.size),
    }


# ── frequency domain (pure numpy) ───────────────────────────────────────────

def psd_welch(x: Sequence[float] | np.ndarray, fs: float,
              nperseg: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """One-sided Welch PSD (Hann window, 50 % overlap).

    Returns ``(freq_hz, Pxx)`` with units of input^2/Hz. Pure numpy — no scipy.
    """
    if fs <= 0:
        raise ValueError("fs must be > 0")
    a = _as_1d(x)
    n = a.size
    seg = int(nperseg) if nperseg else min(256, max(16, (n // 4) or 16))
    seg = min(seg, n)
    win = np.hanning(seg)
    step = seg // 2
    n_seg = max(1, (n - seg) // step + 1)

    wsum = float(np.sum(win ** 2))
    Pxx = np.zeros(seg // 2 + 1)
    for i in range(n_seg):
        chunk = a[i * step: i * step + seg] * win
        if chunk.size < seg:
            break
        sp = np.fft.rfft(chunk)
        Pxx += (sp * np.conj(sp)).real / (fs * wsum)
    Pxx /= n_seg                                   # Welch: average over segments
    if seg % 2 == 0:                               # one-sided PSD: double interior bins
        Pxx[1:-1] *= 2.0
    else:
        Pxx[1:] *= 2.0
    freqs = np.fft.rfftfreq(n_seg and seg, d=1.0 / fs)
    return freqs, Pxx


def dominant_peaks(freqs: np.ndarray, pxx: np.ndarray, top_n: int = 5,
                   min_freq: float = 0.5) -> list[tuple[float, float]]:
    """Top ``top_n`` peaks (freq_hz, density) above ``min_freq``, local maxima."""
    order = np.argsort(pxx)[::-1]
    out: list[tuple[float, float]] = []
    for i in order:
        if len(out) >= top_n:
            break
        f = float(freqs[i])
        if f < min_freq or not (0 < i < len(pxx) - 1):
            continue
        if pxx[i] <= pxx[i - 1] or pxx[i] <= pxx[i + 1]:
            continue
        out.append((f, float(pxx[i])))
    return sorted(out)[:top_n]


def envelope_spectrum(x: Sequence[float] | np.ndarray, fs: float,
                      band: tuple[float, float] = (50.0, 2000.0),
                      nperseg: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Envelope (demodulation) spectrum for early bearing-fault detection.

    Band-passes ``x`` to ``band`` via FFT filtering, takes the analytic-signal
    amplitude (Hilbert), then Welch-PSDs that envelope. Fault impacts modulate
    a structural resonance; the modulation sidebands appear in this low-rate
    spectrum at BPFO/BPFI/FTF and their harmonics.
    """
    if band[0] <= 0 or band[1] > fs / 2:
        raise ValueError("band must satisfy 0 < lo < hi <= fs/2")
    a = _as_1d(x)
    n = a.size
    X = np.fft.rfft(a * np.hanning(n))
    freqs_full = np.fft.rfftfreq(n, d=1.0 / fs)
    mask = (freqs_full >= band[0]) & (freqs_full <= band[1])
    Xb = np.where(mask, X, 0.0)
    xb = np.fft.irfft(Xb, n=n)

    # Hilbert transform via FFT (full-length analytic signal).
    H = np.zeros(n // 2 + 1)
    if n % 2 == 0:
        H[0] = H[n // 2] = 1.0
        H[1:n // 2] = 2.0
    else:
        H[0] = 1.0
        H[1:(n + 1) // 2] = 2.0
    env = np.abs(np.fft.irfft(Xb * H, n=n))

    f_env, p_env = psd_welch(env, fs, nperseg=nperseg or min(512, max(64, n // 8)))
    return f_env, p_env


# ── bearing fault detection ─────────────────────────────────────────────────

def detect_bearing_faults(x: Sequence[float] | np.ndarray, fs: float,
                          geo: BearingGeometry, shaft_rpm: float,
                          harmonics: int = 3, rel_tol_hz: float = 0.5) -> dict[str, Any]:
    """Score energy at each defect line (and its first ``harmonics``).

    For every candidate frequency ``k*f_defect`` a peak is searched in the PSD
    within ±``rel_tol_hz`` Hz; the score is the peak height relative to the
    median of the surrounding 10-bin noise floor. A line is flagged when any
    harmonic scores >= 6 (≈ 7.8 dB above local floor).

    Returns per-line dicts plus an overall ``suspected_faults`` list.
    """
    lines = bearing_defect_lines(geo, shaft_rpm)
    result: dict[str, Any] = {}
    suspected: list[str] = []

    defect_labels = [k for k in lines if not k.endswith("_hz")]
    f_min_line = min((float(lines[k]) for k in defect_labels), default=fs / 2.0)

    # Resolution: keep the bin width well below the lowest defect line so each
    # candidate gets its own search window (>= 4 bins per line).
    nperseg = int(min(len(x), max(256, math.ceil(4.0 * fs / max(f_min_line, 1e-9)))))
    f, pxx = psd_welch(x, fs, nperseg=nperseg)
    binw = float(f[1] - f[0]) if len(f) > 1 else 0.0
    tol = max(rel_tol_hz, 0.5 * binw + 1e-9)

    # Defect harmonics that alias a shaft-order component (k·shaft_freq) are
    # indistinguishable from normal machine tones — exclude them.  The exclusion
    # band is one Hann main-lobe half-width (2 bins): closer components cannot be
    # resolved apart, so the candidate carries no independent fault evidence.
    shaft_hz = float(lines.get("shaft_hz") or shaft_rpm / 60.0)
    collision_tol = max(rel_tol_hz, 2.0 * binw + 1e-9)

    def _collides_with_shaft_order(freq: float) -> bool:
        if shaft_hz <= 0:
            return False
        for k in range(1, int(fs // shaft_hz) + 2):
            if abs(k * shaft_hz - freq) < collision_tol:
                return True
        return False

    # A flagged line must be an independent spectral component: at least this
    # fraction of the strongest line in the spectrum (sidelobe leakage from a
    # strong neighbour never reaches it).
    min_peak_frac = 0.01
    max_pxx = float(pxx.max()) if pxx.size else 0.0

    for label, f0 in ((k, lines[k]) for k in defect_labels):
        best_score, best_k, best_f = 0.0, 1, float(f0)
        best_significant = False
        for k in range(1, harmonics + 1):
            target = k * f0
            if target >= fs / 2:
                break
            if _collides_with_shaft_order(target):
                continue
            lo = max(0, int(np.searchsorted(f, target - tol)))
            hi = min(len(pxx) - 1, int(np.searchsorted(f, target + tol)) + 1)
            if hi <= lo or hi >= len(pxx):
                continue
            window = pxx[lo:hi]
            floor = float(np.median(window))
            peak_i = lo + int(np.argmax(window))
            # local noise floor from bins just outside the search window
            fl_lo = max(0, lo - 10)
            fl_hi = min(len(pxx), hi + 10)
            side = np.concatenate([pxx[fl_lo:lo], pxx[hi:fl_hi]]) if (hi > lo) else window
            floor_local = float(np.median(side)) if side.size else floor
            score = float(window.max()) / max(floor_local, 1e-30)
            significant = float(window.max()) >= min_peak_frac * max_pxx
            if score > best_score:
                best_score, best_k, best_f, best_significant = score, k, target, significant
        flagged = best_score >= 6.0 and best_significant
        result[label] = {
            "freq_hz": round(float(f0), 2),
            "best_harmonic": int(best_k),
            "peak_at_hz": round(float(best_f), 2),
            "score_vs_floor": round(best_score, 1),
            "flagged": bool(flagged),
        }
        if flagged:
            suspected.append(label)

    result["suspected_faults"] = suspected
    return result


# ── severity zoning (ISO 20816-style, approximate) ──────────────────────────

#: RMS velocity thresholds in mm/s — ISO 20816-3 group II style boundaries.
#: These are screening values for general-purpose machinery; use the full
#: standard's tables (machine class + speed band) for acceptance testing.
_ISO_ZONES_MM_S = [(7.1, "A"), (18.0, "B"), (45.0, "C")]


def iso20816_zone(rms_velocity_mm_s: float) -> str:
    """Map RMS velocity (mm/s) to an ISO 20816-style zone A/B/C/D."""
    if rms_velocity_mm_s < 0:
        raise ValueError("rms_velocity_mm_s must be >= 0")
    for limit, zone in _ISO_ZONES_MM_S:
        if rms_velocity_mm_s <= limit:
            return zone
    return "D"


# ── one-shot report ─────────────────────────────────────────────────────────

def analyze_vibration(x: Sequence[float] | np.ndarray, fs: float,
                      shaft_rpm: float | None = None,
                      geometry: BearingGeometry | str | None = None,
                      accel_sensitivity_g_per_unit: float = 1.0) -> dict[str, Any]:
    """Full vibration report for a motor/bearing measurement.

    Parameters
    ----------
    x:
        Acceleration (or velocity) samples.
    fs:
        Sample rate in Hz.
    shaft_rpm:
        Shaft speed — enables defect-line analysis when given with ``geometry``.
    geometry:
        BearingGeometry, or a name from :data:`COMMON_BEARINGS` (e.g. ``"6204"``).
    accel_sensitivity_g_per_unit:
        Scale factor converting raw units to g (default 1 = already in g), so
        the ISO zone uses mm/s RMS velocity via v_rms = a_rms/(2πf) — here we
        approximate with the low-frequency content; treat the zone as screening.

    Returns a JSON-serialisable dict: time metrics, dominant peaks, optional
    bearing fault scores and an ISO-style zone (when input is acceleration in g).
    """
    if fs <= 0:
        raise ValueError("fs must be > 0")
    report: dict[str, Any] = {
        "time": time_metrics(x, fs),
        "dominant_peaks": [
            {"freq_hz": round(f, 2), "density": float(p)} for f, p in
            dominant_peaks(*psd_welch(x, fs))
        ],
    }

    if shaft_rpm is not None and geometry is not None:
        geo = (COMMON_BEARINGS[geometry] if isinstance(geometry, str) else geometry)
        report["bearing"] = {
            "name": geo.name,
            "shaft_rpm": float(shaft_rpm),
            **detect_bearing_faults(x, fs, geo, shaft_rpm),
        }

    # ISO-style zone: convert g-RMS to mm/s RMS using the dominant low-freq
    # content as a proxy for the vibration frequency (screening only).
    rms_g = report["time"]["rms"] * accel_sensitivity_g_per_unit
    peaks = report["dominant_peaks"]
    if peaks and rms_g > 0:
        f_dom = min(p["freq_hz"] for p in peaks[:3]) or 1.0
        v_mm_s = (rms_g * 9806.65) / max(2.0 * math.pi * max(f_dom, 1.0), 1e-9)
        report["zone"] = iso20816_zone(v_mm_s)
        report["v_rms_mm_s_approx"] = round(float(v_mm_s), 3)

    return report
