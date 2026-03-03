from __future__ import annotations

import io
from typing import Iterable

import pandas as pd

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas


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
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(1, 1, 1)

    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data loaded", ha="center", va="center")
        ax.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        return buf.getvalue()

    x, x_label = _pick_x(df)
    if x is None:
        x = df.index.to_series()
    x = pd.to_numeric(x, errors="coerce")

    cols = [c for c in columns if c in df.columns]
    if not cols:
        cols = list(df.columns[:1])

    n = len(df)
    step = 1
    if n > 300_000:
        step = max(1, int(n / 300_000))
    if step > 1:
        df = df.iloc[::step]
        x = x.iloc[::step]

    for col in cols:
        try:
            y = pd.to_numeric(df[col], errors="coerce")
        except Exception:
            continue
        ax.plot(x, y, label=str(col), linewidth=1.0)

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
