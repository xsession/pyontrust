from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class VisionChangeConfig:
    ffmpeg_path: str = "ffmpeg"
    # Extracted-frame rate (frames per second) for analysis.
    fps: float = 2.0
    # Scale frames down for faster analysis; width in pixels.
    scale_width: int = 160

    # Modes:
    # - "blink": detects brightness toggling (useful for LEDs).
    # - "display_change": detects large scene/display changes.
    mode: str = "display_change"

    # Blink: brightness delta threshold (0..255)
    blink_brightness_delta: float = 25.0
    # Display change: mean absolute pixel delta threshold (0..255)
    display_change_delta: float = 12.0


def _parse_pgm_p5(path: pathlib.Path) -> tuple[int, int, bytes]:
    """Parse a binary PGM (P5). Returns (width, height, pixels)."""
    data = path.read_bytes()
    if not data.startswith(b"P5\n") and not data.startswith(b"P5\r\n"):
        raise ValueError("Not a P5 PGM")

    idx = 2

    def _read_token() -> bytes:
        nonlocal idx
        # Skip whitespace
        while idx < len(data) and data[idx] in b" \t\r\n":
            idx += 1
        # Skip comments
        if idx < len(data) and data[idx] == ord("#"):
            while idx < len(data) and data[idx] not in b"\r\n":
                idx += 1
            return _read_token()
        start = idx
        while idx < len(data) and data[idx] not in b" \t\r\n":
            idx += 1
        return data[start:idx]

    w = int(_read_token())
    h = int(_read_token())
    maxval = int(_read_token())
    if maxval != 255:
        raise ValueError(f"Unsupported PGM maxval: {maxval}")

    # Skip single whitespace char after maxval if present.
    while idx < len(data) and data[idx] in b" \t\r\n":
        idx += 1
        break

    pixels = data[idx : idx + (w * h)]
    if len(pixels) != (w * h):
        raise ValueError("Truncated PGM")
    return w, h, pixels


def _mean_u8(values: bytes) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _mean_abs_diff(a: bytes, b: bytes) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    total = 0
    for i in range(n):
        total += abs(a[i] - b[i])
    return float(total) / float(n)


def _ensure_ffmpeg(cfg: VisionChangeConfig) -> Optional[str]:
    exe = shutil.which(cfg.ffmpeg_path)
    if exe:
        return exe
    # allow absolute paths
    if pathlib.Path(cfg.ffmpeg_path).exists():
        return cfg.ffmpeg_path
    return None


def _extract_pgms(video_path: pathlib.Path, out_dir: pathlib.Path, cfg: VisionChangeConfig) -> list[pathlib.Path]:
    ffmpeg = _ensure_ffmpeg(cfg)
    if ffmpeg is None:
        raise FileNotFoundError(f"ffmpeg not found: {cfg.ffmpeg_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%06d.pgm")

    # Use grayscale PGM to avoid extra dependencies (PIL/OpenCV).
    vf = f"fps={cfg.fps},scale={cfg.scale_width}:-1,format=gray"

    cmd = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-i",
        str(video_path),
        "-vf",
        vf,
        "-vcodec",
        "pgm",
        pattern,
    ]

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )

    return sorted(out_dir.glob("frame_*.pgm"))


def analyze_video_changes(
    *,
    artifacts_root: pathlib.Path,
    video_path: str | os.PathLike[str],
    cfg: VisionChangeConfig,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Analyze a recorded webcam video and write change logs into artifacts.

    Produces:
    - `vision_events.jsonl`
    - `vision_summary.json`

    Returns a summary dict.
    """

    video = pathlib.Path(video_path)
    if not video.exists():
        raise FileNotFoundError(str(video))

    events_path = artifacts_root / "vision_events.jsonl"
    summary_path = artifacts_root / "vision_summary.json"

    events: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="vision_frames_") as td:
        frame_dir = pathlib.Path(td)
        frames = _extract_pgms(video, frame_dir, cfg)
        if len(frames) < 2:
            summary = {
                "ok": True,
                "mode": cfg.mode,
                "frames": len(frames),
                "events": 0,
                "reason": "not_enough_frames",
            }
            if extra:
                summary.update(extra)
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            events_path.write_text("", encoding="utf-8")
            return summary

        prev_pixels: bytes | None = None
        prev_mean: float | None = None

        for idx, frame in enumerate(frames):
            _, _, pixels = _parse_pgm_p5(frame)
            mean = _mean_u8(pixels)

            if prev_pixels is not None and prev_mean is not None:
                if cfg.mode == "blink":
                    delta = abs(mean - prev_mean)
                    if delta >= cfg.blink_brightness_delta:
                        events.append(
                            {
                                "frame": idx,
                                "metric": "brightness_delta",
                                "value": delta,
                            }
                        )
                else:
                    delta = _mean_abs_diff(prev_pixels, pixels)
                    if delta >= cfg.display_change_delta:
                        events.append(
                            {
                                "frame": idx,
                                "metric": "mean_abs_pixel_delta",
                                "value": delta,
                            }
                        )

            prev_pixels = pixels
            prev_mean = mean

    # Write events (JSONL).
    with events_path.open("w", encoding="utf-8", newline="\n") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    summary = {
        "ok": True,
        "mode": cfg.mode,
        "video": str(video),
        "frames_analyzed": len(frames),
        "events": len(events),
        "config": {
            "ffmpeg_path": cfg.ffmpeg_path,
            "fps": cfg.fps,
            "scale_width": cfg.scale_width,
            "blink_brightness_delta": cfg.blink_brightness_delta,
            "display_change_delta": cfg.display_change_delta,
        },
    }
    if extra:
        summary.update(extra)

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
