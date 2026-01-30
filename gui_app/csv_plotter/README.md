# csv_plotter

This folder contains:

- **Legacy** Tkinter + Matplotlib CSV viewer (existing implementation)
- **New** NiceGUI frontend + Rust backend (PyO3) implementation

## Structure

- `csv_plotter.py`
  - Legacy application entrypoint (`CSVPlotterApp`) and orchestration.

- `nicegui_csv_plotter.py`
  - NiceGUI app entrypoint (frontend).

- `rust_core/`
  - PyO3 extension providing the CSV backend (parsing + stats + decimation).

- `ui/`
  - Tk/ttk UI building blocks.
  - `ui/menu.py`: menubar wiring (Export, Layout, etc.)
  - `ui/selector.py`: per-subplot selector panel widget
  - `ui/help_content.py`: Help/About dialogs

- `plots/`
  - Plot rendering code (Matplotlib embedding + bottom diagnostics).
  - `plots/plotting.py`: high-level plot layout (`plot_all`)
  - `plots/plot_main.py`: main time-series plot
  - `plots/plot_histogram.py`: histogram bottom plot
  - `plots/plot_stats_table.py`: calculated-values table
  - `plots/plot_abs_check.py`: absolute range check diagnostic
  - `plots/plot_rel_change.py`: relative change diagnostic
  - `plots/plot_checks_common.py`: shared helpers used by diagnostics
  - `plots/plot_checks_legacy.py`: legacy module kept for compatibility

- `persistence/`
  - Saving/loading user state.
  - `persistence/layout.py`: `layout.json` save/load (including UI splitter sash positions)

## Compatibility shims

Files like `menu.py`, `layout.py`, `plotting.py`, etc. still exist at the folder root as thin re-export shims.
They are kept so older imports don’t break, but new code should import from `ui.*`, `plots.*`, and `persistence.*`.

## NiceGUI version (recommended)

1) Build/install the Rust backend:

```powershell
cd C:\GIT\pyontrust\gui_app\csv_plotter\rust_core
python -m pip install -U maturin
python -m maturin build --release -o dist
python -m pip install --force-reinstall .\dist\pyontrust_csv_plotter_core-0.1.0-cp310-abi3-win_amd64.whl
```

2) Run the NiceGUI app:

```powershell
python C:\GIT\pyontrust\gui_app\csv_plotter\nicegui_csv_plotter.py
```

Then open `http://localhost:8080/csv_plotter`.
