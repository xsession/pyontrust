"""Tests for the HTML test-report generator.

Validates the ``ReportBuilder``, SVG chart renderer, and the
convenience ``build_led_blink_report()`` function.

All tests are CI-safe — no hardware, no browser, no external deps.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from pyontrust.analysis.test_report import (
    ReportBuilder,
    _render_svg_line_chart,
    build_led_blink_report,
)
from pyontrust.analysis.led_blink import (
    BlinkResult,
    CaptureConfig,
    RedLEDMaskConfig,
    analyse_brightness_series,
)


# ═══════════════════════════════════════════════════════════════════════
#  Test: ReportBuilder core
# ═══════════════════════════════════════════════════════════════════════


class TestReportBuilder(unittest.TestCase):
    """Unit tests for the ReportBuilder API."""

    def test_minimal_report_renders(self):
        """An empty report renders valid HTML."""
        rb = ReportBuilder(title="Minimal")
        html = rb.render()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<title>Minimal</title>", html)
        # Catppuccin Mocha CSS variables
        self.assertIn("--bg: #1e1e2e", html)
        self.assertIn("pyontrust", html)

    def test_meta_fields_in_header(self):
        rb = ReportBuilder(
            title="T", dut="Board X", operator="Alice",
            test_id="TST-001", environment="Lab A",
        )
        html = rb.render()
        self.assertIn("Board X", html)
        self.assertIn("Alice", html)
        self.assertIn("TST-001", html)
        self.assertIn("Lab A", html)

    def test_add_meta_extra(self):
        rb = ReportBuilder(title="T")
        rb.add_meta("Firmware", "v1.2.3")
        html = rb.render()
        self.assertIn("Firmware", html)
        self.assertIn("v1.2.3", html)

    def test_verdict_pass(self):
        rb = ReportBuilder(title="T")
        rb.set_verdict(True, "All checks passed", "Details here")
        html = rb.render()
        self.assertIn('class="verdict pass"', html)
        self.assertIn("All checks passed", html)
        self.assertIn("Details here", html)

    def test_verdict_fail(self):
        rb = ReportBuilder(title="T")
        rb.set_verdict(False, "Threshold exceeded")
        html = rb.render()
        self.assertIn('class="verdict fail"', html)
        self.assertIn("Threshold exceeded", html)

    def test_section_text(self):
        rb = ReportBuilder(title="T")
        rb.add_section_text("Overview", "Line one\n\nLine two")
        html = rb.render()
        self.assertIn("Overview", html)
        self.assertIn("Line one", html)
        self.assertIn("Line two", html)

    def test_section_kv(self):
        rb = ReportBuilder(title="T")
        rb.add_section_kv("Config", {"Key1": "Val1", "Key2": 42})
        html = rb.render()
        self.assertIn("Key1", html)
        self.assertIn("Val1", html)
        self.assertIn("42", html)
        self.assertIn('class="kv-grid"', html)

    def test_section_table(self):
        rb = ReportBuilder(title="T")
        rb.add_section_table(
            "Metrics",
            ["Name", "Value", "Pass"],
            [["Freq", "2.0 Hz", "✅"], ["Amp", "150", "✅"]],
            numeric_cols={1},
            pass_fail_col=2,
        )
        html = rb.render()
        self.assertIn("data-table", html)
        self.assertIn("Freq", html)
        self.assertIn("2.0 Hz", html)
        self.assertIn("pass-cell", html)

    def test_section_chart(self):
        rb = ReportBuilder(title="T")
        rb.add_section_chart(
            "Waveform",
            [0, 1, 2, 3, 4], [10, 50, 10, 50, 10],
            x_label="Time (s)", y_label="Brightness",
        )
        html = rb.render()
        self.assertIn("<svg", html)
        self.assertIn("polyline", html)
        self.assertIn("Waveform", html)

    def test_section_chart_with_threshold(self):
        rb = ReportBuilder(title="T")
        rb.add_section_chart(
            "Signal", [0, 1, 2], [10, 50, 10],
            threshold_y=30.0,
        )
        html = rb.render()
        self.assertIn("threshold", html)
        self.assertIn("stroke-dasharray", html)

    def test_section_chart_with_secondary(self):
        rb = ReportBuilder(title="T")
        rb.add_section_chart(
            "Dual", [0, 1, 2], [10, 50, 10],
            secondary_y=[5, 25, 5],
            secondary_label="Pixel Count",
        )
        html = rb.render()
        # Two polylines (primary + secondary)
        self.assertEqual(html.count("<polyline"), 2)
        self.assertIn("Pixel Count", html)

    def test_raw_data_embedded(self):
        rb = ReportBuilder(title="T")
        rb.attach_raw_data("test_data", {"freq": 2.0, "ok": True})
        html = rb.render()
        self.assertIn('id="report-data"', html)
        self.assertIn('"freq"', html)

    def test_html_escaping(self):
        """XSS-sensitive characters are escaped."""
        rb = ReportBuilder(title="<script>alert('xss')</script>")
        rb.add_section_text("Test", "a < b && c > d")
        html = rb.render()
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)

    def test_write_creates_file(self):
        rb = ReportBuilder(title="Write Test")
        rb.set_verdict(True, "OK")
        with tempfile.TemporaryDirectory() as td:
            path = rb.write(os.path.join(td, "sub", "report.html"))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 500)
            content = path.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)

    def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            deep_path = os.path.join(td, "a", "b", "c", "report.html")
            rb = ReportBuilder(title="Deep")
            path = rb.write(deep_path)
            self.assertTrue(path.exists())

    def test_fluent_chaining(self):
        """All add_* methods return self for chaining."""
        rb = ReportBuilder(title="Chain")
        result = (
            rb.add_meta("k", "v")
              .add_section_text("T", "txt")
              .add_section_kv("K", {"a": 1})
              .add_section_table("Tbl", ["H"], [["R"]])
              .add_section_chart("C", [0, 1], [0, 1])
              .set_verdict(True, "OK")
              .attach_raw_data("d", {})
        )
        self.assertIs(result, rb)

    def test_print_ready_report(self):
        """Report includes @media print styles."""
        rb = ReportBuilder(title="Print")
        html = rb.render()
        self.assertIn("@media print", html)


# ═══════════════════════════════════════════════════════════════════════
#  Test: SVG chart renderer
# ═══════════════════════════════════════════════════════════════════════


class TestSVGChartRenderer(unittest.TestCase):

    def test_basic_chart(self):
        svg = _render_svg_line_chart([0, 1, 2, 3], [10, 50, 10, 50])
        self.assertIn("<svg", svg)
        self.assertIn("polyline", svg)

    def test_insufficient_data_message(self):
        svg = _render_svg_line_chart([], [])
        self.assertIn("Insufficient data", svg)

    def test_single_point_insufficient(self):
        svg = _render_svg_line_chart([0], [10])
        self.assertIn("Insufficient data", svg)

    def test_constant_y_no_crash(self):
        """All identical Y values → no division by zero."""
        svg = _render_svg_line_chart([0, 1, 2, 3], [50, 50, 50, 50])
        self.assertIn("<svg", svg)

    def test_large_dataset(self):
        """1000 points renders without error."""
        import math
        x = [i / 100.0 for i in range(1000)]
        y = [math.sin(v * 6.28) * 100 + 128 for v in x]
        svg = _render_svg_line_chart(x, y)
        self.assertIn("<svg", svg)

    def test_custom_labels(self):
        svg = _render_svg_line_chart(
            [0, 1], [0, 1],
            x_label="Freq (Hz)", y_label="Amplitude",
            title="Test Chart",
        )
        self.assertIn("Freq (Hz)", svg)
        self.assertIn("Amplitude", svg)
        self.assertIn("Test Chart", svg)

    def test_threshold_line(self):
        svg = _render_svg_line_chart(
            [0, 1, 2], [10, 50, 10],
            threshold_y=30.0,
        )
        self.assertIn("threshold", svg)

    def test_secondary_series(self):
        svg = _render_svg_line_chart(
            [0, 1, 2], [10, 50, 10],
            secondary_y=[5, 25, 5],
            secondary_label="Count",
        )
        self.assertEqual(svg.count("<polyline"), 2)
        self.assertIn("Count", svg)


# ═══════════════════════════════════════════════════════════════════════
#  Test: build_led_blink_report convenience
# ═══════════════════════════════════════════════════════════════════════


class TestBuildLedBlinkReport(unittest.TestCase):

    def _make_result(self, ok=True, freq=2.0) -> BlinkResult:
        """Create a realistic BlinkResult for testing."""
        import math
        n = 240
        dt = 1.0 / 60.0
        ts = [i * dt for i in range(n)]
        period = 1.0 / freq
        br = [200.0 if (t % period) < (period / 2) else 10.0 for t in ts]
        rc = [500 if b > 100 else 0 for b in br]

        if ok:
            return BlinkResult(
                ok=True, frequency_hz=freq, period_s=1.0 / freq,
                duty_cycle=0.5, method="fft", blink_count=int(freq * (n * dt)),
                capture_duration_s=n * dt, frame_count=n,
                actual_fps=60.0, timestamps=ts, brightness=br,
                red_pixel_counts=rc,
            )
        else:
            return BlinkResult(
                ok=False, error="No red LED detected",
                frame_count=n, capture_duration_s=n * dt,
                actual_fps=60.0, timestamps=ts, brightness=[10.0] * n,
                red_pixel_counts=[0] * n,
            )

    def test_pass_report_generated(self):
        result = self._make_result(ok=True, freq=2.0)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(
                result, output_dir=td, dut="Test Board",
            )
            self.assertTrue(path.exists())
            html = path.read_text(encoding="utf-8")
            self.assertIn("PASS", html)
            self.assertIn("2.0", html)
            self.assertIn("Test Board", html)
            self.assertIn("<svg", html)  # charts
            self.assertIn("data-table", html)  # stats table
            self.assertIn("report-data", html)  # raw JSON

    def test_fail_report_generated(self):
        result = self._make_result(ok=False)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(result, output_dir=td)
            self.assertTrue(path.exists())
            html = path.read_text(encoding="utf-8")
            self.assertIn("FAIL", html)
            self.assertIn("No red LED detected", html)

    def test_report_contains_config_sections(self):
        result = self._make_result(ok=True)
        cap_cfg = CaptureConfig(device_index=0, width=640, height=480)
        mask_cfg = RedLEDMaskConfig()
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(
                result, cap_cfg=cap_cfg, mask_cfg=mask_cfg, output_dir=td,
            )
            html = path.read_text(encoding="utf-8")
            self.assertIn("Capture Configuration", html)
            self.assertIn("HSV Mask Configuration", html)
            self.assertIn("640", html)

    def test_report_has_both_charts(self):
        result = self._make_result(ok=True)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(result, output_dir=td)
            html = path.read_text(encoding="utf-8")
            # Two SVG charts: brightness + pixel count
            svg_count = html.count("<svg")
            self.assertGreaterEqual(svg_count, 2)

    def test_report_has_signal_stats_table(self):
        result = self._make_result(ok=True)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(result, output_dir=td)
            html = path.read_text(encoding="utf-8")
            self.assertIn("Signal Statistics", html)
            self.assertIn("Min Brightness", html)
            self.assertIn("Max Brightness", html)

    def test_report_filename_contains_timestamp(self):
        result = self._make_result(ok=True)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(result, output_dir=td)
            self.assertTrue(path.name.startswith("led_blink_"))
            self.assertTrue(path.name.endswith(".html"))

    def test_raw_json_data_embedded(self):
        result = self._make_result(ok=True, freq=3.0)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(result, output_dir=td)
            html = path.read_text(encoding="utf-8")
            # Extract embedded JSON
            start = html.index('id="report-data">') + len('id="report-data">')
            end = html.index("</script>", start)
            raw = json.loads(html[start:end])
            self.assertIn("blink_result", raw)
            self.assertIn("time_series", raw)
            self.assertEqual(raw["blink_result"]["frequency_hz"], 3.0)

    def test_report_is_valid_html(self):
        result = self._make_result(ok=True)
        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(result, output_dir=td)
            html = path.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertTrue(html.strip().endswith("</html>"))
            # Check balanced tags
            self.assertEqual(html.count("<html"), html.count("</html>"))
            self.assertEqual(html.count("<head>"), html.count("</head>"))
            self.assertEqual(html.count("<body>"), html.count("</body>"))


# ═══════════════════════════════════════════════════════════════════════
#  Test: Diagnostic blueprint report routes
# ═══════════════════════════════════════════════════════════════════════


class TestDiagnosticReportRoutes(unittest.TestCase):
    """Test the /diag/api/reports* endpoints."""

    def setUp(self):
        from pyontrust.gateway.app import create_app
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_list_reports_empty(self):
        """GET /diag/api/reports → empty list when no reports exist."""
        resp = self.client.get("/diag/api/reports")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)

    def test_get_nonexistent_report_404(self):
        """GET /diag/api/reports/nonexistent.html → 404."""
        resp = self.client.get("/diag/api/reports/nonexistent.html")
        self.assertEqual(resp.status_code, 404)

    def test_path_traversal_blocked(self):
        """Attempting path traversal in report filename → 404."""
        resp = self.client.get("/diag/api/reports/../../etc/passwd")
        self.assertEqual(resp.status_code, 404)

    def test_list_reports_with_file(self):
        """Create a report file and verify it appears in the list."""
        report_dir = pathlib.Path("test_reports")
        report_dir.mkdir(exist_ok=True)
        test_file = report_dir / "_test_dummy_report.html"
        test_file.write_text("<html><body>test</body></html>", encoding="utf-8")
        try:
            resp = self.client.get("/diag/api/reports")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            names = [r["name"] for r in data]
            self.assertIn("_test_dummy_report.html", names)

            # Verify the report can be served
            resp2 = self.client.get("/diag/api/reports/_test_dummy_report.html")
            self.assertEqual(resp2.status_code, 200)
            self.assertIn(b"test", resp2.data)
        finally:
            # Close any handles before unlink (Windows file locking)
            try:
                resp = resp2 = None  # noqa: F841
                import gc; gc.collect()
                test_file.unlink(missing_ok=True)
            except PermissionError:
                pass  # Windows may hold the file briefly


# ═══════════════════════════════════════════════════════════════════════
#  Test: full pipeline — synthetic blink → analysis → report
# ═══════════════════════════════════════════════════════════════════════


class TestEndToEndSyntheticReport(unittest.TestCase):
    """Generate a synthetic blink, analyse, and produce a report."""

    def test_synthetic_2hz_blink_report(self):
        """2 Hz square wave → analyse → build full report → validate."""
        import math
        n = 300
        fps = 60.0
        freq = 2.0
        dt = 1.0 / fps
        ts = [i * dt for i in range(n)]
        br = [200.0 if (t % (1.0 / freq)) < (0.5 / freq) else 10.0 for t in ts]

        result = analyse_brightness_series(ts, br)
        self.assertTrue(result.ok)

        with tempfile.TemporaryDirectory() as td:
            path = build_led_blink_report(
                result,
                dut="Synthetic 2 Hz square wave",
                test_id="SYNTH-2HZ",
                output_dir=td,
            )
            self.assertTrue(path.exists())
            html = path.read_text(encoding="utf-8")

            # Structural checks
            self.assertIn("PASS", html)
            self.assertIn("Synthetic 2 Hz square wave", html)
            self.assertIn("SYNTH-2HZ", html)
            self.assertIn("<svg", html)
            self.assertIn("Signal Statistics", html)
            self.assertGreater(path.stat().st_size, 5000)


if __name__ == "__main__":
    unittest.main()
