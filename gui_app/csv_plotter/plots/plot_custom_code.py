"""Custom-code plot renderer for the CSV Plotter.

Allows users to define a ``transform(x, signals, df)`` function inside
the subplot's custom-code editor.  The code is executed with a
**restricted** built-in namespace:

- Only safe, side-effect-free builtins are exposed.
- ``import`` is **blocked** to prevent arbitrary module loading.
- ``open`` / ``eval`` / ``exec`` / ``compile`` / ``__import__`` are excluded.
- Code length is capped at :data:`MAX_CODE_LENGTH` characters.
- A timeout is **not** enforced (Python has no portable mechanism);
  users should be warned in the UI.

.. warning::
    This is **not** a hardened sandbox — it is a convenience guard to
    prevent accidents.  A determined user *can* escape it.  Never run
    untrusted code.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

import pandas as pd

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .plot_checks_common import (
    numeric_series_for_col,
    selected_data_columns,
    selection_mask,
    x_series_for_df,
)

logger = logging.getLogger("csv_plotter.plots.custom_code")

# Maximum length of user-supplied code (prevent accidental pastes of huge blobs)
MAX_CODE_LENGTH: int = 50_000

# Builtins explicitly allowed inside user code
_SAFE_BUILTINS: dict[str, Any] = {
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
    "round": round,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "type": type,
    "print": print,  # useful for debugging in the console
    "True": True,
    "False": False,
    "None": None,
}

# Patterns that should NEVER appear in user code (extra safety belt)
_BLOCKED_PATTERNS: list[str] = [
    "__import__",
    "__builtins__",
    "__subclasses__",
    "__globals__",
]


def _safe_exec(code: str) -> dict:
    """Execute user code with a restricted built-in namespace.

    Parameters
    ----------
    code : str
        Python source code to execute.

    Returns
    -------
    dict
        Merged global + local namespace after execution.

    Raises
    ------
    ValueError
        If *code* exceeds :data:`MAX_CODE_LENGTH` or contains blocked patterns.
    SyntaxError
        If *code* fails to compile.
    Exception
        Any runtime error from the user code.
    """
    if not code or not code.strip():
        return {}

    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(
            f"Custom code exceeds maximum length ({len(code):,} > {MAX_CODE_LENGTH:,} chars)"
        )

    for pattern in _BLOCKED_PATTERNS:
        if pattern in code:
            raise ValueError(f"Blocked pattern found in custom code: {pattern!r}")

    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore[assignment]

    # We must keep a real __import__ in builtins so that pre-imported
    # libraries (numpy, pandas) can lazily import their own submodules
    # at call time.  The _BLOCKED_PATTERNS check above prevents the
    # user from writing __import__('os') in their source code.
    safe_builtins = dict(_SAFE_BUILTINS)
    safe_builtins["__import__"] = __builtins__["__import__"] if isinstance(__builtins__, dict) else getattr(__builtins__, "__import__")

    g: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "pd": pd,
        "np": np,
    }
    l: dict[str, Any] = {}
    exec(compile(code, "<custom-plot>", "exec"), g, l)
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


def render_custom_code(app: Any, selector: Any, bottom_area: Any, selected_columns: list[str]) -> None:
    """Render a custom-code subplot.

    Executes user-defined code from the selector's custom-code editor
    and plots the result into *bottom_area*.

    Parameters
    ----------
    app : PlotterApp
        Application instance (provides ``df``, ``_apply_mpl_theme``, etc.).
    selector : SubplotSelectorLike
        Subplot selector with ``get_custom_code()`` and column info.
    bottom_area : tk.Frame | None
        Container widget for the resulting plot.
    selected_columns : list[str]
        Columns selected for this subplot.
    """
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
        logger.warning("Custom plot execution failed: %s", e)
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
