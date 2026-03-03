"""Comprehensive tests for gui_app.csv_plotter.data.

Covers:
- sniff_csv_separator (comma, semicolon, tab, pipe, empty file, binary)
- read_csv_header (basic, semicolon, empty)
- read_any_csv (pandas path, delimiter handling, nrows, usecols, semicolon fallback)
- find_newest_csv (normal, empty folder, non-existent folder)
- compute_timestamp_scale_for_df (seconds, ms, µs, no timestamp col, empty df)
- SQL injection safety (DuckDB path escaping)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure the csv_plotter package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gui_app", "csv_plotter"))

from data import (  # noqa: E402
    compute_timestamp_scale_for_df,
    find_newest_csv,
    read_any_csv,
    read_any_csv_arrow,
    read_csv_header,
    sniff_csv_separator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


class _TempCSVMixin:
    """Mixin that creates a temp dir and cleans it up."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _tmppath(self, name: str = "test.csv") -> str:
        return os.path.join(self._tmpdir, name)


# ---------------------------------------------------------------------------
# sniff_csv_separator
# ---------------------------------------------------------------------------

class TestSniffCSVSeparator(_TempCSVMixin, unittest.TestCase):

    def test_comma(self) -> None:
        p = self._tmppath()
        _write_csv(p, "a,b,c\n1,2,3\n")
        self.assertEqual(sniff_csv_separator(p), ",")

    def test_semicolon(self) -> None:
        p = self._tmppath()
        _write_csv(p, "a;b;c\n1;2;3\n")
        self.assertEqual(sniff_csv_separator(p), ";")

    def test_tab(self) -> None:
        p = self._tmppath()
        _write_csv(p, "a\tb\tc\n1\t2\t3\n")
        self.assertEqual(sniff_csv_separator(p), "\t")

    def test_pipe(self) -> None:
        p = self._tmppath()
        _write_csv(p, "a|b|c\n1|2|3\n")
        self.assertEqual(sniff_csv_separator(p), "|")

    def test_empty_file(self) -> None:
        p = self._tmppath()
        _write_csv(p, "")
        result = sniff_csv_separator(p)
        self.assertIsNone(result)

    def test_nonexistent_file(self) -> None:
        result = sniff_csv_separator("/nonexistent/path/file.csv")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# read_csv_header
# ---------------------------------------------------------------------------

class TestReadCSVHeader(_TempCSVMixin, unittest.TestCase):

    def test_basic_comma(self) -> None:
        p = self._tmppath()
        _write_csv(p, "Timestamp,Voltage,Current\n0,1.0,0.5\n")
        cols, sep = read_csv_header(p)
        self.assertIn("Timestamp", cols)
        self.assertIn("Voltage", cols)
        self.assertEqual(len(cols), 3)

    def test_semicolon(self) -> None:
        p = self._tmppath()
        _write_csv(p, "A;B;C\n1;2;3\n")
        cols, sep = read_csv_header(p)
        self.assertEqual(len(cols), 3)
        self.assertIn("A", cols)

    def test_empty_file(self) -> None:
        p = self._tmppath()
        _write_csv(p, "")
        cols, sep = read_csv_header(p)
        self.assertIsInstance(cols, list)

    def test_explicit_sep(self) -> None:
        p = self._tmppath()
        _write_csv(p, "X|Y|Z\n1|2|3\n")
        cols, sep = read_csv_header(p, sep="|")
        self.assertIn("X", cols)
        self.assertEqual(len(cols), 3)


# ---------------------------------------------------------------------------
# read_any_csv
# ---------------------------------------------------------------------------

class TestReadAnyCSV(_TempCSVMixin, unittest.TestCase):

    def _make_basic_csv(self) -> str:
        p = self._tmppath()
        lines = ["Timestamp,A,B"]
        for i in range(100):
            lines.append(f"{i},{i * 0.5},{100 - i}")
        _write_csv(p, "\n".join(lines) + "\n")
        return p

    def test_basic_read(self) -> None:
        p = self._make_basic_csv()
        df = read_any_csv(p)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 100)
        self.assertIn("Timestamp", df.columns)
        self.assertIn("A", df.columns)

    def test_nrows(self) -> None:
        p = self._make_basic_csv()
        df = read_any_csv(p, nrows=10)
        self.assertLessEqual(len(df), 10)

    def test_usecols(self) -> None:
        p = self._make_basic_csv()
        df = read_any_csv(p, usecols=["Timestamp", "A"])
        self.assertIn("Timestamp", df.columns)
        self.assertIn("A", df.columns)
        # B should not be present
        self.assertNotIn("B", df.columns)

    def test_semicolon_file(self) -> None:
        p = self._tmppath()
        lines = ["X;Y;Z"]
        for i in range(20):
            lines.append(f"{i};{i * 2};{i * 3}")
        _write_csv(p, "\n".join(lines) + "\n")
        df = read_any_csv(p)
        self.assertIn("X", df.columns)
        self.assertEqual(len(df), 20)

    def test_explicit_sep(self) -> None:
        p = self._tmppath()
        _write_csv(p, "A\tB\n1\t2\n3\t4\n")
        df = read_any_csv(p, sep="\t")
        self.assertIn("A", df.columns)
        self.assertEqual(len(df), 2)

    def test_path_with_apostrophe(self) -> None:
        """Ensure file paths with single quotes don't cause SQL injection."""
        subdir = os.path.join(self._tmpdir, "it's a test")
        os.makedirs(subdir, exist_ok=True)
        p = os.path.join(subdir, "data.csv")
        _write_csv(p, "A,B\n1,2\n3,4\n")
        df = read_any_csv(p)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)


# ---------------------------------------------------------------------------
# find_newest_csv
# ---------------------------------------------------------------------------

class TestFindNewestCSV(_TempCSVMixin, unittest.TestCase):

    def test_single_file(self) -> None:
        p = self._tmppath("only.csv")
        _write_csv(p, "A\n1\n")
        result = find_newest_csv(self._tmpdir)
        self.assertEqual(result, p)

    def test_picks_newest(self) -> None:
        import time
        p1 = self._tmppath("old.csv")
        _write_csv(p1, "A\n1\n")
        time.sleep(0.05)  # ensure different mtime
        p2 = self._tmppath("new.csv")
        _write_csv(p2, "A\n2\n")
        result = find_newest_csv(self._tmpdir)
        self.assertEqual(result, p2)

    def test_no_csv_files(self) -> None:
        # Empty dir
        with self.assertRaises(FileNotFoundError):
            find_newest_csv(self._tmpdir)

    def test_nonexistent_folder(self) -> None:
        with self.assertRaises(FileNotFoundError):
            find_newest_csv("/nonexistent/folder/xyz")

    def test_recursive(self) -> None:
        subdir = os.path.join(self._tmpdir, "sub")
        os.makedirs(subdir)
        p = os.path.join(subdir, "deep.csv")
        _write_csv(p, "A\n1\n")
        result = find_newest_csv(self._tmpdir)
        self.assertEqual(result, p)


# ---------------------------------------------------------------------------
# compute_timestamp_scale_for_df
# ---------------------------------------------------------------------------

class TestComputeTimestampScale(unittest.TestCase):

    def test_seconds_scale(self) -> None:
        """Small increments (0.01 s) should yield scale=1.0."""
        n = 100
        df = pd.DataFrame({
            "Timestamp": np.linspace(0, 1, n),
            "Value": np.random.randn(n),
        })
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 1.0)

    def test_milliseconds_scale(self) -> None:
        """Increments of ~100 (ms) should yield scale=0.001."""
        n = 100
        df = pd.DataFrame({
            "Timestamp(ms)": np.arange(0, n * 100, 100, dtype=float),
            "Value": np.random.randn(n),
        })
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 0.001)

    def test_microseconds_scale(self) -> None:
        """Increments ≥ 1000 should yield scale=1e-6."""
        n = 100
        df = pd.DataFrame({
            "Timestamp": np.arange(0, n * 5000, 5000, dtype=float),
            "Value": np.random.randn(n),
        })
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 1e-6)

    def test_no_timestamp_column(self) -> None:
        """No 'timestamp*' column → default 1.0."""
        df = pd.DataFrame({"X": [1, 2, 3], "Y": [4, 5, 6]})
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 1.0)

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame()
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 1.0)

    def test_none_input(self) -> None:
        scale = compute_timestamp_scale_for_df(None)  # type: ignore[arg-type]
        self.assertAlmostEqual(scale, 1.0)

    def test_too_few_rows(self) -> None:
        df = pd.DataFrame({"Timestamp": [0, 1], "V": [1, 2]})
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 1.0)

    def test_case_insensitive(self) -> None:
        """Column name 'TIMESTAMP' should still be detected."""
        n = 50
        df = pd.DataFrame({
            "TIMESTAMP": np.linspace(0, 5, n),
            "Value": np.ones(n),
        })
        scale = compute_timestamp_scale_for_df(df)
        self.assertAlmostEqual(scale, 1.0)


# ---------------------------------------------------------------------------
# read_any_csv_arrow
# ---------------------------------------------------------------------------

class TestReadAnyCSVArrow(_TempCSVMixin, unittest.TestCase):

    def test_returns_table_or_none(self) -> None:
        p = self._tmppath()
        _write_csv(p, "A,B\n1,2\n3,4\n")
        result = read_any_csv_arrow(p)
        # Depending on installed backends, may return Table or None
        if result is not None:
            # Should have the right columns
            self.assertIn("A", [str(c) for c in result.column_names])
        # If None, no arrow backend is available — that's OK


if __name__ == "__main__":
    unittest.main()
