from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

from pyontrust.analysis.csv_reader import compute_timestamp_scale
from pyontrust.analysis.metrics import compute_signal_metrics


_YEAR_2000_EPOCH = 946684800.0
_YEAR_2100_EPOCH = 4102444800.0
_DEFAULT_SERIES_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


@dataclass(frozen=True)
class PlotSeriesScene:
    label: str
    color: str
    x_values: list[float]
    y_values: list[float | None]


@dataclass(frozen=True)
class PlotScene:
    title: str
    x_label: str
    y_label: str
    time_scale: bool
    series: list[PlotSeriesScene]


@dataclass(frozen=True)
class BrowserTriggerScene:
    x_value: float
    label: str
    active: bool = False


@dataclass(frozen=True)
class BrowserSourceSpanScene:
    key: str
    label: str
    start_x: float
    end_x: float
    color: str
    visible: bool = True


def numeric_signal_columns(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in list(df.columns):
        if str(column) == "Timestamp":
            continue
        try:
            series = pd.to_numeric(df[column], errors="coerce")
            if bool(series.notna().any()):
                columns.append(str(column))
        except Exception:
            continue
    return columns


def default_selected_columns(df: pd.DataFrame, *, max_count: int = 4) -> list[str]:
    return numeric_signal_columns(df)[: max(1, int(max_count))]


def is_epoch_seconds(series: pd.Series) -> bool:
    try:
        numeric = pd.to_numeric(series, errors="coerce").dropna()
    except Exception:
        return False
    if numeric.empty:
        return False
    try:
        min_value = float(numeric.min())
        max_value = float(numeric.max())
    except Exception:
        return False
    return _YEAR_2000_EPOCH <= min_value <= _YEAR_2100_EPOCH and _YEAR_2000_EPOCH <= max_value <= _YEAR_2100_EPOCH


def build_x_series(df: pd.DataFrame) -> tuple[pd.Series, str, bool]:
    if "Timestamp" not in df.columns:
        return pd.Series(np.arange(len(df), dtype=float)), "Sample", False

    try:
        raw_x = pd.to_numeric(df["Timestamp"], errors="coerce")
    except Exception:
        return pd.Series(np.arange(len(df), dtype=float)), "Sample", False

    if not bool(raw_x.notna().any()):
        return pd.Series(np.arange(len(df), dtype=float)), "Sample", False
    if is_epoch_seconds(raw_x):
        return raw_x.astype(float), "Timestamp", True

    try:
        scale = float(compute_timestamp_scale(df) or 1.0)
    except Exception:
        scale = 1.0
    if not math.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    x_values = raw_x.astype(float) * scale
    if is_epoch_seconds(x_values):
        return x_values, "Timestamp", True
    if abs(scale - 1.0) < 1e-12:
        return x_values, "Timestamp", False
    return x_values, f"Timestamp ({scale:g}s)", False


def series_color(index: int) -> str:
    return _DEFAULT_SERIES_COLORS[index % len(_DEFAULT_SERIES_COLORS)]


def build_plot_scene(
    df: pd.DataFrame,
    selected_columns: list[str],
    *,
    title_prefix: str = "CSV Plotter",
) -> PlotScene:
    x_series, x_label, time_scale = build_x_series(df)
    valid_x = pd.to_numeric(x_series, errors="coerce")
    x_mask = valid_x.notna()
    x_values = valid_x[x_mask].astype(float).tolist()

    plotted_columns = [str(column) for column in selected_columns if str(column) in df.columns]
    series: list[PlotSeriesScene] = []
    for index, column in enumerate(plotted_columns):
        y_series = pd.to_numeric(df[column], errors="coerce")
        y_values = y_series[x_mask].tolist()
        series.append(
            PlotSeriesScene(
                label=column,
                color=series_color(index),
                x_values=list(x_values),
                y_values=[None if pd.isna(value) else float(value) for value in y_values],
            )
        )

    title = title_prefix if len(plotted_columns) != 1 else f"{title_prefix} - {plotted_columns[0]}"
    return PlotScene(
        title=title,
        x_label=x_label,
        y_label="Signal",
        time_scale=time_scale,
        series=series,
    )


def build_uplot_payload(scene: PlotScene) -> tuple[dict[str, Any], list[list[Any]]]:
    options = {
        "title": scene.title,
        "width": 0,
        "height": 420,
        "hoverSeriesInfo": True,
        "focus": {"alpha": 0.18, "prox": 24},
        "series": [{"label": scene.x_label}] + [
            {"label": series.label, "stroke": series.color, "width": 1.5}
            for series in scene.series
        ],
        "axes": [
            {"scale": "x", "label": scene.x_label},
            {"scale": "y", "label": scene.y_label, "side": 3, "auto": True},
        ],
        "scales": {"x": {"time": bool(scene.time_scale)}, "y": {}},
    }
    if not scene.series:
        return options, [[0.0]]

    payload: list[list[Any]] = [list(scene.series[0].x_values)]
    for series in scene.series:
        payload.append(list(series.y_values))
    return options, payload


def build_browser_plot_model(
    scene: PlotScene,
    *,
    x_window: tuple[float, float] | None = None,
    triggers: list[BrowserTriggerScene] | None = None,
    sources: list[BrowserSourceSpanScene] | None = None,
    active_series: str | None = None,
    y_limits: tuple[float | None, float | None] | None = None,
    show_trigger_markers: bool = True,
) -> dict[str, Any]:
    x_values: list[float] = []
    for series in scene.series:
        for value in list(series.x_values or []):
            try:
                numeric = float(value)
            except Exception:
                continue
            if math.isfinite(numeric):
                x_values.append(numeric)

    domain: list[float] | None = None
    if x_values:
        domain = [float(min(x_values)), float(max(x_values))]

    normalized_window: list[float] | None = None
    if domain is not None and isinstance(x_window, tuple) and len(x_window) == 2:
        try:
            lo = float(min(x_window[0], x_window[1]))
            hi = float(max(x_window[0], x_window[1]))
        except Exception:
            lo = hi = 0.0
        if math.isfinite(lo) and math.isfinite(hi) and hi > lo:
            lo = max(domain[0], lo)
            hi = min(domain[1], hi)
            if hi > lo:
                normalized_window = [float(lo), float(hi)]

    overview = None
    if scene.series:
        overview = {
            "label": scene.series[0].label,
            "color": scene.series[0].color,
            "xValues": list(scene.series[0].x_values),
            "yValues": list(scene.series[0].y_values),
        }

    trigger_models: list[dict[str, Any]] = []
    for trigger in list(triggers or []):
        try:
            x_value = float(trigger.x_value)
        except Exception:
            continue
        if not math.isfinite(x_value):
            continue
        trigger_models.append(
            {
                "xValue": x_value,
                "label": str(trigger.label),
                "active": bool(trigger.active),
            }
        )

    source_models: list[dict[str, Any]] = []
    for source in list(sources or []):
        try:
            start_x = float(source.start_x)
            end_x = float(source.end_x)
        except Exception:
            continue
        if not math.isfinite(start_x) or not math.isfinite(end_x):
            continue
        source_models.append(
            {
                "key": str(source.key),
                "label": str(source.label),
                "startX": start_x,
                "endX": end_x,
                "color": str(source.color),
                "visible": bool(source.visible),
            }
        )

    normalized_y_limits: list[float | None] | None = None
    if isinstance(y_limits, tuple) and len(y_limits) == 2:
        parsed_limits: list[float | None] = []
        for value in y_limits:
            try:
                numeric = float(value) if value is not None else None
            except Exception:
                numeric = None
            parsed_limits.append(numeric if numeric is not None and math.isfinite(numeric) else None)
        if parsed_limits[0] is not None or parsed_limits[1] is not None:
            normalized_y_limits = parsed_limits

    source_key = source_models[0]["key"] if source_models else "primary"
    return {
        "title": scene.title,
        "xLabel": scene.x_label,
        "yLabel": scene.y_label,
        "timeScale": bool(scene.time_scale),
        "domain": domain,
        "xWindow": normalized_window,
        "activeSeries": str(active_series) if active_series else None,
        "series": [
            {
                "label": series.label,
                "color": series.color,
                "xValues": list(series.x_values),
                "yValues": list(series.y_values),
                "sourceKey": source_key,
            }
            for series in scene.series
        ],
        "overview": overview,
        "triggers": trigger_models,
        "sources": source_models,
        "yLimits": normalized_y_limits,
        "showTriggerMarkers": bool(show_trigger_markers),
    }


def build_stats_rows(df: pd.DataFrame, selected_columns: list[str]) -> list[tuple[str, ...]]:
    x_series, _x_label, _time_scale = build_x_series(df)
    rows: list[tuple[str, ...]] = []
    for column in [str(col) for col in selected_columns if str(col) in df.columns]:
        try:
            metrics = compute_signal_metrics(x_series, pd.to_numeric(df[column], errors="coerce"))
        except Exception:
            metrics = ("n/a",) * 10
        rows.append((column, *metrics))
    return rows