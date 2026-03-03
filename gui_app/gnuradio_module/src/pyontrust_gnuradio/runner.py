from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional

from .errors import RunnerError


@dataclass
class RunSpec:
    mode: str  # current | python | conda
    python_exe: str
    conda_env: str
    flowgraph_path: str
    extra_args: str = ""


def _split_args(s: str) -> list[str]:
    # Minimal, predictable splitting (no shell); users can keep it simple.
    return [a for a in s.split() if a]


def _is_grc(path: pathlib.Path) -> bool:
    return path.suffix.lower() == ".grc"


def build_command(spec: RunSpec) -> tuple[list[str], Optional[pathlib.Path]]:
    path = pathlib.Path(spec.flowgraph_path).expanduser().resolve()
    if not path.exists():
        raise RunnerError(f"Flowgraph not found: {path}")

    if spec.mode == "current":
        cmd = [sys.executable]
    elif spec.mode == "conda":
        # conda run -n <env> python <script>
        cmd = ["conda", "run", "-n", spec.conda_env, "python"]
    else:
        cmd = [spec.python_exe]

    out_py: Optional[pathlib.Path] = None
    if _is_grc(path):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pyontrust_grc_"))
        # grcc -d <outdir> <file.grc>
        # Prefer running grcc from the same environment as the chosen runtime.
        grcc_cmd = ["grcc", "-d", str(tmp), str(path)]
        if spec.mode == "conda":
            grcc_cmd = ["conda", "run", "-n", spec.conda_env, "grcc", "-d", str(tmp), str(path)]
        try:
            subprocess.check_call(grcc_cmd)
        except FileNotFoundError as exc:
            raise RunnerError(f"grcc not found: {exc}")
        candidates = sorted(tmp.glob("*.py"))
        if not candidates:
            raise RunnerError(f"grcc produced no .py in {tmp}")
        out_py = candidates[0]
        cmd += [str(out_py)]
    else:
        cmd += [str(path)]

    cmd += _split_args(spec.extra_args)
    return (cmd, out_py)


class ManagedProcess:
    def __init__(self, popen: subprocess.Popen[str], *, generated: Optional[pathlib.Path]) -> None:
        self._popen = popen
        self._generated = generated

    @property
    def pid(self) -> int:
        return int(self._popen.pid)

    def poll(self) -> Optional[int]:
        return self._popen.poll()

    def terminate(self) -> None:
        if self._popen.poll() is None:
            self._popen.terminate()

    def kill(self) -> None:
        if self._popen.poll() is None:
            self._popen.kill()


def start_process(cmd: list[str], *, generated: Optional[pathlib.Path]) -> ManagedProcess:
    if not cmd:
        raise RunnerError("No command to run")

    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise RunnerError(repr(exc))

    return ManagedProcess(p, generated=generated)
