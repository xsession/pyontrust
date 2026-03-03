# CSV Plotter — Tech Stack Migration Plan

> **From:** Tkinter + embedded matplotlib (desktop monolith)
> **To:** Flask + vanilla JS SPA (browser-based, pin_configurator pattern)
>
> Use this document as a **prompt template** when asking an LLM to execute the
> migration.  It maps every existing module to its new role and defines the
> complete REST API, frontend architecture, and phased migration strategy.

---

## 1  Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser (single-page app)                                       │
│  ┌────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐ │
│  │ index.html  │  │  main.js     │  │ CSS inline│  │ Plotly.js│ │
│  │ (layout +   │  │ (all logic,  │  │ Catppuccin│  │ (CDN,    │ │
│  │  structure) │  │  no build)   │  │ dark)     │  │  no npm) │ │
│  └────────────┘  └──────────────┘  └───────────┘  └──────────┘ │
│         ▲ fetch() JSON / PNG ▲                                   │
│         │                     │                                   │
│ ────────┼─────────────────────┼────────────── HTTP ───────────── │
│         │                     │                                   │
│  ┌──────┴─────────────────────┴────────────────────────────────┐ │
│  │  Flask backend  (server.py)                                 │ │
│  │  • serves web/ static files                                 │ │
│  │  • REST JSON endpoints under /api/*                         │ │
│  │  • /api/plot/png — server-side matplotlib PNG rendering      │ │
│  │  • /api/csv/* — CSV loading, parsing, metrics               │ │
│  │  • in-memory state (loaded DataFrames, layout cache)        │ │
│  └──────────────────┬──────────────────────────────────────────┘ │
│                     │ imports                                     │
│  ┌──────────────────┴──────────────────────────────────────────┐ │
│  │  Pure-Python domain modules (REUSED AS-IS)                  │ │
│  │  • data.py — multi-backend CSV reader                       │ │
│  │  • metrics.py — signal metrics (min/max/rms/fft/…)          │ │
│  │  • core/model.py — PlotState dataclass                      │ │
│  │  • core/protocol.py — CsvPlotterProtocol                    │ │
│  │  • core/plotting.py — render_plot_png() headless matplotlib  │ │
│  │  • lang.py — i18n string loader                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **No build step** (no Webpack / Vite / npm) | Instant startup, zero Node.js dep, works on air-gapped lab PCs |
| **Plotly.js via CDN `<script>` tag** | Interactive zoom/pan/hover built-in; no npm; dark theme support; replaces matplotlib in browser |
| **Server-side matplotlib for PNG/SVG export** | Reuse existing `core/plotting.py`; pixel-perfect export to file |
| **Flask serving static + REST** | Simplest mature Python stack, one `pip install flask` |
| **Existing domain modules reused AS-IS** | `data.py`, `metrics.py`, `lang.py`, `core/` have ZERO Tkinter dependency |
| **Catppuccin Mocha dark theme** | Consistent with pin_configurator; developer-friendly |
| **In-memory state** (loaded DFs, layout) | No database; ephemeral-by-design for tool GUIs |
| **WebSocket optional** for live CSV tailing | Auto-reload/auto-load-newest push updates without polling |

---

## 2  Module Migration Map

### 2.1  Modules reused WITHOUT changes (backend domain layer)

| Current file | Lines | What it does | New role |
|---|---:|---|---|
| `data.py` | 520 | Multi-backend CSV reader (polars→duckdb→pyarrow→pandas), separator sniffing, header reading | Called by Flask endpoints to load CSVs |
| `metrics.py` | 217 | Pure compute: min, max, avg, med, p2p, std, rms, crest, freq, period via FFT | Called by `/api/csv/metrics` endpoint |
| `core/model.py` | 35 | `PlotState` dataclass | Backend state container |
| `core/protocol.py` | 85 | `CsvPlotterProtocol` — load/reload CSV, folder scanning | Backend session manager |
| `core/plotting.py` | 75 | `render_plot_png()` — headless matplotlib | `/api/plot/png` and `/api/export/*` endpoints |
| `lang.py` | 53 | i18n loader for `strings.json` | Served as JSON to frontend; or kept server-side for export labels |
| `strings.json` | 52 | Translation strings | Served via `/api/strings` |

### 2.2  Modules REPLACED by Flask endpoints (backend)

| Current file | Lines | Tkinter coupling | New replacement |
|---|---:|---|---|
| `csv_plotter.py` | 4,642 | HEAVY — Tk root, widgets, mainloop, canvas, event binds | `server.py` routes + frontend JS |
| `ui/selector.py` | 1,602 | HEAVY — Tk Listbox, Entry, Frame, event handlers | Frontend JS `sub*` module (subplot selector) |
| `ui/menu.py` | 205 | HEAVY — Tk Menu widget | Frontend HTML tab bar + keyboard shortcuts |
| `ui/help_content.py` | ~100 | Tk messagebox dialogs | Frontend modal / `/api/strings` |
| `persistence/layout.py` | 345 | Mixed — `build_layout_data()` is pure, dialog funcs use Tk | Flask endpoints + JSON save/load |

### 2.3  Plot modules — dual strategy (server-side + client-side)

| Current file | Lines | Tkinter coupling | Migration strategy |
|---|---:|---|---|
| `plots/plotting.py` | 739 | HEAVY — `FigureCanvasTkAgg`, `NavigationToolbar2Tk`, `SpanSelector` | **Delete.** Replace with Plotly.js client-side + server-side PNG export |
| `plots/plot_main.py` | 968 | NONE (returns `MainPlotResult` with `Figure`) | Refactor: extract data prep → new `plot_data.py`; Plotly.js renders in browser |
| `plots/plot_checks_common.py` | 453 | NONE (pure pandas helpers) | **Reuse AS-IS** as backend helper module |
| `plots/plot_abs_check.py` | 168 | LIGHT — uses `FigureCanvasTkAgg` for embedding | Refactor: extract data→JSON, render in Plotly.js |
| `plots/plot_rel_change.py` | 183 | LIGHT — same pattern | Refactor: extract data→JSON, render in Plotly.js |
| `plots/plot_histogram.py` | 236 | LIGHT — same pattern | Refactor: extract data→JSON, render in Plotly.js |
| `plots/plot_stats_table.py` | 325 | HEAVY — Tk Treeview | Replace with HTML `<table>` in frontend |
| `plots/plot_custom_code.py` | 317 | MEDIUM — Tk text widget for code editor | Frontend: `<textarea>` + POST to `/api/csv/custom-code` for safe exec |

---

## 3  New File Structure

```
csv_plotter/
├── run.py                      # CLI entry: argparse → app.run(port, open)
├── server.py                   # Flask app: all REST routes + state management
├── web/
│   ├── index.html              # SPA shell: HTML structure + all CSS
│   └── main.js                 # All frontend logic (vanilla ES2020+)
│
│   # ── Domain modules (reused / lightly refactored) ──
├── data.py                     # [REUSED] Multi-backend CSV reader
├── metrics.py                  # [REUSED] Signal metrics computation
├── lang.py                     # [REUSED] i18n loader
├── strings.json                # [REUSED] Translation strings
├── core/
│   ├── __init__.py
│   ├── model.py                # [REUSED] PlotState dataclass
│   ├── protocol.py             # [REUSED] CsvPlotterProtocol
│   └── plotting.py             # [REUSED] render_plot_png() for server-side export
│
│   # ── Refactored plot data helpers (NO Tkinter) ──
├── plot_data/
│   ├── __init__.py
│   ├── checks_common.py        # [REUSED] from plots/plot_checks_common.py
│   ├── main_series.py          # [EXTRACTED] data prep from plot_main.py → JSON-ready dicts
│   ├── abs_check.py            # [EXTRACTED] data prep from plot_abs_check.py
│   ├── rel_change.py           # [EXTRACTED] data prep from plot_rel_change.py
│   ├── histogram.py            # [EXTRACTED] data prep from plot_histogram.py
│   └── custom_code.py          # [EXTRACTED] safe exec engine from plot_custom_code.py
│
│   # ── Persistence (layout save/load, pure functions) ──
├── persistence/
│   ├── __init__.py
│   └── layout.py               # [REFACTORED] keep build_layout_data / apply; remove Tk dialogs
│
│   # ── Existing assets ──
├── docs/                       # User/developer guides
├── layout.json                 # Persisted default layout
├── requirements.txt            # flask, pandas, numpy, matplotlib, …
├── pyproject.toml              # PEP 621 metadata
│
│   # ── Tests ──
├── tests/
│   ├── conftest.py             # Flask test client + fixtures
│   ├── test_api.py             # Integration tests for all REST endpoints
│   ├── test_data.py            # Unit tests for CSV reading (existing)
│   ├── test_metrics.py         # Unit tests for metrics (existing)
│   ├── test_plot_data.py       # Unit tests for plot data extraction
│   └── test_layout.py          # Unit tests for layout persistence
│
├── Dockerfile                  # Reproducible container
└── start.bat                   # Windows quick-launch
```

---

## 4  REST API Design

### 4.1  CSV Data Operations

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/csv/load` | Load a CSV file | `{"path": "..."}` | `{"columns": [...], "rows": N, "separator": ";", "timestamp_scale": 1e-6}` |
| POST | `/api/csv/load-folder` | Set folder + find newest CSV | `{"folder": "...", "recursive": false}` | Same as load |
| GET | `/api/csv/columns` | Get current columns | — | `{"columns": [...]}` |
| POST | `/api/csv/data` | Get column data (paginated / windowed) | `{"columns": ["A","B"], "x_range": [0, 100], "max_points": 5000}` | `{"x": [...], "series": {"A": [...], "B": [...]}}` |
| POST | `/api/csv/metrics` | Compute signal metrics | `{"columns": ["A","B"], "x_window": [10, 50]}` | `{"A": {"min":..., "max":..., ...}, "B": {...}}` |
| GET | `/api/csv/info` | Current file info | — | `{"path": "...", "rows": N, "cols": N, "mtime": ...}` |
| POST | `/api/csv/reload` | Reload current file | — | Same as load |
| GET | `/api/csv/check-mtime` | Check if file changed | — | `{"changed": true, "mtime": ...}` |

### 4.2  Multi-File Overlay Operations

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/overlay/add` | Add overlay CSV file | `{"path": "..."}` | `{"files": [{path, columns, rows}, ...]}` |
| DELETE | `/api/overlay/<idx>` | Remove overlay file | — | `{"files": [...]}` |
| POST | `/api/overlay/data` | Get multi-file series data | `{"columns": [...], "alignment": "aligned"\|"independent", "shifts": {...}, "max_points": 5000}` | `{"files": [{"path":..., "x":[...], "series":{...}}, ...]}` |

### 4.3  Plot Rendering (Server-Side Export)

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/plot/png` | Render matplotlib PNG | `{"columns": [...], "mode": "timeseries", "width": 1200, "height": 400}` | `image/png` binary |
| POST | `/api/plot/svg` | Render matplotlib SVG | Same | `image/svg+xml` |
| POST | `/api/export/combined-png` | All subplots as one PNG | `{"subplots": [{columns, mode}, ...]}` | `image/png` |

### 4.4  Plot Data (for Client-Side Plotly.js Rendering)

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| POST | `/api/plot-data/timeseries` | Time-series traces for Plotly | `{"subplot_index": 0, "columns": [...], "x_window": null, "max_points": 5000}` | `{"traces": [{"x":[...], "y":[...], "name":"col"}], "layout": {...}}` |
| POST | `/api/plot-data/abs-check` | Abs check view data | Same + `{"barriers": {...}}` | `{"traces": [...], "barriers": {...}}` |
| POST | `/api/plot-data/rel-change` | Rel change view data | Same | `{"traces": [...]}` |
| POST | `/api/plot-data/histogram` | Histogram bin data | `{"columns": [...], "x_window": [...]}` | `{"traces": [{"x": bins, "y": counts, "name": "col"}]}` |
| POST | `/api/plot-data/custom-code` | Execute custom transform + return traces | `{"code": "...", "columns": [...]}` | `{"traces": [...], "error": null}` |

### 4.5  Layout & Settings

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/layout` | Get current layout | — | `{...layout JSON...}` |
| POST | `/api/layout` | Save layout | `{...layout JSON...}` | `{"success": true}` |
| DELETE | `/api/layout` | Clear / reset layout | — | `{"success": true}` |
| POST | `/api/layout/import` | Load layout from file path | `{"path": "..."}` | `{...layout JSON...}` |
| POST | `/api/layout/export` | Save layout to file path | `{"path": "...", "data": {...}}` | `{"success": true}` |

### 4.6  Utilities

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| GET | `/api/strings` | Get i18n strings | — | `{...strings.json contents...}` |
| GET | `/api/history` | Get recent file history | — | `{"files": [...], "index": N}` |
| POST | `/api/history/navigate` | Go prev/next in history | `{"direction": "prev"\|"next"}` | `{"path": "...", "index": N}` |
| POST | `/api/history/clear` | Clear file history | — | `{"success": true}` |
| GET | `/api/folder/browse` | List files in folder | `?path=...&recursive=false` | `{"files": [...], "folders": [...]}` |

---

## 5  Frontend Architecture (main.js)

### 5.1  Module prefix map

Each UI concern gets a **3-letter prefix** for its functions and state variables:

| Prefix | Module | Responsibility |
|--------|--------|----------------|
| `csv` | CSV Loading | File open, folder browse, reload, auto-refresh |
| `sub` | Subplot Selector | Column selection, Y-limits, barriers, per-subplot config |
| `plt` | Plot Renderer | Plotly.js trace building, layout updates, zoom sync |
| `sta` | Stats Table | Metrics table rendering, sorting, row click→highlight |
| `his` | Histogram | Histogram trace rendering in Plotly |
| `ovl` | Overlay Manager | Multi-file overlay panel, file enable/disable, shifts |
| `lay` | Layout Manager | Save/load/clear layout, auto-save timer |
| `cfg` | Settings | Theme, auto-reload period, datashader toggle |
| `hlp` | Help / About | Help modal, keyboard shortcuts display |

### 5.2  JavaScript architecture

```
main.js  (single file, ~2000–3000 lines, "use strict")
│
├── State variables (global lets)
│   csvState = { df_columns: [], file_path: "", rows: 0, ... }
│   subplots = [{ id: 0, columns: [], mode: "timeseries", ... }]
│   ovlFiles = []
│   layData  = {}
│   cfgSettings = { autoReload: false, reloadPeriod: 1000, ... }
│
├── DOM helpers
│   const $ = (sel) => document.querySelector(sel);
│   const $$ = (sel) => document.querySelectorAll(sel);
│   function toast(msg, type) { ... }
│   function api(path, opts) { ... }   // fetch wrapper with error handling
│
├── Module: CSV Loading  (csv*)
│   csvInit() — wire file-open button, folder picker, drag-drop
│   csvLoadFile(path) → POST /api/csv/load → csvOnLoaded(data)
│   csvLoadFolder(folder) → POST /api/csv/load-folder
│   csvReload() → POST /api/csv/reload
│   csvStartAutoReload() — setInterval → GET /api/csv/check-mtime
│   csvOnLoaded(data) — update csvState, call subRenderAll()
│
├── Module: Subplot Selector  (sub*)
│   subInit() — render initial subplot panel
│   subAdd() — add new subplot (clone or blank)
│   subRemove(id) — remove subplot panel + plot
│   subRenderSelector(id) — build column list, mode dropdown, Y-limit inputs
│   subGetConfig(id) → { columns, mode, ylim, barriers, x_window, ... }
│   subSearch(id, query) — filter column list by text
│   subInvertSelection(id) — toggle all columns
│   subRenderAll() — re-render all subplot selectors when columns change
│
├── Module: Plot Renderer  (plt*)
│   pltInit() — create Plotly div containers
│   pltRender(subplotId) → POST /api/plot-data/<mode> → Plotly.react(div, traces, layout)
│   pltRenderAll() — render all subplots
│   pltSyncXRange(sourceId, xRange) — sync zoom across subplots
│   pltOnSelect(subplotId, xRange) — handle span selection → update x_window
│   pltExportPng() → POST /api/plot/png → download blob
│   pltExportSvg() → POST /api/plot/svg → download blob
│   pltSetTheme() — apply Catppuccin colors to Plotly layout
│
├── Module: Stats Table  (sta*)
│   staRender(subplotId, metrics) — build HTML <table> from metrics
│   staSort(col) — client-side column sort
│   staOnRowClick(signal) — toggle highlight on corresponding plot trace
│   staCopyToClipboard() — copy table rows
│
├── Module: Histogram  (his*)
│   hisRender(subplotId) → POST /api/plot-data/histogram → Plotly.react(...)
│
├── Module: Overlay Manager  (ovl*)
│   ovlInit() — render overlay panel per subplot
│   ovlAddFile(subplotId) → POST /api/overlay/add → ovlRender()
│   ovlRemoveFile(subplotId, idx)
│   ovlToggleFile(subplotId, idx) — enable/disable
│   ovlSetShift(subplotId, idx, xShift, yShift)
│   ovlSetAlignment(subplotId, mode) — "aligned" | "independent"
│   ovlRender(subplotId) — rebuild overlay file list UI
│
├── Module: Layout Manager  (lay*)
│   layInit() — check for auto-saved layout, apply if found
│   laySave() → POST /api/layout → toast("Layout saved")
│   layLoad() → GET /api/layout → layApply(data)
│   layApply(data) — restore subplot configs, selections, sash positions
│   layClear() → DELETE /api/layout → reload page
│   layExport() → file download dialog
│   layImport() → file upload → POST /api/layout/import
│   layAutoSaveTimer — setInterval → POST /api/layout every 30s
│
├── Module: Settings  (cfg*)
│   cfgInit() — render settings modal inputs
│   cfgApply() — read form, update cfgSettings, restart timers
│   cfgToggleAutoReload() — start/stop auto-reload polling
│
├── Module: Help  (hlp*)
│   hlpInit() — wire F1, help button
│   hlpShowHelp() — open help modal with content from /api/strings
│   hlpShowAbout() — open about modal
│
└── DOMContentLoaded
    ├── csvInit(), subInit(), pltInit(), staInit(), ovlInit()
    ├── layInit() — restore saved layout
    ├── cfgInit()
    ├── wire global keyboard shortcuts (Ctrl+O, Ctrl+R, F1, F5, Escape)
    └── wire tab switching, resizable panels
```

### 5.3  Plotly.js integration

```javascript
// Catppuccin-themed Plotly layout template
const PLOTLY_LAYOUT = {
    paper_bgcolor: '#1e1e2e',
    plot_bgcolor:  '#252538',
    font:   { color: '#cdd6f4', family: 'Segoe UI, monospace' },
    xaxis:  { gridcolor: '#45475a', zerolinecolor: '#45475a' },
    yaxis:  { gridcolor: '#45475a', zerolinecolor: '#45475a' },
    legend: { bgcolor: 'rgba(0,0,0,0)', font: { color: '#cdd6f4' } },
    margin: { t: 30, b: 40, l: 60, r: 20 },
};

const PLOTLY_COLORS = [
    '#89b4fa', '#a6e3a1', '#f38ba8', '#f9e2af', '#fab387',
    '#cba6f7', '#f5c2e7', '#94e2d5', '#89dceb', '#b4befe',
];

// Server sends downsampled data; Plotly handles zoom/pan/hover natively
async function pltRender(subplotId) {
    const cfg = subGetConfig(subplotId);
    const resp = await api(`/api/plot-data/${cfg.mode}`, {
        method: 'POST',
        body: JSON.stringify({
            subplot_index: subplotId,
            columns: cfg.columns,
            x_window: cfg.x_window,
            max_points: 5000,
        }),
    });
    const data = await resp.json();
    Plotly.react(`plot-${subplotId}`, data.traces, {
        ...PLOTLY_LAYOUT,
        ...data.layout,
    }, { responsive: true, displayModeBar: true });
}
```

### 5.4  Downsampling strategy

- **Client request includes `max_points`** (default 5000)
- **Server** applies LTTB (Largest Triangle Three Buckets) or uniform stride downsampling before sending JSON
- **On zoom**, frontend re-requests data for the visible x-range with higher resolution
- **Plotly's built-in zoom** fires `plotly_relayout` → re-fetch windowed data from server

```javascript
// Re-fetch on zoom
document.getElementById(`plot-${id}`).on('plotly_relayout', (evt) => {
    if (evt['xaxis.range[0]'] !== undefined) {
        const xRange = [evt['xaxis.range[0]'], evt['xaxis.range[1]']];
        subSetXWindow(id, xRange);
        pltRender(id);
        pltSyncXRange(id, xRange);  // sync other subplots
    }
});
```

---

## 6  HTML Structure (index.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CSV Plotter</title>
  <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
  <!-- fallback for offline: <script src="plotly.min.js"></script> -->
  <style>
    /* ─── Catppuccin Mocha theme ─── */
    :root {
      --bg:     #1e1e2e;  --bg2:    #252538;  --bg3:    #2d2d44;
      --fg:     #cdd6f4;  --fg-dim: #6c7086;  --accent: #89b4fa;
      --green:  #a6e3a1;  --red:    #f38ba8;  --yellow: #f9e2af;
      --border: #45475a;  --radius: 6px;
    }
    body { font-family: 'Segoe UI', monospace; background: var(--bg); color: var(--fg);
           display: flex; height: 100vh; overflow: hidden; margin: 0; }
    /* ... (full CSS follows pin_configurator pattern) ... */
  </style>
</head>
<body>
  <!-- ─── Left Sidebar: Controls + Subplot Selectors ─── -->
  <div class="sidebar" id="sidebar">
    <!-- File controls -->
    <div class="file-controls">
      <button onclick="csvOpenFile()">Open CSV</button>
      <button onclick="csvOpenFolder()">Open Folder</button>
      <div class="file-info" id="file-info">No file loaded</div>
      <label><input type="checkbox" id="auto-reload"> Auto-reload</label>
    </div>

    <!-- Subplot selector panels (dynamically added) -->
    <div id="subplot-selectors"></div>
    <button onclick="subAdd()">+ Add Subplot</button>
  </div>

  <!-- ─── Resize Handle ─── -->
  <div class="resize-handle" id="resize-handle"></div>

  <!-- ─── Main Area: Plots + Stats ─── -->
  <div class="main-area" id="main-area">
    <!-- Top toolbar -->
    <div class="toolbar">
      <button onclick="pltRenderAll()">Plot All (Ctrl+R)</button>
      <button onclick="pltExportPng()">Export PNG</button>
      <button onclick="pltExportSvg()">Export SVG</button>
      <button onclick="laySave()">Save Layout (Ctrl+S)</button>
      <button onclick="layLoad()">Load Layout (Ctrl+L)</button>
      <button onclick="hlpShowHelp()">Help (F1)</button>
    </div>

    <!-- Plot containers (dynamically added per subplot) -->
    <div id="plot-panels"></div>
  </div>

  <!-- ─── Modals ─── -->
  <div class="modal-backdrop" id="helpModal"> ... </div>
  <div class="modal-backdrop" id="settingsModal"> ... </div>

  <!-- ─── Toast ─── -->
  <div class="toast" id="toast"></div>

  <script src="main.js"></script>
</body>
</html>
```

### Layout concept

```
┌─────────────────────┬───────────────────────────────────────┐
│  SIDEBAR (resizable) │  MAIN AREA                            │
│                      │                                       │
│  [Open CSV] [Folder] │  [Plot All] [PNG] [SVG] [Layout] [?] │
│  File: data.csv      │                                       │
│  Rows: 5000 Cols: 12 │  ┌─── Subplot 1 ───────────────────┐ │
│  ☐ Auto-reload       │  │  [Plotly.js interactive chart]   │ │
│                      │  │  zoom · pan · hover · select     │ │
│  ╔═══ Subplot 1 ═══╗│  │                                   │ │
│  ║ Mode: [▼ Time]  ║│  │  Stats: Min | Max | Avg | RMS... │ │
│  ║ 🔍 filter...    ║│  │  [Histogram bar chart]            │ │
│  ║ ☑ Current_mA    ║│  └───────────────────────────────────┘ │
│  ║ ☑ Voltage_V     ║│                                       │
│  ║ ☐ Temperature   ║│  ┌─── Subplot 2 ───────────────────┐ │
│  ║ Y-lim: [__]-[__]║│  │  [Plotly.js interactive chart]   │ │
│  ║ Barriers: [cfg] ║│  │                                   │ │
│  ║ Overlay: [+file] ║│  └───────────────────────────────────┘ │
│  ║ [Duplicate][✕]  ║│                                       │
│  ╚══════════════════╝│                                       │
│                      │                                       │
│  ╔═══ Subplot 2 ═══╗│                                       │
│  ║ ...              ║│                                       │
│  ╚══════════════════╝│                                       │
│                      │                                       │
│  [+ Add Subplot]     │                                       │
└─────────────────────┴───────────────────────────────────────┘
```

---

## 7  Backend Implementation Guide (server.py)

### 7.1  Flask app setup

```python
import pathlib, json, uuid, time
from flask import Flask, jsonify, request, send_from_directory

_HERE = pathlib.Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(_HERE / "web"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB CSV upload limit

# ── In-memory state ──
_state = {
    "file_path": None,
    "folder_path": None,
    "df": None,             # current pandas DataFrame
    "columns": [],
    "rows": 0,
    "separator": ";",
    "timestamp_scale": 1.0,
    "mtime": None,
    "overlay_files": [],    # list of {path, df, columns, rows}
    "history": [],
    "history_index": -1,
}

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")
```

### 7.2  Wiring existing modules

```python
# Import reused domain modules directly
from data import read_any_csv, sniff_csv_separator, read_csv_header, find_newest_csv
from data import compute_timestamp_scale_for_df
from metrics import compute_signal_metrics
from core.model import PlotState
from core.protocol import CsvPlotterProtocol
from core.plotting import render_plot_png
from lang import load_strings

# Plot data extraction (refactored from plots/ modules)
from plot_data.main_series import extract_timeseries_traces
from plot_data.abs_check import extract_abs_check_traces
from plot_data.rel_change import extract_rel_change_traces
from plot_data.histogram import extract_histogram_traces
from plot_data.custom_code import safe_exec_transform
from plot_data.checks_common import downsample_series, parse_barriers_from_selector

# Layout persistence (pure functions, Tk dialogs removed)
from persistence.layout import build_layout_data, apply_layout_from_dict
```

### 7.3  Key endpoint implementation pattern

```python
@app.route("/api/csv/load", methods=["POST"])
def csv_load():
    body = request.get_json(force=True)
    path = body.get("path", "")
    if not path or not pathlib.Path(path).is_file():
        return jsonify({"error": f"File not found: {path}"}), 404

    try:
        sep = sniff_csv_separator(path)
        df = read_any_csv(path, sep=sep)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    ts_scale = compute_timestamp_scale_for_df(df) if "Timestamp" in df.columns else 1.0

    _state["file_path"] = str(path)
    _state["df"] = df
    _state["columns"] = list(df.columns)
    _state["rows"] = len(df)
    _state["separator"] = sep
    _state["timestamp_scale"] = ts_scale
    _state["mtime"] = pathlib.Path(path).stat().st_mtime

    # Update history
    _push_history(str(path))

    return jsonify({
        "columns": _state["columns"],
        "rows": _state["rows"],
        "separator": sep,
        "timestamp_scale": ts_scale,
        "path": str(path),
    })

@app.route("/api/csv/metrics", methods=["POST"])
def csv_metrics():
    body = request.get_json(force=True)
    columns = body.get("columns", [])
    x_window = body.get("x_window")
    df = _state["df"]
    if df is None:
        return jsonify({"error": "No CSV loaded"}), 400

    results = {}
    for col in columns:
        if col not in df.columns or col == "Timestamp":
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if x_window and "Timestamp" in df.columns:
            ts = pd.to_numeric(df["Timestamp"], errors="coerce") / _state["timestamp_scale"]
            mask = (ts >= x_window[0]) & (ts <= x_window[1])
            series = series[mask].dropna()
        if len(series) == 0:
            results[col] = None
            continue
        m = compute_signal_metrics(series)
        results[col] = {
            "min": m[0], "max": m[1], "avg": m[2], "med": m[3],
            "p2p": m[4], "std": m[5], "rms": m[6], "crest": m[7],
            "freq": m[8], "period": m[9],
        }
    return jsonify(results)
```

---

## 8  Phased Migration Strategy

### Phase 0 — Preparation (no code changes)
- [x] Read this document
- [ ] Ensure all 88 existing csv_plotter tests pass
- [ ] Install Flask in the project venv: `pip install flask`
- [ ] Download Plotly.js minified to `web/plotly.min.js` for offline fallback

### Phase 1 — Backend scaffolding (server.py + run.py)
**Goal:** Flask app that can load a CSV and serve its columns/data as JSON.

| Task | Details |
|------|---------|
| Create `run.py` | argparse CLI → `server.app.run()` |
| Create `server.py` | Flask app, static file serving, `/api/csv/load`, `/api/csv/columns`, `/api/csv/data` |
| Create `web/` folder | Empty `index.html` with "Hello CSV Plotter" |
| Wire `data.py` | Import and call `read_any_csv()` in the load endpoint |
| Wire `metrics.py` | Implement `/api/csv/metrics` |
| Tests | `test_api.py` — load CSV, check columns, check metrics |

**Validation:** `curl http://localhost:5200/api/csv/load` returns JSON ✓

### Phase 2 — Frontend shell (index.html + main.js basics)
**Goal:** Browser shows sidebar with column list + one Plotly chart.

| Task | Details |
|------|---------|
| Build `index.html` | SPA shell with Catppuccin CSS, sidebar + main layout |
| Build `main.js` scaffolding | DOM helpers, `api()` wrapper, `csvInit()` |
| Column selector | `subRenderSelector()` — checkbox list from `/api/csv/columns` |
| Basic Plotly chart | `pltRender()` — fetch `/api/plot-data/timeseries` → `Plotly.react()` |
| Keyboard shortcuts | Ctrl+O, Ctrl+R, F1, F5 |

**Validation:** Open browser → load CSV → see interactive Plotly chart ✓

### Phase 3 — Full subplot & overlay system
**Goal:** Multi-subplot support, overlay files, all plot modes.

| Task | Details |
|------|---------|
| `sub*` module | Add/remove/duplicate subplots, per-subplot column selection |
| `ovl*` module | Multi-file overlay panel, alignment modes, per-file shifts |
| Plot modes | Implement abs-check, rel-change, histogram, custom-code views |
| `plot_data/` package | Extract data-prep logic from old `plots/*.py`, remove Tkinter deps |
| Stats table | `sta*` module — HTML table with sort, click-to-highlight, copy |
| X-range sync | `plotly_relayout` handler to sync zoom across subplots |

**Validation:** All plot modes render correctly with multi-file overlay ✓

### Phase 4 — Layout, settings & polish
**Goal:** Full feature parity with Tkinter version.

| Task | Details |
|------|---------|
| `lay*` module | Save/load/clear layout via REST, auto-save timer |
| `cfg*` module | Settings modal — auto-reload period, theme, max points |
| `hlp*` module | Help modal with keyboard shortcuts, about dialog |
| File history | `/api/history/*` endpoints + UI dropdown |
| Auto-reload | Polling `/api/csv/check-mtime` → auto-refresh plots |
| Drag-drop | Drop CSV file onto browser → load |
| Resizable panels | CSS `resize` + JS drag handler for sidebar width |
| Perspective integration | Optional: link to open Perspective viewer |

**Validation:** Save layout → reload page → layout restored ✓

### Phase 5 — Testing & cleanup
**Goal:** Full test coverage, remove old Tkinter code.

| Task | Details |
|------|---------|
| API integration tests | All endpoints tested via Flask test client |
| Plot data unit tests | Verify data extraction produces correct JSON |
| E2E smoke test | Selenium/Playwright basic flow (optional) |
| Remove old Tkinter files | Delete `csv_plotter.py`, `ui/`, `plots/plotting.py` |
| Update documentation | Revise UserGuide.md, DeveloperGuide.md |
| Update `pyproject.toml` | Replace tkinter deps with flask |

---

## 9  Feature Parity Checklist

| Feature (Tkinter version) | New implementation | Priority |
|---|---|---|
| Open CSV file | POST `/api/csv/load` + JS file dialog | P0 |
| Open folder + find newest | POST `/api/csv/load-folder` | P0 |
| Column selection per subplot | `sub*` JS module — checkbox list | P0 |
| Time-series plot | Plotly.js `scatter` trace | P0 |
| Zoom / pan / hover | Plotly.js built-in | P0 (free) |
| X-range sync across subplots | `plotly_relayout` handler | P0 |
| Signal metrics table | HTML `<table>` from `/api/csv/metrics` | P0 |
| Histogram | Plotly.js `histogram` trace | P1 |
| Multi-file overlay | `ovl*` module + `/api/overlay/*` | P1 |
| Abs check / barriers | Plotly.js `shape` annotations | P1 |
| Rel change view | Plotly.js horizontal lines | P1 |
| Custom code transform | `<textarea>` + POST `/api/plot-data/custom-code` | P2 |
| Manual Y-limits | Plotly `layout.yaxis.range` | P1 |
| Span selection (time window) | Plotly `select` / `lasso` events | P1 |
| Layout save / load / auto-save | `lay*` module + `/api/layout` | P1 |
| Export PNG / SVG | Server-side matplotlib `render_plot_png()` | P1 |
| Auto-reload when file changes | JS polling `/api/csv/check-mtime` | P1 |
| Auto-load newest in folder | JS polling + `/api/csv/load-folder` | P1 |
| File history (prev/next) | `/api/history/*` + dropdown | P2 |
| Per-file X/Y shifts (overlay) | `ovl*` module inputs | P2 |
| Keyboard shortcuts | JS `keydown` listener | P1 |
| i18n strings | Served from `/api/strings`, applied in JS | P2 |
| Resizable sidebar | CSS + JS drag handler | P1 |
| Right-click context menus | Custom JS context menu | P3 |
| Perspective viewer integration | Link/iframe to external viewer | P3 |
| Datashader rendering | Server-side only for huge files → send PNG | P3 |
| Drag-and-drop CSV | HTML5 drag events → POST `/api/csv/load` | P2 |
| Help / About dialogs | Modal windows | P2 |

---

## 10  Dependencies

### Python (requirements.txt)

```
flask>=3.0.0
werkzeug>=3.0.0
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
```

Optional (already used by data.py):
```
polars>=0.20.0          # fast CSV reading
duckdb>=0.9.0           # SQL-based CSV reading
pyarrow>=14.0.0         # Arrow-based CSV reading
datashader>=0.16.0      # server-side large-dataset rendering
```

### Frontend

**Zero npm dependencies.** Browser-native APIs only:
- `Plotly.js` via CDN `<script>` tag (or local `plotly.min.js` for offline)
- `fetch()` for HTTP
- `FileReader` for drag-and-drop CSV loading
- `navigator.clipboard` for copy-to-clipboard (stats table)
- CSS custom properties for Catppuccin theming
- No React, no Vue, no build step

---

## 11  Project Stats (estimated)

| File | Est. Lines | Role |
|------|------:|------|
| `server.py` | ~600–800 | Flask routes + state management |
| `web/main.js` | ~2,000–3,000 | All frontend logic |
| `web/index.html` | ~500–800 | Layout + all CSS |
| `data.py` | 520 | [REUSED] CSV reader |
| `metrics.py` | 217 | [REUSED] Signal metrics |
| `core/model.py` | 35 | [REUSED] PlotState |
| `core/protocol.py` | 85 | [REUSED] CSV protocol |
| `core/plotting.py` | 75 | [REUSED] Headless matplotlib |
| `lang.py` | 53 | [REUSED] i18n loader |
| `plot_data/*.py` | ~400–500 | [EXTRACTED] Plot data helpers |
| `persistence/layout.py` | ~200 | [REFACTORED] Layout pure funcs |
| `run.py` | ~40 | CLI entry point |
| **Total new code** | **~3,500–5,000** | |
| **Total reused** | **~1,385** | |
| **Code DELETED** | **~8,500** | Old Tkinter monolith + UI modules |

---

## 12  How to Use This Document as a Prompt

When asking an LLM to implement a migration phase:

```
Implement Phase 2 of the CSV Plotter migration plan.

Context:
- Phase 1 is complete: server.py serves /api/csv/load and /api/csv/data
- The csv_plotter/ folder already contains data.py, metrics.py, core/, lang.py
- Plotly.js is loaded via CDN in index.html

Requirements from CSV_PLOTTER_REFACTOR.md:
- Build index.html with Catppuccin Mocha dark theme (section 6)
- Build main.js with csv* and sub* modules (section 5.2)
- Implement basic Plotly chart rendering (section 5.3)
- Wire keyboard shortcuts Ctrl+O, Ctrl+R, F1, F5

[paste relevant sections 5, 6 from this document]
```
