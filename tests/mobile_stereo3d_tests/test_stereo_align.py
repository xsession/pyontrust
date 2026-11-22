"""Camera-position compensation for loosely placed stereo cameras."""
from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from pyontrust.analysis.stereo import StereoAnalyzer, StereoConfig  # noqa: E402
from pyontrust.analysis.stereo_align import (AlignmentError, PairAlignment, blend,  # noqa: E402
                                             estimate_alignment)

H, W = 480, 640


def _scene(seed=1):
    """left/right of a textured background (disparity 20 px) and a near box (50 px)."""
    rng = np.random.default_rng(seed)
    tex = cv2.GaussianBlur((rng.random((H, W + 300)) * 255).astype(np.uint8), (0, 0), 1.2)
    left = tex[:, 100:100 + W].copy()
    right = tex[:, 120:120 + W].copy()
    right[150:330, 250:450] = tex[150:330, 400:600]
    return left, right


def _misplace(img, roll=3.0, zoom=1.1, dy=25):
    M = cv2.getRotationMatrix2D((W / 2, H / 2), roll, zoom)
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, H))


def test_recovers_zoom_roll_and_height():
    left, right = _scene()
    al = estimate_alignment(left, _misplace(right))
    assert al.scale == pytest.approx(1 / 1.1, rel=2e-3)
    assert al.roll_deg == pytest.approx(3.0, abs=0.05)
    assert al.residual_px < 0.3 and al.before_px > 10
    assert not al.swapped


def test_alignment_restores_matching_and_relative_depth():
    left, right = _scene()
    bad = _misplace(right)
    al = estimate_alignment(left, bad)
    fixed = al.warp_right(bad, (W, H))
    cfg = StereoConfig(fx=600, fy=600, cx=W / 2, cy=H / 2, baseline_m=0.1,
                       num_disp=al.num_disp(W), disparity_offset_px=al.offset_px(W))
    res = StereoAnalyzer(cfg).run(left, fixed)
    raw = StereoAnalyzer(StereoConfig(fx=600, fy=600, cx=W / 2, cy=H / 2, baseline_m=0.1, num_disp=96)).run(left, bad)
    assert res.valid_mask.mean() > 2 * raw.valid_mask.mean()
    d = np.where(res.valid_mask, res.disparity_px + al.offset_px(W), np.nan)
    step = np.nanmedian(d[180:300, 320:480]) - np.nanmedian(d[60:140, 60:580])
    assert step == pytest.approx(30, abs=0.5)                     # near box 30 px closer than the background
    z = np.where(res.valid_mask, res.depth_m, np.nan)
    assert np.nanmedian(z[180:300, 320:480]) < np.nanmedian(z[60:140, 60:580])


def test_resolution_independent_and_serialisable():
    left, right = _scene()
    al = estimate_alignment(left, _misplace(right))
    again = PairAlignment.from_dict(al.to_dict())
    assert again == al
    assert again.offset_px(1280) == pytest.approx(2 * al.offset_px(640))
    m2 = al.matrix(2 * W, 2 * H)
    m1 = al.matrix(W, H)
    assert np.allclose(m2[:, :2], m1[:, :2]) and np.allclose(m2[:, 2], 2 * m1[:, 2])


def test_swapped_cameras_are_detected():
    left, right = _scene()
    al = estimate_alignment(right, left)
    assert al.swapped


def test_blend_follows_drift_smoothly():
    a = PairAlignment(scale=1.0, roll_deg=0.0, ty=0.0, shift=0.0, disp_span=0.05)
    b = PairAlignment(scale=1.1, roll_deg=2.0, ty=0.01, shift=0.02, disp_span=0.04)
    m = blend(a, b, 0.5)
    assert m.scale == pytest.approx(1.05) and m.roll_deg == pytest.approx(1.0)
    assert m.disp_span == pytest.approx(0.045)          # window never shrinks below the newest
    assert blend(None, b) is b
    calibrated = PairAlignment(scale=1.0, roll_deg=0.0, ty=0.0, shift=0.0, disp_span=0.05, bias=0.01)
    assert blend(calibrated, b).bias == 0.01, "tracking keeps the reference-distance calibration"


def test_featureless_scene_is_refused():
    flat = np.full((H, W), 128, np.uint8)
    with pytest.raises(AlignmentError):
        estimate_alignment(flat, flat)


# ── gateway ───────────────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    from flask import Flask

    import pyontrust.gateway.blueprints.scan3d as sb

    sb._ALIGN.clear()
    left, right = _scene()
    bad = _misplace(right)
    monkeypatch.setattr(sb, "grab_simultaneous",
                        lambda sources, still=False: {sources[0]: cv2.cvtColor(left, cv2.COLOR_GRAY2BGR),
                                                      sources[1]: cv2.cvtColor(bad, cv2.COLOR_GRAY2BGR)})
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(sb.bp, url_prefix="/scan3d")
    with app.test_client() as c:
        yield c
    sb._ALIGN.clear()


def test_align_route_stores_and_capture_uses_it(client, tmp_path):
    pair = {"left": "usb:0", "right": "usb:2", "rotate": 0}
    q = "left=usb:0&right=usb:2&rotate=0"
    assert client.get(f"/scan3d/api/align?{q}").get_json()["aligned"] is False
    d = client.post("/scan3d/api/align", json={**pair, "width": 640, "tries": 1}).get_json()
    assert d["ok"] and d["alignment"]["scale"] == pytest.approx(1 / 1.1, rel=5e-3)
    assert d["preview"]["before_b64"] and d["preview"]["after_b64"] and d["warning"] is None
    assert client.get(f"/scan3d/api/align?{q}").get_json()["aligned"] is True

    import pyontrust.gateway.blueprints.scan3d as sb
    assert sb._align_file().is_file(), "alignment persisted in the station data dir"

    cap = client.post("/scan3d/api/capture", json={**pair, "max_px": 640, "num_disp": "auto",
                                                   "fx": 600, "fx_width": 640}).get_json()
    assert cap["ok"] and cap["stats"]["aligned"] and cap["stats"]["valid_pct"] > 50

    assert client.post("/scan3d/api/align/clear", json=pair).get_json()["ok"]
    assert client.get(f"/scan3d/api/align?{q}").get_json()["aligned"] is False


def test_reference_distance_calibrates_absolute_depth(client):
    pair = {"left": "usb:0", "right": "usb:2", "rotate": 0}
    d = client.post("/scan3d/api/align", json={**pair, "width": 640, "tries": 1, "ref_distance_mm": 2000,
                                               "fx": 600, "fx_width": 640, "baseline_mm": 100}).get_json()
    assert d["ok"] and "reference" in d["note"]
    cap = client.post("/scan3d/api/capture", json={**pair, "max_px": 640, "fx": 600, "fx_width": 640,
                                                   "baseline_mm": 100}).get_json()
    assert cap["stats"]["depth_median_m"] == pytest.approx(2.0, rel=0.15)


def test_align_rejects_same_camera(client):
    assert client.post("/scan3d/api/align", json={"left": "usb:0", "right": "usb:0"}).status_code == 400


def test_live_depth_aligns_by_itself_and_guides_placement(client):
    import pyontrust.gateway.blueprints.scan3d as sb

    q = "left=usb:0&right=usb:2&rotate=0&width=640&track=1&num_disp=auto"
    r = client.get(f"/scan3d/api/depth_stream?{q}", buffered=False)
    part = next(iter(r.response))
    r.close()
    assert part.startswith(b"--frame") and b"\xff\xd8" in part
    st = client.get("/scan3d/api/depth_stats").get_json()
    assert st["placement"]["ok"] and st["placement"]["inliers"] >= st["placement"]["need"]
    assert st["aligned"] and st["valid_pct"] > 50
    assert client.get("/scan3d/api/align?left=usb:0&right=usb:2&rotate=0").get_json()["aligned"]
    sb._DEPTH_LIVE.clear()


def test_two_cameras_of_one_phone_are_refused(client):
    r = client.post("/scan3d/api/capture", json={"left": "phone:SER1:0", "right": "phone:SER1:2"})
    assert r.status_code == 400 and "one camera at a time" in r.get_json()["error"]
