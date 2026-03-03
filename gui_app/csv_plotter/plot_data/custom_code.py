"""Custom-code execution engine for the CSV Plotter.

Ported from ``plots/plot_custom_code.py``: runs user-supplied
``transform(x, signals, df)`` in a restricted namespace and returns
Plotly-ready trace data.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger("csv_plotter.plot_data.custom_code")

MAX_CODE_LENGTH: int = 50_000

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "range": range, "float": float, "int": int, "str": str, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "enumerate": enumerate, "zip": zip, "sorted": sorted, "round": round,
    "map": map, "filter": filter, "any": any, "all": all,
    "isinstance": isinstance, "type": type, "print": print,
    "True": True, "False": False, "None": None,
}

_BLOCKED_PATTERNS: list[str] = [
    "__import__", "__builtins__", "__subclasses__", "__globals__",
]


def _safe_exec(code: str) -> dict:
    if not code or not code.strip():
        return {}
    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(f"Code exceeds max length ({len(code):,} > {MAX_CODE_LENGTH:,})")
    for pat in _BLOCKED_PATTERNS:
        if pat in code:
            raise ValueError(f"Blocked pattern: {pat!r}")

    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore[assignment]

    safe_builtins = dict(_SAFE_BUILTINS)
    safe_builtins["__import__"] = (
        __builtins__["__import__"] if isinstance(__builtins__, dict)
        else getattr(__builtins__, "__import__")
    )

    g: dict[str, Any] = {"__builtins__": safe_builtins, "pd": pd, "np": np}
    l: dict[str, Any] = {}
    exec(compile(code, "<custom-plot>", "exec"), g, l)
    merged = dict(g)
    merged.update(l)
    return merged


def _normalize_output(out: Any, *, index: pd.Index, x: pd.Series) -> dict[str, pd.Series]:
    if out is None:
        return {}
    if isinstance(out, dict):
        res: dict[str, pd.Series] = {}
        for k, v in out.items():
            if isinstance(v, pd.Series):
                res[str(k)] = v
            else:
                try:
                    res[str(k)] = pd.Series(v, index=index)
                except Exception:
                    continue
        return res
    if isinstance(out, pd.Series):
        return {"out": out}
    try:
        f = float(out)
        return {"out": pd.Series([f] * len(index), index=index)}
    except Exception:
        pass
    try:
        return {"out": pd.Series(out, index=index)}
    except Exception:
        return {}


def extract_custom_code_traces(
    *,
    df: pd.DataFrame,
    selected_columns: list[str],
    code: str,
    x_window: list[float] | None = None,
    max_points: int = 5_000,
) -> dict:
    """Execute user code and return Plotly traces.

    Returns ``{"traces": [...], "layout": {...}, "error": str|None}``.
    """
    from .checks_common import build_x_series, data_columns, downsample_series

    cols = data_columns(df, selected_columns)
    if not cols:
        return {"traces": [], "layout": {}, "error": "No columns selected"}

    x = build_x_series(df)

    # Build signals
    signals: dict[str, pd.Series] = {}
    mask = None
    if x_window and len(x_window) == 2:
        try:
            lo, hi = float(x_window[0]), float(x_window[1])
            mask = (x >= lo) & (x <= hi)
        except Exception:
            mask = None

    for col in cols:
        y = pd.to_numeric(df[col], errors="coerce")
        if mask is not None:
            y = y.where(mask)
        y = y.dropna()
        if len(y) > 0:
            signals[col] = y

    x_run = x[mask] if mask is not None else x
    df_win = df.loc[x_run.index] if mask is not None else df

    try:
        ns = _safe_exec(code)
        out = None
        if callable(ns.get("transform")):
            out = ns["transform"](x=x_run, signals=signals, df=df_win)
        elif "out" in ns:
            out = ns["out"]
        else:
            raise RuntimeError("Define transform(x, signals, df) or set variable 'out'.")
    except Exception as e:
        logger.warning("Custom code failed: %s", e)
        return {"traces": [], "layout": {}, "error": str(e)}

    series_map = _normalize_output(out, index=x_run.index, x=x_run)
    traces: list[dict] = []
    for name, s in series_map.items():
        try:
            y_plot = s.loc[x_run.index]
        except Exception:
            y_plot = s

        x_ds, y_ds = downsample_series(
            pd.Series(x_run.values, dtype=float),
            pd.Series(y_plot.values, dtype=float),
            max_points=max_points,
        )
        traces.append({
            "x": x_ds.values.tolist(),
            "y": y_ds.values.tolist(),
            "name": name,
            "type": "scatter",
            "mode": "lines",
        })

    return {
        "traces": traces,
        "layout": {"title": "Custom Code"},
        "error": None,
    }
