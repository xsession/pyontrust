"""Automated depth-from-focus pipeline: capture -> stack -> metric depth -> report.

One call does the whole job (no external programs):

    from pyontrust.analysis.auto_depth import AutoDepthPipeline
    pipe = AutoDepthPipeline(n_frames=16, step_um=2.0)
    rep = pipe.run()                      # captures via ADB helper APK
    rep.height_um                        # metric height map in um
    rep.report_path                      # JSON report with stats + exports

If ``frames`` are supplied (e.g. from a microscope rig or the camera island),
capture is skipped and only stack+depth+report run.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoDepthReport:
    """Result of :meth:`AutoDepthPipeline.run`."""

    stacked_image: np.ndarray          # uint8 BGR composite
    focus_index_map: np.ndarray        # int32 (H, W) best frame per pixel
    confidence_map: np.ndarray         # float32 (H, W) selection margin
    height_um: np.ndarray              # float32 (H, W) metric height in um
    stats: dict[str, Any] = field(default_factory=dict)
    exports: dict[str, str] = field(default_factory=dict)
    report_path: Path | None = None


class AutoDepthPipeline:
    """Capture -> stack -> depth map -> exports + JSON report."""

    def __init__(
        self,
        n_frames: int = 12,
        step_um: float = 1.0,
        z0_um: float = 0.0,
        window: int = 9,
        gamma: float = 2.0,
        feather_sigma: float = 3.0,
        align: bool = True,
        export: tuple[str, ...] = ("png", "stl"),
        px_um: float = 1.0,
    ) -> None:
        if n_frames < 2:
            raise ValueError("n_frames must be >= 2")
        if step_um <= 0:
            raise ValueError("step_um must be > 0")
        self.n_frames = int(n_frames)
        self.step_um = float(step_um)
        self.z0_um = float(z0_um)
        self.window = window
        self.gamma = gamma
        self.feather_sigma = feather_sigma
        self.align = align
        self.export = tuple(export)
        self.px_um = float(px_um)



    def run(
        self,
        frames: Sequence[np.ndarray] | None = None,
        backend: str = "auto",
        camera_id: int = 0,
        out_dir: str | Path = "/tmp/pyontrust_auto_depth",
    ) -> AutoDepthReport:
        """Execute the full pipeline and return a report (with JSON on disk)."""
        t0 = time.time()
        from pyontrust.analysis.focus_depth import best_focus_map, height_to_stl, heightmap_from_index
        from pyontrust.analysis.focus_stacking import FocusSchedule, capture_focus_series, stack_images

        if frames is None:
            schedule = FocusSchedule(n_frames=self.n_frames)
            frames = capture_focus_series(
                n_frames=len(schedule.positions()),
                camera_id=camera_id,
                out_dir=out_dir,
                backend=backend,
                schedule=schedule,
            )
        else:
            schedule = None

        stacked = stack_images(
            [np.asarray(f) for f in frames],
            window=self.window, gamma=self.gamma,
            feather_sigma=self.feather_sigma, align=self.align,
        ).image
        idx, conf = best_focus_map([np.asarray(f) for f in frames], self.window)
        height = heightmap_from_index(idx, z0_um=self.z0_um, step_um=self.step_um)

        out = Path(out_dir)
        exports: dict[str, str] = {}
        if "png" in self.export:
            from pyontrust.analysis.focus_depth import export_heightmap_png
            exports["heightmap_png"] = str(export_heightmap_png(height, out / "heightmap.png"))
        if "stl" in self.export:
            path, n_tri = height_to_stl(height, px_um=self.px_um, path=out / "surface.stl")
            exports["mesh_stl"] = str(path)

        h = height.astype(np.float64)
        stats: dict[str, Any] = {
            "n_frames": len(frames),
            "step_um": self.step_um,
            "z0_um": self.z0_um,
            "height_min_um": float(h.min()),
            "height_max_um": float(h.max()),
            "height_mean_um": float(h.mean()),
            "height_std_um": float(h.std()),
            "confidence_mean": float(conf.mean()),
            "elapsed_s": round(time.time() - t0, 3),
        }
        if schedule is not None:
            stats["schedule"] = schedule.to_dict()

        report_path = out / "auto_depth_report.json"
        payload = {**stats, "exports": exports}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2))
        logger.info("auto-depth done: %d frames -> %s (%.1f s)", len(frames), report_path, stats["elapsed_s"])

        return AutoDepthReport(
            stacked_image=stacked, focus_index_map=idx, confidence_map=conf,
            height_um=height, stats=stats, exports=exports, report_path=report_path,
        )


__all__ = ["AutoDepthPipeline", "AutoDepthReport"]

