"""Depth-from-focus: turn a multi-focus stack into metric height maps + meshes.

Pure software — no external programs. Given the same focus series that
``pyontrust.analysis.focus_stacking`` composites, this module recovers *which*
frame is sharpest at every pixel and converts that index into a physical
height map (micrometres) when the stage step size is known:

* ``best_focus_map()``      per-pixel best frame index + selection confidence
* ``heightmap_from_index()`` focus index -> height in um (z0 + idx * step)
* ``export_heightmap_png()`` 16-bit PNG, full-range normalised
* ``height_to_stl()``        binary STL mesh of the surface (vectorised)

Use cases: microscopy / macro AOI with a Z-stage, 3D scanning of small parts,
surface relief analysis. For stereo-camera depth see ``pyontrust.analysis.stereo``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

try:  # OpenCV is required for the imaging path (optional at import time)
    import cv2
except ImportError:  # pragma: no cover - exercised only without opencv
    cv2 = None

logger = logging.getLogger(__name__)


def _require_cv2() -> None:
    if cv2 is None:
        raise RuntimeError(
            "OpenCV (cv2) is required for depth-from-focus. Install with: pip install opencv-python"
        )


@dataclass(frozen=True)
class DepthResult:
    """Output of :meth:`FocusDepthAnalyzer.run`."""

    stacked_image: np.ndarray      # uint8 BGR composite, sharp across the depth range
    focus_index_map: np.ndarray    # int32 (H, W): best frame index per pixel
    confidence_map: np.ndarray     # float32 (H, W) in [0, 1]: selection margin
    height_um: np.ndarray          # float32 (H, W): surface height in micrometres
    z0_um: float                   # height of focus position 0
    step_um: float                 # stage travel between consecutive frames
    exports: dict = field(default_factory=dict)   # path -> written file


def best_focus_map(
    frames: Sequence[np.ndarray], window: int = 9
) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel argmax of local sharpness across a focus series.

    Returns ``(index_map, confidence_map)`` where ``confidence`` is the normalised
    margin between the best and second-best frame at each pixel (1 = unambiguous).
    """
    _require_cv2()
    from pyontrust.analysis.focus_stacking import sharpness_map

    frames = [np.asarray(f) for f in frames]
    if len(frames) < 2:
        raise ValueError("need at least 2 frames")
    h, w = frames[0].shape[:2]
    for i, im in enumerate(frames):
        if im.shape[:2] != (h, w):
            raise ValueError(f"frame {i} shape {im.shape[:2]} != base {(h, w)}")

    maps = np.stack([sharpness_map(im, window) for im in frames]).astype(np.float32)
    idx = np.argmax(maps, axis=0).astype(np.int32)
    best = np.take_along_axis(maps, idx[None], axis=0)[0]
    second = np.sort(maps, axis=0)[-2]
    conf = np.clip((best - second) / (best + 1e-6), 0.0, 1.0).astype(np.float32)
    return idx, conf



def heightmap_from_index(
    index_map: np.ndarray, z0_um: float = 0.0, step_um: float = 1.0
) -> np.ndarray:
    """Convert a best-focus index map to physical height (micrometres).

    ``height = z0_um + index * step_um`` — valid when the Z-stage moved exactly
    ``step_um`` between consecutive captures and frame 0 was at height ``z0_um``.
    """
    if step_um <= 0:
        raise ValueError("step_um must be > 0")
    return (float(z0_um) + index_map.astype(np.float32) * float(step_um)).astype(np.float32)


def export_heightmap_png(height_um: np.ndarray, path: str | Path) -> Path:
    """Write a 16-bit PNG height map, normalised to the full uint16 range."""
    _require_cv2()
    h = np.asarray(height_um, dtype=np.float32)
    lo, hi = float(h.min()), float(h.max())
    if hi - lo < 1e-9:
        norm = np.zeros_like(h, dtype=np.uint16)
    else:
        norm = ((h - lo) / (hi - lo) * 65535.0).astype(np.uint16)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out), norm):
        raise RuntimeError(f"failed to write {out}")
    return out


def height_to_stl(
    height_um: np.ndarray,
    px_um: float = 1.0,
    py_um: float | None = None,
    path: str | Path = "surface.stl",
    max_cells: int = 2_000_000,
) -> tuple[Path, int]:
    """Build a binary STL mesh of the height field (vectorised, no deps).

    Parameters
    ----------
    height_um : float array (H, W) — surface height in micrometres.
    px_um / py_um : physical size of one pixel along X / Y (um).
    max_cells : memory guard; the grid is downsampled if H*W exceeds this.

    Returns ``(path, n_triangles)``.
    """
    _require_cv2()
    h = np.asarray(height_um, dtype=np.float32)
    if h.ndim != 2:
        raise ValueError("height_um must be a 2-D array")
    H, W = h.shape
    if min(H, W) < 2:
        raise ValueError("need at least a 2x2 grid for triangulation")

    if H * W > max_cells:
        scale = float(np.sqrt(max_cells / (H * W)))
        nh = max(2, int(round(H * scale)))
        nw = max(2, int(round(W * scale)))
        h = cv2.resize(h, (nw, nh), interpolation=cv2.INTER_AREA)
        H, W = nh, nw

    py_um = float(py_um if py_um is not None else px_um)
    xs = np.arange(W, dtype=np.float32) * float(px_um)
    ys = np.arange(H, dtype=np.float32) * float(py_um)
    X, Y = np.meshgrid(xs, ys)

    # cell corners (H-1, W-1) each -> 2 triangles with upward normals
    v00 = np.stack([X[:-1, :-1], Y[:-1, :-1], h[:-1, :-1]], axis=-1)
    v10 = np.stack([X[1:, :-1], Y[1:, :-1], h[1:, :-1]], axis=-1)
    v01 = np.stack([X[:-1, 1:], Y[:-1, 1:], h[:-1, 1:]], axis=-1)
    v11 = np.stack([X[1:, 1:], Y[1:, 1:], h[1:, 1:]], axis=-1)

    tris = []
    for a, b, c in ((v00, v10, v11), (v00, v11, v01)):
        e1 = b - a
        e2 = c - a
        n = np.cross(e1, e2)
        nn = np.linalg.norm(n, axis=-1, keepdims=True)
        n = np.where(nn > 0, n / np.maximum(nn, 1e-30), np.array([0.0, 0.0, 1.0], dtype=np.float32))
        tris.append(np.concatenate([n, a, b, c], axis=-1).reshape(-1, 12))
    data = np.concatenate(tris).astype("<f4")

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_tri = int(data.size // 12)
    # binary STL record: normal(3f)+v0(3f)+v1(3f)+v2(3f)+attribute(u2) = 50 bytes
    rec = np.zeros((n_tri, 25), dtype="<u2")
    rec[:, :24] = data.reshape(n_tri, 12).view("<u2").reshape(n_tri, 24)
    with open(out, "wb") as fh:
        fh.write(b"pyontrust focus-depth mesh".ljust(80, b"\x00"))
        fh.write(np.uint32(n_tri).tobytes())
        fh.write(rec.tobytes())
    return out, n_tri



class FocusDepthAnalyzer:
    """One-call pipeline: frames -> sharp composite + metric depth map + exports.

    >>> analyzer = FocusDepthAnalyzer(step_um=2.0, z0_um=100.0)
    >>> res = analyzer.run(frames, out_dir="out", export=("png", "stl"))
    >>> res.height_um.mean()          # mean surface height in um
    """

    def __init__(self, step_um: float = 1.0, z0_um: float = 0.0, window: int = 9) -> None:
        if step_um <= 0:
            raise ValueError("step_um must be > 0")
        self.step_um = float(step_um)
        self.z0_um = float(z0_um)
        self.window = window

    def run(
        self,
        frames: Sequence[np.ndarray],
        out_dir: str | Path = "/tmp/pyontrust_focus_depth",
        export: tuple[str, ...] = ("png", "stl"),
        px_um: float = 1.0,
    ) -> DepthResult:
        """Composite ``frames`` and derive the depth map; optionally write exports."""
        _require_cv2()
        from pyontrust.analysis.focus_stacking import stack_images

        frames = [np.asarray(f) for f in frames]
        if len(frames) < 2:
            raise ValueError("need at least 2 frames")

        stacked = stack_images(list(frames), window=self.window, align=True).image
        idx, conf = best_focus_map(frames, self.window)
        height = heightmap_from_index(idx, z0_um=self.z0_um, step_um=self.step_um)

        out = Path(out_dir)
        exports: dict[str, str] = {}
        if "png" in export:
            path = out / "heightmap.png"
            _write_png16(height, path)
            exports["heightmap_png"] = str(path)
        if "stl" in export:
            path, n_tri = height_to_stl(height, px_um=px_um, path=out / "surface.stl")
            exports["mesh_stl"] = str(path)
            logger.info("STL mesh written: %s (%d triangles)", path, n_tri)

        return DepthResult(
            stacked_image=stacked,
            focus_index_map=idx,
            confidence_map=conf,
            height_um=height,
            z0_um=self.z0_um,
            step_um=self.step_um,
            exports=exports,
        )


def export_heightmap_png(height_um: np.ndarray, path: str | Path) -> Path:
    """Public wrapper: normalise to 16-bit and write a PNG height map."""
    _require_cv2()
    out = Path(path)
    _write_png16(np.asarray(height_um), out)
    return out


def _write_png16(height_um: np.ndarray, path: Path) -> None:
    """Normalise to full 16-bit range and write (uint16 PNG)."""
    h = np.asarray(height_um, dtype=np.float32)
    lo, hi = float(h.min()), float(h.max())
    if hi - lo < 1e-9:
        norm = np.zeros_like(h)
    else:
        norm = (h - lo) / (hi - lo)
    img = (norm * 65535.0).clip(0, 65535).astype(np.uint16)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


__all__ = [
    "DepthResult",
    "FocusDepthAnalyzer",
    "best_focus_map",
    "heightmap_from_index",
    "export_heightmap_png",
    "height_to_stl",
]
