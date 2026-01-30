from __future__ import annotations

from pathlib import Path

from nicegui import ui

from . import backend
from .state import AppState
from .components.chart import render_chart
from .components.stats import render_stats


def _default_x(columns: list[str]) -> str:
    for preferred in ("Timestamp", "timestamp", "time", "Time"):
        if preferred in columns:
            return preferred
    return columns[0] if columns else ""


@ui.page("/")
def root_page() -> None:
    ui.label("CSV Plotter").classes("text-h5")
    ui.link("Open CSV Plotter", "/csv_plotter")
    ui.timer(0.01, lambda: ui.navigate.to("/csv_plotter"), once=True)


@ui.page("/csv_plotter")
def csv_plotter_page() -> None:
    # If Rust backend isn't installed, show a clear message instead of a 404.
    try:
        backend.require_core()
    except Exception as e:
        ui.label(f"Rust backend missing: {e}").classes("text-red-600")
        ui.label("Build/install it from gui_app/csv_plotter/rust_core (maturin)")
        return

    state = AppState()

    ui.label("CSV Plotter (NiceGUI + Rust)").classes("text-h5")

    with ui.row().classes("w-full items-end"):
        path_in = ui.input("CSV path").props("clearable").classes("w-2/3")
        load_btn = ui.button("Load")

    with ui.row().classes("w-full items-end"):
        x_sel = ui.select(options=[], label="X column").classes("w-1/3")
        y_sel = ui.select(options=[], label="Y columns", multiple=True).classes("w-2/3")

    max_points_in = ui.number("Max points", value=state.max_points, format="%d").props("min=100 step=100").classes(
        "w-40"
    )

    chart = ui.echart({"series": []}).classes("w-full h-[520px]")

    stats_table = ui.table(
        columns=[
            {"name": "signal", "label": "Signal", "field": "signal"},
            {"name": "min", "label": "Min", "field": "min"},
            {"name": "max", "label": "Max", "field": "max"},
            {"name": "mean", "label": "Mean", "field": "mean"},
            {"name": "median", "label": "Median", "field": "median"},
            {"name": "p2p", "label": "P2P", "field": "p2p"},
        ],
        rows=[],
        row_key="signal",
    ).classes("w-full")

    def do_load() -> None:
        path = str(path_in.value or "").strip()
        if not path:
            ui.notify("Choose a CSV path", type="warning")
            return
        p = Path(path)
        if not p.exists() or not p.is_file():
            ui.notify("File not found", type="negative")
            return

        cols = backend.read_columns(str(p))
        state.csv_path = str(p)
        state.columns = cols
        state.x_col = _default_x(cols)
        state.y_cols = []

        x_sel.options = cols
        x_sel.value = state.x_col
        y_sel.options = cols
        y_sel.value = []
        x_sel.update()
        y_sel.update()

        ui.notify(f"Loaded columns: {len(cols)}")

    def do_plot() -> None:
        if not state.csv_path:
            return
        x_col = str(x_sel.value or "").strip()
        y_cols = [str(c) for c in (y_sel.value or [])]
        if not x_col or not y_cols:
            chart.options = {"series": []}
            chart.update()
            stats_table.rows = []
            stats_table.update()
            return

        max_points = int(max_points_in.value or state.max_points)
        data = backend.read_plot_data(state.csv_path, x_col, y_cols, max_points)
        render_chart(chart, data, x_col, y_cols)
        render_stats(stats_table, data.get("stats", {}))

    load_btn.on("click", lambda: (do_load(), do_plot()))
    x_sel.on("update:model-value", lambda _e: do_plot())
    y_sel.on("update:model-value", lambda _e: do_plot())
    max_points_in.on("update:model-value", lambda _e: do_plot())


def run() -> None:
    ui.run(title="CSV Plotter", reload=False)
