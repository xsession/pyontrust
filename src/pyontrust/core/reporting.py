"""Artifact serialisation — CSV, JSON, Markdown report writers.

All functions are pure I/O: they take data objects and write files.
No third-party dependencies.
"""

from __future__ import annotations

import csv
import json
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyontrust.core.models import PowerSummary, PowerTest, PowerTrace, TestArtifacts


def write_power_trace_csv(path: pathlib.Path, trace: PowerTrace) -> None:
    """Write a power trace to a CSV file."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["t_s", "current_a", "voltage_v", "power_w"])
        for s in trace.samples:
            writer.writerow([f"{s.t_s:.9f}", f"{s.current_a:.12g}", f"{s.voltage_v:.12g}", f"{s.power_w:.12g}"])


def write_summary_json(path: pathlib.Path, summary: PowerSummary) -> None:
    """Write a power summary to a JSON file."""
    path.write_text(json.dumps(summary.__dict__, indent=2), encoding="utf-8")


def write_report_md(path: pathlib.Path, test: PowerTest, summary: PowerSummary, artifacts: TestArtifacts) -> None:
    """Write a Markdown test report."""
    lines: list[str] = []
    lines.append(f"# {test.name}")
    lines.append("")
    if test.description:
        lines.append(test.description)
        lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Duration (s): {summary.duration_s:.6f}")
    lines.append(f"- Samples: {summary.samples}")
    lines.append(f"- Avg current (A): {summary.avg_current_a:.9f}")
    lines.append(f"- Max current (A): {summary.max_current_a:.9f}")
    lines.append(f"- Avg voltage (V): {summary.avg_voltage_v:.6f}")
    lines.append(f"- Avg power (W): {summary.avg_power_w:.9f}")
    lines.append(f"- Charge (C): {summary.charge_c:.9f}")
    lines.append(f"- Energy (J): {summary.energy_j:.9f}")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- Meta: {artifacts.meta_path.name}")
    lines.append(f"- Recorders: {artifacts.recorders_dir.name}/")
    lines.append(f"- Trace CSV: {artifacts.trace_csv_path.name}")
    lines.append(f"- Summary JSON: {artifacts.summary_json_path.name}")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
