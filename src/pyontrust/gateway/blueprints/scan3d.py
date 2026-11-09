"""3D Scan GUI backend — stereo depth, disparity and point cloud.

Wraps :class:`pyontrust.analysis.stereo.StereoAnalyzer` (rectify -> SGBM
disparity -> metric depth ``Z = fx*B/d`` -> XYZ point cloud) behind a small
JSON API for the ``/scan3d`` web page.

Two input modes:
  * ``simulated`` — a synthetic textured scene with objects at known depths
    (works out of the box, no hardware needed);
  * ``upload``    — base64-encoded left/right images from a real stereo rig.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_from_directory
from pathlib import Path

logger = logging.getLogger("pyontrust.gateway.scan3d")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "scan3d"
bp = Blueprint(
    "scan3d", __name__, static_folder=str(_WEB_DIR), static_url_path="/static",
)


def _json_body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _b64_png(arr: np.ndarray) -> str:
    import cv2

    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return base64.b64encode(buf.tobytes()).decode()


def _decode_image(b64: str) -> np.ndarray:
    import cv2

    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image (expected PNG/JPEG)")
    return img


def _synthetic_pair(cfg: Any, width: int = 480, height: int = 360, seed: int = 11):
    """Textured scene with three objects at known depths + a far background.

    The texture is low-frequency value noise (smooth gradients), which SGBM
    block matching handles well — pure white noise would defeat it.  Every
    region gets its true disparity ``d = fx * baseline / Z`` applied in the
    right image, so the recovered depth map shows flat plateaus at each
    object's depth and a plateau at the background depth (5 m).
    """
    import cv2

    rng = np.random.default_rng(seed)

    # Structured texture: small random grid upscaled with cubic interpolation.
    gw, gh = max(8, width // 16), max(8, height // 16)
    coarse = rng.integers(40, 220, (gh, gw)).astype(np.float32)
    gray = cv2.resize(coarse, (width, height), interpolation=cv2.INTER_CUBIC)
    gray = np.clip(gray.astype(np.uint8), 0, 255)
    left = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    objects = [
        dict(x=int(width * 0.25), y=int(height * 0.30), ow=90, oh=70, z_m=0.5),   # near (d≈86px)
        dict(x=int(width * 0.45), y=int(height * 0.15), ow=120, oh=90, z_m=1.0),  # mid  (d≈43px)
        dict(x=int(width * 0.70), y=int(height * 0.55), ow=75, oh=65, z_m=2.0),   # far  (d≈22px)
    ]

    right = left.copy()

    def shift_region(img_l: np.ndarray, img_r: np.ndarray, x0: int, y0: int, ow: int, oh: int, d_px: float) -> None:
        """Copy region from left into right shifted left by round(d_px)."""
        shift = int(round(d_px))
        if shift <= 0:
            return
        dx0, dx1 = max(0, x0 - shift), min(width, x0 + ow - shift)
        if dx1 <= dx0:
            return
        cx0 = x0 + (dx0 - (x0 - shift))  # source column aligned to clipped dest
        for c in range(3):
            img_r[y0:y0 + oh, dx0:dx1, c] = img_l[y0:y0 + oh, cx0:cx0 + (dx1 - dx0), c]

    # Background first: treat as a plane at 5 m so it gets a finite disparity.
    bg_d = float(cfg.fx) * float(cfg.baseline_m) / 5.0
    if int(round(bg_d)) > 0:
        for c in range(3):
            right[:, : width - int(round(bg_d)), c] = left[:, int(round(bg_d)):, c]

    # Objects on top: flat shaded patches (easy to match) at their true depths.
    for o in objects:
        shade = int(rng.integers(140, 230))
        patch = rng.integers(max(0, shade - 25), min(255, shade + 25), (o["oh"], o["ow"]), dtype=np.uint8)
        x0, y0, ow, oh = o["x"], o["y"], o["ow"], o["oh"]
        for c in range(3):
            left[y0:y0 + oh, x0:x0 + ow, c] = patch
        d_px = float(cfg.fx) * float(cfg.baseline_m) / o["z_m"]
        shift_region(left, right, x0, y0, ow, oh, d_px)

    return left, right


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/run", methods=["POST"])
def run_scan() -> Response:
    """Analyse one stereo pair and return depth/disparity images + stats."""
    body = _json_body()
    mode = str(body.get("mode", "simulated"))

    fx = float(body.get("fx", 600.0))
    fy = float(body.get("fy", fx))
    cx = float(body.get("cx", 240.0))
    cy = float(body.get("cy", 180.0))
    baseline_m = float(body.get("baseline_mm", 120.0)) / 1000.0
    num_disp = int(body.get("num_disp", 96))

    from pyontrust.analysis.stereo import StereoAnalyzer, StereoConfig

    cfg = StereoConfig(
        fx=fx, fy=fy, cx=cx, cy=cy, baseline_m=baseline_m,
        num_disp=max(16, (num_disp // 16) * 16), block_size=7, min_disparity=0,
    )

    t0 = time.time()
    if mode == "upload":
        left_b64 = str(body.get("left_b64") or "")
        right_b64 = str(body.get("right_b64") or "")
        if not left_b64 or not right_b64:
            return jsonify({"ok": False, "error": "upload mode requires left_b64 and right_b64"}), 400
        left = _decode_image(left_b64)
        right = _decode_image(right_b64)
    else:
        width = max(128, min(1920, int(body.get("width", 480))))
        height = max(96, min(1920, int(body.get("height", 360))))
        seed = int(body.get("seed", 11))
        left, right = _synthetic_pair(cfg, width=width, height=height, seed=seed)

    res = StereoAnalyzer(cfg).run(left, right)

    valid = res.valid_mask
    depth = res.depth_m
    with np.errstate(invalid="ignore"):
        dmin = float(np.nanmin(depth)) if valid.any() else None
        dmax = float(np.nanmax(depth)) if valid.any() else None
        dmed = float(np.nanmedian(depth)) if valid.any() else None

    # depth map -> colormap (invalid pixels black)
    import cv2

    h, w = depth.shape
    lo, hi = (dmin, dmax) if (dmin is not None and dmax is not None and dmax > dmin) else (0.0, 1.0)
    norm = np.clip((depth - lo) / (hi - lo), 0.0, 1.0)
    depth_img = cv2.applyColorMap((np.nan_to_num(norm) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    depth_img[~valid] = 0

    disp = np.where(res.disparity_px > 0, res.disparity_px, 0.0)
    dmax_disp = float(disp.max()) if disp.size else 1.0
    disp_img = cv2.applyColorMap((np.clip(disp / max(1e-6, dmax_disp), 0.0, 1.0) * 255).astype(np.uint8), cv2.COLORMAP_JET)

    stats: dict[str, Any] = {
        "mode": mode,
        "width": int(w), "height": int(h),
        "valid_pct": round(100.0 * float(valid.mean()), 2),
        "n_points": int(valid.sum()),
        "depth_min_m": dmin, "depth_max_m": dmax, "depth_median_m": dmed,
        "baseline_mm": baseline_m * 1000.0,
        "elapsed_s": round(time.time() - t0, 3),
    }

    logger.info("scan3d run (%s): %.1f%% matched in %.3fs", mode, stats["valid_pct"], stats["elapsed_s"])

    return jsonify({
        "ok": True,
        "stats": stats,
        "images": {
            "left_b64": _b64_png(res.left_rect),
            "right_b64": _b64_png(res.right_rect),
            "depth_b64": _b64_png(depth_img),
            "disparity_b64": _b64_png(disp_img),
        },
    })
