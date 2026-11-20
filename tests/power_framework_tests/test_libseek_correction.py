"""Seek Compact image correction: shutter FFC, bad pixels, frame selection."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from pyontrust.instruments import libseek_driver as ld  # noqa: E402


def _cam():
    cam = ld.LibSeekCamera(camera_type="compact")
    cam._is_opened = True
    return cam


def _scene(rng, h=154, w=206):
    y, x = np.mgrid[:h, :w]
    scene = 6500 + 300 * ((x - 100) ** 2 + (y - 77) ** 2 < 30 ** 2)  # warm disc
    fpn = rng.normal(0, 1800, (h, w))                                # per-pixel offsets
    bad = rng.random((h, w)) < 0.05
    return scene.astype(np.float32), fpn.astype(np.float32), bad


def test_ffc_removes_fixed_pattern_and_bad_pixels():
    rng = np.random.default_rng(1)
    scene, fpn, bad = _scene(rng)
    shutter = 6900 + fpn
    shutter[bad] += 3000
    cam = _cam()
    cam._ffc_frame = np.clip(shutter, 0, 65535).astype(np.uint16)
    out = None
    for _ in range(ld.BAD_PIXEL_FRAMES + 1):
        cam._last_raw = np.clip(scene + fpn + rng.normal(0, 3, scene.shape), 0, 65535).astype(np.uint16)
        out = cam._retrieve().astype(np.float32)
    assert cam._bad_mask is not None and cam._bad_mask[bad].mean() > 0.95
    # The disc must stand out clearly against a flat background.
    y, x = np.mgrid[:154, :206]
    disc = (x - 100) ** 2 + (y - 77) ** 2 < 25 ** 2
    bg = (x - 100) ** 2 + (y - 77) ** 2 > 40 ** 2
    assert out[disc].mean() - out[bg].mean() == pytest.approx(300, abs=30)
    assert out[bg].std() < 15, "background must be flat after correction"


def test_pre_calibration_frames_never_used_as_image(monkeypatch):
    cam = _cam()
    raw = ld.COMPACT_RAW_WIDTH * ld.COMPACT_RAW_HEIGHT

    def frame(fid, val):
        f = np.full(raw, val, np.uint16)
        f[10] = fid
        return f

    seq = iter([frame(6, 1111), frame(1, 2222), frame(3, 3333)])
    monkeypatch.setattr(cam, "_get_frame", lambda: next(seq))
    assert cam._do_grab()
    assert int(np.median(cam._last_raw)) == 3333
    assert int(np.median(cam._ffc_frame)) == 2222


def test_flat_field_capture_save_and_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("PYONTRUST_SEEK_FLAT_FIELD", str(tmp_path / "ff.npy"))
    cam = _cam()
    vignette = np.zeros((154, 206), np.float32)
    vignette[:, :20] = 40.0  # warm left edge
    monkeypatch.setattr(cam, "grab", lambda: (8000 + vignette).astype(np.uint16))
    info = cam.capture_flat_field(8)
    assert (tmp_path / "ff.npy").is_file() and info["frames"] == 8

    cam2 = _cam()
    cam2._load_saved_flat_field()
    cam2._last_raw = (8000 + vignette).astype(np.uint16)
    out = cam2._retrieve().astype(np.float32)
    assert np.ptp(out) <= 1, "flat-field must cancel the vignette"

    cam2.clear_flat_field()
    assert not (tmp_path / "ff.npy").exists() and cam2._additional_ffc is None
