"""Tests for pyontrust.analysis.auto_depth (automated capture->stack->depth pipeline)."""
from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from pyontrust.analysis.auto_depth import AutoDepthPipeline


def _frames(n: int = 6, w: int = 160, h: int = 120):
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


class TestAutoDepthPipeline:
    def test_full_run_with_frames(self, tmp_path):
        rep = AutoDepthPipeline(n_frames=6, step_um=5.0, z0_um=100.0).run(
            frames=_frames(), out_dir=tmp_path
        )
        assert rep.height_um[60, 20] == pytest.approx(105.0)
        assert rep.height_um[60, 140] == pytest.approx(120.0)
        assert set(rep.exports) == {"heightmap_png", "mesh_stl"}

    def test_report_json_written(self, tmp_path):
        rep = AutoDepthPipeline(n_frames=6).run(frames=_frames(), out_dir=tmp_path)
        payload = json.loads(rep.report_path.read_text())
        for key in ("n_frames", "step_um", "height_min_um", "height_max_um", "elapsed_s"):
            assert key in payload
        assert payload["n_frames"] == 6

    def test_no_exports(self, tmp_path):
        rep = AutoDepthPipeline(n_frames=6, export=()).run(frames=_frames(), out_dir=tmp_path)
        assert rep.exports == {}
        assert rep.report_path.exists()

    def test_bad_params_rejected(self):
        with pytest.raises(ValueError, match="n_frames"):
            AutoDepthPipeline(n_frames=1)
        with pytest.raises(ValueError, match="step_um"):
            AutoDepthPipeline(step_um=0)

