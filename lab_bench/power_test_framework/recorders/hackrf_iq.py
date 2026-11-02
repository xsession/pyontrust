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
class HackRfIqRecorder(Recorder):
    """Record raw IQ samples using `hackrf_transfer`.

    Produces:
    - `recorders/<name>.iq` (raw interleaved IQ)
    - `recorders/<name>.log`

    Notes
    - This records for the whole test run (start->stop). It does not set a fixed duration.
    - Requires HackRF tools installed and accessible on PATH, or set `tool_path`.
    """

    name: str = "hackrf"
    tool_path: str = "hackrf_transfer"

    freq_hz: int = 2_402_000_000
    sample_rate_hz: int = 10_000_000
    baseband_filter_hz: Optional[int] = None

    lna_gain_db: Optional[int] = None
    vga_gain_db: Optional[int] = None
    amp_enable: bool = False

    device_serial: Optional[str] = None
    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None

    skip_if_missing: bool = True

    _proc: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _iq_path: pathlib.Path | None = field(default=None, init=False, repr=False)
    _log_path: pathlib.Path | None = field(default=None, init=False, repr=False)

    def start(self, ctx: TestContext) -> None:
        if self._proc is not None:
            raise RuntimeError(f"Recorder '{self.name}' already started")

        exe = shutil.which(self.tool_path)
        if exe is None and self.skip_if_missing:
            ctx.recorder_outputs[self.name] = {
                "type": "hackrf_iq",
                "skipped": True,
                "reason": f"Executable not found: {self.tool_path}",
            }
            return

        out_dir = ctx.artifacts.recorders_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        iq_path = out_dir / f"{self.name}.iq"
        log_path = out_dir / f"{self.name}.log"
        self._iq_path = iq_path
        self._log_path = log_path

        # Avoid mixing runs.
        if iq_path.exists():
            iq_path.unlink()

        cmd: list[str] = [
            self.tool_path,
            "-r",
            str(iq_path),
            "-f",
            str(int(self.freq_hz)),
            "-s",
            str(int(self.sample_rate_hz)),
        ]
        if self.baseband_filter_hz is not None:
            cmd += ["-b", str(int(self.baseband_filter_hz))]
        if self.lna_gain_db is not None:
            cmd += ["-l", str(int(self.lna_gain_db))]
        if self.vga_gain_db is not None:
            cmd += ["-g", str(int(self.vga_gain_db))]
        if self.amp_enable:
            cmd += ["-a", "1"]
        if self.device_serial:
            cmd += ["-d", str(self.device_serial)]

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
            "type": "hackrf_iq",
            "skipped": False,
            "command": cmd,
            "iq": str(iq_path),
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
