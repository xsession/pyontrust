"""HTML report builder for parallel lux measurement results.

Convenience module that wraps :class:`~pyontrust.analysis.test_report.ReportBuilder`
to produce a complete, self-contained HTML report from a
:class:`~pyontrust.analysis.lux_measurement.LuxResult`.

Usage::

    from pyontrust.analysis.lux_report import build_lux_report
    path = build_lux_report(result, cfg=cfg, output_dir="test_reports")
"""

from __future__ import annotations

import os
import pathlib
import platform
from datetime import datetime
from typing import Any, Optional

from pyontrust.analysis.test_report import ReportBuilder, _CHART_COLOURS


def build_lux_report(
    result: Any,  # LuxResult
    *,
    title: str = "Parallel Lux Measurement Report",
    dut: str = "",
    operator: str = "",
    test_id: str = "",
    cfg: Any = None,  # LuxCaptureConfig
    output_dir: str | pathlib.Path = "test_reports",
) -> pathlib.Path:
    """Build and write a complete HTML report for a parallel lux measurement.

    Parameters
    ----------
    result : LuxResult
        The analysis result (from ``analyse_parallel_lux`` or
        ``measure_parallel_lux``).
    title : str
        Report title.
    cfg : LuxCaptureConfig, optional
        Capture configuration (included as a section if provided).
    output_dir : path-like
        Directory for the output HTML file.

    Returns
    -------
    pathlib.Path
        The resolved path to the written HTML file.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"lux_parallel_{ts}.html"
    out_path = pathlib.Path(output_dir) / filename

    rb = ReportBuilder(
        title=title,
        dut=dut or "Webcam + Android Light Sensor",
        operator=operator or os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        test_id=test_id or f"LUX-PARALLEL-{ts}",
        environment=f"{platform.node()} / {platform.system()} {platform.release()}",
    )

    # ── Verdict ─────────────────────────────────────────────────────
    if result.ok:
        parts = []
        if result.webcam_lux_delta is not None:
            parts.append(f"Webcam Δlux: {result.webcam_lux_delta:.1f}")
        if result.android_lux_delta is not None:
            parts.append(f"Android Δlux: {result.android_lux_delta:.1f}")
        if result.correlation is not None:
            parts.append(f"Pearson r: {result.correlation:.4f}")
        msg = "PASS — " + " · ".join(parts) if parts else "PASS"
        details = (
            f"Cycles: {result.n_cycles} · "
            f"Webcam frames: {result.webcam_frame_count} · "
            f"Android samples: {result.android_sample_count} · "
            f"Duration: {result.capture_duration_s:.2f} s"
        )
        rb.set_verdict(passed=True, message=msg, details=details)
    else:
        rb.set_verdict(
            passed=False,
            message=f"FAIL — {result.error or 'Unknown error'}",
            details=(
                f"Webcam frames: {result.webcam_frame_count} · "
                f"Android samples: {result.android_sample_count}"
            ),
        )

    # ── Description ─────────────────────────────────────────────────
    rb.add_section_text("Test Description", (
        "This test measures ambient light (lux) simultaneously from two "
        "independent sources — a USB webcam (V-channel brightness with "
        "linear calibration) and an Android phone's hardware light sensor "
        "(via ADB or simulated).\n\n"
        "The phone's flashlight (torch) is cycled ON/OFF to create a "
        "controlled step-change in illuminance. Both sensors should track "
        "the same light event, allowing cross-validation via Pearson "
        "correlation and cross-correlation lag estimation."
    ))

    # ── Results summary KV ──────────────────────────────────────────
    kv: dict[str, str] = {
        "Status": "PASS ✅" if result.ok else "FAIL ❌",
        "Capture Duration": f"{result.capture_duration_s:.3f} s",
        "Torch Cycles": str(result.n_cycles),
        "Webcam Frames": str(result.webcam_frame_count),
        "Webcam FPS": f"{result.webcam_actual_fps:.1f}",
        "Android Samples": str(result.android_sample_count),
    }
    if result.webcam_lux_mean_on is not None:
        kv["Webcam Mean Lux (ON)"] = f"{result.webcam_lux_mean_on:.1f}"
    if result.webcam_lux_mean_off is not None:
        kv["Webcam Mean Lux (OFF)"] = f"{result.webcam_lux_mean_off:.1f}"
    if result.webcam_lux_delta is not None:
        kv["Webcam Δ Lux (ON − OFF)"] = f"{result.webcam_lux_delta:.1f}"
    if result.android_lux_mean_on is not None:
        kv["Android Mean Lux (ON)"] = f"{result.android_lux_mean_on:.1f}"
    if result.android_lux_mean_off is not None:
        kv["Android Mean Lux (OFF)"] = f"{result.android_lux_mean_off:.1f}"
    if result.android_lux_delta is not None:
        kv["Android Δ Lux (ON − OFF)"] = f"{result.android_lux_delta:.1f}"
    if result.correlation is not None:
        kv["Pearson Correlation (r)"] = f"{result.correlation:.4f}"
    if result.lag_ms is not None:
        kv["Cross-Correlation Lag"] = f"{result.lag_ms:.1f} ms"

    rb.add_section_kv("Measurement Results", kv)

    # ── Capture configuration ───────────────────────────────────────
    if cfg is not None:
        cfg_kv: dict[str, str] = {
            "Device Index": str(getattr(cfg, "device_index", 0)),
            "Resolution": f"{getattr(cfg, 'width', 640)} × {getattr(cfg, 'height', 480)}",
            "Target FPS": f"{getattr(cfg, 'target_fps', 30.0)}",
            "Warmup Frames": str(getattr(cfg, "warmup_frames", 10)),
            "ROI": str(getattr(cfg, "roi", None)) if getattr(cfg, "roi", None) else "Full frame",
            "Torch ON Duration": f"{getattr(cfg, 'torch_on_s', 3.0)} s",
            "Torch OFF Duration": f"{getattr(cfg, 'torch_off_s', 3.0)} s",
            "Torch Cycles": str(getattr(cfg, "n_cycles", 3)),
            "Pre-Capture Baseline": f"{getattr(cfg, 'pre_capture_s', 1.0)} s",
            "Android Mode": str(getattr(cfg, "android_mode", "simulated")),
            "Lux Scale": str(getattr(cfg, "lux_scale", 2.0)),
            "Lux Offset": str(getattr(cfg, "lux_offset", 0.0)),
        }
        rb.add_section_kv("Capture Configuration", cfg_kv)

    # ── Webcam lux time-series chart ────────────────────────────────
    if result.webcam_timestamps and result.webcam_lux:
        rb.add_section_chart(
            "Webcam Estimated Lux",
            result.webcam_timestamps,
            result.webcam_lux,
            x_label="Time (s)",
            y_label="Estimated Lux",
            chart_title="Webcam V-Channel → Estimated Lux vs Time",
            colour=_CHART_COLOURS[0],
        )

    # ── Android lux time-series chart ───────────────────────────────
    if result.android_timestamps and result.android_lux:
        rb.add_section_chart(
            "Android Light Sensor (Lux)",
            result.android_timestamps,
            result.android_lux,
            x_label="Time (s)",
            y_label="Lux (sensor)",
            chart_title="Android Ambient Light Sensor vs Time",
            colour=_CHART_COLOURS[1],
        )

    # ── Overlay chart: both series on same axes ─────────────────────
    if (result.webcam_timestamps and result.webcam_lux
            and result.android_timestamps and result.android_lux):
        import numpy as np  # lazy OK here — test_report already uses it in analysis path

        # Resample Android to webcam timestamps for overlay
        a_interp = np.interp(
            result.webcam_timestamps,
            result.android_timestamps,
            result.android_lux,
        ).tolist()

        rb.add_section_chart(
            "Overlay — Webcam vs Android",
            result.webcam_timestamps,
            result.webcam_lux,
            x_label="Time (s)",
            y_label="Webcam Lux",
            chart_title="Webcam (blue) vs Android (green) Lux",
            colour=_CHART_COLOURS[0],
            secondary_y=a_interp,
            secondary_label="Android Lux (resampled)",
        )

    # ── Webcam raw brightness chart ─────────────────────────────────
    if result.webcam_timestamps and result.webcam_brightness:
        rb.add_section_chart(
            "Webcam Raw Brightness (V-Channel)",
            result.webcam_timestamps,
            result.webcam_brightness,
            x_label="Time (s)",
            y_label="Brightness (0–255)",
            chart_title="Mean V-Channel Brightness vs Time",
            colour=_CHART_COLOURS[4],
        )

    # ── Statistics table ────────────────────────────────────────────
    if result.ok and (result.webcam_lux or result.android_lux):
        import numpy as np

        rows = []
        if result.webcam_lux:
            wa = np.array(result.webcam_lux)
            rows.extend([
                ["Webcam — Min Lux", f"{float(wa.min()):.1f}"],
                ["Webcam — Max Lux", f"{float(wa.max()):.1f}"],
                ["Webcam — Mean Lux", f"{float(wa.mean()):.1f}"],
                ["Webcam — Std Lux", f"{float(wa.std()):.1f}"],
            ])
        if result.android_lux:
            aa = np.array(result.android_lux)
            rows.extend([
                ["Android — Min Lux", f"{float(aa.min()):.1f}"],
                ["Android — Max Lux", f"{float(aa.max()):.1f}"],
                ["Android — Mean Lux", f"{float(aa.mean()):.1f}"],
                ["Android — Std Lux", f"{float(aa.std()):.1f}"],
            ])
        if result.correlation is not None:
            rows.append(["Pearson r", f"{result.correlation:.4f}"])
        if result.lag_ms is not None:
            rows.append(["Cross-Corr Lag", f"{result.lag_ms:.1f} ms"])

        rb.add_section_table(
            "Signal Statistics",
            ["Metric", "Value"],
            rows,
            numeric_cols={1},
        )

    # ── Torch events table ──────────────────────────────────────────
    if result.torch_events:
        torch_rows = [
            [f"{evt['t']:.3f}", evt["state"]]
            for evt in result.torch_events
        ]
        rb.add_section_table(
            "Torch Events Log",
            ["Time (s)", "State"],
            torch_rows,
            numeric_cols={0},
        )

    # ── Raw data (embedded JSON) ────────────────────────────────────
    rb.attach_raw_data("lux_result", result.summary())
    if result.webcam_timestamps:
        rb.attach_raw_data("webcam_series", {
            "timestamps": result.webcam_timestamps,
            "lux": result.webcam_lux,
            "brightness": result.webcam_brightness,
        })
    if result.android_timestamps:
        rb.attach_raw_data("android_series", {
            "timestamps": result.android_timestamps,
            "lux": result.android_lux,
        })
    if result.torch_events:
        rb.attach_raw_data("torch_events", result.torch_events)

    return rb.write(out_path)
