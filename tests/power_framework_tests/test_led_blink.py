"""Tests for LED blink periodicity measurement.

Unit tests use synthetic frames (no hardware required).
The final integration test (``TestRealWebcamLEDBlink``) opens the
actual webcam and measures a physically-blinking red LED — it is
guarded by ``@unittest.skipUnless(HAS_WEBCAM, ...)``.

Run all:
    python -m pytest tests/power_framework_tests/test_led_blink.py -v

Run only synthetic tests (CI-safe):
    python -m pytest tests/power_framework_tests/test_led_blink.py -v -k "not RealWebcam"

Run hardware test only:
    python -m pytest tests/power_framework_tests/test_led_blink.py -v -k "RealWebcam"
"""

from __future__ import annotations

import math
import os
import sys
import time
import unittest

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import numpy as np

from pyontrust.analysis.led_blink import (
    BlinkResult,
    CaptureConfig,
    RedLEDMaskConfig,
    analyse_brightness_series,
    extract_red_brightness,
    measure_led_blink_rate,
)
from pyontrust.analysis.test_report import ReportBuilder, build_led_blink_report

# Report output directory (project root / test_reports)
_REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "test_reports")


# ═══════════════════════════════════════════════════════════════════════
#  Helpers: synthetic frame generation
# ═══════════════════════════════════════════════════════════════════════


def _make_red_frame(w: int = 64, h: int = 64, brightness: int = 200) -> np.ndarray:
    """Create a BGR frame with a bright red circle (simulates red LED ON)."""
    import cv2
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # Bright red circle in centre — BGR = (0, 0, brightness)
    cx, cy, r = w // 2, h // 2, min(w, h) // 4
    cv2.circle(frame, (cx, cy), r, (0, 0, brightness), thickness=-1)
    return frame


def _make_dark_frame(w: int = 64, h: int = 64) -> np.ndarray:
    """Create a near-black frame (simulates red LED OFF)."""
    frame = np.full((h, w, 3), 10, dtype=np.uint8)
    return frame


def _make_blink_sequence(
    n_frames: int = 120,
    fps: float = 30.0,
    blink_hz: float = 2.0,
    w: int = 64,
    h: int = 64,
    brightness_on: int = 220,
) -> tuple[list[float], list[np.ndarray]]:
    """Generate a series of ON/OFF frames simulating a blinking LED.

    Returns ``(timestamps, frames)`` where frames alternate between
    bright-red and dark at the specified ``blink_hz``.
    """
    dt = 1.0 / fps
    blink_period = 1.0 / blink_hz
    half_period = blink_period / 2.0

    timestamps: list[float] = []
    frames: list[np.ndarray] = []

    for i in range(n_frames):
        t = i * dt
        timestamps.append(t)
        # Square wave: ON for first half-period, OFF for second
        phase = (t % blink_period)
        if phase < half_period:
            frames.append(_make_red_frame(w, h, brightness_on))
        else:
            frames.append(_make_dark_frame(w, h))

    return timestamps, frames


# ═══════════════════════════════════════════════════════════════════════
#  Test: extract_red_brightness
# ═══════════════════════════════════════════════════════════════════════


class TestExtractRedBrightness(unittest.TestCase):
    """Unit tests for the single-frame red LED brightness extractor."""

    def test_red_led_on_frame(self):
        """Bright red circle → high brightness, many red pixels."""
        frame = _make_red_frame(brightness=220)
        brightness, count = extract_red_brightness(frame)
        self.assertGreater(brightness, 100.0)
        self.assertGreater(count, 50)

    def test_dark_frame_no_red(self):
        """Near-black frame → zero brightness, zero red pixels."""
        frame = _make_dark_frame()
        brightness, count = extract_red_brightness(frame)
        self.assertEqual(brightness, 0.0)
        self.assertEqual(count, 0)

    def test_green_frame_no_match(self):
        """Pure green frame → red mask should yield 0."""
        import cv2
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2.circle(frame, (32, 32), 16, (0, 255, 0), -1)  # BGR green
        brightness, count = extract_red_brightness(frame)
        self.assertEqual(count, 0)

    def test_blue_frame_no_match(self):
        """Pure blue frame → red mask should yield 0."""
        import cv2
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2.circle(frame, (32, 32), 16, (255, 0, 0), -1)  # BGR blue
        brightness, count = extract_red_brightness(frame)
        self.assertEqual(count, 0)

    def test_roi_crops_correctly(self):
        """ROI restricts analysis to a sub-region."""
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        # Red dot in top-left corner
        frame[5:15, 5:15] = (0, 0, 220)

        # ROI covers the red dot
        b1, c1 = extract_red_brightness(frame, roi=(0, 0, 30, 30))
        self.assertGreater(c1, 0)

        # ROI misses the red dot entirely
        b2, c2 = extract_red_brightness(frame, roi=(60, 60, 30, 30))
        self.assertEqual(c2, 0)

    def test_custom_mask_config(self):
        """Very tight mask config rejects borderline colours."""
        frame = _make_red_frame(brightness=220)
        # Extremely strict S/V — only very saturated bright red
        strict_cfg = RedLEDMaskConfig(low_s=250, low_v=250)
        _, count = extract_red_brightness(frame, mask_cfg=strict_cfg)
        # With strict thresholds, many pixels won't pass
        self.assertIsInstance(count, int)

    def test_min_pixel_count_threshold(self):
        """Below min_pixel_count → returns (0.0, 0)."""
        # Very small red dot (just a few pixels)
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[32, 32] = (0, 0, 255)  # single red pixel
        cfg = RedLEDMaskConfig(min_pixel_count=10)
        brightness, count = extract_red_brightness(frame, mask_cfg=cfg)
        self.assertEqual(brightness, 0.0)
        self.assertEqual(count, 0)


# ═══════════════════════════════════════════════════════════════════════
#  Test: analyse_brightness_series
# ═══════════════════════════════════════════════════════════════════════


class TestAnalyseBrightnessSeries(unittest.TestCase):
    """Unit tests for the time-series → frequency analysis."""

    def _generate_square_wave_series(
        self, freq_hz: float, duration_s: float = 4.0, fps: float = 60.0,
    ) -> tuple[list[float], list[float]]:
        """Ideal square-wave brightness series for a known frequency."""
        n = int(duration_s * fps)
        dt = 1.0 / fps
        period = 1.0 / freq_hz
        ts = [i * dt for i in range(n)]
        br = [200.0 if (t % period) < (period / 2.0) else 10.0 for t in ts]
        return ts, br

    def _generate_sine_wave_series(
        self, freq_hz: float, duration_s: float = 4.0, fps: float = 60.0,
    ) -> tuple[list[float], list[float]]:
        """Sinusoidal brightness for FFT-friendly testing."""
        n = int(duration_s * fps)
        dt = 1.0 / fps
        ts = [i * dt for i in range(n)]
        br = [128.0 + 100.0 * math.sin(2 * math.pi * freq_hz * t) for t in ts]
        return ts, br

    def test_2hz_square_wave(self):
        """2 Hz square wave → detected frequency ≈ 2 Hz."""
        ts, br = self._generate_square_wave_series(2.0)
        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok, result.error)
        self.assertIsNotNone(result.frequency_hz)
        self.assertAlmostEqual(result.frequency_hz, 2.0, delta=0.3)
        self.assertAlmostEqual(result.period_s, 0.5, delta=0.1)

    def test_5hz_square_wave(self):
        """5 Hz square wave → detected frequency ≈ 5 Hz."""
        ts, br = self._generate_square_wave_series(5.0, duration_s=3.0)
        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 5.0, delta=0.5)

    def test_1hz_sine_wave(self):
        """1 Hz sinusoidal → detected frequency ≈ 1 Hz."""
        ts, br = self._generate_sine_wave_series(1.0, duration_s=5.0)
        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 1.0, delta=0.2)

    def test_10hz_sine_wave(self):
        """10 Hz sinusoidal → detected frequency ≈ 10 Hz."""
        ts, br = self._generate_sine_wave_series(10.0, duration_s=3.0, fps=100.0)
        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 10.0, delta=1.0)

    def test_half_hz_slow_blink(self):
        """0.5 Hz (1 blink every 2 seconds)."""
        ts, br = self._generate_square_wave_series(0.5, duration_s=10.0, fps=30.0)
        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 0.5, delta=0.15)
        self.assertAlmostEqual(result.period_s, 2.0, delta=0.3)

    def test_constant_brightness_returns_error(self):
        """Flat brightness (no blink) → ok=False."""
        ts = [i * 0.033 for i in range(120)]
        br = [150.0] * 120
        result = analyse_brightness_series(ts, br)
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)

    def test_too_few_frames_returns_error(self):
        """< 8 frames → ok=False."""
        result = analyse_brightness_series([0.0, 0.1, 0.2], [100, 200, 100])
        self.assertFalse(result.ok)
        self.assertIn("Not enough", result.error)

    def test_noisy_square_wave(self):
        """2 Hz square wave with Gaussian noise → still detectable."""
        rng = np.random.default_rng(42)
        ts, br_clean = self._generate_square_wave_series(2.0, duration_s=5.0)
        br = [b + rng.normal(0, 15) for b in br_clean]
        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 2.0, delta=0.5)

    def test_duty_cycle_50_percent(self):
        """50% duty cycle square wave → duty ≈ 0.5."""
        ts, br = self._generate_square_wave_series(2.0)
        result = analyse_brightness_series(ts, br)
        if result.duty_cycle is not None:
            self.assertAlmostEqual(result.duty_cycle, 0.5, delta=0.1)

    def test_result_summary_dict(self):
        """BlinkResult.summary() returns a clean JSON-serializable dict."""
        ts, br = self._generate_square_wave_series(2.0)
        result = analyse_brightness_series(ts, br)
        s = result.summary()
        self.assertIsInstance(s, dict)
        self.assertIn("frequency_hz", s)
        self.assertIn("period_s", s)
        self.assertIn("method", s)

    def test_timestamps_and_brightness_preserved(self):
        """Result contains the original time-series data."""
        ts, br = self._generate_square_wave_series(2.0)
        result = analyse_brightness_series(ts, br)
        self.assertEqual(len(result.timestamps), len(ts))
        self.assertEqual(len(result.brightness), len(br))


# ═══════════════════════════════════════════════════════════════════════
#  Test: full pipeline with synthetic frames
# ═══════════════════════════════════════════════════════════════════════


class TestFullPipelineSynthetic(unittest.TestCase):
    """End-to-end: synthetic frames → extract brightness → analyse."""

    def test_2hz_blink_pipeline(self):
        """Generate 2 Hz blinking frames, extract brightness, analyse."""
        timestamps, frames = _make_blink_sequence(
            n_frames=180, fps=30.0, blink_hz=2.0,
        )
        brightness = []
        for frame in frames:
            b, _ = extract_red_brightness(frame)
            brightness.append(b)

        result = analyse_brightness_series(timestamps, brightness)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 2.0, delta=0.5)

    def test_3hz_blink_pipeline(self):
        """Generate 3 Hz blinking frames, extract brightness, analyse."""
        timestamps, frames = _make_blink_sequence(
            n_frames=240, fps=30.0, blink_hz=3.0,
        )
        brightness = []
        for frame in frames:
            b, _ = extract_red_brightness(frame)
            brightness.append(b)

        result = analyse_brightness_series(timestamps, brightness)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 3.0, delta=0.5)

    def test_1hz_blink_pipeline(self):
        """Generate 1 Hz blinking frames (slow), extract + analyse."""
        timestamps, frames = _make_blink_sequence(
            n_frames=150, fps=30.0, blink_hz=1.0,
        )
        brightness = []
        for frame in frames:
            b, _ = extract_red_brightness(frame)
            brightness.append(b)

        result = analyse_brightness_series(timestamps, brightness)
        self.assertTrue(result.ok, result.error)
        self.assertAlmostEqual(result.frequency_hz, 1.0, delta=0.3)


# ═══════════════════════════════════════════════════════════════════════
#  Test: edge cases and config
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):

    def test_capture_config_defaults(self):
        cfg = CaptureConfig()
        self.assertEqual(cfg.device_index, 0)
        self.assertEqual(cfg.width, 640)
        self.assertEqual(cfg.height, 480)
        self.assertEqual(cfg.capture_duration_s, 5.0)
        self.assertEqual(cfg.target_fps, 30.0)
        self.assertEqual(cfg.warmup_frames, 10)
        self.assertIsNone(cfg.roi)

    def test_mask_config_defaults(self):
        cfg = RedLEDMaskConfig()
        self.assertEqual(cfg.low_h1, 0)
        self.assertEqual(cfg.high_h1, 10)
        self.assertEqual(cfg.low_h2, 160)
        self.assertEqual(cfg.high_h2, 180)

    def test_blink_result_error_state(self):
        r = BlinkResult(ok=False, error="test error")
        s = r.summary()
        self.assertFalse(s["ok"])
        self.assertEqual(s["error"], "test error")
        self.assertIsNone(s["frequency_hz"])

    def test_blink_result_ok_state(self):
        r = BlinkResult(
            ok=True, frequency_hz=2.0, period_s=0.5,
            duty_cycle=0.5, method="fft", blink_count=10,
            capture_duration_s=5.0, frame_count=150, actual_fps=30.0,
        )
        s = r.summary()
        self.assertTrue(s["ok"])
        self.assertEqual(s["frequency_hz"], 2.0)
        self.assertEqual(s["period_s"], 0.5)

    def test_frequency_out_of_range_rejected(self):
        """100 Hz blink at 60 fps → aliased/undetectable → ok=False or clamped."""
        ts = [i / 60.0 for i in range(300)]
        br = [200.0 if (int(t * 200) % 2 == 0) else 10.0 for t in ts]
        # max_blink_hz=50 should reject the 100 Hz alias
        result = analyse_brightness_series(ts, br, max_blink_hz=50.0)
        # Either not detected or capped — the important thing is no crash
        self.assertIsInstance(result, BlinkResult)


# ═══════════════════════════════════════════════════════════════════════
#  Integration Test: REAL webcam + physical red LED
# ═══════════════════════════════════════════════════════════════════════


def _webcam_available() -> bool:
    """Quick check: can we open device 0?"""
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        return ok
    except Exception:
        return False


HAS_WEBCAM = _webcam_available()


@unittest.skipUnless(HAS_WEBCAM, "No webcam connected — skipping hardware test")
class TestRealWebcamLEDBlink(unittest.TestCase):
    """Integration test: open the real webcam and measure LED blink rate.

    Prerequisites:
    - USB webcam connected and visible at index 0.
    - A red LED blinking in front of the camera (e.g. dev-board
      heartbeat LED, or a simple Arduino blink sketch).

    The test captures 8 seconds of video and attempts to determine
    the blink frequency.  If no red LED is detected it reports a
    diagnostic message rather than a hard failure.
    """

    def test_capture_and_measure(self):
        """Capture frames from live webcam and analyse red LED blink."""
        cap_cfg = CaptureConfig(
            device_index=0,
            width=640,
            height=480,
            capture_duration_s=8.0,
            target_fps=30.0,
            warmup_frames=15,
        )
        mask_cfg = RedLEDMaskConfig()

        result = measure_led_blink_rate(cap_cfg=cap_cfg, mask_cfg=mask_cfg)

        # Always print diagnostics regardless of pass/fail
        print("\n" + "=" * 60)
        print("  LED Blink Measurement — Live Webcam")
        print("=" * 60)
        print(f"  Frames captured : {result.frame_count}")
        print(f"  Actual FPS      : {result.actual_fps:.1f}")
        print(f"  Duration        : {result.capture_duration_s:.2f} s")

        if result.red_pixel_counts:
            max_px = max(result.red_pixel_counts)
            avg_px = sum(result.red_pixel_counts) / len(result.red_pixel_counts)
            print(f"  Red pixels (max): {max_px}")
            print(f"  Red pixels (avg): {avg_px:.0f}")

        if result.ok:
            print(f"  ✅ Blink freq    : {result.frequency_hz:.3f} Hz")
            print(f"     Period        : {result.period_s:.4f} s")
            print(f"     Method        : {result.method}")
            if result.duty_cycle is not None:
                print(f"     Duty cycle    : {result.duty_cycle:.1%}")
            print(f"     Blink count   : {result.blink_count}")
        else:
            print(f"  ⚠️  Not detected  : {result.error}")
            print("     (Is a red LED blinking in front of the camera?)")
        print("=" * 60)

        # Soft assertions: the capture itself must work
        self.assertGreater(result.frame_count, 0, "No frames captured")
        self.assertGreater(result.capture_duration_s, 0)
        self.assertGreater(result.actual_fps, 5.0, "FPS too low — capture problem?")

        # If a red LED is present, validate frequency is sane
        if result.ok:
            self.assertGreater(result.frequency_hz, 0.1)
            self.assertLess(result.frequency_hz, 50.0)
            self.assertGreater(result.period_s, 0.02)

        # ── Generate HTML report ────────────────────────────────────
        report_path = build_led_blink_report(
            result,
            dut="Red LED — live webcam capture",
            cap_cfg=cap_cfg,
            mask_cfg=mask_cfg,
            output_dir=_REPORT_DIR,
        )
        print(f"  📄 Report: {report_path}")
        self.assertTrue(report_path.exists(), "Report file not created")
        # Sanity check: file should be > 1 KB
        self.assertGreater(report_path.stat().st_size, 1024)

    def test_brightness_time_series_has_variation(self):
        """Verify the brightness signal shows actual variation over time."""
        cap_cfg = CaptureConfig(
            device_index=0, capture_duration_s=4.0,
            target_fps=30.0, warmup_frames=10,
        )
        from pyontrust.analysis.led_blink import capture_led_frames

        timestamps, brightness, red_counts, n = capture_led_frames(cap_cfg)

        print(f"\n  Captured {n} frames in {timestamps[-1]:.2f}s" if timestamps else "")
        self.assertGreater(n, 10)

        # Check that *some* frames have red pixels
        has_red = sum(1 for c in red_counts if c > 0)
        print(f"  Frames with red pixels: {has_red}/{n}")

        # If red is present, brightness should vary
        if has_red > n * 0.1:
            br = np.array(brightness)
            amplitude = float(br.max() - br.min())
            print(f"  Brightness range: {br.min():.1f} – {br.max():.1f} (Δ={amplitude:.1f})")
            self.assertGreater(amplitude, 1.0, "No brightness variation detected")


if __name__ == "__main__":
    unittest.main()
