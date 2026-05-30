from __future__ import annotations

import io
from typing import Any, Iterable

import numpy as np
import pandas as pd

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

from .plot_scene import BrowserTriggerScene, PlotScene


_PANEL_SERIES_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
]


def _pick_x(df: pd.DataFrame) -> tuple[pd.Series, str]:
    if "Timestamp" in df.columns:
        try:
            return pd.to_numeric(df["Timestamp"], errors="coerce"), "Timestamp"
        except Exception:
            return df.index.to_series(), "Index"
    return df.index.to_series(), "Index"


def render_plot_png(
    df: pd.DataFrame,
    columns: Iterable[str],
    *,
    width: int = 1200,
    height: int = 700,
    title: str | None = None,
) -> bytes:
    fig = Figure(figsize=(max(2, width / 100), max(2, height / 100)), dpi=100)
    FigureCanvas(fig)
    ax = fig.add_subplot(1, 1, 1)

    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data loaded", ha="center", va="center")
        ax.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        return buf.getvalue()

    x, x_label = _pick_x(df)
    x = pd.to_numeric(x, errors="coerce")

    cols = [column for column in columns if column in df.columns]
    if not cols:
        cols = list(df.columns[:1])

    n = len(df)
    step = 1
    if n > 300_000:
        step = max(1, int(n / 300_000))
    if step > 1:
        df = df.iloc[::step]
        x = x.iloc[::step]

    for column in cols:
        try:
            y = pd.to_numeric(df[column], errors="coerce")
        except Exception:
            continue
        ax.plot(x, y, label=str(column), linewidth=1.0)

    ax.set_xlabel(x_label)
    ax.set_ylabel("Value")
    if title:
        ax.set_title(title)
    if len(cols) > 1:
        ax.legend(loc="best", fontsize=8)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    return buf.getvalue()


def render_plot_scene_image(
    scene: PlotScene,
    *,
    fmt: str = "png",
    width: int = 1200,
    height: int = 700,
    x_window: tuple[float, float] | None = None,
    triggers: Iterable[BrowserTriggerScene] | None = None,
    y_limits: tuple[float | None, float | None] | None = None,
    show_triggers: bool = True,
) -> bytes:
    fmt = str(fmt or "png").strip().lower()
    if fmt not in ("png", "svg"):
        raise ValueError(f"Unsupported image export format: {fmt}")

    fig = Figure(figsize=(max(2, width / 100), max(2, height / 100)), dpi=100)
    FigureCanvas(fig)
    ax = fig.add_subplot(1, 1, 1)

    _render_plot_scene_axis(
        ax,
        scene,
        x_window=x_window,
        triggers=triggers,
        y_limits=y_limits,
        show_triggers=show_triggers,
    )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=100, bbox_inches="tight")
    return buf.getvalue()


def _render_plot_scene_axis(
    ax,
    scene: PlotScene,
    *,
    x_window: tuple[float, float] | None = None,
    triggers: Iterable[BrowserTriggerScene] | None = None,
    y_limits: tuple[float | None, float | None] | None = None,
    show_triggers: bool = True,
) -> None:
    plotted = False
    for series in list(getattr(scene, "series", []) or []):
        frame = pd.DataFrame({"x": list(series.x_values or []), "y": list(series.y_values or [])})
        frame["x"] = pd.to_numeric(frame["x"], errors="coerce")
        frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
        frame = frame.dropna()
        if frame.empty:
            continue
        if isinstance(x_window, tuple) and len(x_window) == 2:
            try:
                lo = float(min(x_window[0], x_window[1]))
                hi = float(max(x_window[0], x_window[1]))
            except Exception:
                lo = hi = 0.0
            frame = frame.loc[(frame["x"] >= lo) & (frame["x"] <= hi)]
            if frame.empty:
                continue
        ax.plot(frame["x"], frame["y"], label=str(series.label), linewidth=1.3, color=str(series.color or "#1f77b4"))
        plotted = True

    if not plotted:
        ax.text(0.5, 0.5, "No plot data available", ha="center", va="center")
        ax.set_axis_off()
        return

    if bool(show_triggers):
        for trigger in list(triggers or []):
            try:
                x_value = float(trigger.x_value)
            except Exception:
                continue
            ax.axvline(
                x=x_value,
                color="#c62828" if bool(getattr(trigger, "active", False)) else "#8a8a8a",
                linewidth=1.0,
                linestyle="--",
                alpha=0.9 if bool(getattr(trigger, "active", False)) else 0.6,
            )

    if isinstance(x_window, tuple) and len(x_window) == 2:
        try:
            ax.set_xlim(float(min(x_window[0], x_window[1])), float(max(x_window[0], x_window[1])))
        except Exception:
            pass

    if isinstance(y_limits, tuple) and len(y_limits) == 2:
        try:
            ymin = float(y_limits[0]) if y_limits[0] is not None else None
        except Exception:
            ymin = None
        try:
            ymax = float(y_limits[1]) if y_limits[1] is not None else None
        except Exception:
            ymax = None
        if ymin is not None or ymax is not None:
            try:
                ax.set_ylim(bottom=ymin, top=ymax)
            except Exception:
                pass

    ax.set_xlabel(str(getattr(scene, "x_label", "X") or "X"))
    ax.set_ylabel(str(getattr(scene, "y_label", "Y") or "Y"))
    ax.set_title(str(getattr(scene, "title", "CSV Plotter") or "CSV Plotter"))
    if len(list(getattr(scene, "series", []) or [])) > 1:
        ax.legend(loc="best", fontsize=8)


def render_combined_plot_scene_image(
    scenes: Iterable[tuple[PlotScene, tuple[float, float] | None, Iterable[BrowserTriggerScene] | None, tuple[float | None, float | None] | None, bool]],
    *,
    fmt: str = "png",
    width: int = 1400,
    height_per_plot: int = 420,
) -> bytes:
    prepared = list(scenes or [])
    if not prepared:
        raise ValueError("No plot scenes are available for combined export.")

    fmt = str(fmt or "png").strip().lower()
    if fmt not in ("png", "svg"):
        raise ValueError(f"Unsupported image export format: {fmt}")

    plot_count = max(1, len(prepared))
    fig = Figure(figsize=(max(3, width / 100), max(2, (height_per_plot * plot_count) / 100)), dpi=100)
    FigureCanvas(fig)
    axes = fig.subplots(plot_count, 1, squeeze=False)

    for index, (scene, x_window, triggers, y_limits, show_triggers) in enumerate(prepared):
        ax = axes[index][0]
        _render_plot_scene_axis(ax, scene, x_window=x_window, triggers=triggers, y_limits=y_limits, show_triggers=show_triggers)
        if ax.axison and not ax.get_title():
            ax.set_title(str(getattr(scene, "title", f"Plot {index + 1}") or f"Plot {index + 1}"))

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=100, bbox_inches="tight")
    return buf.getvalue()


def render_panel_payload_image(
    payload: dict,
    *,
    fmt: str = "png",
    width: int = 1200,
    height: int = 700,
) -> bytes:
    fmt = str(fmt or "png").strip().lower()
    if fmt not in ("png", "svg"):
        raise ValueError(f"Unsupported image export format: {fmt}")

    fig = Figure(figsize=(max(2, width / 100), max(2, height / 100)), dpi=100)
    FigureCanvas(fig)
    ax = fig.add_subplot(1, 1, 1)

    title = str((payload or {}).get("title") or "CSV Plotter")
    _render_panel_payload_axis(ax, payload)
    if ax.axison:
        ax.set_title(title)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=100, bbox_inches="tight")
    return buf.getvalue()


def render_combined_browser_export_image(
    items: Iterable[dict[str, Any]],
    *,
    fmt: str = "png",
    width: int = 1400,
    height_per_plot: int = 420,
) -> bytes:
    prepared = list(items or [])
    if not prepared:
        raise ValueError("No subplot exports are available for combined export.")

    fmt = str(fmt or "png").strip().lower()
    if fmt not in ("png", "svg"):
        raise ValueError(f"Unsupported image export format: {fmt}")

    plot_count = max(1, len(prepared))
    fig = Figure(figsize=(max(3, width / 100), max(2, (height_per_plot * plot_count) / 100)), dpi=100)
    FigureCanvas(fig)
    axes = fig.subplots(plot_count, 1, squeeze=False)

    for index, item in enumerate(prepared):
        ax = axes[index][0]
        kind = str(item.get("kind") or "").strip().lower()
        title = str(item.get("title") or f"Plot {index + 1}")
        if kind == "scene":
            _render_plot_scene_axis(
                ax,
                item["scene"],
                x_window=item.get("x_window"),
                triggers=item.get("triggers"),
                y_limits=item.get("y_limits"),
                show_triggers=bool(item.get("show_triggers", True)),
            )
        elif kind == "payload":
            _render_panel_payload_axis(ax, item.get("payload") or {})
        else:
            ax.text(0.5, 0.5, "No plot data available", ha="center", va="center")
            ax.set_axis_off()
        if ax.axison:
            ax.set_title(title)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=100, bbox_inches="tight")
    return buf.getvalue()


def _render_panel_payload_axis(ax, payload: dict) -> None:
    kind = str((payload or {}).get("kind") or "").strip().lower()
    if kind == "histogram":
        _render_histogram_payload(ax, payload)
    elif kind in ("spectrum", "abs", "rel", "custom"):
        _render_line_payload(ax, payload)
    elif kind == "detector":
        _render_detector_payload(ax, payload)
    elif kind == "stats":
        _render_stats_payload(ax, payload)
    else:
        ax.text(0.5, 0.5, "No plot data available", ha="center", va="center")
        ax.set_axis_off()


def _render_stats_payload(ax, payload: dict) -> None:
    rows = list((payload or {}).get("rows") or [])
    if not rows:
        ax.text(0.5, 0.5, "No statistics available", ha="center", va="center")
        ax.set_axis_off()
        return

    headers = ["source", "signal", "min", "max", "avg", "std", "freq"]
    table_rows: list[list[str]] = []
    for row in rows[:20]:
        table_rows.append([
            str(row.get("source", "")),
            str(row.get("signal", "")),
            str(row.get("min", "")),
            str(row.get("max", "")),
            str(row.get("avg", "")),
            str(row.get("std", "")),
            str(row.get("freq", "")),
        ])

    ax.axis("off")
    table = ax.table(cellText=table_rows, colLabels=headers, loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.4)


def _render_line_payload(ax, payload: dict) -> None:
    series = list((payload or {}).get("series") or [])
    barriers = list((payload or {}).get("barriers") or [])
    plotted = False
    for index, item in enumerate(series):
        frame = pd.DataFrame({"x": list(item.get("x") or []), "y": list(item.get("y") or [])})
        frame["x"] = pd.to_numeric(frame["x"], errors="coerce")
        frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
        frame = frame.dropna()
        if frame.empty:
            continue
        ax.plot(
            frame["x"],
            frame["y"],
            label=str(item.get("label") or f"Series {index + 1}"),
            linewidth=1.4,
            color=_PANEL_SERIES_COLORS[index % len(_PANEL_SERIES_COLORS)],
        )
        plotted = True
    for item in barriers:
        frame = pd.DataFrame({"x": list(item.get("x") or []), "y": list(item.get("y") or [])})
        frame["x"] = pd.to_numeric(frame["x"], errors="coerce")
        frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
        frame = frame.dropna()
        if frame.empty:
            continue
        ax.plot(
            frame["x"],
            frame["y"],
            label=str(item.get("label") or "Barrier"),
            linewidth=1.0,
            linestyle="--",
            color="#c62828",
        )
        plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "No panel data available", ha="center", va="center")
        ax.set_axis_off()
        return
    if len(series) + len(barriers) > 1:
        ax.legend(loc="best", fontsize=8)


def _render_histogram_payload(ax, payload: dict) -> None:
    plotted = False
    for index, item in enumerate(list((payload or {}).get("series") or [])):
        centers = pd.to_numeric(pd.Series(item.get("centers") or []), errors="coerce")
        counts = pd.to_numeric(pd.Series(item.get("counts") or []), errors="coerce")
        widths = pd.to_numeric(pd.Series(item.get("widths") or []), errors="coerce")
        frame = pd.DataFrame({"x": centers, "y": counts, "w": widths}).dropna()
        if frame.empty:
            continue
        ax.bar(
            frame["x"],
            frame["y"],
            width=frame["w"],
            alpha=0.5,
            label=str(item.get("label") or f"Series {index + 1}"),
            color=_PANEL_SERIES_COLORS[index % len(_PANEL_SERIES_COLORS)],
            align="center",
        )
        plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "No histogram data available", ha="center", va="center")
        ax.set_axis_off()
        return
    if len(list((payload or {}).get("series") or [])) > 1:
        ax.legend(loc="best", fontsize=8)
    ax.set_xlabel("Value")
    ax.set_ylabel("Count")


def _render_detector_payload(ax, payload: dict) -> None:
    matrix = np.asarray((payload or {}).get("matrix") or [], dtype=float)
    if matrix.ndim != 2 or matrix.size == 0:
        ax.text(0.5, 0.5, "No detector data available", ha="center", va="center")
        ax.set_axis_off()
        return
    im = ax.imshow(matrix, origin="upper", aspect="equal", cmap="viridis")
    ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    labels = (payload or {}).get("labels") or []
    for row_index, row in enumerate(labels):
        for col_index, label in enumerate(row or []):
            if not label:
                continue
            value = matrix[row_index, col_index] if row_index < matrix.shape[0] and col_index < matrix.shape[1] else float("nan")
            text = str(label)
            if np.isfinite(value):
                text = f"{text}\n{value:.3g}"
            ax.text(col_index, row_index, text, ha="center", va="center", fontsize=8, color="white")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")