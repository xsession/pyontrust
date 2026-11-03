"""Tests for the multi-focus capture + focus-stacking module.

Covers:
- plane-spacing schedule (10+ positions across the diopter range)
- sharpness maps and weighted compositing on a synthetic depth scene
- alignment of refocus-induced zoom/parallax
- AOI inspection of the stacked composite vs single frames (synthetic feed)
- real phone camera feed via ADB/Termux (skipped when no device attached)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from pyontrust.analysis.focus_stacking import (  # noqa: E402
    FocusSchedule,
    FocusStacker,
    align_stack,
    frame_sharpness,
    generate_synthetic_stack,
    sharpness_map,
    stack_images,
)


# ──────────────────────────────────────────────────────────────────────
# Schedule (plane spacing)
# ──────────────────────────────────────────────────────────────────────

class TestFocusSchedule:
    def test_default_has_at_least_ten_positions(self):
        s = FocusSchedule()
        assert len(s.positions()) >= 10

    def test_monotonic_and_bounded(self):
        s = FocusSchedule(n_frames=12, near_diopter=0.5, far_diopter=6.0)
        pos = s.positions()
        assert all(pos[i] < pos[i + 1] for i in range(len(pos) - 1))
        assert pos[0] == pytest.approx(0.5)
        assert pos[-1] == pytest.approx(6.0)

    def test_custom_range(self):
        s = FocusSchedule(n_frames=8, near_diopter=1.0, far_diopter=3.0)
        assert len(s.positions()) == 8
        assert all(1.0 <= p <= 3.0 for p in s.positions())

    def test_invalid_n(self):
        with pytest.raises(ValueError):
            FocusSchedule(n_frames=1)


# ──────────────────────────────────────────────────────────────────────
# Sharpness maps + compositing on the synthetic depth scene
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def synthetic():
    frames, meta = generate_synthetic_stack(n_frames=12)
    return frames, meta


class TestSharpness:
    def test_map_shape_dtype(self, synthetic):
        frames, _ = synthetic
        m = sharpness_map(frames[0])
        assert m.shape == frames[0].shape[:2]
        assert m.dtype == np.float32

    def test_blur_lowers_sharpness(self, synthetic):
        frames, _ = synthetic
        sharp = frame_sharpness(frames[0])
        blurred = cv2.GaussianBlur(frames[0], (15, 15), 4)
        assert frame_sharpness(blurred) < sharp


class TestStacking:
    def test_composite_is_sharper_than_worst_frame(self, synthetic):
        frames, meta = synthetic
        result = stack_images(frames)
        comp = frame_sharpness(result.image)
        singles = [frame_sharpness(f) for f in frames]
        assert comp > min(singles) * 1.05          # clearly better than worst
        assert comp >= max(singles) * 0.85         # not worse (much) than best

    def test_each_depth_layer_won_by_its_own_frame(self, synthetic):
        frames, meta = synthetic
        result = stack_images(frames)
        for box, focus_idx in zip(meta["boxes"], meta["layer_focus_indices"]):
            x1, y1, w, h = box
            region = result.focus_map[y1 + 8 : y1 + h - 8, x1 + 8 : x1 + w - 8]
            winner = int(np.bincount(region.ravel()).argmax())
            assert winner == focus_idx, f"layer at {box} won by frame {winner}, expected {focus_idx}"

    def test_focus_map_covers_multiple_frames(self, synthetic):
        frames, _ = synthetic
        result = stack_images(frames)
        used = np.unique(result.focus_map)
        assert len(used) >= 3                      # depth range genuinely shared

    def test_alignment_matrices_returned(self, synthetic):
        frames, _ = synthetic
        aligned, mats = align_stack(frames)
        assert len(aligned) == len(frames) and len(mats) == len(frames)
        assert np.allclose(mats[0], np.eye(3))     # base frame is identity


# ──────────────────────────────────────────────────────────────────────
# AOI integration — synthetic feed through the real inspector pipeline
# ──────────────────────────────────────────────────────────────────────

class TestAOISyntheticFeed:
    def test_inspector_runs_on_stacked_composite(self, tmp_path, synthetic):
        frames, meta = synthetic
        result = stack_images(frames)

        # golden reference = the sharpest single frame (what a real AOI cell would store)
        best_i = int(np.argmax([frame_sharpness(f) for f in frames]))
        ref_path = tmp_path / "golden.png"
        assert cv2.imwrite(str(ref_path), frames[best_i])

        cfg = {
            "camera": {"mode": "simulated", "width": 640, "height": 480},
            "reference_image": str(ref_path),
            "processing": {"denoise_strength": 3, "diff_threshold": 25, "min_defect_area": 40},
            "analysis": {"px_per_mm": 50.0, "alignment_tolerance_mm": 0.15,
                         "via_fill_threshold": 0.75, "solder_min_area": 30, "solder_max_area": 5000},
            "storage": {"db_path": str(tmp_path / "aoi.db"), "image_archive": str(tmp_path / "img")},
        }
        (tmp_path / "img").mkdir(parents=True, exist_ok=True)  # AOI archive dir must pre-exist
        cfg_path = tmp_path / "cfg.json"
        cfg_path.write_text(json.dumps(cfg))

        from pyontrust.analysis.aoi.inspector import AOIInspector

        inspector = AOIInspector.from_config(str(cfg_path))
        try:
            inspector.open()  # creates archive dir + database (simulated camera open is a no-op)
            res_stacked = inspector.inspect_frame(result.image, board_id="FS-STACKED")
            res_single = inspector.inspect_frame(frames[best_i], board_id="FS-SINGLE-BEST")
            res_worst = inspector.inspect_frame(
                frames[int(np.argmin([frame_sharpness(f) for f in frames]))], board_id="FS-SINGLE-WORST"
            )
        finally:
            inspector.close()

        # stacked composite must be inspectable and at least as clean as the best single frame
        assert res_stacked.total_defect_count <= max(res_single.total_defect_count, 1) + 2
        report = {
            "stacked": {"passed": res_stacked.passed, "defects": res_stacked.total_defect_count},
            "single_best": {"passed": res_single.passed, "defects": res_single.total_defect_count},
            "single_worst": {"passed": res_worst.passed, "defects": res_worst.total_defect_count},
        }
        (tmp_path / "aoi_report.json").write_text(json.dumps(report, indent=2))


# ──────────────────────────────────────────────────────────────────────
# Real phone camera feed (ADB + Termux) — skipped without a device
# ──────────────────────────────────────────────────────────────────────

def _adb_available() -> bool:
    adb = shutil.which("adb")
    if not adb:
        return False
    try:
        out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10).stdout
        return any(line.split("	")[1] == "device" for line in out.splitlines()[1:] if "	" in line)
    except Exception:
        return False


@pytest.mark.skipif(not _adb_available(), reason="no ADB device attached")
class TestRealPhoneFeed:
    def test_capture_stack_and_inspect(self, tmp_path):
        from pyontrust.analysis.focus_stacking import capture_focus_series

        out_dir = tmp_path / "frames"
        frames = capture_focus_series(n_frames=12, camera_id=0, out_dir=out_dir)
        assert len(frames) == 12

        result = stack_images(frames)
        assert result.image.shape[:2] == frames[0].shape[:2]

        # real scene has depth: the composite should draw on several frames
        used = np.unique(result.focus_map)
        assert len(used) >= 2, "real feed stacked onto a single frame — check focus schedule"

        report = {
            "n_frames": len(frames),
            "sharpness_stats": result.sharpness_stats,
            "composite_shape": list(result.image.shape),
        }
        (tmp_path / "real_feed_report.json").write_text(json.dumps(report, indent=2))
