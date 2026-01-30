from __future__ import annotations

from typing import Any


try:
    import pyontrust_csv_plotter_core as _core
except Exception as e:  # pragma: no cover
    _core = None
    _core_import_error = e
else:
    _core_import_error = None


def require_core():
    if _core is None:  # pragma: no cover
        raise RuntimeError(f"Rust backend not available: {_core_import_error}")
    return _core


def read_columns(path: str) -> list[str]:
    core = require_core()
    cols = core.read_csv_header(path)
    return [str(c) for c in cols]


def read_plot_data(path: str, x_col: str, y_cols: list[str], max_points: int) -> dict[str, Any]:
    core = require_core()
    return core.read_xy_decimated(path, x_col, y_cols, int(max_points))
