from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ObjectDetectConfig:
    ffmpeg_path: str = "ffmpeg"

    # Extracted-frame rate (frames per second) for analysis.
    fps: float = 2.0
    # Scale frames down for faster analysis; width in pixels.
    scale_width: int = 320

    # Ultralytics YOLO model name or path (downloaded on first run).
    model: str = "yolov8n.pt"
    conf: float = 0.25

    # If True, attempt `pip install ultralytics` inside the current venv.
    bootstrap_ml: bool = False


def _in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _pip_install(packages: list[str]) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *packages])


def _ensure_ffmpeg(cfg: ObjectDetectConfig) -> Optional[str]:
    exe = shutil.which(cfg.ffmpeg_path)
    if exe:
        return exe
    if pathlib.Path(cfg.ffmpeg_path).exists():
        return cfg.ffmpeg_path
    return None


def _ensure_ultralytics(*, cfg: ObjectDetectConfig, module_name: str = "ultralytics") -> tuple[bool, str | None]:
    try:
        __import__(module_name)
        return True, None
    except Exception:
        if not cfg.bootstrap_ml:
            return False, "ml_missing"

    if not _in_virtualenv():
        return False, "refuse_bootstrap_outside_venv"

    try:
        _pip_install(["ultralytics>=8.0.0"])
        __import__(module_name)
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"bootstrap_failed:{type(exc).__name__}"


def _extract_jpegs(video_path: pathlib.Path, out_dir: pathlib.Path, cfg: ObjectDetectConfig) -> list[pathlib.Path]:
    ffmpeg = _ensure_ffmpeg(cfg)
    if ffmpeg is None:
        raise FileNotFoundError(f"ffmpeg not found: {cfg.ffmpeg_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%06d.jpg")

    vf = f"fps={cfg.fps},scale={cfg.scale_width}:-1"

    cmd = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-i",
        str(video_path),
        "-vf",
        vf,
        "-q:v",
        "3",
        pattern,
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )

    return sorted(out_dir.glob("frame_*.jpg"))


def analyze_video_objects(
    *,
    artifacts_root: pathlib.Path,
    video_path: str | os.PathLike[str],
    cfg: ObjectDetectConfig,
    extra: Optional[dict[str, Any]] = None,
    # For tests.
    _ultralytics_module: str = "ultralytics",
) -> dict[str, Any]:
    """Run object detection on frames extracted from a webcam recording.

    Produces:
    - `object_events.jsonl` (one JSON per frame with detections)
    - `object_summary.json`

    Returns a summary dict. If ML is missing and `bootstrap_ml` is False, returns a skipped summary.
    """

    ok_ml, reason = _ensure_ultralytics(cfg=cfg, module_name=_ultralytics_module)

    video = pathlib.Path(video_path)
    if not video.exists():
        raise FileNotFoundError(str(video))

    events_path = artifacts_root / "object_events.jsonl"
    summary_path = artifacts_root / "object_summary.json"

    if not ok_ml:
        summary = {
            "ok": True,
            "skipped": True,
            "reason": reason,
            "video": str(video),
            "backend": "ultralytics",
        }
        if extra:
            summary.update(extra)
        events_path.write_text("", encoding="utf-8")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    from ultralytics import YOLO  # type: ignore

    model = YOLO(cfg.model)

    label_counts: dict[str, int] = {}
    frames_analyzed = 0

    with tempfile.TemporaryDirectory(prefix="object_frames_") as td:
        frame_dir = pathlib.Path(td)
        frames = _extract_jpegs(video, frame_dir, cfg)
        frames_analyzed = len(frames)

        with events_path.open("w", encoding="utf-8", newline="\n") as f:
            for idx, img in enumerate(frames):
                # Stream=False to keep it simple and deterministic.
                results = model.predict(source=str(img), conf=cfg.conf, verbose=False)
                detections: list[dict[str, Any]] = []

                for r in results:
                    names = getattr(r, "names", {}) or {}
                    boxes = getattr(r, "boxes", None)
                    if boxes is None:
                        continue

                    # Ultralytics Boxes fields are torch tensors.
                    xyxy = getattr(boxes, "xyxy", None)
                    confs = getattr(boxes, "conf", None)
                    clss = getattr(boxes, "cls", None)
                    if xyxy is None or confs is None or clss is None:
                        continue

                    try:
                        xyxy_list = xyxy.tolist()
                        conf_list = confs.tolist()
                        cls_list = clss.tolist()
                    except Exception:
                        continue

                    for b, c, k in zip(xyxy_list, conf_list, cls_list):
                        cls_id = int(k)
                        label = str(names.get(cls_id, cls_id))
                        detections.append(
                            {
                                "label": label,
                                "conf": float(c),
                                "bbox_xyxy": [float(x) for x in b],
                            }
                        )
                        label_counts[label] = label_counts.get(label, 0) + 1

                f.write(
                    json.dumps(
                        {
                            "frame": idx,
                            "detections": detections,
                        }
                    )
                    + "\n"
                )

    top_labels = sorted(label_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

    summary = {
        "ok": True,
        "skipped": False,
        "backend": "ultralytics",
        "video": str(video),
        "frames_analyzed": frames_analyzed,
        "detections": sum(label_counts.values()),
        "top_labels": [{"label": k, "count": v} for k, v in top_labels],
        "config": {
            "ffmpeg_path": cfg.ffmpeg_path,
            "fps": cfg.fps,
            "scale_width": cfg.scale_width,
            "model": cfg.model,
            "conf": cfg.conf,
            "bootstrap_ml": cfg.bootstrap_ml,
        },
    }
    if extra:
        summary.update(extra)

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
