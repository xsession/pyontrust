# GUI Technical Stack — Prompt Template

> Use this document as a **system prompt / context block** when asking an LLM to
> build a new tool GUI that follows the same architecture as the Zephyr Pin
> Configurator.  Copy the whole file (or the sections you need) into the prompt.

---

## 1  Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  Browser (single-page app)                               │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  index.html    │  │  main.js     │  │  CSS (inline)│  │
│  │  (layout +     │  │  (all logic, │  │  Catppuccin  │  │
│  │   structure)   │  │   no build)  │  │  dark theme) │  │
│  └───────────────┘  └──────────────┘  └──────────────┘  │
│         ▲ fetch() JSON ▲                                 │
│         │               │                                │
│ ────────┼───────────────┼─────────────── HTTP ────────── │
│         │               │                                │
│  ┌──────┴───────────────┴──────────────────────────────┐ │
│  │  Flask backend  (server.py)                         │ │
│  │  • serves static files from  web/                   │ │
│  │  • REST JSON endpoints under /api/*                 │ │
│  │  • no templates, no SSR, no WebSocket               │ │
│  │  • in-memory state dicts (jobs, caches)             │ │
│  └──────────────────┬──────────────────────────────────┘ │
│                     │ imports                             │
│  ┌──────────────────┴──────────────────────────────────┐ │
│  │  Pure-Python domain modules  (*.py in project root) │ │
│  │  • dataclass schemas                                │ │
│  │  • generators / parsers / registries                │ │
│  │  • zero web/UI coupling                             │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **No build step** (no Webpack / Vite / npm) | Instant startup, zero Node.js dependency, works on air-gapped lab PCs |
| **Vanilla JS + CSS** — no React, no framework | Minimal toolchain, full control, easy to read/audit |
| **All CSS in `<style>` inside index.html** | Single file to ship, no FOUC, easy theme tweaking |
| **Flask serving static + REST** | Simplest mature Python web stack, one `pip install flask` |
| **Domain logic in separate `.py` modules** | Testable without server, clean separation of concerns |
| **In-memory state** (dicts keyed by job ID) | No database needed; ephemeral-by-design for tool GUIs |
| **Catppuccin Mocha dark theme** | Developer-friendly, high contrast, consistent palette |

---

## 2  File Structure

```
project_root/
├── run.py                  # CLI entry point (argparse → app.run)
├── server.py               # Flask app: routes + JSON serialisation
├── web/
│   ├── index.html          # SPA shell: HTML structure + all CSS
│   └── main.js             # All frontend logic (vanilla ES2020+)
├── board_schema.py         # Dataclass schema (domain model)
├── <domain>_registry.py    # Registry pattern modules (data providers)
├── <domain>_generator.py   # Code/config generators (pure functions)
├── <domain>_parser.py      # File parsers (PDF, DTS, etc.)
├── boards/                 # Data: board definitions (Python modules)
│   ├── __init__.py         # BOARDS dict registry
│   └── <board>.py          # One file per board variant
├── tests/
│   ├── conftest.py
│   └── test_*.py           # pytest unit tests
├── requirements.txt        # Pinned deps (flask, werkzeug, etc.)
├── pyproject.toml          # PEP 621 metadata + tool configs
├── Dockerfile              # Reproducible dev/CI container
├── start.bat               # Windows quick-launch script
└── VERSION                 # Semver string
```

---

## 3  Backend Pattern (server.py)

### 3.1  Flask app setup

```python
from flask import Flask, jsonify, request, send_from_directory

_HERE = pathlib.Path(__file__).resolve().parent

app = Flask(
    __name__,
    static_folder=str(_HERE / "web"),
    static_url_path="",
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # upload limit

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")
```

### 3.2  REST endpoint patterns

Every endpoint follows the same shape:

```python
# READ — list or get
@app.route("/api/<resource>")
def list_resources():
    return jsonify([...])

@app.route("/api/<resource>/<id>")
def get_resource(id: str):
    obj = _lookup(id)
    if obj is None:
        return jsonify({"error": f"Not found: {id}"}), 404
    return jsonify(obj_to_dict(obj))

# WRITE — create / generate / compute
@app.route("/api/<resource>", methods=["POST"])
def create_resource():
    body = request.get_json(force=True)
    # validate
    # call domain module
    # return result
    return jsonify({"success": True, ...})

# FILE UPLOAD (multipart)
@app.route("/api/parse-file", methods=["POST"])
def parse_file():
    f = request.files["file"]
    job_id = uuid.uuid4().hex[:12]
    path = _UPLOAD_DIR / f"{job_id}_{secure_filename(f.filename)}"
    f.save(str(path))
    result = domain_parser.parse(str(path))
    _JOBS[job_id] = {"info": result, "path": str(path)}
    return jsonify({"job_id": job_id, "result": result_to_dict(result)})
```

### 3.3  Convention checklist

- [x] All responses are `jsonify(...)` — never return HTML from `/api/*`
- [x] Errors return `{"error": "message"}` with 4xx/5xx status
- [x] No global mutable state except explicit caches / job stores
- [x] Domain modules imported at top or in a lazy block, never inline
- [x] `_reload_*()` helper to hot-reload data after generation
- [x] Upload dir created with `mkdir(exist_ok=True)` at module level

---

## 4  Frontend Pattern (index.html + main.js)

### 4.1  HTML structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tool Name</title>
  <style>
    /* ─── All CSS lives here ─── */
  </style>
</head>
<body>

  <!-- Header bar -->
  <div class="header"> ... </div>

  <!-- Top-level tab bar -->
  <div class="app-tabs">
    <div class="app-tab active" data-app-tab="tab1">Tab 1</div>
    <div class="app-tab" data-app-tab="tab2">Tab 2</div>
  </div>

  <!-- Tab content panels -->
  <div class="tab-content active" data-app-content="tab1">
    <!-- 3-column layout: sidebar | main | detail panel -->
    <div class="main">
      <div class="sidebar-panel"> ... </div>
      <div class="center-area"> ... </div>
      <div class="detail-panel"> ... </div>
    </div>
  </div>

  <div class="tab-content" data-app-content="tab2"> ... </div>

  <!-- Modals (hidden by default) -->
  <div class="modal-backdrop" id="myModal"> ... </div>

  <!-- Toast notification -->
  <div class="toast" id="toast"></div>

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
  --accent:   #89b4fa;
  --green:    #a6e3a1;
  --red:      #f38ba8;
  --yellow:   #f9e2af;
  --peach:    #fab387;
  --mauve:    #cba6f7;
  --pink:     #f5c2e7;
  --teal:     #94e2d5;
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

```
main.js  (single file, ~2500 lines, "use strict")
│
├── State variables (global lets)
│   boardData, pinStates, periphStates, selectedPin, ...
│
├── DOM helpers
│   const $ = (sel) => document.querySelector(sel);
│   const $$ = (sel) => document.querySelectorAll(sel);
│   function toast(msg) { ... }
│
├── Module: Pin Configurator
│   loadBoardList() → loadBoard(name) → renderPeripherals()
│   renderChip()       ← SVG generation (inline string builder)
│   selectPin()        → renderConfigPanel()
│   generateOutput()   → POST /api/generate
│   saveToProject()    → POST /api/save-project
│
├── Module: Package Manager  (prefixed pkg*)
│   pkgInit(), pkgUploadPdf(), pkgRenderJobList(),
│   pkgSelectJob(), pkgRenderDetail(), pkgGenerate(), pkgLoadExisting()
│
├── Module: Module Configurator  (prefixed mod*)
│   modInit(), modRenderSidebar(), modSelectModule(),
│   modRenderBody(), modRenderOption(), modGenerateAll()
│
├── Module: Peripheral Configurator  (prefixed pcfg*)
│   pcfgInit(), pcfgLoadBoards(), pcfgLoadInstances(),
│   pcfgRenderSidebar(), pcfgSelectInstance(), pcfgGenerate()
│
├── Module: Clock Configurator  (prefixed clk*)
│   clkInit(), clkLoadTrees(), clkLoadTree(),
│   clkRenderSidebar(), clkRenderBody(), clkGenerate()
│
├── Module: Import  (prefixed imp*)
│   impInit(), impReset(), impSetupDragDrop(), impReadFile(),
│   impParseAndPreview(), impScanProject(), impApply()
│
├── Module: MCU Lookup  (prefixed mcu*)
│   mcuInit(), mcuLookup(), mcuFetchDatasheet()
│
└── DOMContentLoaded
    ├── loadBoardList()
    ├── wires all event listeners
    ├── tab switching: $$(".app-tab").forEach(...)
    └── calls *Init() for each module
```

### 4.4  Convention checklist

- [x] Each UI "module" uses a **3-letter prefix** for all its functions and state vars
- [x] All API calls use `fetch()` with `async/await` — no callbacks, no Axios
- [x] DOM is built via **innerHTML string templates** — no virtual DOM
- [x] SVG chip diagram rendered via string concatenation (inline `<svg>`)
- [x] Tab switching uses `data-app-tab` / `data-app-content` attributes
- [x] Modals use `.modal-backdrop.show` / `.modal-backdrop` toggle
- [x] Toast notifications via a shared `toast(msg)` function
- [x] Keyboard shortcuts (Escape, Ctrl+G) via `document.addEventListener("keydown")`
- [x] Drag-and-drop file upload via standard HTML5 events
- [x] No localStorage / sessionStorage — state is ephemeral

---

## 5  Domain Module Pattern

### 5.1  Schema (dataclasses)

```python
# board_schema.py — example
from dataclasses import dataclass, field
from enum import Enum

class PinKind(str, Enum):
    IO = "io"; PWR = "power"; GND = "ground"; SPEC = "special"

@dataclass
class AltFunction:
    function_id: int
    pincm: int
    name: str
    peripheral: str
    signal: str
    direction: str = "io"

@dataclass
class Pin:
    number: int
    name: str
    ...
    alt_functions: list[AltFunction] = field(default_factory=list)

@dataclass
class BoardDef:
    soc: str
    board: str
    ...
    pins: list[Pin] = field(default_factory=list)
```

### 5.2  Registry pattern

```python
# module_registry.py — example
_MODULES: dict[str, dict] = {}

def _register(module_def: dict):
    _MODULES[module_def["id"]] = module_def

def get_all_modules() -> list[dict]:
    return list(_MODULES.values())

def get_module(module_id: str) -> dict | None:
    return _MODULES.get(module_id)

# Registrations at module level
_register({ "id": "bluetooth", "name": "Bluetooth", "categories": [...] })
_register({ "id": "wifi", "name": "Wi-Fi", ... })
```

### 5.3  Generator pattern

```python
# dts_generator.py — example
from dataclasses import dataclass

@dataclass
class GenerateResult:
    overlay: str     # .overlay file content
    prj_conf: str    # prj.conf content

def generate(assignments, peripherals, board_name="custom") -> GenerateResult:
    """Pure function: inputs → output strings. No I/O."""
    overlay_lines = []
    conf_lines = []
    # ... build output ...
    return GenerateResult(overlay="\n".join(overlay_lines), ...)
```

### 5.4  Parser pattern

```python
# pdf_parser.py — example
@dataclass
class DatasheetInfo:
    device: DeviceInfo
    packages: list[PackageInfo]
    pin_mux: dict[str, list[MuxEntry]]

def parse_datasheet(pdf_path: str, verbose=False) -> DatasheetInfo:
    """Read a PDF, extract structured data. Pure I/O at boundary only."""
    ...
```

---

## 6  REST API Reference

Full endpoint list from the Pin Configurator (30 routes):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve index.html |
| GET | `/api/boards` | List available boards |
| GET | `/api/board/<name>` | Full board definition |
| POST | `/api/generate` | Generate DTS overlay + prj.conf |
| POST | `/api/save-project` | Write files to Zephyr project dir |
| POST | `/api/parse-pdf` | Upload + parse MCU datasheet PDF |
| POST | `/api/generate-package` | Generate board .py from parsed PDF |
| GET | `/api/generated-packages` | List board definition files |
| GET | `/api/parse-jobs` | List parsed PDF jobs |
| GET | `/api/modules` | List Zephyr module configs |
| POST | `/api/generate-module-config` | Generate Kconfig from selections |
| GET | `/api/peripheral-templates` | List peripheral config templates |
| GET | `/api/peripheral-instances/<board>` | Board peripherals + templates |
| POST | `/api/generate-peripheral-config` | Generate DTS from peripheral values |
| GET | `/api/clock-trees` | List clock tree definitions |
| GET | `/api/clock-tree/<id>` | Full clock tree for SoC |
| POST | `/api/clock-frequencies` | Compute frequencies from values |
| POST | `/api/generate-clock-config` | Generate clock DTS/conf |
| POST | `/api/import-config` | Parse existing overlay/conf |
| POST | `/api/scan-project` | Scan Zephyr project dir for configs |
| POST | `/api/identify-mcu` | Identify MCU from part number |
| POST | `/api/fetch-datasheet` | Download datasheet from web |
| GET | `/api/driver-templates` | List Zephyr driver templates |
| POST | `/api/generate-driver` | Generate driver source code |
| POST | `/api/parse-sensor-pdf` | Upload + parse sensor datasheet |
| GET | `/api/sensor-jobs` | List parsed sensor jobs |
| GET | `/api/sensor-job/<id>` | Get parsed sensor details |
| GET | `/api/sensor-job/<id>/header` | Generate register header |
| POST | `/api/sensor-job/<id>/driver` | Generate sensor driver code |
| POST | `/api/identify-sensor` | Identify sensor from part number |

---

## 7  Deployment & Launch

### Local (Windows)

```bat
@echo off
set VENV=path\to\.venv\Scripts\python.exe
%VENV% run.py --port 5100 --open
```

### Local (any OS)

```bash
python run.py --port 5100 --open    # --debug for hot-reload
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . /app/
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5100
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "5100"]
```

### run.py pattern

```python
def main():
    parser = argparse.ArgumentParser(description="Tool Name")
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    if args.open:
        webbrowser.open(f"http://{args.host}:{args.port}")

    from server import app
    app.run(host=args.host, port=args.port, debug=args.debug)
```

---

## 8  Testing

```
tests/
├── conftest.py          # Shared fixtures (Flask test client, temp dirs)
├── test_api.py          # Integration tests against Flask endpoints
├── test_<domain>.py     # Unit tests for each domain module
```

```python
# conftest.py
import pytest
from server import app as flask_app

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c

# test_api.py
def test_list_boards(client):
    r = client.get("/api/boards")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
```

---

## 9  Project Stats (reference size)

| File | Lines | Role |
|------|------:|------|
| `server.py` | ~1,080 | Flask routes + JSON serialisation |
| `web/main.js` | ~2,634 | All frontend logic |
| `web/index.html` | ~1,704 | Layout + all CSS |
| `module_registry.py` | ~1,065 | Zephyr module data |
| `peripheral_registry.py` | ~1,201 | Peripheral config data |
| `clock_registry.py` | ~1,120 | Clock tree data |
| `pdf_parser.py` | ~835 | MCU datasheet parser |
| `sensor_parser.py` | ~1,072 | Sensor datasheet parser |
| `driver_generator.py` | ~521 | Zephyr driver codegen |
| `package_generator.py` | ~486 | Board package codegen |
| `board_schema.py` | ~148 | Dataclass domain model |
| `dts_generator.py` | ~163 | DTS overlay generator |
| `overlay_parser.py` | ~330 | Import overlay parser |
| `datasheet_fetcher.py` | ~313 | MCU identify + download |
| `run.py` | ~43 | CLI entry point |
| **Total Python** | **~10,800** | |
| **Total JS + HTML** | **~4,340** | |
| **Grand Total** | **~15,140** | |

---

## 10  How to Use This Template

When asking an LLM to build a new tool GUI:

1. **Copy sections 1–8** into the system prompt or first user message.
2. **Replace domain nouns**: swap "board/pin/peripheral" with your domain concepts (e.g., "device/register/protocol").
3. **Define your API endpoints**: list the REST routes your tool needs (follow the patterns from section 3.2).
4. **Define your data model**: describe your dataclasses (follow section 5.1).
5. **Specify tabs**: list the top-level tabs your UI needs (follow section 4.1).

### Example prompt

> Build a GUI tool for **[your domain]** following the pin_configurator
> architecture described below.
>
> **Backend**: Flask, Python 3.10+, no database, REST JSON API.
> **Frontend**: Single-page vanilla JS + CSS (no build step), Catppuccin dark
> theme, tab-based layout with sidebar + main + detail panels.
>
> Tabs needed: [Tab1], [Tab2], [Tab3]
>
> API endpoints:
> - GET /api/things — list all things
> - POST /api/generate — generate output from selections
>
> Data model:
> - Thing: name, type, properties dict
> - GenerateResult: output_text, config_text
>
> [paste sections 1-8 from GUI_STACK_TEMPLATE.md]

---

## 11  Dependencies

### Python (requirements.txt)

```
flask>=3.0.0
werkzeug>=3.0.0
```

Optional (add only if your domain needs them):

```
pdfplumber>=0.10.0      # PDF parsing
requests>=2.31.0        # HTTP fetching
pytest>=8.0.0           # Testing
```

### Frontend

**Zero npm dependencies.** The frontend uses only browser-native APIs:
- `fetch()` for HTTP
- `FormData` for file uploads
- `FileReader` for drag-and-drop
- `navigator.clipboard` for copy-to-clipboard
- SVG via inline string templates
- CSS custom properties for theming
