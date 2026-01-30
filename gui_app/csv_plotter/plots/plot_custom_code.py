import tkinter as tk
from tkinter import ttk

import pandas as pd

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .plot_checks_common import (
    numeric_series_for_col,
    selected_data_columns,
    selection_mask,
    x_series_for_df,
)


def _safe_exec(code: str) -> dict:
    """Execute user code with a small, useful sandbox.

    This is not a hardened sandbox. It is only meant to prevent accidental access
    to Tk internals and provide predictable names.
    """
    try:
        import numpy as np
    except Exception:
        np = None

    safe_builtins = {
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "enumerate": enumerate,
        "zip": zip,
        "sorted": sorted,
    }

    g = {
        "__builtins__": safe_builtins,
        "pd": pd,
        "np": np,
    }
    l: dict = {}
    exec(compile(code or "", "<custom-plot>", "exec"), g, l)
    # Return merged namespace so users can define either in globals or locals.
    merged = dict(g)
    merged.update(l)
    return merged


def _normalize_output(out, *, index: pd.Index, x: pd.Series):
    """Normalize output into a dict[str, pd.Series] to plot."""
    if out is None:
        return {}

    # dict of series
    if isinstance(out, dict):
        res: dict[str, pd.Series] = {}
        for k, v in out.items():
            name = str(k)
            if isinstance(v, pd.Series):
                s = v
            else:
                try:
                    s = pd.Series(v, index=index)
                except Exception:
                    continue
            res[name] = s
        return res

    # single series
    if isinstance(out, pd.Series):
        return {"out": out}

    # scalar
    try:
        f = float(out)
        return {"out": pd.Series([f] * len(index), index=index)}
    except Exception:
        pass

    # array-like
    try:
        s = pd.Series(out, index=index)
        return {"out": s}
    except Exception:
        return {}


def render_custom_code(app, selector, bottom_area, selected_columns: list[str]) -> None:
    if bottom_area is None:
        return

    try:
        df = app.df
    except Exception:
        return
    if not isinstance(df, pd.DataFrame):
        return

    cols = selected_data_columns(df, selected_columns)
    if len(cols) < 1:
        return

    try:
        code = selector.get_custom_code() if hasattr(selector, "get_custom_code") else ""
    except Exception:
        code = ""

    mask = selection_mask(app, selector)
    full_x = x_series_for_df(df)
    x = full_x[mask] if mask is not None else full_x

    # Build signal inputs (numeric + shift + window)
    signals: dict[str, pd.Series] = {}
    for col in cols:
        try:
            y = numeric_series_for_col(app, selector, str(col), mask=mask)
        except Exception:
            continue
        if mask is not None:
            try:
                y = y[mask]
            except Exception:
                pass
        try:
            y = y.dropna()
        except Exception:
            pass
        if len(y) == 0:
            continue
        signals[str(col)] = y

    # Align df to the same index as x
    try:
        df_win = df.loc[x.index]
    except Exception:
        df_win = df

    # Run user code
    try:
        ns = _safe_exec(code)
        out = None
        if callable(ns.get("transform")):
            out = ns["transform"](x=x, signals=signals, df=df_win)
        elif "out" in ns:
            out = ns.get("out")
        else:
            raise RuntimeError("Define transform(x, signals, df) or set variable 'out'.")
    except Exception as e:
        err = ttk.Label(bottom_area, text=f"Custom plot error: {e}", anchor="w", justify="left")
        err.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        return

    # Normalize and plot
    fig = Figure(figsize=(8, 2.2), dpi=100)
    ax = fig.add_subplot(111)

    try:
        series_map = _normalize_output(out, index=x.index, x=x)
    except Exception:
        series_map = {}

    plotted = False
    for name, s in (series_map or {}).items():
        try:
            # Align to x (index-based) if possible
            try:
                y_plot = s.loc[x.index]
            except Exception:
                y_plot = s
            ax.plot(x, y_plot, label=str(name))
            plotted = True
        except Exception:
            continue

    ax.set_title("Custom")
    ax.grid(True)

    if plotted:
        try:
            fig.subplots_adjust(right=0.72)
        except Exception:
            pass
        try:
            ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, frameon=True)
        except Exception:
            pass

    try:
        app._apply_mpl_theme(fig, [ax])
    except Exception:
        pass

    frame = ttk.Frame(bottom_area)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    try:
        if hasattr(app, "plot_canvases"):
            app.plot_canvases.append(canvas)
    except Exception:
        pass
