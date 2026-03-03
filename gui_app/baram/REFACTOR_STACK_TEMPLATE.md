# Baram CFD — Refactoring to Flask + Vanilla JS Stack

> Use this document as a **system prompt / context block** when asking an LLM to
> refactor a Baram module (BaramFlow, BaramMesh, or BaramEditor) from the current
> PySide6 desktop app into a browser-based SPA following the Pin Configurator
> architecture. Copy the whole file (or the sections you need) into the prompt.

---

## 1  Architecture Overview (Target)

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser (single-page app)                                       │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │  index.html     │  │  main.js     │  │  CSS (inline)       │  │
│  │  (layout +      │  │  (all logic, │  │  Catppuccin Mocha   │  │
│  │   structure)    │  │   no build)  │  │  dark theme         │  │
│  └────────────────┘  └──────────────┘  └─────────────────────┘  │
│         ▲ fetch() JSON ▲                                         │
│         │               │                                        │
│ ────────┼───────────────┼──────────────────── HTTP ────────────  │
│         │               │                                        │
│  ┌──────┴───────────────┴─────────────────────────────────────┐  │
│  │  Flask backend  (server.py)                                │  │
│  │  • serves static files from  web/                          │  │
│  │  • REST JSON endpoints under /api/*                        │  │
│  │  • WebSocket via flask-sock for solver log streaming       │  │
│  │  • in-memory state + project file persistence              │  │
│  └──────────────────┬────────────────────────────────────────┘  │
│                     │ imports                                    │
│  ┌──────────────────┴────────────────────────────────────────┐  │
│  │  Pure-Python domain modules  (*.py in project root)       │  │
│  │  • coredb (XML + XSD config database — reused as-is)      │  │
│  │  • openfoam case generator (reused as-is)                 │  │
│  │  • solver launcher / process monitor (adapted)            │  │
│  │  • mesh utilities (adapted from baramMesh)                │  │
│  │  • schema / models (dataclasses replacing Qt signals)     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                     │ optional                                   │
│  ┌──────────────────┴────────────────────────────────────────┐  │
│  │  VTK.js / Three.js  (3D rendering in browser)             │  │
│  │  • replaces desktop VTK actor pipeline                    │  │
│  │  • server exports mesh as glTF / VTP via REST             │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Current vs Target — mapping key decisions

| Current (PySide6 Desktop) | Target (Flask + Vanilla JS) | Migration Notes |
|---|---|---|
| **PySide6 / Qt 6 widgets** | Vanilla HTML + CSS + JS | Replace .ui → HTML panels; signals/slots → fetch + DOM events |
| **Qt Designer .ui files** (564 files) | `index.html` `<style>` + `<div>` sections | Each .ui page → a `<div class="tab-content">` panel |
| **qasync (asyncio + Qt)** | `async/await` on server; `fetch()` on client | Long ops become REST or WebSocket endpoints |
| **CoreDB (lxml + XSD)** | **Reuse as-is** on server | Expose via REST: `GET/PUT /api/coredb/<xpath>` |
| **FileDB (h5py + HDF5)** | **Reuse as-is** on server | Files stay server-side; browser gets JSON summaries |
| **VTK 3D rendering** | VTK.js or Three.js in browser | Server exports glTF/VTP; JS renders interactively |
| **pyqtgraph / matplotlib** | Chart.js or Plotly.js (zero-build CDN) | Server sends JSON arrays; JS charts them |
| **PySide6-QtAds docking** | CSS grid panels with drag-resize | Simpler but covers console + chart + 3D view panels |
| **OpenFOAM solver launcher** | **Reuse as-is** on server | `/api/solver/start`, `/api/solver/stop`, WebSocket log tail |
| **gmsh mesh generation** | **Reuse as-is** on server | `/api/mesh/generate` → progress via WebSocket |
| **psutil process monitor** | **Reuse as-is** on server | `/api/solver/status` polling or WebSocket push |
| **Navigator QTreeWidget** | Sidebar `<ul>` tree (CSS + JS) | Same hierarchy: Setup / Solution / Results |
| **Module-level singletons** | Flask `g` / app-context globals | Same pattern, scoped to Flask app context |
| **XPath read/write** | REST JSON: `{ xpath, value }` | Thin REST wrapper around `CoreDBWriter` |

---

## 2  File Structure (Target)

```
baram-web/
├── run.py                     # CLI entry (argparse → app.run)
├── server.py                  # Flask app: routes + JSON + WebSocket
├── web/
│   ├── index.html             # SPA shell: all HTML + all CSS
│   ├── main.js                # All frontend logic (vanilla ES2020+)
│   ├── vtk-lite.js            # Optional: VTK.js bundle for 3D (CDN fallback)
│   └── chart-helper.js        # Optional: Chart.js / Plotly wrapper
│
│── coredb/                    # ⟵ REUSED from baramFlow/coredb/
│   ├── __init__.py
│   ├── coredb.py              # XML + XSD config database
│   ├── coredb_reader.py
│   ├── coredb_writer.py
│   ├── project.py
│   ├── filedb.py              # HDF5 persistence
│   └── schema/                # XSD schema files
│
│── openfoam/                  # ⟵ REUSED from baramFlow/openfoam/
│   ├── case_generator.py
│   ├── solver.py
│   ├── file_system.py
│   ├── parallel.py
│   ├── boundary_conditions/
│   ├── constant/
│   └── system/
│
│── backends/                  # ⟵ REUSED from baramFlow/backends/
│   ├── openfoam_backend.py
│   └── external_backend.py
│
│── mesh/                      # ⟵ Adapted from baramMesh
│   ├── mesh_generator.py
│   ├── mesh_quality.py
│   └── stl_parser.py
│
│── domain/                    # NEW: web-specific domain helpers
│   ├── project_manager.py     # Project lifecycle (replaces App singleton)
│   ├── solver_monitor.py      # Process monitor (replaces CaseManager)
│   ├── cfd_schema.py          # Dataclass summaries for JSON serialisation
│   └── export_vtk.py          # VTK → glTF/VTP export for browser 3D
│
├── tests/
│   ├── conftest.py            # Flask test client + temp project dirs
│   ├── test_api.py            # Integration: all REST endpoints
│   ├── test_coredb_api.py     # CoreDB read/write via REST
│   ├── test_solver_api.py     # Solver lifecycle via REST
│   └── test_mesh_api.py       # Mesh generation via REST
│
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── start.bat                  # Windows quick-launch
└── VERSION
```

---

## 3  Backend Pattern (server.py)

### 3.1  Flask app setup

```python
import pathlib, uuid, json, threading
from flask import Flask, jsonify, request, send_from_directory
from flask_sock import Sock                       # WebSocket for log streaming

_HERE = pathlib.Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(_HERE / "web"),
    static_url_path="",
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024   # CFD meshes can be large
sock = Sock(app)

# ── Project state (replaces App singleton) ──
from domain.project_manager import ProjectManager
_pm = ProjectManager()

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")
```

### 3.2  REST endpoint patterns — CoreDB bridge

The CoreDB stays unchanged. The server wraps XPath read/write in JSON:

```python
# ── CoreDB read ──
@app.route("/api/coredb")
def coredb_read():
    """Read one or more XPath values from CoreDB."""
    xpaths = request.args.getlist("xpath")          # ?xpath=...&xpath=...
    db = _pm.current_project.coredb
    result = {xp: db.getValue(xp) for xp in xpaths}
    return jsonify(result)

# ── CoreDB write (transactional) ──
@app.route("/api/coredb", methods=["PUT"])
def coredb_write():
    """Write values to CoreDB. Body: { "writes": [ {xpath, value}, ... ] }"""
    body = request.get_json(force=True)
    writer = CoreDBWriter()
    for w in body["writes"]:
        writer.append(w["xpath"], w["value"], w.get("label", ""))
    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation errors"}), 422
    return jsonify({"success": True})
```

### 3.3  REST endpoint patterns — Navigator pages

Each Qt "ContentPage" becomes a REST resource returning its current state and accepting updates:

```python
# ── General settings page ──
@app.route("/api/pages/general")
def page_general():
    db = _pm.coredb
    return jsonify({
        "gravity":     [db.getValue(".//gravity/x"), db.getValue(".//gravity/y"), db.getValue(".//gravity/z")],
        "operating_pressure": db.getValue(".//operatingConditions/pressure"),
        "solver_type": db.getValue(".//general/solverType"),
        "time_transient": db.getValue(".//general/timeTransient") == "true",
    })

@app.route("/api/pages/general", methods=["PUT"])
def page_general_save():
    body = request.get_json(force=True)
    writer = CoreDBWriter()
    writer.append(".//gravity/x", str(body["gravity"][0]), "Gravity X")
    writer.append(".//gravity/y", str(body["gravity"][1]), "Gravity Y")
    writer.append(".//gravity/z", str(body["gravity"][2]), "Gravity Z")
    # ... etc
    errors = writer.write()
    if errors:
        return jsonify({"error": f"{errors} validation errors"}), 422
    return jsonify({"success": True})

# ── Boundary conditions ──
@app.route("/api/boundary-conditions")
def list_boundary_conditions():
    """Returns list of BCs with type, region, name."""
    ...

@app.route("/api/boundary-conditions/<bc_id>", methods=["PUT"])
def update_boundary_condition(bc_id):
    """Update a single BC — mirrors WallDialog / VelocityInletDialog etc."""
    ...
```

### 3.4  REST endpoint patterns — Solver lifecycle

```python
# ── Solver ──
@app.route("/api/solver/initialize", methods=["POST"])
def solver_initialize():
    """Generate OpenFOAM case + initialise fields."""
    _pm.case_manager.generateCase()
    return jsonify({"success": True})

@app.route("/api/solver/start", methods=["POST"])
def solver_start():
    """Launch solver process (OpenFOAM or external)."""
    _pm.case_manager.startSolver()
    return jsonify({"status": "running"})

@app.route("/api/solver/stop", methods=["POST"])
def solver_stop():
    _pm.case_manager.stopSolver()
    return jsonify({"status": "stopped"})

@app.route("/api/solver/status")
def solver_status():
    return jsonify(_pm.case_manager.getStatus())

# ── WebSocket for live solver logs ──
@sock.route("/ws/solver-log")
def solver_log_ws(ws):
    """Stream solver stdout/stderr to browser in real-time."""
    while True:
        line = _pm.case_manager.readNextLogLine()  # blocking
        if line is None:
            break
        ws.send(json.dumps({"type": "log", "text": line}))
```

### 3.5  REST endpoint patterns — Mesh

```python
@app.route("/api/mesh/upload", methods=["POST"])
def mesh_upload():
    """Upload STL/STEP/IGES geometry file."""
    f = request.files["file"]
    job_id = uuid.uuid4().hex[:12]
    path = _UPLOAD_DIR / f"{job_id}_{f.filename}"
    f.save(str(path))
    return jsonify({"job_id": job_id, "filename": f.filename})

@app.route("/api/mesh/generate", methods=["POST"])
def mesh_generate():
    """Start mesh generation (snappyHexMesh). Returns job_id for progress."""
    ...

@app.route("/api/mesh/export-gltf/<job_id>")
def mesh_export_gltf(job_id):
    """Export mesh as glTF for browser 3D rendering."""
    ...

@app.route("/api/mesh/quality/<job_id>")
def mesh_quality(job_id):
    """Return mesh quality metrics (cell count, skewness, etc.)."""
    ...
```

### 3.6  REST endpoint patterns — 3D view data

```python
@app.route("/api/scene/mesh-data")
def scene_mesh_data():
    """Return current mesh as glTF binary for VTK.js / Three.js."""
    ...

@app.route("/api/scene/field-data")
def scene_field_data():
    """Return scalar/vector field data for colour mapping in 3D view."""
    field = request.args.get("field", "p")   # p, U, T, k, epsilon ...
    timestep = request.args.get("time", "latest")
    ...
```

### 3.7  Convention checklist

- [x] All responses are `jsonify(...)` — never return HTML from `/api/*`
- [x] Errors return `{"error": "message"}` with 4xx/5xx status
- [x] CoreDB accessed only via `ProjectManager` — never raw globals
- [x] Solver log streaming uses WebSocket (not polling)
- [x] Upload dir created with `mkdir(exist_ok=True)` at module level
- [x] Domain modules (coredb, openfoam, mesh) imported unchanged from Baram
- [x] Long operations (mesh gen, solve) are async with progress reporting

---

## 4  Frontend Pattern (index.html + main.js)

### 4.1  HTML structure — mirrors Baram's Navigator + Dock layout

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BaramFlow Web</title>
  <style>
    /* ─── All CSS lives here (Catppuccin Mocha) ─── */
  </style>
</head>
<body>

  <!-- Header bar (project name + status) -->
  <div class="header">
    <span class="logo">🌊 BaramFlow</span>
    <span id="projectName">No project</span>
    <span id="solverStatus" class="status-badge">IDLE</span>
  </div>

  <!-- Top-level app tabs (mirrors BaramFlow / BaramMesh / BaramEditor) -->
  <div class="app-tabs">
    <div class="app-tab active" data-app-tab="flow">Flow Setup</div>
    <div class="app-tab" data-app-tab="mesh">Mesh</div>
    <div class="app-tab" data-app-tab="results">Results</div>
  </div>

  <!-- ═══ Tab: Flow Setup ═══ -->
  <div class="tab-content active" data-app-content="flow">
    <div class="main">

      <!-- Left sidebar: Navigator tree (mirrors QTreeWidget) -->
      <div class="sidebar-panel">
        <div class="nav-tree" id="navTree">
          <div class="nav-section">Setup</div>
          <div class="nav-item active" data-page="general">General</div>
          <div class="nav-item" data-page="models">Models</div>
          <div class="nav-item" data-page="materials">Materials</div>
          <div class="nav-item" data-page="cell-zones">Cell Zone Conditions</div>
          <div class="nav-item" data-page="boundary-conditions">Boundary Conditions</div>
          <div class="nav-section">Solution</div>
          <div class="nav-item" data-page="numerical">Numerical Conditions</div>
          <div class="nav-item" data-page="monitors">Monitors</div>
          <div class="nav-item" data-page="initialization">Initialization</div>
          <div class="nav-item" data-page="run-conditions">Run Conditions</div>
          <div class="nav-item" data-page="run">Run</div>
        </div>
      </div>

      <!-- Center: Page content (replaces QStackedWidget) -->
      <div class="center-area" id="pageContent">
        <!-- Dynamically filled by JS based on nav selection -->
      </div>

      <!-- Right: 3D view + dock panels (replaces QtAds docking) -->
      <div class="detail-panel">
        <div class="dock-tabs">
          <span class="dock-tab active" data-dock="3d">3D View</span>
          <span class="dock-tab" data-dock="console">Console</span>
          <span class="dock-tab" data-dock="chart">Residuals</span>
          <span class="dock-tab" data-dock="monitor">Monitor</span>
        </div>
        <div class="dock-content active" data-dock-content="3d">
          <canvas id="renderCanvas"></canvas>
        </div>
        <div class="dock-content" data-dock-content="console">
          <pre id="consoleLog"></pre>
        </div>
        <div class="dock-content" data-dock-content="chart">
          <canvas id="residualChart"></canvas>
        </div>
        <div class="dock-content" data-dock-content="monitor">
          <div id="monitorPanel"></div>
        </div>
      </div>

    </div>
  </div>

  <!-- ═══ Tab: Mesh ═══ -->
  <div class="tab-content" data-app-content="mesh">
    <div class="main">
      <div class="sidebar-panel">
        <div class="nav-tree" id="meshNavTree">
          <div class="nav-item active" data-page="geometry">Geometry</div>
          <div class="nav-item" data-page="region">Region</div>
          <div class="nav-item" data-page="base-grid">Base Grid</div>
          <div class="nav-item" data-page="castellation">Castellation</div>
          <div class="nav-item" data-page="snap">Snap</div>
          <div class="nav-item" data-page="boundary-layer">Boundary Layer</div>
          <div class="nav-item" data-page="mesh-export">Export</div>
        </div>
      </div>
      <div class="center-area" id="meshPageContent"></div>
      <div class="detail-panel">
        <canvas id="meshRenderCanvas"></canvas>
      </div>
    </div>
  </div>

  <!-- ═══ Tab: Results ═══ -->
  <div class="tab-content" data-app-content="results">
    <div class="main">
      <div class="sidebar-panel" id="resultsSidebar"></div>
      <div class="center-area" id="resultsContent"></div>
      <div class="detail-panel">
        <canvas id="resultsRenderCanvas"></canvas>
      </div>
    </div>
  </div>

  <!-- Modals (hidden by default) -->
  <div class="modal-backdrop" id="projectModal">
    <div class="modal">
      <div class="modal-header">Open / New Project</div>
      <div class="modal-body" id="projectModalBody"></div>
      <div class="modal-footer">
        <button class="btn" onclick="closeModal('projectModal')">Cancel</button>
        <button class="btn btn-accent" id="projectOpenBtn">Open</button>
      </div>
    </div>
  </div>

  <div class="modal-backdrop" id="bcEditModal">
    <div class="modal modal-wide">
      <div class="modal-header">Edit Boundary Condition</div>
      <div class="modal-body" id="bcEditBody"></div>
      <div class="modal-footer">
        <button class="btn" onclick="closeModal('bcEditModal')">Cancel</button>
        <button class="btn btn-accent" id="bcSaveBtn">Save</button>
      </div>
    </div>
  </div>

  <!-- Toast notification -->
  <div class="toast" id="toast"></div>

  <!-- Optional CDN libs (no npm, no build) -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <script src="main.js"></script>
</body>
</html>
```

### 4.2  CSS theme (Catppuccin Mocha)

```css
:root {
  --bg:       #1e1e2e;
  --bg2:      #252538;
  --bg3:      #2d2d44;
  --fg:       #cdd6f4;
  --fg-dim:   #6c7086;
  --accent:   #89b4fa;    /* blue — primary actions */
  --green:    #a6e3a1;    /* solver running / success */
  --red:      #f38ba8;    /* solver error / stop */
  --yellow:   #f9e2af;    /* warnings */
  --peach:    #fab387;    /* mesh quality caution */
  --mauve:    #cba6f7;    /* monitor highlights */
  --pink:     #f5c2e7;
  --teal:     #94e2d5;    /* 3D wireframe accent */
  --border:   #45475a;
  --radius:   6px;
}
body {
  font-family: 'Segoe UI', Consolas, monospace;
  background: var(--bg);
  color: var(--fg);
  display: flex; flex-direction: column; height: 100vh; overflow: hidden;
}
```

### 4.3  JavaScript architecture

Each Baram "ContentPage" (`.ui` + `.py`) becomes a JS module with a **3-letter prefix**:

```
main.js  (single file, ~4000–6000 lines, "use strict")
│
├── State variables
│   currentProject, currentPage, solverStatus, coredbCache, ...
│
├── DOM helpers
│   const $ = sel => document.querySelector(sel);
│   const $$ = sel => document.querySelectorAll(sel);
│   function toast(msg) { ... }
│   function showModal(id) / closeModal(id)
│
├── Module: Project Manager  (prefixed prj*)
│   prjInit(), prjOpenDialog(), prjNew(), prjOpen(path),
│   prjSave(), prjRecent(), prjExport()
│
├── Module: CoreDB Bridge  (prefixed cdb*)
│   cdbRead(xpaths) → fetch GET /api/coredb?xpath=...
│   cdbWrite(writes) → fetch PUT /api/coredb
│   cdbCache, cdbInvalidate()
│
├── Module: Navigator  (prefixed nav*)
│   navInit(), navSelect(page), navBuildTree(),
│   navRenderPage(page) → dispatches to page module
│
├── Module: General Page  (prefixed gen*)           ← replaces GeneralPage(.ui)
│   genInit(), genLoad(), genRender(), genSave()
│
├── Module: Models Page  (prefixed mdl*)            ← replaces ModelsPage(.ui)
│   mdlInit(), mdlLoad(), mdlRender(), mdlSave()
│   mdlToggleTurbulence(), mdlToggleEnergy()
│
├── Module: Materials Page  (prefixed mat*)         ← replaces MaterialsPage(.ui)
│   matInit(), matLoad(), matRenderList(), matEdit(id), matSave()
│
├── Module: Boundary Conditions  (prefixed bcs*)    ← replaces BC dialogs (31 types)
│   bcsInit(), bcsLoadList(), bcsRenderList(),
│   bcsEdit(id) → opens bcEditModal → dispatches to type-specific renderer
│   bcsRenderWall(), bcsRenderVelocityInlet(), bcsRenderPressureOutlet(), ...
│   bcsSave()
│
├── Module: Cell Zones  (prefixed czn*)
│   cznInit(), cznLoad(), cznRender(), cznSave()
│
├── Module: Numerical Conditions  (prefixed num*)
│   numInit(), numLoad(), numRender(), numSave()
│
├── Module: Monitors  (prefixed mon*)
│   monInit(), monLoadList(), monAdd(), monEdit(), monDelete(),
│   monRenderDetail()
│
├── Module: Initialization  (prefixed ini*)
│   iniInit(), iniLoad(), iniRender(), iniSave(),
│   iniInitializeFields() → POST /api/solver/initialize
│
├── Module: Run Conditions  (prefixed rco*)
│   rcoInit(), rcoLoad(), rcoRender(), rcoSave()
│
├── Module: Solver Run  (prefixed slv*)             ← replaces CaseManager UI
│   slvInit(), slvStart(), slvStop(), slvPause(),
│   slvConnectWebSocket() → /ws/solver-log → updates console + chart
│   slvUpdateStatus(), slvParseResidual(line) → Chart.js update
│
├── Module: Mesh  (prefixed msh*)                   ← replaces BaramMesh views
│   mshInit(), mshUploadGeometry(), mshSetBaseGrid(),
│   mshConfigCastellation(), mshConfigSnap(), mshConfigBoundaryLayer(),
│   mshGenerate() → POST /api/mesh/generate + WebSocket progress
│   mshExport()
│
├── Module: 3D Viewer  (prefixed v3d*)              ← replaces VTK rendering
│   v3dInit(canvasId), v3dLoadMesh(url),
│   v3dSetField(field, timestep), v3dSetColormap(),
│   v3dRotate(), v3dZoom(), v3dPan(),
│   v3dToggleWireframe(), v3dToggleAxes()
│   (uses Three.js or VTK.js loaded from CDN)
│
├── Module: Results  (prefixed res*)
│   resInit(), resLoadTimesteps(), resSelectTimestep(),
│   resRenderFieldSelector(), resExportCSV(), resScreenshot()
│
├── Module: Charts  (prefixed cht*)                 ← replaces pyqtgraph
│   chtInit(canvasId), chtAddSeries(name, color),
│   chtAppendPoint(series, x, y), chtClear(),
│   chtAutoScale()
│
└── DOMContentLoaded
    ├── prjInit() → show project open modal
    ├── navInit() → wire sidebar tree clicks
    ├── wire app-tab / dock-tab switching
    ├── wire keyboard shortcuts (Escape, Ctrl+S, Ctrl+R)
    └── slvInit() → setup solver status polling
```

### 4.4  Page render pattern (replaces .ui + ContentPage)

Every navigation page follows the same lifecycle:

```javascript
// ── General Page (gen*) — replaces baramFlow/view/setup/general/general_page.py ──

let genData = {};

async function genLoad() {
  genData = await (await fetch("/api/pages/general")).json();
}

function genRender() {
  const html = `
    <div class="page-header">General</div>
    <div class="form-section">
      <label>Solver Type</label>
      <select id="genSolverType">
        <option value="pressureBased" ${genData.solver_type === 'pressureBased' ? 'selected' : ''}>Pressure-Based</option>
        <option value="densityBased" ${genData.solver_type === 'densityBased' ? 'selected' : ''}>Density-Based</option>
      </select>
    </div>
    <div class="form-section">
      <label>Time</label>
      <div class="radio-group">
        <label><input type="radio" name="genTime" value="false" ${!genData.time_transient ? 'checked' : ''}> Steady</label>
        <label><input type="radio" name="genTime" value="true" ${genData.time_transient ? 'checked' : ''}> Transient</label>
      </div>
    </div>
    <div class="form-section">
      <label>Gravity (m/s²)</label>
      <div class="input-row">
        <input type="number" id="genGravX" value="${genData.gravity[0]}" step="any">
        <input type="number" id="genGravY" value="${genData.gravity[1]}" step="any">
        <input type="number" id="genGravZ" value="${genData.gravity[2]}" step="any">
      </div>
    </div>
    <div class="form-section">
      <label>Operating Pressure (Pa)</label>
      <input type="number" id="genOpPressure" value="${genData.operating_pressure}" step="any">
    </div>
    <button class="btn btn-accent" onclick="genSave()">Save</button>
  `;
  $("#pageContent").innerHTML = html;
}

async function genSave() {
  const body = {
    solver_type: $("#genSolverType").value,
    time_transient: document.querySelector('input[name="genTime"]:checked').value === "true",
    gravity: [
      parseFloat($("#genGravX").value),
      parseFloat($("#genGravY").value),
      parseFloat($("#genGravZ").value),
    ],
    operating_pressure: parseFloat($("#genOpPressure").value),
  };
  const r = await fetch("/api/pages/general", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const d = await r.json();
  if (d.error) toast("⚠️ " + d.error);
  else toast("✅ General settings saved");
}
```

### 4.5  Solver log WebSocket pattern (replaces qasync log monitor)

```javascript
let slvSocket = null;

function slvConnectWebSocket() {
  slvSocket = new WebSocket(`ws://${location.host}/ws/solver-log`);
  slvSocket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "log") {
      // Append to console panel
      const pre = $("#consoleLog");
      pre.textContent += msg.text + "\n";
      pre.scrollTop = pre.scrollHeight;
      // Parse residual data for chart
      const residual = slvParseResidual(msg.text);
      if (residual) {
        chtAppendPoint(residual.field, residual.iteration, residual.value);
      }
    }
  };
  slvSocket.onclose = () => slvUpdateStatus("disconnected");
}
```

### 4.6  Convention checklist

- [x] Each UI "module" uses a **3-letter prefix** for all its functions and state vars
- [x] All API calls use `fetch()` with `async/await` — no callbacks, no Axios
- [x] DOM is built via **innerHTML string templates** — no virtual DOM
- [x] 3D rendering via Three.js or VTK.js loaded from CDN — no npm
- [x] Charts via Chart.js from CDN — replaces pyqtgraph
- [x] Tab switching uses `data-app-tab` / `data-app-content` attributes
- [x] Dock-panel switching uses `data-dock` / `data-dock-content` attributes
- [x] Navigator tree uses `data-page` attributes → dispatches to `*Load()` + `*Render()`
- [x] Modals use `.modal-backdrop.show` toggle
- [x] Toast notifications via shared `toast(msg)` function
- [x] Solver log streaming via WebSocket (not polling)
- [x] Keyboard shortcuts: Escape (close modal), Ctrl+S (save page), Ctrl+R (run solver)
- [x] No localStorage — state from server via REST on each page load

---

## 5  Domain Module Patterns

### 5.1  Reusing CoreDB as-is

The CoreDB module (`coredb/`) is **the most critical reuse target**. It contains:
- XML tree with XSD validation for all CFD parameters
- Typed readers (`GeneralDB`, `TurbulenceModelDB`, `MaterialDB`, etc.)
- Transactional `CoreDBWriter` with backup/rollback
- `FileDB` for HDF5 binary persistence

**No changes needed** — just import and expose via REST.

### 5.2  Reusing OpenFOAM backend as-is

The `openfoam/` module generates all case files. It reads from CoreDB and writes OpenFOAM dictionaries:
- `CaseGenerator` → `constant/`, `system/`, `0/`
- `Solver` → finds executable, sets env vars, launches via MPI
- BC generators → one per field type (U, p, T, k, ε, ω, nut, …)

**No changes needed** — call from Flask route handlers.

### 5.3  Replacing Qt signals with REST/WebSocket events

| Current Qt Pattern | Web Replacement |
|---|---|
| `project.projectOpened.emit()` | `POST /api/project/open` → returns project summary JSON |
| `caseManager.statusChanged.emit(status)` | `GET /api/solver/status` or WebSocket push |
| `coredb.valueChanged.emit(xpath)` | Client polls after write, or WebSocket push `{"type":"coredb-changed","xpath":...}` |
| `QFileDialog.getOpenFileName()` | `<input type="file">` + `POST /api/mesh/upload` |
| `QMessageBox.warning()` | `toast("⚠️ ...")` in JS |
| `QProgressDialog` | `<div class="progress-bar">` updated via WebSocket |

### 5.4  ProjectManager (replaces App singleton)

```python
# domain/project_manager.py
from dataclasses import dataclass, field
from pathlib import Path
from coredb.coredb import CoreDB
from coredb.filedb import FileDB
from openfoam.case_generator import CaseGenerator

@dataclass
class Project:
    path: Path
    name: str
    coredb: CoreDB
    filedb: FileDB

class ProjectManager:
    """Replaces the module-level App() singleton from PySide6."""

    def __init__(self):
        self._current: Project | None = None
        self._recent: list[str] = []

    @property
    def current_project(self) -> Project:
        if not self._current:
            raise RuntimeError("No project open")
        return self._current

    @property
    def coredb(self) -> CoreDB:
        return self.current_project.coredb

    def open(self, path: str) -> Project:
        p = Path(path)
        coredb = CoreDB.load(p / "case.xml")
        filedb = FileDB(p / "files.h5")
        self._current = Project(path=p, name=p.name, coredb=coredb, filedb=filedb)
        return self._current

    def create(self, path: str, template: str = "default") -> Project:
        ...

    def close(self):
        self._current = None

    def list_recent(self) -> list[str]:
        return self._recent
```

### 5.5  SolverMonitor (replaces CaseManager signals)

```python
# domain/solver_monitor.py
import subprocess, threading, queue
from dataclasses import dataclass
from enum import Enum

class SolverState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"

@dataclass
class SolverStatus:
    state: SolverState
    iteration: int = 0
    elapsed_s: float = 0.0
    residuals: dict[str, float] = None   # field → last residual

class SolverMonitor:
    """Replaces CaseManager + Qt signal-based monitoring."""

    def __init__(self):
        self.status = SolverStatus(state=SolverState.IDLE)
        self._process: subprocess.Popen | None = None
        self._log_queue: queue.Queue = queue.Queue()

    def start(self, case_dir: str, solver_cmd: list[str]):
        self._process = subprocess.Popen(
            solver_cmd, cwd=case_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self.status.state = SolverState.RUNNING
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        for line in self._process.stdout:
            self._log_queue.put(line.rstrip())
        self._process.wait()
        self.status.state = (
            SolverState.FINISHED if self._process.returncode == 0
            else SolverState.ERROR
        )

    def read_next_log_line(self, timeout=1.0) -> str | None:
        try:
            return self._log_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        if self._process:
            self._process.terminate()
            self.status.state = SolverState.IDLE

    def get_status(self) -> dict:
        return {
            "state": self.status.state.value,
            "iteration": self.status.iteration,
            "elapsed_s": self.status.elapsed_s,
        }
```

---

## 6  REST API Reference (Full)

### Project

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve index.html |
| GET | `/api/project` | Current project info |
| POST | `/api/project/open` | Open existing project |
| POST | `/api/project/new` | Create new project |
| POST | `/api/project/save` | Save current project |
| GET | `/api/project/recent` | List recent projects |

### CoreDB (generic XPath bridge)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/coredb?xpath=...` | Read XPath values |
| PUT | `/api/coredb` | Write XPath values (transactional) |

### Pages (Navigator content — typed endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/pages/general` | General settings (solver type, gravity, etc.) |
| PUT | `/api/pages/general` | Save general settings |
| GET | `/api/pages/models` | Turbulence, energy, species models |
| PUT | `/api/pages/models` | Save model settings |
| GET | `/api/pages/materials` | Material list |
| PUT | `/api/pages/materials/<id>` | Update material properties |
| GET | `/api/pages/cell-zones` | Cell zone conditions |
| PUT | `/api/pages/cell-zones/<id>` | Update cell zone |
| GET | `/api/pages/numerical` | Numerical conditions |
| PUT | `/api/pages/numerical` | Save numerical conditions |
| GET | `/api/pages/initialization` | Initialization settings |
| PUT | `/api/pages/initialization` | Save initialization settings |
| GET | `/api/pages/run-conditions` | Run conditions (timestep, end time) |
| PUT | `/api/pages/run-conditions` | Save run conditions |

### Boundary Conditions

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/boundary-conditions` | List all BCs |
| GET | `/api/boundary-conditions/<id>` | Get BC detail (type-specific fields) |
| PUT | `/api/boundary-conditions/<id>` | Update BC |
| POST | `/api/boundary-conditions` | Add new BC |
| DELETE | `/api/boundary-conditions/<id>` | Remove BC |

### Monitors

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/monitors` | List monitors |
| POST | `/api/monitors` | Add monitor point/surface |
| PUT | `/api/monitors/<id>` | Update monitor |
| DELETE | `/api/monitors/<id>` | Remove monitor |
| GET | `/api/monitors/<id>/data` | Get monitor time-series data |

### Solver

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/solver/initialize` | Generate case + initialize fields |
| POST | `/api/solver/start` | Launch solver |
| POST | `/api/solver/stop` | Stop solver |
| GET | `/api/solver/status` | Current solver state + iteration |
| WS | `/ws/solver-log` | Live log stream (WebSocket) |
| GET | `/api/solver/residuals` | Residual history (for chart reload) |

### Mesh

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/mesh/upload` | Upload geometry (STL/STEP/IGES) |
| GET | `/api/mesh/geometries` | List uploaded geometries |
| POST | `/api/mesh/generate` | Start mesh generation |
| GET | `/api/mesh/status` | Mesh gen progress |
| WS | `/ws/mesh-log` | Live mesh gen log (WebSocket) |
| GET | `/api/mesh/quality` | Quality metrics |
| GET | `/api/mesh/export-gltf` | Export mesh as glTF for 3D view |

### 3D Scene

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/scene/mesh-data` | Current mesh as glTF binary |
| GET | `/api/scene/field-data?field=p&time=latest` | Scalar/vector field for colour map |
| GET | `/api/scene/timesteps` | Available timesteps |

### Results

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/results/fields` | Available result fields |
| GET | `/api/results/export-csv?fields=p,U&time=100` | Export field data as CSV |
| GET | `/api/results/screenshot` | Server-side render screenshot |

---

## 7  Deployment & Launch

### Local (Windows)

```bat
@echo off
set VENV=.\venv\Scripts\python.exe
%VENV% run.py --port 5100 --open
```

### Local (any OS)

```bash
python run.py --port 5100 --open    # --debug for hot-reload
```

### Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0  # VTK/gmsh deps
WORKDIR /app
COPY . /app/
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5100
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "5100"]
```

### run.py pattern

```python
def main():
    parser = argparse.ArgumentParser(description="BaramFlow Web")
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--project", type=str, default=None,
                        help="Auto-open project directory")
    args = parser.parse_args()

    if args.open:
        import webbrowser
        webbrowser.open(f"http://{args.host}:{args.port}")

    from server import app
    app.run(host=args.host, port=args.port, debug=args.debug)
```

---

## 8  Testing

```
tests/
├── conftest.py                # Flask test client + temp CoreDB fixtures
├── test_api_project.py        # Project open/create/save endpoints
├── test_api_coredb.py         # CoreDB XPath read/write via REST
├── test_api_pages.py          # Page GET/PUT for general, models, etc.
├── test_api_boundary.py       # Boundary condition CRUD
├── test_api_solver.py         # Solver lifecycle: init → start → status → stop
├── test_api_mesh.py           # Mesh upload → generate → quality → export
└── test_domain_solver.py      # Unit test SolverMonitor (no HTTP)
```

```python
# conftest.py
import pytest, tempfile, shutil
from pathlib import Path
from server import app as flask_app

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c

@pytest.fixture
def sample_project(tmp_path):
    """Create a minimal CoreDB project for testing."""
    from coredb.coredb import CoreDB
    db = CoreDB.createDefault()
    db.save(tmp_path / "case.xml")
    return str(tmp_path)

# test_api_coredb.py
def test_coredb_read_gravity(client, sample_project):
    client.post("/api/project/open", json={"path": sample_project})
    r = client.get("/api/coredb?xpath=.//gravity/x&xpath=.//gravity/y&xpath=.//gravity/z")
    assert r.status_code == 200
    data = r.get_json()
    assert ".//gravity/x" in data

def test_coredb_write_validates(client, sample_project):
    client.post("/api/project/open", json={"path": sample_project})
    r = client.put("/api/coredb", json={
        "writes": [{"xpath": ".//gravity/x", "value": "not_a_number"}]
    })
    assert r.status_code == 422
```

---

## 9  Migration Mapping — .ui Widgets → HTML Components

Each PySide6 widget type maps to a simple HTML pattern:

| Qt Widget | HTML Replacement | JS Interaction |
|---|---|---|
| `QLineEdit` | `<input type="text">` | `.value` |
| `QDoubleSpinBox` | `<input type="number" step="any">` | `.value` (parseFloat) |
| `QSpinBox` | `<input type="number" step="1">` | `.value` (parseInt) |
| `QComboBox` | `<select><option>...</select>` | `.value` / `.selectedIndex` |
| `QCheckBox` | `<input type="checkbox">` | `.checked` |
| `QRadioButton` (in group) | `<input type="radio" name="group">` | `:checked` selector |
| `QLabel` | `<label>` or `<span>` | `.textContent` |
| `QPushButton` | `<button class="btn">` | `onclick` handler |
| `QTabWidget` | `data-tab` / `data-tab-content` divs | CSS `.active` toggle |
| `QTreeWidget` | `<ul class="tree">` with nested `<li>` | click → `navSelect()` |
| `QTableWidget` | `<table>` with `<thead>/<tbody>` | innerHTML rebuild |
| `QListWidget` | `<div class="list">` with items | innerHTML rebuild |
| `QGroupBox` | `<fieldset>` or `<div class="form-section">` | — |
| `QStackedWidget` | Multiple `<div>` with `.active` toggle | CSS display:none/block |
| `QProgressBar` | `<div class="progress"><div class="bar">` | `.style.width` |
| `QFileDialog` | `<input type="file">` + FormData upload | fetch + FormData |
| `QMessageBox` | `toast(msg)` or modal | — |
| `QSplitter` | CSS `resize: horizontal` or drag divider | mousedown/mousemove |
| `QDockWidget` | dock-tab panels (see §4.1) | CSS `.active` toggle |
| VTK `QVTKRenderWindow` | `<canvas>` + Three.js / VTK.js | JS 3D library |
| pyqtgraph `PlotWidget` | Chart.js `<canvas>` | Chart.js API |

---

## 10  Migration Priority — Phased Approach

### Phase 1: Core skeleton (Week 1)
- [ ] `run.py` + `server.py` + `web/index.html` + `web/main.js`
- [ ] Project open/create/save endpoints
- [ ] CoreDB bridge (generic XPath read/write)
- [ ] Navigator sidebar with tab switching
- [ ] General page (load/render/save round-trip)

### Phase 2: Setup pages (Week 2–3)
- [ ] Models page (turbulence, energy, species toggles)
- [ ] Materials page (list + edit modal)
- [ ] Cell zone conditions page
- [ ] Boundary conditions page (list + type-specific edit modals)
- [ ] Numerical conditions page

### Phase 3: Solver lifecycle (Week 3–4)
- [ ] Initialization page + `/api/solver/initialize`
- [ ] Run conditions page
- [ ] Solver start/stop/status
- [ ] WebSocket log streaming → console panel
- [ ] Residual chart (Chart.js) parsing solver output

### Phase 4: Mesh (Week 4–5)
- [ ] Geometry upload (STL/STEP)
- [ ] Mesh parameter pages (base grid, castellation, snap, boundary layer)
- [ ] Mesh generation + WebSocket progress
- [ ] Mesh quality metrics

### Phase 5: 3D visualization (Week 5–6)
- [ ] Server-side VTK → glTF export
- [ ] Three.js or VTK.js canvas setup
- [ ] Mesh surface rendering with orbit controls
- [ ] Scalar field colour mapping
- [ ] Timestep slider

### Phase 6: Results & polish (Week 6–7)
- [ ] Results tab: field selector + timestep browser
- [ ] Monitor data charts
- [ ] CSV export
- [ ] Keyboard shortcuts, drag-drop, responsive layout

---

## 11  Dependencies

### Python (requirements.txt)

```
flask>=3.0.0
flask-sock>=0.7.0          # WebSocket support for log streaming
werkzeug>=3.0.0

# ── Reused from Baram (server-side only) ──
lxml>=5.0.0                # CoreDB XML
xmlschema>=3.0.0           # CoreDB XSD validation
h5py>=3.10.0               # FileDB HDF5 persistence
numpy>=1.26.0              # Mesh data, VTK interop
PyYAML>=6.0.0              # Configuration files
psutil>=5.9.0              # Solver process monitoring
filelock>=3.12.0           # Single-instance project locking

# ── Optional (mesh, export) ──
gmsh>=4.11                 # Mesh generation
vtk>=9.3.0                 # Server-side VTK → glTF export
trimesh>=4.0.0             # STL/STEP → glTF conversion
```

### Frontend

**Zero npm dependencies.** Browser-native + CDN-only:

| Library | CDN | Purpose |
|---|---|---|
| Chart.js 4.x | `cdn.jsdelivr.net/npm/chart.js@4` | Residual plots, monitor charts |
| Three.js (r160+) | `cdn.jsdelivr.net/npm/three@0.160` | 3D mesh rendering |
| — or VTK.js | `unpkg.com/@kitware/vtk.js` | Alternative 3D (closer to desktop VTK) |
| — | `fetch()`, `WebSocket`, `FormData` | All built-in browser APIs |

---

## 12  How to Use This Template

When asking an LLM to refactor a specific Baram module:

1. **Copy sections 1–8** into the system prompt.
2. **Specify the target module**: BaramFlow, BaramMesh, or BaramEditor.
3. **Specify the pages to migrate**: list the ContentPage classes from the `view/` directory.
4. **Provide the .ui file content** for complex dialogs (so the LLM knows the exact form fields).
5. **Provide the current Python page class** (so the LLM knows XPaths and validation logic).

### Example prompt

> Refactor the **General page** from BaramFlow into the web stack described below.
>
> **Current files:**
> - `baramFlow/view/setup/general/general_page.py` (attached)
> - `baramFlow/view/setup/general/general_page.ui` (attached)
>
> **Generate:**
> 1. Flask endpoint pair: `GET /api/pages/general` and `PUT /api/pages/general`
> 2. JS module (`gen*` prefix) with `genLoad()`, `genRender()`, `genSave()`
> 3. HTML panel content (form fields matching the .ui layout)
>
> Follow the architecture from sections 1–8 of `REFACTOR_STACK_TEMPLATE.md`.

---

## 13  Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **564 .ui files is a massive migration** | Prioritize by usage frequency; start with General + Models + BCs |
| **VTK 3D rendering parity** | Accept reduced fidelity initially; Three.js covers 80% of needs |
| **OpenFOAM environment setup** | Reuse `Solver.launchEnvironment()` — it already handles cross-platform |
| **CoreDB XSD schema complexity** | Don't touch it — wrap in REST, let existing validation handle it |
| **Real-time solver logs** | WebSocket (flask-sock) is battle-tested; no polling fallback needed |
| **Large mesh file transfers** | Serve glTF as binary blob, not JSON; use streaming response |
| **Multi-user concurrency** | Out of scope for v1 — single-user like desktop app |
| **Batch runs / parametric studies** | Phase 2+; batch state already in CoreDB, just needs REST endpoints |
