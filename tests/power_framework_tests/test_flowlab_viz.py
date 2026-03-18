"""Tests for FlowLab inline-viz blocks: plot_trace, plot_histogram, fft_spectrum,
gauge_display, table_display, live_video, waterfall_display, plot_xy, plot_heatmap.

Verifies that each viz block returns a ``_viz`` dict in its outputs
with the correct ``type`` key and plottable data arrays.
"""
from __future__ import annotations

import json
import unittest

from pyontrust.gateway.flowlab_engine import ExecContext, FlowLabEngine


def _make_trace(n=200, rate=1000):
    """Build a synthetic power_trace dict."""
    import math
    t = [i / rate for i in range(n)]
    current = [0.001 + 0.0005 * math.sin(2 * math.pi * 50 * ti) for ti in t]
    return {"time_s": t, "current_a": current, "sample_rate_hz": rate, "n_samples": n}


class TestPlotTraceViz(unittest.TestCase):
    """Plot Trace block returns _viz with type='trace' and data arrays."""

    def test_returns_viz_trace(self):
        engine = FlowLabEngine()
        ctx = ExecContext()
        trace = _make_trace(500)
        out = engine.block_registry["plot_trace"](
            {"title": "Power Trace", "style": "lines", "y_label": "Current (A)"},
            {"trace": trace}, ctx)
        self.assertIn("_viz", out)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "trace")
        self.assertEqual(viz["title"], "Power Trace")
        self.assertIn("x", viz)
        self.assertIn("y", viz)
        self.assertGreater(len(viz["y"]), 0)
        self.assertEqual(viz["style"], "lines")

    def test_trace_downsampled(self):
        """Large traces are downsampled for rendering."""
        ctx = ExecContext()
        trace = _make_trace(5000)
        out = FlowLabEngine.block_registry["plot_trace"](
            {"title": "Big", "style": "lines"}, {"trace": trace}, ctx)
        viz = out["_viz"]
        self.assertLessEqual(len(viz["y"]), 510)  # max ~500

    def test_empty_trace(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_trace"](
            {"title": "Empty"}, {"trace": {}}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "trace")
        self.assertEqual(len(viz["y"]), 0)

    def test_trace_from_plain_list(self):
        """plot_trace accepts a plain list of y-values as trace input."""
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_trace"](
            {"title": "List"}, {"trace": [1.0, 2.0, 3.0, 4.0]}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "trace")
        self.assertEqual(viz["y"], [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(viz["x"], [0, 1, 2, 3])

    def test_trace_from_list_of_dicts(self):
        """plot_trace accepts a list of point dicts."""
        ctx = ExecContext()
        points = [
            {"time_s": 0.0, "current_a": 0.01},
            {"time_s": 0.5, "current_a": 0.02},
            {"time_s": 1.0, "current_a": 0.03},
        ]
        out = FlowLabEngine.block_registry["plot_trace"](
            {"title": "Dicts"}, {"trace": points}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["y"], [0.01, 0.02, 0.03])
        self.assertEqual(viz["x"], [0.0, 0.5, 1.0])

    def test_trace_from_empty_list(self):
        """plot_trace handles an empty list gracefully."""
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_trace"](
            {"title": "Empty List"}, {"trace": []}, ctx)
        viz = out["_viz"]
        self.assertEqual(len(viz["y"]), 0)


class TestPlotXYViz(unittest.TestCase):

    def test_returns_viz_xy(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_xy"](
            {"title": "Scatter", "mode": "markers"},
            {"x": [1, 2, 3], "y": [4, 5, 6]}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "xy")
        self.assertEqual(len(viz["x"]), 3)
        self.assertEqual(viz["mode"], "markers")


class TestPlotHistogramViz(unittest.TestCase):

    def test_returns_viz_histogram(self):
        import random
        random.seed(42)
        data = [random.gauss(0, 1) for _ in range(200)]
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_histogram"](
            {"title": "Test Hist", "bins": 20, "color": "#a6e3a1"},
            {"data": data}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "histogram")
        self.assertEqual(len(viz["bin_counts"]), 20)
        self.assertEqual(len(viz["bin_edges"]), 21)
        self.assertEqual(viz["color"], "#a6e3a1")
        self.assertEqual(sum(viz["bin_counts"]), 200)

    def test_histogram_dict_input(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_histogram"](
            {"title": "Dict", "bins": 10},
            {"data": {"values": [1.0, 2.0, 3.0, 4.0, 5.0]}}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "histogram")
        self.assertGreater(len(viz["bin_counts"]), 0)

    def test_histogram_empty(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_histogram"](
            {"title": "Empty", "bins": 10}, {"data": []}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["bin_counts"], [])


class TestFFTSpectrumViz(unittest.TestCase):

    def test_fft_returns_viz(self):
        trace = _make_trace(1000, 1000)
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["fft_spectrum"](
            {"n_peaks": 3, "window": "hann"},
            {"trace": trace}, ctx)
        self.assertIn("_viz", out)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "fft")
        self.assertIn("freq_hz", viz)
        self.assertIn("amplitude", viz)
        self.assertGreater(len(viz["amplitude"]), 0)
        # Peaks should include 50 Hz (from the sine in _make_trace)
        peak_freqs = [p["freq_hz"] for p in viz.get("peaks", [])]
        self.assertTrue(any(45 <= f <= 55 for f in peak_freqs),
                        f"Expected ~50Hz peak, got {peak_freqs}")

    def test_fft_empty_data(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["fft_spectrum"](
            {"n_peaks": 5}, {"trace": {}}, ctx)
        self.assertNotIn("_viz", out)  # empty data → no viz


class TestGaugeDisplayViz(unittest.TestCase):

    def test_returns_viz_gauge(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["gauge_display"](
            {"title": "Temp", "unit": "°C", "min_val": 0, "max_val": 100,
             "green_max": 60, "yellow_max": 80},
            {"value": 42}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "gauge")
        self.assertEqual(viz["value"], 42)
        self.assertEqual(viz["unit"], "°C")
        self.assertEqual(viz["min"], 0)
        self.assertEqual(viz["max"], 100)


class TestTableDisplayViz(unittest.TestCase):

    def test_dict_input(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["table_display"](
            {"max_rows": 100},
            {"data": {"a": [1, 2, 3], "b": [4, 5, 6]}}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "table")
        self.assertEqual(viz["headers"], ["a", "b"])
        self.assertEqual(len(viz["rows"]), 3)

    def test_list_of_dicts(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["table_display"](
            {"max_rows": 100},
            {"data": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "table")
        self.assertEqual(len(viz["rows"]), 2)

    def test_plain_list(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["table_display"](
            {"max_rows": 100},
            {"data": [10, 20, 30]}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["headers"], ["value"])
        self.assertEqual(len(viz["rows"]), 3)


class TestHeatmapViz(unittest.TestCase):

    def test_2d_grid(self):
        ctx = ExecContext()
        grid = [[1, 2, 3], [4, 5, 6]]
        out = FlowLabEngine.block_registry["plot_heatmap"](
            {"title": "Test HM", "colorscale": "Inferno"},
            {"data": grid}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "heatmap")
        self.assertEqual(len(viz["grid"]), 2)

    def test_dict_with_grid_key(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["plot_heatmap"](
            {"title": "Dict HM"},
            {"data": {"grid": [[1, 2], [3, 4]]}}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "heatmap")
        self.assertEqual(len(viz["grid"]), 2)


class TestLiveVideoViz(unittest.TestCase):

    def test_returns_viz_video(self):
        """Without cv2 (or mocked), returns an error viz."""
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["live_video"](
            {"camera_index": 99, "width": 320, "height": 240}, {}, ctx)
        self.assertIn("_viz", out)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "video")
        # Either has 'src' or 'error'
        self.assertTrue("src" in viz or "error" in viz)

    def test_mock_camera(self):
        """Mock cv2 to return a valid frame."""
        import unittest.mock as mock
        import base64

        # Create a fake frame (2x2 black image)
        fake_frame_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100  # fake JPEG
        mock_cv2 = mock.MagicMock()
        mock_cv2.CAP_DSHOW = 700
        mock_cv2.CAP_PROP_FRAME_WIDTH = 3
        mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
        mock_cv2.IMWRITE_JPEG_QUALITY = 1
        cap = mock.MagicMock()
        cap.read.return_value = (True, mock.MagicMock(shape=(240, 320, 3)))
        mock_cv2.VideoCapture.return_value = cap
        mock_cv2.imencode.return_value = (True, fake_frame_data)

        with mock.patch.dict('sys.modules', {'cv2': mock_cv2}):
            ctx = ExecContext()
            out = FlowLabEngine.block_registry["live_video"](
                {"camera_index": 0, "width": 320, "height": 240}, {}, ctx)
            viz = out["_viz"]
            self.assertEqual(viz["type"], "video")
            self.assertIn("src", viz)
            self.assertTrue(viz["src"].startswith("data:image/jpeg;base64,"))
            self.assertEqual(viz["width"], 320)
            self.assertEqual(viz["height"], 240)


class TestWaterfallDisplayViz(unittest.TestCase):

    def test_returns_waterfall(self):
        ctx = ExecContext()
        spectrum = {"freq_hz": [0, 100, 200, 300, 400, 500],
                    "amplitude": [0.01, 0.05, 0.1, 0.08, 0.03, 0.01]}
        out = FlowLabEngine.block_registry["waterfall_display"](
            {"title": "Waterfall", "history_rows": 16, "colorscale": "Inferno"},
            {"spectrum": spectrum}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "waterfall")
        self.assertEqual(len(viz["grid"]), 1)  # single row for one-shot
        self.assertEqual(viz["n_rows"], 16)
        self.assertGreater(len(viz["grid"][0]), 0)

    def test_empty_spectrum(self):
        ctx = ExecContext()
        out = FlowLabEngine.block_registry["waterfall_display"](
            {"title": "Empty"}, {"spectrum": {}}, ctx)
        viz = out["_viz"]
        self.assertEqual(viz["type"], "waterfall")
        self.assertEqual(viz["grid"], [])


class TestVizEndToEnd(unittest.TestCase):
    """Execute a complete diagram with viz blocks and verify results."""

    def test_simulated_to_fft_to_trace(self):
        """simulated_power → fft_spectrum → plot_trace chain produces viz."""
        engine = FlowLabEngine()
        diagram = {
            "blocks": [
                {"id": "src", "type": "simulated_power", "x": 0, "y": 0,
                 "params": {"sample_rate_hz": 1000, "duration_s": 1,
                            "base_current_a": 0.001, "noise_a": 0.0001}},
                {"id": "fft", "type": "fft_spectrum", "x": 200, "y": 0,
                 "params": {"n_peaks": 5, "window": "hann"}},
                {"id": "plt", "type": "plot_trace", "x": 400, "y": 0,
                 "params": {"title": "Current", "style": "lines"}},
            ],
            "wires": [
                {"from": {"block": "src", "port": "trace"},
                 "to": {"block": "fft", "port": "trace"}},
                {"from": {"block": "src", "port": "trace"},
                 "to": {"block": "plt", "port": "trace"}},
            ],
        }
        result = engine.execute(diagram)
        self.assertIsNone(result.get("error"))

        # FFT block should have _viz
        fft_res = result["block_results"]["fft"]
        self.assertTrue(fft_res.get("ok"))
        fft_outputs = fft_res["outputs"]
        self.assertIn("_viz", fft_outputs)
        self.assertEqual(fft_outputs["_viz"]["type"], "fft")

        # Plot trace should have _viz
        plt_res = result["block_results"]["plt"]
        self.assertTrue(plt_res.get("ok"))
        plt_outputs = plt_res["outputs"]
        self.assertIn("_viz", plt_outputs)
        self.assertEqual(plt_outputs["_viz"]["type"], "trace")

    def test_simulated_to_histogram(self):
        engine = FlowLabEngine()
        diagram = {
            "blocks": [
                {"id": "src", "type": "simulated_power", "x": 0, "y": 0,
                 "params": {"sample_rate_hz": 1000, "duration_s": 0.5}},
                {"id": "hist", "type": "plot_histogram", "x": 200, "y": 0,
                 "params": {"title": "Distribution", "bins": 30}},
            ],
            "wires": [
                {"from": {"block": "src", "port": "trace"},
                 "to": {"block": "hist", "port": "data"}},
            ],
        }
        result = engine.execute(diagram)
        hist_out = result["block_results"]["hist"]["outputs"]
        self.assertIn("_viz", hist_out)
        self.assertEqual(hist_out["_viz"]["type"], "histogram")

    def test_gauge_display_end_to_end(self):
        engine = FlowLabEngine()
        diagram = {
            "blocks": [
                {"id": "c", "type": "constant", "x": 0, "y": 0,
                 "params": {"value": "75"}},
                {"id": "g", "type": "gauge_display", "x": 200, "y": 0,
                 "params": {"title": "Speed", "unit": "km/h",
                            "min_val": 0, "max_val": 200,
                            "green_max": 80, "yellow_max": 140}},
            ],
            "wires": [
                {"from": {"block": "c", "port": "value"},
                 "to": {"block": "g", "port": "value"}},
            ],
        }
        result = engine.execute(diagram)
        g_out = result["block_results"]["g"]["outputs"]
        self.assertEqual(g_out["_viz"]["type"], "gauge")
        self.assertEqual(g_out["_viz"]["value"], 75)

    def test_viz_data_is_json_safe(self):
        """All _viz data must survive JSON serialisation."""
        engine = FlowLabEngine()
        diagram = {
            "blocks": [
                {"id": "s", "type": "simulated_power", "x": 0, "y": 0,
                 "params": {"sample_rate_hz": 500, "duration_s": 0.2}},
                {"id": "p", "type": "plot_trace", "x": 200, "y": 0,
                 "params": {"title": "JSON Test"}},
            ],
            "wires": [
                {"from": {"block": "s", "port": "trace"},
                 "to": {"block": "p", "port": "trace"}},
            ],
        }
        result = engine.execute(diagram)
        # Must be fully JSON-serialisable
        text = json.dumps(result)
        parsed = json.loads(text)
        self.assertIn("_viz", parsed["block_results"]["p"]["outputs"])

    def test_block_registry_has_new_types(self):
        """live_video and waterfall_display are in the registry."""
        engine = FlowLabEngine()
        self.assertIn("live_video", engine.block_registry)
        self.assertIn("waterfall_display", engine.block_registry)


class TestFlowLabBlueprintViz(unittest.TestCase):
    """Test that viz blocks appear in the blueprint block list."""

    @classmethod
    def setUpClass(cls):
        from pyontrust.gateway.app import create_app
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_block_list_includes_viz_types(self):
        r = self.client.get("/flowlab/api/blocks")
        data = json.loads(r.data)
        block_list = data["blocks"]
        for bt in ("plot_trace", "plot_histogram", "fft_spectrum",
                    "gauge_display", "table_display", "live_video",
                    "waterfall_display", "plot_heatmap", "plot_xy"):
            self.assertIn(bt, block_list, f"{bt} missing from block list")

    def test_execute_viz_diagram(self):
        """Execute a diagram with viz blocks and check _viz in response."""
        diagram = {
            "blocks": [
                {"id": "src", "type": "simulated_power", "x": 0, "y": 0,
                 "params": {"sample_rate_hz": 500, "duration_s": 0.2}},
                {"id": "pt", "type": "plot_trace", "x": 200, "y": 0,
                 "params": {"title": "Test"}},
            ],
            "wires": [
                {"from": {"block": "src", "port": "trace"},
                 "to": {"block": "pt", "port": "trace"}},
            ],
        }
        r = self.client.post("/flowlab/api/execute",
                             data=json.dumps(diagram),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.data)
        pt_out = result["block_results"]["pt"]["outputs"]
        self.assertIn("_viz", pt_out)
        self.assertEqual(pt_out["_viz"]["type"], "trace")

    def test_flowlab_js_has_viz_types(self):
        """The FlowLab JS bundle includes viz block types."""
        r = self.client.get("/flowlab/static/flowlab.js")
        self.assertEqual(r.status_code, 200)
        js = r.data.decode("utf-8")
        self.assertIn("live_video", js)
        self.assertIn("waterfall_display", js)
        self.assertIn("VIZ_TYPES", js)
        self.assertIn("renderVizInNode", js)
        self.assertIn("foreignObject", js)


if __name__ == "__main__":
    unittest.main()
