"""HTML test-report generator — enterprise-grade, self-contained.

Generates a single-file HTML report with the Catppuccin Mocha theme,
embedded SVG time-series charts, tabular metrics, and a pass/fail
verdict banner.  The report is fully self-contained (no external CSS
or JS dependencies) and can be opened directly in any browser.

Usage::

    from pyontrust.analysis.test_report import ReportBuilder

    rb = ReportBuilder(
        title="LED Blink Periodicity Test",
        dut="nRF9160-DK — Heartbeat LED",
    )
    rb.add_section_text("Overview", "Measured red LED blink rate …")
    rb.add_section_kv("Configuration", {"Device": "webcam:0", …})
    rb.add_section_chart("Brightness Time-Series", ts, brightness)
    rb.add_section_table("Frequency Analysis", headers, rows)
    rb.set_verdict(passed=True, message="1.001 Hz detected")
    rb.write("test_reports/led_blink_20260309_120000.html")

Design
------
* Stdlib-only core (``html.escape``, ``json``, ``datetime``).
* SVG chart renderer — no matplotlib / plotly dependency.
* Follows project conventions: lazy imports, CalVer, Catppuccin.
* ``ReportSection`` protocol lets callers add arbitrary sections.
"""

from __future__ import annotations

import html
import json
import math
import os
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import pyontrust

# ═══════════════════════════════════════════════════════════════════════
#  CSS — Catppuccin Mocha theme (self-contained)
# ═══════════════════════════════════════════════════════════════════════

_CSS = """\
:root {
  --bg: #1e1e2e; --bg2: #252538; --bg3: #2d2d44; --bg4: #353550;
  --fg: #cdd6f4; --fg-dim: #6c7086;
  --accent: #89b4fa; --green: #a6e3a1; --red: #f38ba8;
  --yellow: #f9e2af; --peach: #fab387; --mauve: #cba6f7;
  --teal: #94e2d5; --border: #45475a; --radius: 6px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--fg); line-height: 1.6;
  padding: 0; margin: 0;
}
.report { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

/* ── Header ── */
.report-header {
  border-bottom: 2px solid var(--accent); padding-bottom: 20px; margin-bottom: 28px;
}
.report-header h1 { color: var(--accent); font-size: 26px; margin-bottom: 4px; }
.report-header .subtitle { color: var(--fg-dim); font-size: 13px; }
.report-meta {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px 24px; margin-top: 14px; font-size: 12px;
}
.report-meta .key { color: var(--fg-dim); font-weight: 600; }
.report-meta .val { color: var(--fg); font-family: monospace; font-size: 11px; }

/* ── Verdict banner ── */
.verdict {
  padding: 16px 24px; border-radius: var(--radius); margin-bottom: 28px;
  display: flex; align-items: center; gap: 14px; font-size: 15px; font-weight: 700;
}
.verdict.pass { background: rgba(166,227,161,0.12); border: 2px solid var(--green); color: var(--green); }
.verdict.fail { background: rgba(243,139,168,0.12); border: 2px solid var(--red); color: var(--red); }
.verdict .icon { font-size: 28px; }
.verdict .details { font-size: 12px; font-weight: 400; color: var(--fg-dim); margin-top: 2px; }

/* ── Sections ── */
.section { margin-bottom: 28px; }
.section h2 {
  font-size: 15px; font-weight: 700; color: var(--accent);
  text-transform: uppercase; letter-spacing: 1px;
  border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-bottom: 14px;
}
.section-text { font-size: 13px; line-height: 1.7; color: var(--fg); }
.section-text p { margin-bottom: 10px; }

/* ── Key-value grid ── */
.kv-grid {
  display: grid; grid-template-columns: 180px 1fr; gap: 4px 16px;
  font-size: 13px; background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px 18px;
}
.kv-grid .key { color: var(--fg-dim); font-weight: 600; }
.kv-grid .val { color: var(--fg); font-family: monospace; font-size: 12px; word-break: break-all; }

/* ── Tables ── */
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  background: var(--bg3); color: var(--accent); font-weight: 700;
  text-align: left; padding: 8px 12px; border-bottom: 2px solid var(--border);
  text-transform: uppercase; letter-spacing: 0.5px; font-size: 11px;
}
.data-table td {
  padding: 7px 12px; border-bottom: 1px solid var(--border);
  font-family: monospace; font-size: 11px;
}
.data-table tr:hover td { background: var(--bg2); }
.data-table .num { text-align: right; }
.data-table .pass-cell { color: var(--green); font-weight: 700; }
.data-table .fail-cell { color: var(--red); font-weight: 700; }

/* ── SVG chart ── */
.chart-container {
  background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px; overflow-x: auto;
}
.chart-container svg { display: block; margin: 0 auto; }

/* ── Footer ── */
.report-footer {
  margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
  font-size: 11px; color: var(--fg-dim); text-align: center;
}

/* ── Print ── */
@media print {
  body { background: #fff; color: #222; }
  .report { padding: 0; }
  .verdict.pass { border-color: #2a9d4e; color: #2a9d4e; background: #e6f9ee; }
  .verdict.fail { border-color: #d64040; color: #d64040; background: #fde8e8; }
  .kv-grid, .data-table th { background: #f5f5f5; }
  .chart-container { background: #fafafa; }
}
"""

# ═══════════════════════════════════════════════════════════════════════
#  SVG chart renderer (stdlib-only, no matplotlib)
# ═══════════════════════════════════════════════════════════════════════

_CHART_COLOURS = ["#89b4fa", "#a6e3a1", "#f38ba8", "#f9e2af", "#cba6f7", "#fab387", "#94e2d5"]


def _render_svg_line_chart(
    x: Sequence[float],
    y: Sequence[float],
    *,
    width: int = 900,
    height: int = 280,
    x_label: str = "Time (s)",
    y_label: str = "Brightness",
    title: str = "",
    colour: str = _CHART_COLOURS[0],
    threshold_y: Optional[float] = None,
    secondary_y: Optional[Sequence[float]] = None,
    secondary_label: str = "",
    secondary_colour: str = _CHART_COLOURS[1],
) -> str:
    """Render an SVG line chart as an HTML string.

    Supports optional horizontal threshold line and a secondary Y series.
    """
    if not x or not y or len(x) < 2:
        return '<p class="section-text" style="color:var(--fg-dim);">Insufficient data for chart.</p>'

    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 40
    cw = width - pad_l - pad_r
    ch = height - pad_t - pad_b

    x_min, x_max = float(min(x)), float(max(x))
    y_min, y_max = float(min(y)), float(max(y))

    # Include secondary series in Y range
    if secondary_y:
        y_min = min(y_min, float(min(secondary_y)))
        y_max = max(y_max, float(max(secondary_y)))

    # Pad Y range
    y_range = y_max - y_min
    if y_range < 1e-9:
        y_range = 1.0
    y_min -= y_range * 0.05
    y_max += y_range * 0.05
    x_range = x_max - x_min
    if x_range < 1e-9:
        x_range = 1.0

    def sx(v: float) -> float:
        return pad_l + (v - x_min) / x_range * cw

    def sy(v: float) -> float:
        return pad_t + (1.0 - (v - y_min) / (y_max - y_min)) * ch

    lines: list[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{width}" height="{height}" '
                 f'viewBox="0 0 {width} {height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#252538" rx="6"/>')

    # Title
    if title:
        lines.append(f'<text x="{width // 2}" y="18" '
                     f'text-anchor="middle" fill="#cdd6f4" font-size="12" '
                     f'font-weight="700">{html.escape(title)}</text>')

    # Grid lines + Y axis labels
    n_ticks = 5
    for i in range(n_ticks + 1):
        yv = y_min + (y_max - y_min) * i / n_ticks
        py = sy(yv)
        lines.append(f'<line x1="{pad_l}" y1="{py:.1f}" x2="{width - pad_r}" y2="{py:.1f}" '
                     f'stroke="#45475a" stroke-width="0.5"/>')
        label = f"{yv:.1f}" if abs(yv) < 1000 else f"{yv:.0f}"
        lines.append(f'<text x="{pad_l - 6}" y="{py + 4:.1f}" '
                     f'text-anchor="end" fill="#6c7086" font-size="10">{label}</text>')

    # X axis labels
    n_x_ticks = min(8, len(x))
    for i in range(n_x_ticks + 1):
        xv = x_min + x_range * i / n_x_ticks
        px = sx(xv)
        lines.append(f'<text x="{px:.1f}" y="{height - 8}" '
                     f'text-anchor="middle" fill="#6c7086" font-size="10">{xv:.2f}</text>')

    # Axis labels
    lines.append(f'<text x="{width // 2}" y="{height - 0}" '
                 f'text-anchor="middle" fill="#6c7086" font-size="10">{html.escape(x_label)}</text>')
    lines.append(f'<text x="14" y="{height // 2}" '
                 f'text-anchor="middle" fill="#6c7086" font-size="10" '
                 f'transform="rotate(-90,14,{height // 2})">{html.escape(y_label)}</text>')

    # Threshold line
    if threshold_y is not None and y_min <= threshold_y <= y_max:
        ty = sy(threshold_y)
        lines.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{width - pad_r}" y2="{ty:.1f}" '
                     f'stroke="#f9e2af" stroke-width="1" stroke-dasharray="6,4"/>')
        lines.append(f'<text x="{width - pad_r + 2}" y="{ty + 3:.1f}" '
                     f'fill="#f9e2af" font-size="9">threshold</text>')

    # Secondary series
    if secondary_y and len(secondary_y) == len(x):
        pts = " ".join(f"{sx(x[i]):.1f},{sy(secondary_y[i]):.1f}" for i in range(len(x)))
        lines.append(f'<polyline points="{pts}" fill="none" '
                     f'stroke="{secondary_colour}" stroke-width="1.2" opacity="0.7"/>')
        if secondary_label:
            lines.append(f'<text x="{pad_l + 10}" y="{pad_t + 14}" '
                         f'fill="{secondary_colour}" font-size="10">● {html.escape(secondary_label)}</text>')

    # Primary series
    pts = " ".join(f"{sx(x[i]):.1f},{sy(y[i]):.1f}" for i in range(len(x)))
    lines.append(f'<polyline points="{pts}" fill="none" '
                 f'stroke="{colour}" stroke-width="1.5"/>')

    # Legend
    lx = pad_l + 10
    ly = pad_t + 2 if not secondary_y else pad_t + 26
    lines.append(f'<text x="{lx}" y="{ly}" fill="{colour}" font-size="10">● {html.escape(y_label)}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  Section builders
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class _Section:
    title: str
    html: str
    order: int = 0


# ═══════════════════════════════════════════════════════════════════════
#  ReportBuilder — main API
# ═══════════════════════════════════════════════════════════════════════


class ReportBuilder:
    """Fluent builder for self-contained HTML test reports.

    All ``add_*`` methods return ``self`` for chaining.
    """

    def __init__(
        self,
        title: str = "Test Report",
        dut: str = "",
        operator: str = "",
        test_id: str = "",
        environment: str = "",
    ) -> None:
        self.title = title
        self.dut = dut
        self.operator = operator
        self.test_id = test_id
        self.environment = environment
        self.created = datetime.now(timezone.utc)
        self._sections: list[_Section] = []
        self._verdict_html: str = ""
        self._meta_extra: dict[str, str] = {}
        self._raw_data: dict[str, Any] = {}

    # ── Meta ────────────────────────────────────────────────────────

    def add_meta(self, key: str, value: str) -> "ReportBuilder":
        """Add an extra key-value pair to the header metadata block."""
        self._meta_extra[key] = value
        return self

    def attach_raw_data(self, key: str, data: Any) -> "ReportBuilder":
        """Attach JSON-serialisable raw data (embedded in a <script> tag)."""
        self._raw_data[key] = data
        return self

    # ── Verdict ─────────────────────────────────────────────────────

    def set_verdict(
        self,
        passed: bool,
        message: str,
        details: str = "",
    ) -> "ReportBuilder":
        cls = "pass" if passed else "fail"
        icon = "✅" if passed else "❌"
        det = f'<div class="details">{html.escape(details)}</div>' if details else ""
        self._verdict_html = (
            f'<div class="verdict {cls}">'
            f'<span class="icon">{icon}</span>'
            f'<div><div>{html.escape(message)}</div>{det}</div>'
            f'</div>'
        )
        return self

    # ── Sections ────────────────────────────────────────────────────

    def add_section_text(self, title: str, text: str) -> "ReportBuilder":
        """Add a free-text section (supports <p> line splitting)."""
        paras = text.strip().split("\n\n")
        body = "".join(f"<p>{html.escape(p.strip())}</p>" for p in paras if p.strip())
        self._sections.append(_Section(title, f'<div class="section-text">{body}</div>'))
        return self

    def add_section_html(self, title: str, raw_html: str) -> "ReportBuilder":
        """Add a section with pre-rendered HTML (caller's responsibility)."""
        self._sections.append(_Section(title, raw_html))
        return self

    def add_section_kv(
        self,
        title: str,
        data: dict[str, Any],
    ) -> "ReportBuilder":
        """Add a key-value grid section."""
        rows = "".join(
            f'<div class="key">{html.escape(str(k))}</div>'
            f'<div class="val">{html.escape(str(v))}</div>'
            for k, v in data.items()
        )
        self._sections.append(_Section(title, f'<div class="kv-grid">{rows}</div>'))
        return self

    def add_section_table(
        self,
        title: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        *,
        numeric_cols: Optional[set[int]] = None,
        pass_fail_col: Optional[int] = None,
    ) -> "ReportBuilder":
        """Add a data table section.

        Parameters
        ----------
        numeric_cols : set of column indices to right-align
        pass_fail_col : column index to colour green/red by value
        """
        nc = numeric_cols or set()
        th = "".join(
            f'<th class="{"num" if i in nc else ""}">{html.escape(str(h))}</th>'
            for i, h in enumerate(headers)
        )
        trs: list[str] = []
        for row in rows:
            tds: list[str] = []
            for i, cell in enumerate(row):
                cls_parts: list[str] = []
                if i in nc:
                    cls_parts.append("num")
                if pass_fail_col is not None and i == pass_fail_col:
                    sv = str(cell).lower()
                    if sv in ("pass", "passed", "true", "yes", "✅"):
                        cls_parts.append("pass-cell")
                    elif sv in ("fail", "failed", "false", "no", "❌"):
                        cls_parts.append("fail-cell")
                cls = f' class="{" ".join(cls_parts)}"' if cls_parts else ""
                tds.append(f"<td{cls}>{html.escape(str(cell))}</td>")
            trs.append(f"<tr>{''.join(tds)}</tr>")

        table_html = (
            f'<table class="data-table">'
            f'<thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(trs)}</tbody>'
            f'</table>'
        )
        self._sections.append(_Section(title, table_html))
        return self

    def add_section_chart(
        self,
        title: str,
        x: Sequence[float],
        y: Sequence[float],
        *,
        x_label: str = "Time (s)",
        y_label: str = "Value",
        chart_title: str = "",
        colour: str = _CHART_COLOURS[0],
        threshold_y: Optional[float] = None,
        secondary_y: Optional[Sequence[float]] = None,
        secondary_label: str = "",
    ) -> "ReportBuilder":
        """Add an SVG line-chart section."""
        svg = _render_svg_line_chart(
            x, y,
            x_label=x_label, y_label=y_label,
            title=chart_title or title, colour=colour,
            threshold_y=threshold_y,
            secondary_y=secondary_y,
            secondary_label=secondary_label,
        )
        self._sections.append(_Section(
            title, f'<div class="chart-container">{svg}</div>',
        ))
        return self

    # ── Render ──────────────────────────────────────────────────────

    def render(self) -> str:
        """Render the complete HTML report as a string."""
        meta_items: dict[str, str] = {}
        if self.test_id:
            meta_items["Test ID"] = self.test_id
        if self.dut:
            meta_items["DUT"] = self.dut
        if self.operator:
            meta_items["Operator"] = self.operator
        if self.environment:
            meta_items["Environment"] = self.environment
        meta_items["Generated"] = self.created.strftime("%Y-%m-%d %H:%M:%S UTC")
        meta_items["Platform"] = f"pyontrust {pyontrust.__version__}"
        meta_items.update(self._meta_extra)

        meta_html = "".join(
            f'<div><span class="key">{html.escape(k)}:</span> '
            f'<span class="val">{html.escape(v)}</span></div>'
            for k, v in meta_items.items()
        )

        sections_html = ""
        for sec in self._sections:
            sections_html += (
                f'<div class="section">'
                f'<h2>{html.escape(sec.title)}</h2>'
                f'{sec.html}'
                f'</div>\n'
            )

        raw_script = ""
        if self._raw_data:
            raw_script = (
                f'<script type="application/json" id="report-data">'
                f'{json.dumps(self._raw_data, default=str)}'
                f'</script>'
            )

        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(self.title)}</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="report">
  <div class="report-header">
    <h1>{html.escape(self.title)}</h1>
    <div class="subtitle">Automated Test Report — pyontrust Enterprise Platform</div>
    <div class="report-meta">{meta_html}</div>
  </div>
  {self._verdict_html}
  {sections_html}
  <div class="report-footer">
    Generated by <strong>pyontrust {html.escape(pyontrust.__version__)}</strong>
    &nbsp;·&nbsp; {html.escape(self.created.strftime("%Y-%m-%d %H:%M:%S UTC"))}
    &nbsp;·&nbsp; Report is self-contained — no external dependencies
  </div>
</div>
{raw_script}
</body>
</html>"""

    # ── Write ───────────────────────────────────────────────────────

    def write(self, path: str | pathlib.Path) -> pathlib.Path:
        """Render and write the report to a file.

        Creates parent directories if needed. Returns the resolved path.
        """
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.render(), encoding="utf-8")
        return p.resolve()


# ═══════════════════════════════════════════════════════════════════════
#  Convenience: build a LED blink report from a BlinkResult
# ═══════════════════════════════════════════════════════════════════════


def build_led_blink_report(
    result: Any,  # BlinkResult (avoid circular import at type level)
    *,
    title: str = "LED Blink Periodicity Test Report",
    dut: str = "",
    operator: str = "",
    test_id: str = "",
    cap_cfg: Any = None,  # CaptureConfig
    mask_cfg: Any = None,  # RedLEDMaskConfig
    output_dir: str | pathlib.Path = "test_reports",
) -> pathlib.Path:
    """Build and write a complete HTML report for a LED blink measurement.

    Returns the path to the written HTML file.
    """
    import platform
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"led_blink_{ts}.html"
    out_path = pathlib.Path(output_dir) / filename

    rb = ReportBuilder(
        title=title,
        dut=dut or "Red LED — webcam capture",
        operator=operator or os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
        test_id=test_id or f"LED-BLINK-{ts}",
        environment=f"{platform.node()} / {platform.system()} {platform.release()}",
    )

    # ── Verdict ─────────────────────────────────────────────────────
    if result.ok:
        rb.set_verdict(
            passed=True,
            message=f"PASS — Blink frequency: {result.frequency_hz:.4f} Hz "
                    f"(period: {result.period_s:.4f} s)",
            details=f"Method: {result.method} · "
                    f"Blinks: {result.blink_count} · "
                    f"Frames: {result.frame_count} · "
                    f"Duration: {result.capture_duration_s:.2f} s",
        )
    else:
        rb.set_verdict(
            passed=False,
            message=f"FAIL — {result.error or 'Unknown error'}",
            details=f"Frames: {result.frame_count} · "
                    f"Duration: {result.capture_duration_s:.2f} s",
        )

    # ── Overview ────────────────────────────────────────────────────
    rb.add_section_text("Test Description", (
        "This test captures video frames from a USB webcam, isolates red LED "
        "pixels using HSV colour masking, tracks brightness over time, and "
        "computes the blink frequency using FFT, zero-crossing, and "
        "peak-interval analysis.\n\n"
        "The test validates that a red LED is blinking at a detectable, "
        "stable frequency within the configured measurement window."
    ))

    # ── Results summary ─────────────────────────────────────────────
    results_kv: dict[str, str] = {
        "Status": "PASS ✅" if result.ok else "FAIL ❌",
        "Frequency": f"{result.frequency_hz:.4f} Hz" if result.frequency_hz else "—",
        "Period": f"{result.period_s:.4f} s" if result.period_s else "—",
        "Duty Cycle": f"{result.duty_cycle:.1%}" if result.duty_cycle is not None else "—",
        "Detection Method": result.method or "—",
        "Blink Count": str(result.blink_count),
        "Capture Duration": f"{result.capture_duration_s:.3f} s",
        "Frames Captured": str(result.frame_count),
        "Actual FPS": f"{result.actual_fps:.1f}",
    }
    rb.add_section_kv("Measurement Results", results_kv)

    # ── Capture configuration ───────────────────────────────────────
    if cap_cfg is not None:
        cfg_kv: dict[str, str] = {
            "Device Index": str(cap_cfg.device_index),
            "Resolution": f"{cap_cfg.width} × {cap_cfg.height}",
            "Target FPS": f"{cap_cfg.target_fps}",
            "Capture Duration": f"{cap_cfg.capture_duration_s} s",
            "Warmup Frames": str(cap_cfg.warmup_frames),
            "ROI": str(cap_cfg.roi) if cap_cfg.roi else "Full frame",
        }
        rb.add_section_kv("Capture Configuration", cfg_kv)

    # ── Mask configuration ──────────────────────────────────────────
    if mask_cfg is not None:
        mask_kv: dict[str, str] = {
            "Red Range 1 (H)": f"{mask_cfg.low_h1} – {mask_cfg.high_h1}",
            "Red Range 2 (H)": f"{mask_cfg.low_h2} – {mask_cfg.high_h2}",
            "Saturation (S)": f"{mask_cfg.low_s} – {mask_cfg.high_s}",
            "Value (V)": f"{mask_cfg.low_v} – {mask_cfg.high_v}",
            "Min Pixel Count": str(mask_cfg.min_pixel_count),
        }
        rb.add_section_kv("HSV Mask Configuration", mask_kv)

    # ── Brightness time-series chart ────────────────────────────────
    if result.timestamps and result.brightness:
        # Compute threshold for chart annotation
        br = result.brightness
        threshold = (max(br) + min(br)) / 2.0 if br else None

        rb.add_section_chart(
            "Brightness Time-Series",
            result.timestamps, result.brightness,
            x_label="Time (s)", y_label="Red LED Brightness",
            chart_title="Red LED Mean Brightness vs Time",
            threshold_y=threshold,
        )

    # ── Red pixel count chart ───────────────────────────────────────
    if result.timestamps and result.red_pixel_counts:
        rb.add_section_chart(
            "Red Pixel Count",
            result.timestamps,
            [float(c) for c in result.red_pixel_counts],
            x_label="Time (s)", y_label="Pixel Count",
            chart_title="Red Mask Pixel Count vs Time",
            colour=_CHART_COLOURS[2],
        )

    # ── Frequency analysis details ──────────────────────────────────
    if result.timestamps and result.brightness and len(result.brightness) >= 8:
        import numpy as np
        br_arr = np.array(result.brightness)
        stats_rows = [
            ["Min Brightness", f"{float(br_arr.min()):.2f}"],
            ["Max Brightness", f"{float(br_arr.max()):.2f}"],
            ["Mean Brightness", f"{float(br_arr.mean()):.2f}"],
            ["Std Deviation", f"{float(br_arr.std()):.2f}"],
            ["Amplitude (p-p)", f"{float(br_arr.max() - br_arr.min()):.2f}"],
        ]
        if result.red_pixel_counts:
            rc = np.array(result.red_pixel_counts, dtype=float)
            stats_rows.append(["Max Red Pixels", f"{int(rc.max())}"])
            stats_rows.append(["Mean Red Pixels", f"{rc.mean():.0f}"])
            stats_rows.append(["Frames w/ Red", f"{int(np.sum(rc > 0))} / {len(rc)}"])

        rb.add_section_table(
            "Signal Statistics",
            ["Metric", "Value"],
            stats_rows,
            numeric_cols={1},
        )

    # ── Raw data (embedded JSON for machine consumption) ────────────
    rb.attach_raw_data("blink_result", result.summary())
    if result.timestamps:
        rb.attach_raw_data("time_series", {
            "timestamps": result.timestamps,
            "brightness": result.brightness,
            "red_pixel_counts": result.red_pixel_counts,
        })

    return rb.write(out_path)
