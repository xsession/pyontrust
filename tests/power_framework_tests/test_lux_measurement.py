"""Tests for parallel lux measurement — webcam + Android light sensor.

Unit tests use synthetic data (no hardware required).
The final integration test opens real webcam + Android sensor and is
guarded by ``@unittest.skipUnless(HAS_WEBCAM, ...)``.

Run all:
    python -m pytest tests/power_framework_tests/test_lux_measurement.py -v

Run only synthetic tests (CI-safe):
    python -m pytest tests/power_framework_tests/test_lux_measurement.py -v -k "not RealHardware"
"""

from __future__ import annotations

import gc
import math
import os
import pathlib
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import numpy as np

from pyontrust.analysis.lux_measurement import (
    LuxCaptureConfig,
    LuxResult,
    SimulatedTorch,
    analyse_parallel_lux,
    brightness_to_lux,
    classify_on_off_regions,
    frame_to_brightness,
    measure_parallel_lux,
)

# ═══════════════════════════════════════════════════════════════════════
#  Helpers: synthetic data generation
# ═══════════════════════════════════════════════════════════════════════


def _make_bright_frame(w: int = 64, h: int = 64, brightness: int = 200) -> np.ndarray:
    """Create a bright BGR frame (torch ON)."""
    frame = np.full((h, w, 3), brightness, dtype=np.uint8)
    return frame


def _make_dark_frame(w: int = 64, h: int = 64, brightness: int = 20) -> np.ndarray:
    """Create a dark BGR frame (torch OFF)."""
    frame = np.full((h, w, 3), brightness, dtype=np.uint8)
    return frame


def _make_synthetic_parallel_data(
    duration_s: float = 18.0,
    webcam_fps: float = 30.0,
    android_rate_hz: float = 10.0,
    n_cycles: int = 3,
    torch_on_s: float = 2.0,
    torch_off_s: float = 2.0,
    pre_capture_s: float = 1.0,
    on_brightness: float = 200.0,
    off_brightness: float = 20.0,
    on_lux_phone: float = 800.0,
    off_lux_phone: float = 50.0,
    noise_std: float = 5.0,
) -> tuple[list[float], list[float], list[float], list[float], list[dict]]:
    """Generate synthetic parallel capture data.

    Returns (webcam_ts, webcam_brightness, android_ts, android_lux, torch_events).
    """
    rng = np.random.default_rng(42)

    # Build torch events
    torch_events = []
    t = pre_capture_s
    for _ in range(n_cycles):
        torch_events.append({"t": t, "state": "ON"})
        t += torch_on_s
        torch_events.append({"t": t, "state": "OFF"})
        t += torch_off_s

    # Webcam series
    n_web = int(duration_s * webcam_fps)
    w_ts = [i / webcam_fps for i in range(n_web)]
    w_br = []
    for ts in w_ts:
        state = "OFF"
        for evt in torch_events:
            if evt["t"] <= ts:
                state = evt["state"]
            else:
                break
        base = on_brightness if state == "ON" else off_brightness
        w_br.append(float(base + rng.normal(0, noise_std)))

    # Android series
    n_and = int(duration_s * android_rate_hz)
    a_ts = [i / android_rate_hz for i in range(n_and)]
    a_lux = []
    for ts in a_ts:
        state = "OFF"
        for evt in torch_events:
            if evt["t"] <= ts:
                state = evt["state"]
            else:
                break
        base = on_lux_phone if state == "ON" else off_lux_phone
        a_lux.append(float(base + rng.normal(0, noise_std * 2)))

    return w_ts, w_br, a_ts, a_lux, torch_events


# ═══════════════════════════════════════════════════════════════════════
#  Test: frame_to_brightness
# ═══════════════════════════════════════════════════════════════════════


class TestFrameToBrightness(unittest.TestCase):
    """Tests for the webcam brightness extraction."""

    def test_bright_frame(self):
        frame = _make_bright_frame(brightness=200)
        br = frame_to_brightness(frame)
        self.assertGreater(br, 150)

    def test_dark_frame(self):
        frame = _make_dark_frame(brightness=10)
        br = frame_to_brightness(frame)
        self.assertLess(br, 30)

    def test_roi_crop(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # Light patch in top-left 20×20
        frame[0:20, 0:20] = 200
        br_full = frame_to_brightness(frame)
        br_roi = frame_to_brightness(frame, roi=(0, 0, 20, 20))
        self.assertGreater(br_roi, br_full * 2)

    def test_gradient_frame(self):
        """Gradient should yield ~middle brightness."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            frame[i, :] = i * 2  # 0 to 198
        br = frame_to_brightness(frame)
        self.assertAlmostEqual(br, 99.0, delta=10)


# ═══════════════════════════════════════════════════════════════════════
#  Test: brightness_to_lux
# ═══════════════════════════════════════════════════════════════════════


class TestBrightnessToLux(unittest.TestCase):
    """Tests for the linear calibration function."""

    def test_default_scale(self):
        lux = brightness_to_lux(100.0)
        self.assertAlmostEqual(lux, 200.0)  # 100 * 2.0 + 0

    def test_custom_scale(self):
        lux = brightness_to_lux(100.0, scale=3.0, offset=10.0)
        self.assertAlmostEqual(lux, 310.0)

    def test_zero_brightness(self):
        lux = brightness_to_lux(0.0)
        self.assertAlmostEqual(lux, 0.0)

    def test_negative_result_clamped(self):
        """Negative offset should be clamped to 0."""
        lux = brightness_to_lux(1.0, scale=1.0, offset=-100.0)
        self.assertEqual(lux, 0.0)

    def test_max_brightness(self):
        lux = brightness_to_lux(255.0, scale=2.0, offset=0.0)
        self.assertAlmostEqual(lux, 510.0)


# ═══════════════════════════════════════════════════════════════════════
#  Test: SimulatedTorch
# ═══════════════════════════════════════════════════════════════════════


class TestSimulatedTorch(unittest.TestCase):
    """Tests for the simulated torch controller."""

    def test_initial_state_off(self):
        t = SimulatedTorch()
        self.assertFalse(t.is_on)

    def test_toggle_on(self):
        t = SimulatedTorch()
        result = t.on()
        self.assertTrue(result)
        self.assertTrue(t.is_on)

    def test_toggle_off(self):
        t = SimulatedTorch()
        t.on()
        t.off()
        self.assertFalse(t.is_on)

    def test_events_recorded(self):
        t = SimulatedTorch()
        t.on()
        time.sleep(0.01)
        t.off()
        events = t.events
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["state"], "ON")
        self.assertEqual(events[1]["state"], "OFF")
        self.assertGreater(events[1]["t"], events[0]["t"])

    def test_multiple_cycles(self):
        t = SimulatedTorch()
        for _ in range(5):
            t.on()
            t.off()
        self.assertEqual(len(t.events), 10)
        self.assertFalse(t.is_on)


# ═══════════════════════════════════════════════════════════════════════
#  Test: classify_on_off_regions
# ═══════════════════════════════════════════════════════════════════════


class TestClassifyOnOff(unittest.TestCase):
    """Tests for ON/OFF region classification."""

    def test_no_events_all_off(self):
        timestamps = [0.0, 1.0, 2.0, 3.0]
        on_idx, off_idx = classify_on_off_regions(timestamps, [])
        self.assertEqual(on_idx, [])
        self.assertEqual(off_idx, [0, 1, 2, 3])

    def test_single_on_event(self):
        timestamps = [0.0, 0.5, 1.0, 1.5, 2.0]
        events = [{"t": 0.8, "state": "ON"}]
        on_idx, off_idx = classify_on_off_regions(timestamps, events)
        # Indices 0, 1 are before ON → OFF; indices 2, 3, 4 are after → ON
        self.assertEqual(off_idx, [0, 1])
        self.assertEqual(on_idx, [2, 3, 4])

    def test_on_off_cycle(self):
        timestamps = [float(i) for i in range(10)]
        events = [
            {"t": 2.0, "state": "ON"},
            {"t": 5.0, "state": "OFF"},
        ]
        on_idx, off_idx = classify_on_off_regions(timestamps, events)
        # t=0,1 → OFF; t=2,3,4 → ON; t=5,6,7,8,9 → OFF
        self.assertEqual(on_idx, [2, 3, 4])
        self.assertEqual(off_idx, [0, 1, 5, 6, 7, 8, 9])

    def test_multiple_cycles(self):
        timestamps = [float(i) * 0.5 for i in range(20)]  # 0.0 to 9.5
        events = [
            {"t": 1.0, "state": "ON"},
            {"t": 3.0, "state": "OFF"},
            {"t": 5.0, "state": "ON"},
            {"t": 7.0, "state": "OFF"},
        ]
        on_idx, off_idx = classify_on_off_regions(timestamps, events)
        total = len(on_idx) + len(off_idx)
        self.assertEqual(total, 20)
        # Samples at t=1.0 to t=2.5 should be ON (indices 2,3,4,5)
        for i in on_idx:
            t = timestamps[i]
            # Should be in [1.0, 3.0) or [5.0, 7.0)
            self.assertTrue(
                (1.0 <= t < 3.0) or (5.0 <= t < 7.0),
                f"Index {i} (t={t}) should be in ON region",
            )


# ═══════════════════════════════════════════════════════════════════════
#  Test: analyse_parallel_lux
# ═══════════════════════════════════════════════════════════════════════


class TestAnalyseParallelLux(unittest.TestCase):
    """Tests for the pure-compute analysis function."""

    def test_basic_analysis(self):
        """Synthetic data with clear ON/OFF should yield positive delta."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data()
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        self.assertTrue(result.ok)
        self.assertIsNone(result.error)

    def test_webcam_lux_delta(self):
        """Webcam should detect a brightness difference between ON and OFF."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data(
            on_brightness=200, off_brightness=20,
        )
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        self.assertIsNotNone(result.webcam_lux_delta)
        self.assertGreater(result.webcam_lux_delta, 100)  # should be ~360

    def test_android_lux_delta(self):
        """Android sensor should detect a lux difference between ON and OFF."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data(
            on_lux_phone=800, off_lux_phone=50,
        )
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        self.assertIsNotNone(result.android_lux_delta)
        self.assertGreater(result.android_lux_delta, 500)  # should be ~750

    def test_high_correlation(self):
        """Two series tracking the same light event should be highly correlated."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data(
            noise_std=2.0,  # low noise for strong correlation
        )
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        self.assertIsNotNone(result.correlation)
        self.assertGreater(result.correlation, 0.8)

    def test_lag_small(self):
        """Synchronised sources should have near-zero lag."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data(
            noise_std=1.0,
        )
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        self.assertIsNotNone(result.lag_ms)
        self.assertLess(abs(result.lag_ms), 500)  # less than 500 ms

    def test_too_few_webcam_frames(self):
        result = analyse_parallel_lux(
            [0.0, 1.0], [100.0, 200.0],
            [0.0, 0.5, 1.0], [300, 300, 300],
            [],
        )
        self.assertFalse(result.ok)
        self.assertIn("Too few webcam", result.error)

    def test_too_few_android_samples(self):
        result = analyse_parallel_lux(
            [0.0, 0.5, 1.0, 1.5, 2.0], [100, 200, 100, 200, 100],
            [0.0], [300],
            [],
        )
        self.assertFalse(result.ok)
        self.assertIn("Too few Android", result.error)

    def test_constant_light_no_delta(self):
        """If torch never toggles, both ON/OFF regions should be similar."""
        # No torch events → all samples classified as OFF
        w_ts = [i * 0.1 for i in range(100)]
        w_br = [100.0 + np.random.normal(0, 2) for _ in range(100)]
        a_ts = [i * 0.2 for i in range(50)]
        a_lux = [300.0 + np.random.normal(0, 2) for _ in range(50)]

        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, [])
        self.assertTrue(result.ok)
        # No ON samples → webcam_lux_mean_on should be None
        self.assertIsNone(result.webcam_lux_mean_on)
        self.assertIsNone(result.android_lux_mean_on)

    def test_summary_dict(self):
        """summary() should return a serialisable dict."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data()
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)
        s = result.summary()

        self.assertIsInstance(s, dict)
        self.assertTrue(s["ok"])
        self.assertIn("webcam_lux_delta", s)
        self.assertIn("correlation", s)
        self.assertIn("lag_ms", s)

    def test_n_cycles_count(self):
        """n_cycles should match the number of ON events."""
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data(n_cycles=5)
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)
        self.assertEqual(result.n_cycles, 5)

    def test_webcam_lux_values_are_scaled(self):
        """Webcam lux should be brightness × scale + offset."""
        w_ts = [0.0, 1.0, 2.0, 3.0, 4.0]
        w_br = [100.0, 100.0, 100.0, 100.0, 100.0]
        a_ts = [0.0, 1.0, 2.0, 3.0]
        a_lux = [200.0, 200.0, 200.0, 200.0]

        result = analyse_parallel_lux(
            w_ts, w_br, a_ts, a_lux, [],
            lux_scale=3.0, lux_offset=5.0,
        )
        # All webcam lux should be 100*3+5 = 305
        for lux_val in result.webcam_lux:
            self.assertAlmostEqual(lux_val, 305.0)


# ═══════════════════════════════════════════════════════════════════════
#  Test: LuxCaptureConfig
# ═══════════════════════════════════════════════════════════════════════


class TestLuxCaptureConfig(unittest.TestCase):
    """Tests for the configuration dataclass."""

    def test_default_values(self):
        cfg = LuxCaptureConfig()
        self.assertEqual(cfg.device_index, 0)
        self.assertEqual(cfg.n_cycles, 3)
        self.assertEqual(cfg.torch_on_s, 3.0)
        self.assertEqual(cfg.android_mode, "simulated")

    def test_frozen(self):
        cfg = LuxCaptureConfig()
        with self.assertRaises(AttributeError):
            cfg.n_cycles = 10  # type: ignore

    def test_custom_config(self):
        cfg = LuxCaptureConfig(
            n_cycles=5,
            torch_on_s=1.0,
            torch_off_s=2.0,
            lux_scale=3.5,
            android_mode="adb",
        )
        self.assertEqual(cfg.n_cycles, 5)
        self.assertEqual(cfg.lux_scale, 3.5)
        self.assertEqual(cfg.android_mode, "adb")


# ═══════════════════════════════════════════════════════════════════════
#  Test: LuxResult
# ═══════════════════════════════════════════════════════════════════════


class TestLuxResult(unittest.TestCase):
    """Tests for the result dataclass."""

    def test_default_is_not_ok(self):
        r = LuxResult()
        self.assertFalse(r.ok)

    def test_summary_includes_error(self):
        r = LuxResult(ok=False, error="Something went wrong")
        s = r.summary()
        self.assertIn("error", s)
        self.assertEqual(s["error"], "Something went wrong")

    def test_summary_without_error(self):
        r = LuxResult(ok=True, capture_duration_s=10.0)
        s = r.summary()
        self.assertNotIn("error", s)
        self.assertEqual(s["capture_duration_s"], 10.0)


# ═══════════════════════════════════════════════════════════════════════
#  Test: Report generation for lux measurement
# ═══════════════════════════════════════════════════════════════════════


class TestLuxReport(unittest.TestCase):
    """Tests for the lux-measurement report builder."""

    def test_report_from_synthetic_data(self):
        from pyontrust.analysis.test_report import ReportBuilder
        from pyontrust.analysis.lux_measurement import analyse_parallel_lux

        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data()
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        rb = ReportBuilder(
            title="Parallel Lux Measurement Report",
            dut="Webcam + Android",
        )
        rb.set_verdict(passed=result.ok, message="Lux measurement complete")
        rb.add_section_kv("Results", {
            "Webcam Δlux": f"{result.webcam_lux_delta:.1f}" if result.webcam_lux_delta else "—",
            "Android Δlux": f"{result.android_lux_delta:.1f}" if result.android_lux_delta else "—",
            "Correlation": f"{result.correlation:.4f}" if result.correlation is not None else "—",
        })

        if result.webcam_timestamps and result.webcam_lux:
            rb.add_section_chart(
                "Webcam Estimated Lux",
                result.webcam_timestamps, result.webcam_lux,
                x_label="Time (s)", y_label="Lux",
            )

        html = rb.render()
        self.assertIn("Parallel Lux", html)
        self.assertIn("--bg: #1e1e2e", html)  # Catppuccin CSS
        self.assertIn("<svg", html)  # SVG chart

    def test_build_lux_report_convenience(self):
        """Test the build_lux_report convenience function."""
        from pyontrust.analysis.lux_report import build_lux_report

        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data()
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_reports")
        path = build_lux_report(
            result,
            output_dir=out_dir,
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1024)

        # Read and check HTML content
        html = path.read_text(encoding="utf-8")
        self.assertIn("Parallel Lux", html)
        self.assertIn("<svg", html)  # has charts
        self.assertIn("application/json", html)  # has embedded data

        # Cleanup
        try:
            path.unlink()
        except PermissionError:
            pass

    def test_report_with_failed_result(self):
        from pyontrust.analysis.lux_report import build_lux_report

        result = LuxResult(ok=False, error="Webcam not found")
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_reports")
        path = build_lux_report(result, output_dir=out_dir)

        self.assertTrue(path.exists())
        html = path.read_text(encoding="utf-8")
        self.assertIn("FAIL", html)
        self.assertIn("Webcam not found", html)

        try:
            path.unlink()
        except PermissionError:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  Test: Diagnostic blueprint routes (lux)
# ═══════════════════════════════════════════════════════════════════════


class TestDiagnosticLuxRoutes(unittest.TestCase):
    """Test the lux measurement API endpoint."""

    @classmethod
    def setUpClass(cls):
        # Lazy import to avoid gateway dep in pure-analysis tests
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
        from pyontrust.gateway.app import create_app
        cls._app = create_app()
        cls._app.config["TESTING"] = True

    def test_lux_measure_endpoint_exists(self):
        with self._app.test_client() as c:
            # POST with simulated mode (no real hardware)
            resp = c.post("/diag/api/lux_measure", json={
                "android_mode": "simulated",
                "n_cycles": 1,
                "torch_on_s": 0.3,
                "torch_off_s": 0.3,
                "pre_capture_s": 0.1,
                "duration_s": 1.0,
            })
            self.assertIn(resp.status_code, [200, 500])
            # Even if webcam isn't available, the endpoint should exist
            data = resp.get_json()
            self.assertIsNotNone(data)


# ═══════════════════════════════════════════════════════════════════════
#  Test: End-to-end synthetic (no hardware)
# ═══════════════════════════════════════════════════════════════════════


class TestEndToEndSynthetic(unittest.TestCase):
    """Full pipeline: synthetic data → analysis → report."""

    def test_full_pipeline(self):
        from pyontrust.analysis.lux_report import build_lux_report

        # Generate synthetic data
        w_ts, w_br, a_ts, a_lux, events = _make_synthetic_parallel_data(
            duration_s=20.0,
            n_cycles=3,
            torch_on_s=2.0,
            torch_off_s=2.0,
            pre_capture_s=1.5,
            on_brightness=210,
            off_brightness=15,
            on_lux_phone=900,
            off_lux_phone=30,
            noise_std=3.0,
        )

        # Analyse
        result = analyse_parallel_lux(w_ts, w_br, a_ts, a_lux, events)

        # Verify analysis
        self.assertTrue(result.ok)
        self.assertGreater(result.webcam_lux_delta, 200)
        self.assertGreater(result.android_lux_delta, 500)
        self.assertGreater(result.correlation, 0.85)

        # Generate report
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_reports")
        path = build_lux_report(
            result,
            cfg=LuxCaptureConfig(n_cycles=3),
            output_dir=out_dir,
        )

        self.assertTrue(path.exists())
        size_kb = path.stat().st_size / 1024
        self.assertGreater(size_kb, 2)  # at least 2 KB

        print(f"\n✅ Synthetic lux report: {path} ({size_kb:.1f} KB)")
        print(f"   Webcam  Δlux = {result.webcam_lux_delta:.1f}")
        print(f"   Android Δlux = {result.android_lux_delta:.1f}")
        print(f"   Pearson r    = {result.correlation:.4f}")
        print(f"   Lag          = {result.lag_ms:.1f} ms")

        try:
            path.unlink()
        except PermissionError:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  Test: Real hardware (webcam + Android phone)
# ═══════════════════════════════════════════════════════════════════════

# Detect if a real webcam is available
HAS_WEBCAM = False
try:
    import cv2 as _cv2
    _cap = _cv2.VideoCapture(0, _cv2.CAP_DSHOW)
    if _cap.isOpened():
        HAS_WEBCAM = True
    _cap.release()
except Exception:
    pass


@unittest.skipUnless(HAS_WEBCAM, "No webcam available — skipping hardware test")
class TestRealHardwareLuxMeasure(unittest.TestCase):
    """Integration test: real webcam + simulated Android sensor.

    Runs a short lux measurement with 2 fast torch cycles.
    Generates an HTML report.
    """

    def test_capture_and_measure(self):
        from pyontrust.analysis.lux_report import build_lux_report

        cfg = LuxCaptureConfig(
            device_index=0,
            width=640,
            height=480,
            target_fps=30.0,
            warmup_frames=15,
            torch_on_s=1.5,
            torch_off_s=1.5,
            n_cycles=2,
            pre_capture_s=0.5,
            android_mode="simulated",
            android_sample_rate_hz=10.0,
        )

        result = measure_parallel_lux(cfg, use_real_torch=False)

        self.assertTrue(result.ok, f"Measurement failed: {result.error}")
        self.assertGreater(result.webcam_frame_count, 20)
        self.assertGreater(result.android_sample_count, 5)

        print(f"\n📸 Webcam: {result.webcam_frame_count} frames, "
              f"{result.webcam_actual_fps:.1f} FPS")
        print(f"📱 Android: {result.android_sample_count} samples")

        if result.webcam_lux_delta is not None:
            print(f"   Webcam  Δlux = {result.webcam_lux_delta:.1f}")
        if result.android_lux_delta is not None:
            print(f"   Android Δlux = {result.android_lux_delta:.1f}")
        if result.correlation is not None:
            print(f"   Pearson r    = {result.correlation:.4f}")

        # Generate report
        report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_reports")
        path = build_lux_report(
            result,
            cfg=cfg,
            output_dir=report_dir,
        )

        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1024)
        print(f"📄 Report: {path} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    unittest.main()
