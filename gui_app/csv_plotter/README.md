# CSV Plotter

Enterprise-grade CSV signal viewer built on **Tkinter + Matplotlib**.

## Features

- **Multi-subplot** layout with independent signal selection, Y-limits, and X-windows.
- **Multi-file overlay** — compare signals across files with per-file time/amplitude shifts.
- **Auto-detect delimiter** (comma, semicolon, tab, pipe) and timestamp units (s, ms, µs).
- **10 signal metrics** per channel: min, max, avg, median, peak-to-peak, std, RMS, crest factor, frequency, period.
- **FFT-based frequency estimation** with zero-crossing fallback.
- **Custom-code plot** — define `transform(x, signals, df)` to add computed traces.
- **Layout persistence** — save/load complete UI state to `layout.json`.
- **Multi-backend I/O** — Polars → DuckDB → PyArrow → pandas (graceful fallback).
- **Datashader** support for million-point traces.
- **Structured logging** with rotating file output (see `core/logger.py`).

## Quick Start

```bash
# Install core dependencies
pip install pandas numpy matplotlib

# Optional high-performance backends
pip install polars duckdb pyarrow

# Launch
python csv_plotter.py
```

## Architecture

```
csv_plotter/
├── csv_plotter.py          # Main app class (CSVPlotterApp) + entrypoint
├── data.py                 # Multi-backend CSV I/O with auto delimiter detection
├── metrics.py              # Pure-compute signal metrics (no GUI dependency)
├── lang.py                 # i18n string tables
├── core/
│   ├── __init__.py
│   ├── interfaces.py       # Protocol types (PlotterApp, SubplotSelectorLike)
│   ├── logger.py           # Structured logging with RotatingFileHandler
│   ├── model.py            # PlotState dataclass
│   ├── plotting.py         # Headless PNG render
│   └── protocol.py         # CsvPlotterProtocol (legacy)
├── ui/
│   ├── __init__.py
│   ├── menu.py             # Menubar wiring (Export, Layout, etc.)
│   ├── selector.py         # Per-subplot selector panel widget
│   └── help_content.py     # Help / About dialogs
├── plots/
│   ├── plotting.py         # High-level plot layout (plot_all)
│   ├── plot_main.py        # Main time-series plot renderer
│   ├── plot_histogram.py   # Histogram bottom plot
│   ├── plot_stats_table.py # Calculated-values table
│   ├── plot_custom_code.py # User-defined custom code plot (sandboxed exec)
│   ├── plot_abs_check.py   # Absolute range check diagnostic
│   ├── plot_rel_change.py  # Relative change diagnostic
│   └── plot_checks_common.py  # Shared helpers
├── persistence/
│   ├── __init__.py
│   └── layout.py           # layout.json save/load
└── pyproject.toml          # Package metadata + tool config
```

## Testing

```bash
# From the repo root
python -m pytest tests/csv_plotter_tests/ -v

# With coverage
python -m pytest tests/csv_plotter_tests/ --cov=gui_app/csv_plotter --cov-report=term-missing
```

### Test modules

| Test file | Covers |
|-----------|--------|
| `test_metrics.py` | Signal metrics, FFT, zero-crossing, edge cases (34 tests) |
| `test_data.py` | CSV I/O, sniffing, timestamp scale, SQL injection safety (30 tests) |
| `test_custom_code.py` | Sandbox exec, security boundaries, output normalization (23 tests) |
| `test_csv_plotter_core.py` | Rust core bridge (header + decimated read) |

## Type Safety

Modules that accept the main application object should type the parameter as:

```python
from core.interfaces import PlotterApp, SubplotSelectorLike

def build_main_plot(app: PlotterApp, selector: SubplotSelectorLike, ...) -> ...:
    ...
```

This enables `mypy` / `pyright` static analysis and mock-based testing without importing the 4000-line `CSVPlotterApp` class.

## Security Model

The **custom-code plot** executes user-supplied Python via `exec()` with:

- Restricted built-ins (no `open`, `eval`, `exec`, `compile`).
- Blocked source patterns (`__import__`, `__builtins__`, `__subclasses__`, `__globals__`).
- Code length limit (50 KB).

> **Warning:** This is **not** a hardened sandbox. It prevents accidents in a desktop app context. Never execute untrusted code from external sources.

## Compatibility shims

Files like `menu.py`, `layout.py`, `plotting.py`, etc. still exist at the folder root as thin re-export shims.
They are kept so older imports don’t break, but new code should import from `ui.*`, `plots.*`, and `persistence.*`.
