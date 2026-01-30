from __future__ import annotations

import os
import tempfile
import unittest


class TestCsvPlotterCore(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import pyontrust_csv_plotter_core as core  # noqa: F401
        except Exception as e:  # pragma: no cover
            self.skipTest(f"pyontrust_csv_plotter_core not installed: {e}")

    def test_header_and_stats(self) -> None:
        import pyontrust_csv_plotter_core as core

        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("Timestamp,A,B\n")
                for i in range(100):
                    f.write(f"{i},{i*0.5},{100-i}\n")

            cols = core.read_csv_header(path)
            self.assertIn("Timestamp", cols)
            self.assertIn("A", cols)

            out = core.read_xy_decimated(path, "Timestamp", ["A", "B"], 20)
            self.assertIn("x", out)
            self.assertIn("series", out)
            self.assertIn("stats", out)

            self.assertLessEqual(len(out["x"]), 20)
            self.assertIn("A", out["series"])
            self.assertIn("B", out["series"])

            stats_a = out["stats"]["A"]
            self.assertAlmostEqual(stats_a["min"], 0.0)
            self.assertAlmostEqual(stats_a["max"], 49.5)
            self.assertAlmostEqual(stats_a["p2p"], 49.5)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
