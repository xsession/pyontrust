"""Spectroscopy GUI backend — slit-image spectrometer pipeline.

Wraps :class:`pyontrust.mobile.spectroscopy.SpectrometerPipeline` (Theremino
V5 port: column extraction -> irradiance correction -> dark subtraction ->
spatial smoothing -> nm-grid resampling) behind a small JSON API for the
``/spec`` web page, plus peak detection with reference-line labelling from
``pyontrust.mobile.spectroscopy.known_lines``.

The default source is a synthetic slit image (diffraction-grating style) with
the selected lamp's emission lines, so the tool works out of the box without
camera hardware; real slit images can be uploaded in ``upload`` mode.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_from_directory
from pathlib import Path

logger = logging.getLogger("pyontrust.gateway.spectroscopy")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "spec"
bp = Blueprint(
    "spectroscopy", __name__, static_folder=str(_WEB_DIR), static_url_path="/static",
)


def _json_body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/lamps")
def lamps() -> Response:
    from pyontrust.mobile.spectroscopy.known_lines import KNOWN_LINES_NM

    return jsonify({"ok": True, "lamps": sorted(KNOWN_LINES_NM.keys())})


def _synthetic_slit_image(
    lamp_lines: list[float], width: int = 512, height: int = 64, seed: int = 7,
) -> np.ndarray:
    """Diffraction-grating slit image with the lamp's emission lines.

    Column i maps linearly to ``nm_min + (nm_max - nm_min) * i / (width - 1)``
    over [380, 750] nm — matching the calibration used in :func:`run_spectrum`.
    Each line is a Gaussian on top of a smooth continuum; per-pixel values are
    identical across RGB channels (the pipeline sums all three).
    """
    rng = np.random.default_rng(seed)
    nm_min, nm_max = 380.0, 750.0

    nms = nm_min + (nm_max - nm_min) * np.arange(width) / max(1, width - 1)
    # smooth continuum background (~12% of full scale with a gentle slope)
    spec = 0.10 + 0.04 * (nms - nm_min) / (nm_max - nm_min)

    bins_per_nm = max(1, width - 1) / (nm_max - nm_min)
    for line in lamp_lines:
        if not (nm_min <= line <= nm_max):
            continue
        amp = float(rng.uniform(0.55, 1.0))
        sigma_nm = float(rng.uniform(1.2, 2.6))
        spec += amp * np.exp(-0.5 * ((nms - line) / (sigma_nm * bins_per_nm)) ** 2)

    spec += rng.normal(0.0, 0.004, width)
    col = np.clip(spec, 0.0, 1.0)

    img = np.zeros((height, width, 3), dtype=np.uint8)
    for c in range(3):
        # slight per-channel gain so RGB weighting is exercised realistically
        img[:, :, c] = (col * rng.uniform(200, 255)).astype(np.uint8)
    return img


def _decode_image(b64: str) -> np.ndarray:
    import cv2

    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # BGR
    if img is None:
        raise ValueError("could not decode image (expected PNG/JPEG)")
    return img[:, :, ::-1]  # -> RGB


@bp.route("/api/run", methods=["POST"])
def run_spectrum() -> Response:
    """Run one slit image through the full pipeline; return spectrum + peaks."""
    body = _json_body()
    mode = str(body.get("mode", "simulated"))

    nm_min = float(body.get("nm_min", 380.0))
    nm_max = float(body.get("nm_max", 750.0))
    n_bins = max(64, min(1024, int(body.get("n_bins", 256))))
    kfilter = float(np.clip(float(body.get("kfilter", 0.5)), 0.05, 1.0))
    average_n = max(1, min(32, int(body.get("average_n", 1))))

    from pyontrust.mobile.spectroscopy import (
        SpectrometerPipeline, WavelengthCalibration, find_peaks, nearest_line,
    )
    from pyontrust.mobile.spectroscopy.known_lines import KNOWN_LINES_NM

    t0 = time.time()

    if mode == "upload":
        img_b64 = str(body.get("image_b64") or "")
        if not img_b64:
            return jsonify({"ok": False, "error": "upload mode requires image_b64"}), 400
        image = _decode_image(img_b64)
    else:
        lamp = str(body.get("lamp", "mercury"))
        if lamp not in KNOWN_LINES_NM:
            return jsonify({"ok": False, "error": f"unknown lamp '{lamp}'"}), 400
        seed = int(body.get("seed", 7))
        image = _synthetic_slit_image(KNOWN_LINES_NM[lamp], width=512, height=64, seed=seed)

    # Linear calibration: sensor bin i <-> nm over [nm_min, nm_max] (width-1 bins).
    n_cols = int(image.shape[1])
    calib_bins = np.arange(n_cols, dtype=np.float64)
    calib_nms = nm_min + (nm_max - nm_min) * calib_bins / max(1, n_cols - 1)

    pipe = SpectrometerPipeline(
        WavelengthCalibration(bins=calib_bins, nms=calib_nms),
        nm_min=nm_min, nm_max=nm_max, n_bins=n_bins, kfilter=kfilter, average_n=average_n,
    )
    spectrum = np.asarray(pipe.process_image(image), dtype=np.float64).reshape(-1)

    # Uniform output grid: nm_i = nm_min + (nm_max - nm_min) * i / n_bins
    grid_nm = nm_min + (nm_max - nm_min) * np.arange(n_bins) / n_bins

    peaks_raw = find_peaks(spectrum, delta=3)
    # Significance gate: drop noise bumps riding on the continuum slope — keep
    # only peaks at >= 20% of the strongest peak (real emission lines).
    sig_floor = 0.2 * float(spectrum.max()) if spectrum.size else 0.0
    peaks_raw = [(i, v) for i, v in peaks_raw if v >= sig_floor]
    lamp_for_label = str(body.get("lamp", "mercury")) if mode == "simulated" else "mercury"
    peaks: list[dict[str, Any]] = []
    for idx, value in peaks_raw:
        nm = float(grid_nm[idx])
        ref_nm, delta = nearest_line(nm, lamp_for_label)
        peaks.append({
            "index": int(idx),
            "nm": round(nm, 2),
            "intensity": round(float(value), 1),
            "nearest_nm": float(ref_nm),
            "delta_nm": round(float(delta), 3),
        })

    s = spectrum
    stats: dict[str, Any] = {
        "mode": mode,
        "n_bins": int(n_bins),
        "nm_min": nm_min, "nm_max": nm_max,
        "n_peaks": len(peaks),
        "strongest_nm": peaks[0]["nm"] if peaks else None,
        "max_intensity": round(float(s.max()), 1) if s.size else 0.0,
        "median_intensity": round(float(np.median(s)), 1) if s.size else 0.0,
        "elapsed_s": round(time.time() - t0, 3),
    }

    logger.info("spectroscopy run (%s): %d peaks in %.3fs", mode, len(peaks), stats["elapsed_s"])

    return jsonify({
        "ok": True,
        "stats": stats,
        "grid_nm": [round(float(v), 3) for v in grid_nm],
        "spectrum": [float(v) for v in s],
        "peaks": peaks,
    })
