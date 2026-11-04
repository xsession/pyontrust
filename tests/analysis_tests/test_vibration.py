"""Tests for pyontrust.analysis.vibration (motor & bearing vibration analysis)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from pyontrust.analysis.vibration import (
    COMMON_BEARINGS,
    BearingGeometry,
    analyze_vibration,
    bearing_defect_lines,
    detect_bearing_faults,
    dominant_peaks,
    envelope_spectrum,
    iso20816_zone,
    psd_welch,
    time_metrics,
)

FS = 4800.0


def _t(n: int | float, fs: float = FS) -> np.ndarray:
    return np.arange(int(n)) / fs


# ── bearing defect lines ────────────────────────────────────────────────────

def test_defect_lines_6204_at_600rpm():
    """Classic 6204 values at 10 Hz shaft speed (within ±3 %)."""
    lines = bearing_defect_lines(COMMON_BEARINGS["6204"], 600.0)
    assert lines["shaft_hz"] == pytest.approx(10.0, rel=1e-9)
    assert lines["BPFO"] == pytest.approx(33.58, rel=0.03)
    assert lines["BPFI"] == pytest.approx(56.58, rel=0.03)
    assert lines["FTF"] == pytest.approx(3.73, rel=0.03)


def test_defect_lines_scale_linearly_with_speed():
    geo = COMMON_BEARINGS["6204"]
    lo = bearing_defect_lines(geo, 300.0)
    hi = bearing_defect_lines(geo, 900.0)
    for key in ("BPFO", "BPFI", "FTF"):
        assert hi[key] == pytest.approx(3.0 * lo[key], rel=1e-9)


def test_geometry_validation():
    with pytest.raises(ValueError):
        BearingGeometry("bad", d_ball_mm=-1, pitch_dia_mm=20, n_balls=9)
    with pytest.raises(ValueError):
        BearingGeometry("bad", d_ball_mm=5, pitch_dia_mm=20, n_balls=1)


# ── time metrics ────────────────────────────────────────────────────────────

def test_time_metrics_pure_sine():
    t = _t(8 * FS)
    x = 3.0 * np.sin(2 * math.pi * 50.0 * t)
    m = time_metrics(x, FS)
    assert m["rms"] == pytest.approx(3.0 / math.sqrt(2), rel=1e-6)
    assert m["peak"] == pytest.approx(3.0, rel=1e-6)
    assert m["crest_factor"] == pytest.approx(math.sqrt(2), rel=1e-4)
    # sine kurtosis = 1.5 (Gaussian reference is 3)
    assert m["kurtosis"] == pytest.approx(1.5, rel=0.05)


def test_time_metrics_rejects_bad_input():
    with pytest.raises(ValueError):
        time_metrics([1.0, 2.0], FS)          # too short
    with pytest.raises(ValueError):
        time_metrics(np.ones((4, 4)), FS)     # not 1-D
    with pytest.raises(ValueError):
        time_metrics([1.0] * 8, -1.0)


# ── PSD ─────────────────────────────────────────────────────────────────────

def test_psd_welch_peak_location_and_power():
    t = _t(4 * FS)
    x = np.sin(2 * math.pi * 500.0 * t) + 0.1 * np.random.default_rng(7).standard_normal(len(t))
    f, pxx = psd_welch(x, FS)
    peak_f = float(f[np.argmax(pxx)])
    assert peak_f == pytest.approx(500.0, abs=FS / 256 * 1.5)
    # Parseval: integrated PSD ≈ signal power (sine A=1 → 0.5 + noise 0.01)
    total = float(np.sum(pxx)) * (f[1] - f[0])
    assert total == pytest.approx(0.5, rel=0.25)


def test_dominant_peaks_sorted():
    t = _t(4 * FS)
    x = np.sin(2 * math.pi * 100.0 * t) + 0.5 * np.sin(2 * math.pi * 300.0 * t)
    peaks = dominant_peaks(*psd_welch(x, FS), max_peaks=4)
    freqs = [p[0] for p in peaks]
    assert freqs == sorted(freqs, reverse=True)
    assert any(abs(f - 100.0) < 25 for f in freqs)


# ── bearing fault detection ─────────────────────────────────────────────────

def test_detects_synthetic_bpfo_fault():
    """A tone at the BPFO line of a 6204 @ 600 RPM must be flagged."""
    geo = COMMON_BEARINGS["6204"]
    lines = bearing_defect_lines(geo, 600.0)
    t = _t(3 * FS)
    x = (np.sin(2 * math.pi * lines["BPFO"] * t)          # outer-race defect tone
         + 0.3 * np.sin(2 * math.pi * lines["shaft_hz"] * t))
    res = detect_bearing_faults(x, FS, geo, 600.0)
    assert "BPFO" in res["suspected_faults"]


def test_healthy_signal_not_flagged():
    """Only shaft-order content → no defect line should be flagged."""
    geo = COMMON_BEARINGS["6204"]
    t = _t(3 * FS)
    x = (np.sin(2 * math.pi * 10.0 * t)
         + 0.5 * np.sin(2 * math.pi * 20.0 * t))
    res = detect_bearing_faults(x, FS, geo, 600.0)
    assert res["suspected_faults"] == []


def test_envelope_spectrum_runs():
    t = _t(2 * FS)
    x = np.sin(2 * math.pi * 100.0 * t) * (1 + 0.5 * np.sin(2 * math.pi * 7.0 * t))
    f_env, p_env = envelope_spectrum(x, FS)
    assert len(f_env) == len(p_env) > 0
    assert float(np.max(p_env)) > 0


# ── ISO zone + full report ──────────────────────────────────────────────────

def test_iso20816_zone_boundaries():
    assert iso20816_zone(0.5) == "A"
    assert iso20816_zone(7.1) == "A"
    assert iso20816_zone(7.2) == "B"
    assert iso20816_zone(18.0) == "B"
    assert iso20816_zone(18.1) == "C"
    assert iso20816_zone(45.0) == "C"
    assert iso20816_zone(45.1) == "D"
    with pytest.raises(ValueError):
        iso20816_zone(-1.0)


def test_analyze_vibration_full_report_json_serializable():
    geo = COMMON_BEARINGS["6204"]
    lines = bearing_defect_lines(geo, 600.0)
    t = _t(3 * FS)
    x = np.sin(2 * math.pi * lines["BPFO"] * t) + 0.2 * np.random.default_rng(1).standard_normal(len(t))
    report = analyze_vibration(x, FS, shaft_rpm=600.0, geometry="6204")

    assert "time" in report and "dominant_peaks" in report and "bearing" in report
    assert report["bearing"]["name"] == "6204"
    assert "BPFO" in report["bearing"]["suspected_faults"]
    json.dumps(report)  # must be JSON-serializable
