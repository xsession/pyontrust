# Multi-Subplot CSV Viewer — Developer Guide

This guide explains how the CSV plotter is organized, where to change behavior, and how persistence/timebase work.

## Running locally
From repo root:
- Run: `mp/python/python.exe app/csv_plotter/csv_plotter.py`

## High-level architecture
- **UI/controller**: `app/csv_plotter/csv_plotter.py`
- **Subplot config UI**: `app/csv_plotter/ui/selector.py`
- **Rendering pipeline**: `app/csv_plotter/plots/plotting.py`
- **Plot implementations**:
  - main: `app/csv_plotter/plots/plot_main.py`
  - histogram: `app/csv_plotter/plots/plot_histogram.py`
  - checks: `app/csv_plotter/plots/plot_abs_check.py`, `plot_rel_change.py`, common helpers
- **Metrics**: `app/csv_plotter/metrics.py`
- **Persistence**: `app/csv_plotter/persistence/layout.py` → `layout.json`

See infographic: `docs/infographics/architecture.svg`

## Plot lifecycle (mental model)
1. User changes selector state (signals/overlays/window/etc.)
2. App calls `request_replot()` (debounced)
3. `plots/plotting.py` renders:
   - main plot
   - optional bottom panels (table/hist/checks)
4. Selector state + global settings are persisted to `layout.json` (debounced autosave)

See infographic: `docs/infographics/render_pipeline.svg`

## Timebase (effective scale to seconds)
### Concepts
- **auto scale**: derived from the file’s timestamp axis (heuristic)
- **global fixed timebase**: Settings → Timebase (unit + step)
- **per-file timebase**: stored per overlay in the subplot selector
- **effective scale**: per-file override > global fixed override > auto

### Key functions
- `CSVPlotterApp._get_df_for_path(path, selector)` returns `(df, effective_scale_to_seconds)`
- `CSVPlotterApp._effective_scale_to_seconds_for_path(...)`
- `CSVPlotterApp._effective_timebase_mode_for_path(...)` returns `fixed|auto`

### Why `fixed` mode is special
Some files contain a `Timestamp` column that is actually a sample counter. When the effective timebase is **fixed**, the Stats Table builds a uniform time axis using `sample_index * dt_seconds` for frequency/period estimation.

See infographic: `docs/infographics/timebase_modes.svg`

## Toolbar Home behavior
The Matplotlib toolbar Home button is wrapped in `plots/plotting.py` so it:
- resets to full view
- clears selector window state
- avoids re-saving a new window via xlim callbacks

## Persistence format
`layout.json` stores:
- root settings (including `timebase`)
- per-subplot state (including overlays, `x_window`, and `file_timebase`)

Entry points:
- build: `build_layout_data(app)`
- apply: `apply_layout_subplots(app, data)`

See infographic: `docs/infographics/layout_persistence.svg`

## Common change locations
- **Add new bottom panel**: `plots/plotting.py` + new renderer module
- **Change Table metrics**: `metrics.py` and call sites in `plot_main.py`
- **Add new persisted selector state**: `ui/selector.py` + `persistence/layout.py`

## Notes
- Optional integrations (Perspective/uvicorn) may not be installed in all envs.
- Keep changes minimal and debounced (the UI can replot frequently).
