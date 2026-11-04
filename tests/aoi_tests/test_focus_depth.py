"""Tests for pyontrust.analysis.focus_depth (native depth-from-focus)."""
from __future__ import annotations

import struct

import cv2
import numpy as np
import pytest

from pyontrust.analysis.focus_depth import (
    FocusDepthAnalyzer,
    best_focus_map,
    export_heightmap_png,
    height_to_stl,
    heightmap_from_index,
)


def _frames(n: int = 6, w: int = 160, h: int = 120):
    """Left half sharp at frame 1, right half sharp at frame n-2."""
    rng = np.random.default_rng(7)
    tex = rng.integers(0, 255, (h, w), dtype=np.uint8)
    out = []
    for i in range(n):
        img = tex.copy()
        sl, sr = abs(i - 1), abs(i - (n - 2))
        if sl:
            img[:, : w // 2] = cv2.GaussianBlur(img[:, : w // 2], (0, 0), sl * 1.5)
        if sr:
            img[:, w // 2:] = cv2.GaussianBlur(img[:, w // 2:], (0, 0), sr * 1.5)
        out.append(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    return out


class TestBestFocusMap:
    def test_recovers_known_focus_indices(self):
        idx, conf = best_focus_map(_frames())
        assert np.median(idx[:, :40]) == 1.0
        assert np.median(idx[:, 120:]) == 4.0

    def test_confidence_in_unit_range(self):
        _, conf = best_focus_map(_frames())
        assert conf.min() >= 0.0 and conf.max() <= 1.0

    def test_single_frame_rejected(self):
        with pytest.raises(ValueError, match="at least 2"):
            best_focus_map([np.zeros((8, 8, 3), np.uint8)])

    def test_shape_mismatch_rejected(self):
        a = np.zeros((10, 10, 3), np.uint8)
        b = np.zeros((12, 10, 3), np.uint8)
        with pytest.raises(ValueError, match="shape"):
            best_focus_map([a, b])


class TestHeightmap:
    def test_index_to_height(self):
        idx = np.array([[0, 1], [2, 5]], dtype=np.int32)
        h = heightmap_from_index(idx, z0_um=100.0, step_um=5.0)
        assert h.tolist() == [[100.0, 105.0], [110.0, 125.0]]

    def test_bad_step_rejected(self):
        with pytest.raises(ValueError, match="step_um"):
            heightmap_from_index(np.zeros((2, 2), np.int32), step_um=0)



class TestStlExport:
    def test_triangle_count_and_file_layout(self, tmp_path):
        h = np.zeros((4, 5), dtype=np.float32)
        out, n_tri = height_to_stl(h, path=tmp_path / "m.stl")
        expected = 2 * (4 - 1) * (5 - 1)
        assert n_tri == expected
        blob = open(out, "rb").read()
        assert len(blob) == 80 + 4 + n_tri * 50
        assert struct.unpack("<I", blob[80:84])[0] == n_tri

    def test_decimation_respects_max_cells(self, tmp_path):
        h = np.random.default_rng(3).random((64, 64)).astype(np.float32)
        out, n_tri = height_to_stl(h, path=tmp_path / "m.stl", max_cells=1000)
        assert n_tri <= 2 * 1000

    def test_1d_rejected(self):
        with pytest.raises(ValueError, match="2-D"):
            height_to_stl(np.zeros(5, dtype=np.float32))


class TestAnalyzer:
    def test_end_to_end_heights_and_exports(self, tmp_path):
        res = FocusDepthAnalyzer(step_um=5.0, z0_um=100.0).run(
            _frames(), out_dir=tmp_path, export=("png", "stl")
        )
        assert res.height_um[60, 20] == pytest.approx(105.0)   # left: idx 1
        assert res.height_um[60, 140] == pytest.approx(120.0)  # right: idx 4
        png = cv2.imread(res.exports["heightmap_png"], cv2.IMREAD_UNCHANGED)
        assert png.dtype == np.uint16 and png.shape[:2] == res.height_um.shape
        stl = open(res.exports["mesh_stl"], "rb").read()
        n_tri = struct.unpack("<I", stl[80:84])[0]
        h, w = res.height_um.shape
        assert len(stl) == 84 + n_tri * 50

    def test_no_exports_requested(self, tmp_path):
        res = FocusDepthAnalyzer().run(_frames(), out_dir=tmp_path, export=())
        assert res.exports == {}
