from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .base import Recorder
from ..platform import creationflags_no_window

if TYPE_CHECKING:
    from ..core import TestContext


@dataclass
class FfmpegWebcamRecorder(Recorder):
    """Record webcam video via `ffmpeg`.

    Produces:
    - `recorders/<name>.mp4`
    - `recorders/<name>.log`

    Cross-platform input:
    - Windows: set `input_device` to the DirectShow device name (e.g. "Integrated Camera").
    - Linux: default `input_device` is `/dev/video0`.
    """

    name: str = "webcam"
    ffmpeg_path: str = "ffmpeg"

    input_device: Optional[str] = None
    framerate: int = 30
    video_size: Optional[str] = None  # e.g. "1280x720"

    codec: str = "libx264"
    preset: str = "ultrafast"

    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None
    skip_if_missing: bool = True

    _proc: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _mp4_path: pathlib.Path | None = field(default=None, init=False, repr=False)
    _log_path: pathlib.Path | None = field(default=None, init=False, repr=False)

    def start(self, ctx: TestContext) -> None:
        if self._proc is not None:
            raise RuntimeError(f"Recorder '{self.name}' already started")

        exe = shutil.which(self.ffmpeg_path)
        if exe is None and self.skip_if_missing:
            ctx.recorder_outputs[self.name] = {
                "type": "ffmpeg_webcam",
                "skipped": True,
                "reason": f"Executable not found: {self.ffmpeg_path}",
            }
            return

        is_windows = os.name == "nt"
        input_device = self.input_device
        if is_windows:
            if not input_device:
                raise ValueError("On Windows you must set input_device to a DirectShow camera name")
            input_args = ["-f", "dshow", "-i", f"video={input_device}"]
        else:
            input_args = ["-f", "v4l2", "-i", input_device or "/dev/video0"]

        out_dir = ctx.artifacts.recorders_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        mp4_path = out_dir / f"{self.name}.mp4"
        log_path = out_dir / f"{self.name}.log"
        self._mp4_path = mp4_path
        self._log_path = log_path

        if mp4_path.exists():
            mp4_path.unlink()

        cmd: list[str] = [
            self.ffmpeg_path,
            "-y",
            "-nostdin",
            "-loglevel",
            "info",
            "-framerate",
            str(int(self.framerate)),
        ]
        if self.video_size:
            cmd += ["-video_size", self.video_size]

        cmd += input_args
        cmd += [
            "-c:v",
            self.codec,
            "-preset",
            self.preset,
            str(mp4_path),
        ]

        env = None
        if self.env is not None:
            env = dict(os.environ)
            env.update(self.env)

        f = log_path.open("w", encoding="utf-8", newline="")
        try:
            self._proc = subprocess.Popen(
                cmd,
                cwd=self.cwd,
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags_no_window(),
            )
        finally:
            f.close()

        ctx.recorder_outputs[self.name] = {
            "type": "ffmpeg_webcam",
            "skipped": False,
            "command": cmd,
            "video": str(mp4_path),
            "log": str(log_path),
        }

    def stop(self, ctx: TestContext) -> None:
        proc = self._proc
        if proc is None:
            return

        if proc.poll() is None:
            proc.terminate()
            deadline = time.time() + 5.0
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.05)
            if proc.poll() is None:
                proc.kill()

        ctx.recorder_outputs.setdefault(self.name, {})
        ctx.recorder_outputs[self.name]["exit_code"] = proc.poll()
        self._proc = None
