from __future__ import annotations

import os
import pathlib
import subprocess
import time
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from .base import Recorder
from ..platform import creationflags_no_window

if TYPE_CHECKING:
    from ..core import TestContext


@dataclass
class ProcessRecorder(Recorder):
    """Recorder that wraps an external process.

    The process is launched at `start()` and terminated at `stop()`.
    Stdout/stderr are captured to `recorders/<name>.log`.
    """

    name: str
    command: list[str]
    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None
    terminate_timeout_s: float = 5.0
    skip_if_missing: bool = True

    _proc: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _log_path: pathlib.Path | None = field(default=None, init=False, repr=False)

    def start(self, ctx: TestContext) -> None:
        if self._proc is not None:
            raise RuntimeError(f"Recorder '{self.name}' already started")

        exe = shutil.which(self.command[0])
        if exe is None and self.skip_if_missing:
            ctx.recorder_outputs[self.name] = {
                "type": "process",
                "skipped": True,
                "reason": f"Executable not found: {self.command[0]}",
                "command": self.command,
            }
            return

        log_path = ctx.artifacts.recorders_dir / f"{self.name}.log"
        self._log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

        env = None
        if self.env is not None:
            env = dict(os.environ)
            env.update(self.env)

        f = log_path.open("w", encoding="utf-8", newline="")
        try:
            self._proc = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags_no_window(),
            )
        finally:
            # The child process has its own handle; close ours to avoid ResourceWarning.
            f.close()

        ctx.recorder_outputs[self.name] = {
            "type": "process",
            "skipped": False,
            "command": self.command,
            "cwd": self.cwd,
            "log": str(log_path),
        }

    def stop(self, ctx: TestContext) -> None:
        proc = self._proc
        if proc is None:
            return

        if proc.poll() is None:
            proc.terminate()
            deadline = time.time() + self.terminate_timeout_s
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.05)
            if proc.poll() is None:
                proc.kill()

        ctx.recorder_outputs.setdefault(self.name, {})
        ctx.recorder_outputs[self.name]["exit_code"] = proc.poll()
        self._proc = None
