"""Microscopy GUI backend — focus stacking + depth-from-focus.

Wraps :class:`pyontrust.analysis.auto_depth.AutoDepthPipeline` (capture ->
stack -> metric height map -> exports) behind a small JSON API for the
``/micro`` web page.  The default source is a synthetic multi-depth PCB scene
(``generate_synthetic_stack``), so the tool works out of the box without any
camera hardware; supplying real frames later only requires swapping the frame
source in :func:`run_stack`.
"""
from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_from_directory

logger = logging.getLogger("pyontrust.gateway.microscopy")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "micro"
bp = Blueprint(
    "microscopy", __name__, static_folder=str(_WEB_DIR), static_url_path="/static",
)

_LAST: dict[str, Any] = {}  # summary of the most recent run (in-process)


def _json_body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _b64_png(arr: np.ndarray) -> str:
    import cv2

    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return base64.b64encode(buf.tobytes()).decode()


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/run", methods=["POST"])
def run_stack() -> Response:
    """Run the full focus-stacking + depth pipeline and return images + stats."""
    body = _json_body()
    n_frames = max(2, min(32, int(body.get("n_frames", 8))))
    step_um = float(body.get("step_um", 2.0))
    z0_um = float(body.get("z0_um", 0.0))
    px_um = float(body.get("px_um", 1.0))
    width = max(64, min(1920, int(body.get("width", 480))))
    height = max(64, min(1920, int(body.get("height", 360))))
    seed = int(body.get("seed", 7))

    from pyontrust.analysis.auto_depth import AutoDepthPipeline
    from pyontrust.analysis.focus_stacking import generate_synthetic_stack

    # size is (h, w) in the generator's signature
    frames, meta = generate_synthetic_stack(n_frames=n_frames, size=(height, width), seed=seed)

    pipe = AutoDepthPipeline(
        n_frames=len(frames), step_um=step_um, z0_um=z0_um, px_um=px_um,
        export=("png", "stl"),
    )
    out_dir = tempfile.mkdtemp(prefix="pyontrust_micro_")
    rep = pipe.run(frames=frames, out_dir=out_dir)

    heightmap_png_b64: str | None = None
    hm_path = Path(rep.exports.get("heightmap_png", "")) if rep.exports else None
    if hm_path is not None and hm_path.is_file():
        import cv2

        img = cv2.imread(str(hm_path))
        if img is not None:
            heightmap_png_b64 = _b64_png(img)

    logger.info(
        "microscopy run: %d frames, %.1f um range in %.3fs",
        len(frames), rep.stats.get("height_max_um", 0.0) - rep.stats.get("height_min_um", 0.0),
        rep.stats.get("elapsed_s", 0.0),
    )

    _LAST.update(stats=rep.stats, report_path=str(rep.report_path) if rep.report_path else None)

    return jsonify({
        "ok": True,
        "stats": rep.stats,
        "stacked_png_b64": _b64_png(rep.stacked_image),
        "heightmap_png_b64": heightmap_png_b64,
        "exports": {k: str(v) for k, v in (rep.exports or {}).items()},
        "report_path": str(rep.report_path) if rep.report_path else None,
    })


@bp.route("/api/last")
def last_run() -> Response:
    """Summary of the most recent run (kept in-process)."""
    return jsonify({"ok": True, "stats": _LAST.get("stats"), "report_path": _LAST.get("report_path")})
