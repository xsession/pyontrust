"""CSV-based power meters — replay from file or process output."""

from __future__ import annotations

import csv
import os
import pathlib
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from pyontrust.core.models import PowerSample
from pyontrust.core.utils import creationflags_no_window


def _float_cell(row: dict[str, str], key: str) -> float:
    if key not in row:
        raise KeyError(f"Missing column '{key}'. Available: {sorted(row.keys())}")
    return float(row[key])


def _read_csv_rows(path: pathlib.Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        return list(reader)


@dataclass
class CsvFilePowerMeter:
    """Reads samples from a CSV file."""

    csv_path: str | os.PathLike[str]
    t_col: str = "t_s"
    i_col: str = "current_a"
    v_col: str = "voltage_v"
    time_offset_s: float = 0.0

    def open(self) -> None:
        return

    def close(self) -> None:
        return

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        time.sleep(max(0.0, duration_s))
        path = pathlib.Path(self.csv_path)
        rows = _read_csv_rows(path)
        for r in rows:
            yield PowerSample(
                t_s=_float_cell(r, self.t_col) + self.time_offset_s,
                current_a=_float_cell(r, self.i_col),
                voltage_v=_float_cell(r, self.v_col),
            )


@dataclass
class CsvProcessPowerMeter:
    """Runs a process that produces a CSV file, then reads it."""

    command: list[str]
    csv_path: str | os.PathLike[str]
    t_col: str = "t_s"
    i_col: str = "current_a"
    v_col: str = "voltage_v"
    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None

    _last_run_log: pathlib.Path | None = field(default=None, init=False)

    def open(self) -> None:
        return

    def close(self) -> None:
        return

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        csv_path = pathlib.Path(self.csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if csv_path.exists():
            csv_path.unlink()

        args = [a.format(duration_s=duration_s, csv_path=str(csv_path)) for a in self.command]
        log_path = csv_path.parent / f"power_meter_{int(time.time())}.log"
        self._last_run_log = log_path

        env = None
        if self.env is not None:
            env = dict(os.environ)
            env.update(self.env)

        with log_path.open("w", encoding="utf-8", newline="") as f:
            proc = subprocess.Popen(
                args,
                cwd=self.cwd,
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags_no_window(),
            )
            rc = proc.wait()
            if rc != 0:
                raise RuntimeError(f"Power meter process failed rc={rc}. See log: {log_path}")

        rows = _read_csv_rows(csv_path)
        for r in rows:
            yield PowerSample(
                t_s=_float_cell(r, self.t_col),
                current_a=_float_cell(r, self.i_col),
                voltage_v=_float_cell(r, self.v_col),
            )


def create_csv_file(config: dict[str, Any]) -> CsvFilePowerMeter:
    """Entry-point factory for CSV file power meter."""
    return CsvFilePowerMeter(
        csv_path=config["csv_path"],
        t_col=config.get("t_col", "t_s"),
        i_col=config.get("i_col", "current_a"),
        v_col=config.get("v_col", "voltage_v"),
    )


def create_csv_process(config: dict[str, Any]) -> CsvProcessPowerMeter:
    """Entry-point factory for CSV process power meter."""
    return CsvProcessPowerMeter(
        command=list(config["command"]),
        csv_path=config["csv_path"],
        t_col=config.get("t_col", "t_s"),
        i_col=config.get("i_col", "current_a"),
        v_col=config.get("v_col", "voltage_v"),
        cwd=config.get("cwd"),
    )
