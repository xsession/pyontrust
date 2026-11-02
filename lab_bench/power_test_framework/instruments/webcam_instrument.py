"""Webcam instrument — capture + visual inspection.

Provides a *first-class instrument* for the webcam (without IR filter)
that the user has pointed at the lab bench.  Supports:

- Still frame capture (snapshot)
- Background video recording (start/stop)
- LED blink detection (via ``vision_change_logger``)
- Object detection post-processing (via ``vision_object_detector``)

Usage in a test profile::

    "instruments": {
      "webcam": {
        "type": "webcam",
        "input_device": "HD USB Camera",
        "framerate": 30,
        "video_size": "1280x720"
      }
    }
"""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..platform import creationflags_no_window

logger = logging.getLogger("pyontrust.instruments.webcam")


@dataclass
class WebcamInstrument:
    """Webcam capture with visual analysis support.

    Parameters
    ----------
    input_device : str
        DirectShow device name on Windows (e.g. ``"HD USB Camera"``),
        or V4L2 path on Linux (e.g. ``"/dev/video0"``).
    ffmpeg_path : str
        Path to ffmpeg binary.
    framerate : int
        Capture frame rate.
    video_size : str
        Capture resolution (e.g. ``"1280x720"``).
    codec : str
        Video codec for recording.
    preset : str
        Encoding preset.
    skip_if_missing : bool
        Skip gracefully if ffmpeg is not installed.
    """

    input_device: str = ""
    ffmpeg_path: str = "ffmpeg"
    framerate: int = 30
    video_size: str = "1280x720"
    codec: str = "libx264"
    preset: str = "ultrafast"
    skip_if_missing: bool = True

    _ffmpeg_exe: Optional[str] = field(default=None, init=False, repr=False)
    _rec_proc: subprocess.Popen | None = field(default=None, init=False, repr=False)

    def open(self) -> None:
        self._ffmpeg_exe = shutil.which(self.ffmpeg_path)
        if self._ffmpeg_exe is None and not self.skip_if_missing:
            raise FileNotFoundError(f"ffmpeg not found: {self.ffmpeg_path}")
        logger.info("Webcam instrument: ffmpeg=%s device=%s", self._ffmpeg_exe or "MISSING", self.input_device)

    def close(self) -> None:
        self.stop_recording()

    # ---- Snapshot --------------------------------------------------------

    def snapshot(self, output_path: str | pathlib.Path) -> bool:
        """Capture a single frame to a JPEG/PNG file.

        Returns True on success, False if ffmpeg missing and skip_if_missing.
        """
        if self._ffmpeg_exe is None:
            if self.skip_if_missing:
                return False
            raise FileNotFoundError("ffmpeg not found")

        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = self._base_input_cmd() + [
            "-frames:v", "1",
            "-update", "1",
            "-y",
            str(output_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=creationflags_no_window(),
        )
        if result.returncode != 0:
            logger.warning("Snapshot failed rc=%d: %s", result.returncode, result.stderr[:300])
            return False
        logger.info("Snapshot saved: %s", output_path)
        return True

    # ---- Background Recording --------------------------------------------

    def start_recording(self, output_path: str | pathlib.Path) -> bool:
        """Start background video recording.

        Returns True if started, False if skipped.
        """
        if self._ffmpeg_exe is None:
            if self.skip_if_missing:
                logger.warning("ffmpeg not found — skipping webcam recording")
                return False
            raise FileNotFoundError("ffmpeg not found")

        if self._rec_proc is not None:
            raise RuntimeError("Recording already in progress")

        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = self._base_input_cmd() + [
            "-c:v", self.codec,
            "-preset", self.preset,
            "-y",
            str(output_path),
        ]

        logger.info("Starting webcam recording: %s", " ".join(cmd))
        self._rec_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags_no_window(),
        )
        return True

    def stop_recording(self) -> Optional[int]:
        """Stop background recording. Returns exit code or None."""
        if self._rec_proc is None:
            return None

        try:
            # Send 'q' to ffmpeg stdin for graceful stop (finalises mp4 container)
            if self._rec_proc.stdin:
                self._rec_proc.stdin.write(b"q")
                self._rec_proc.stdin.flush()
            self._rec_proc.wait(timeout=10)
        except Exception:
            try:
                self._rec_proc.terminate()
                self._rec_proc.wait(timeout=5)
            except Exception:
                try:
                    self._rec_proc.kill()
                except Exception:
                    pass

        rc = self._rec_proc.poll()
        self._rec_proc = None
        logger.info("Webcam recording stopped (rc=%s)", rc)
        return rc

    # ---- Visual Analysis -------------------------------------------------

    def detect_led_blinks(
        self,
        video_path: str | pathlib.Path,
        *,
        fps: float = 2.0,
        brightness_delta: float = 25.0,
    ) -> list[dict[str, Any]]:
        """Detect LED blink events in a recorded video.

        Delegates to ``vision_change_logger`` (already in the framework).
        Returns a list of change events ``[{"t_s": ..., "type": "blink", ...}]``.
        """
        from ..vision_change_logger import VisionChangeConfig, detect_changes

        cfg = VisionChangeConfig(
            ffmpeg_path=self.ffmpeg_path,
            fps=fps,
            mode="blink",
            blink_brightness_delta=brightness_delta,
        )
        return detect_changes(pathlib.Path(video_path), cfg)

    def detect_display_changes(
        self,
        video_path: str | pathlib.Path,
        *,
        fps: float = 2.0,
        delta_threshold: float = 12.0,
    ) -> list[dict[str, Any]]:
        """Detect display/scene changes in a recorded video.

        Returns a list of change events.
        """
        from ..vision_change_logger import VisionChangeConfig, detect_changes

        cfg = VisionChangeConfig(
            ffmpeg_path=self.ffmpeg_path,
            fps=fps,
            mode="display_change",
            display_change_delta=delta_threshold,
        )
        return detect_changes(pathlib.Path(video_path), cfg)

    def detect_objects(
        self,
        video_path: str | pathlib.Path,
        *,
        model: str = "yolov8n.pt",
        conf: float = 0.25,
    ) -> list[dict[str, Any]]:
        """Run YOLO object detection on a recorded video.

        Requires ``ultralytics`` (optional dependency).
        Returns per-frame detections.
        """
        from ..vision_object_detector import ObjectDetectConfig, detect_objects_in_video

        cfg = ObjectDetectConfig(
            ffmpeg_path=self.ffmpeg_path,
            model=model,
            conf=conf,
        )
        return detect_objects_in_video(pathlib.Path(video_path), cfg)

    # ---- Internal --------------------------------------------------------

    def _base_input_cmd(self) -> list[str]:
        """Build the ffmpeg input portion of the command."""
        assert self._ffmpeg_exe is not None

        is_windows = os.name == "nt"
        cmd: list[str] = [
            self._ffmpeg_exe,
            "-nostdin",
            "-loglevel", "warning",
        ]

        if is_windows:
            if not self.input_device:
                raise ValueError("On Windows, set input_device to a DirectShow camera name")
            cmd += ["-f", "dshow", "-framerate", str(self.framerate)]
            if self.video_size:
                cmd += ["-video_size", self.video_size]
            cmd += ["-i", f"video={self.input_device}"]
        else:
            dev = self.input_device or "/dev/video0"
            cmd += ["-f", "v4l2", "-framerate", str(self.framerate)]
            if self.video_size:
                cmd += ["-video_size", self.video_size]
            cmd += ["-i", dev]

        return cmd
