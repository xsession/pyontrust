from __future__ import annotations

"""Webcam capture adapter placeholder.

If you want the webcam to "see" the setup during runs, `ffmpeg` is a pragmatic dependency.
This adapter is intentionally not implemented yet to avoid assuming device names.
"""


class WebcamFfmpegRecorder:
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def open(self) -> None:
        return

    def close(self) -> None:
        return
