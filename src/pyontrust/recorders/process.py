"""Process recorder — wraps an external process as a background recorder."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from pyontrust.core.utils import creationflags_no_window

if TYPE_CHECKING:
    from pyontrust.core.models import TestContext


@dataclass
class ProcessRecorder:
    """Recorder that wraps an external process."""

    name: str
    command: list[str]
    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None
    terminate_timeout_s: float = 5.0
    skip_if_missing: bool = True

    _proc: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _log_path: pathlib.Path | None = field(default=None, init=False, repr=False)

    def start(self, ctx: "TestContext") -> None:
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
            f.close()

        ctx.recorder_outputs[self.name] = {
            "type": "process",
            "skipped": False,
            "command": self.command,
            "cwd": self.cwd,
            "log": str(log_path),
        }

    def stop(self, ctx: "TestContext") -> None:
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


def create(config: dict[str, Any]) -> ProcessRecorder:
    """Entry-point factory for process recorder."""
    return ProcessRecorder(
        name=str(config["name"]),
        command=list(config["command"]),
        cwd=config.get("cwd"),
        skip_if_missing=bool(config.get("skip_if_missing", True)),
    )


def create_tshark(config: dict[str, Any]) -> ProcessRecorder:
    """Factory for tshark/Wireshark recorder."""
    iface = str(config.get("interface", "1"))
    out = str(config.get("out", "capture.pcapng"))
    return ProcessRecorder(
        name=str(config.get("name", "tshark")),
        command=["tshark", "-i", iface, "-w", out],
        skip_if_missing=True,
    )
