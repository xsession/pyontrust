"""
Zephyr Pin Configurator – Flask backend.

Serves the web UI and provides REST endpoints for:
  GET  /api/boards              – list available boards
  GET  /api/board/<name>        – full board definition (pins, peripherals)
  POST /api/generate            – generate DTS overlay + prj.conf from state
  POST /api/save-project        – save the pin config state to a project dir
  POST /api/parse-pdf           – parse an MCU datasheet PDF
  POST /api/generate-package    – generate board definition .py from parsed data
  GET  /api/generated-packages  – list previously generated packages
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import sys
import threading
import uuid

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

# Ensure package is importable when run directly
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from board_schema import board_to_frontend
from boards import BOARDS
from dts_generator import PinAssignment, PeripheralConfig, generate
from pdf_parser import parse_datasheet, DatasheetInfo
from package_generator import generate_board_files


app = Flask(
    __name__,
    static_folder=str(_HERE / "web"),
    static_url_path="",
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit

log = logging.getLogger(__name__)

# ── Upload / temp storage ─────────────────────────────────────────────

_UPLOAD_DIR = _HERE / ".uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)

# In-memory store for parsed PDFs (session-scoped, keyed by job_id)
_PARSED_JOBS: dict[str, dict] = {}

# ── Board registry ────────────────────────────────────────────────────

_BOARD_CACHE: dict = {}


def _get_board(name: str):
    if name not in _BOARD_CACHE:
        builder = BOARDS.get(name)
        if builder is None:
            return None
        _BOARD_CACHE[name] = builder()
    return _BOARD_CACHE[name]


# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/boards")
def list_boards():
    return jsonify([
        {"id": k, "name": _get_board(k).soc, "board": _get_board(k).board}
        for k in BOARDS
    ])


@app.route("/api/board/<name>")
def get_board(name: str):
    brd = _get_board(name)
    if brd is None:
        return jsonify({"error": f"Board '{name}' not found"}), 404
    return jsonify(board_to_frontend(brd))


@app.route("/api/generate", methods=["POST"])
def generate_overlay():
    """
    Expects JSON body:
    {
      "board": "mspm0g3507",
      "assignments": [ { pin_name, pincm, function_id, af_name,
                          peripheral, signal, direction,
                          bias_pull_up, bias_pull_down,
                          drive_open_drain, input_enable } ... ],
      "peripherals": [ { name, dts_node, compatible, enabled } ... ]
    }
    """
    body = request.get_json(force=True)

    assignments = [
        PinAssignment(
            pin_name=a["pin_name"],
            pincm=a["pincm"],
            function_id=a["function_id"],
            af_name=a.get("af_name", ""),
            peripheral=a["peripheral"],
            signal=a["signal"],
            direction=a.get("direction", "io"),
            bias_pull_up=a.get("bias_pull_up", False),
            bias_pull_down=a.get("bias_pull_down", False),
            drive_open_drain=a.get("drive_open_drain", False),
            input_enable=a.get("input_enable", False),
        )
        for a in body.get("assignments", [])
    ]

    periphs = [
        PeripheralConfig(
            name=p["name"],
            dts_node=p.get("dts_node", ""),
            compatible=p.get("compatible", ""),
            enabled=p.get("enabled", False),
        )
        for p in body.get("peripherals", [])
    ]

    result = generate(assignments, periphs, board_name=body.get("board", "custom"))

    return jsonify({
        "overlay": result.overlay,
        "prj_conf": result.prj_conf,
    })


@app.route("/api/save-project", methods=["POST"])
def save_project():
    """
    Write generated files directly into a Zephyr project directory.

    Body:
    {
      "project_path": "C:/path/to/app",
      "overlay": "...",
      "prj_conf": "...",
      "board": "mspm0g3507"
    }
    """
    body = request.get_json(force=True)
    project = pathlib.Path(body["project_path"])

    if not project.is_dir():
        return jsonify({"error": f"Directory does not exist: {project}"}), 400

    board = body.get("board", "custom_board")

    overlay_path = project / f"{board}.overlay"
    conf_path = project / "prj.conf"

    overlay_path.write_text(body["overlay"], encoding="utf-8")

    # Merge into existing prj.conf if present
    existing = ""
    if conf_path.exists():
        existing = conf_path.read_text(encoding="utf-8")
    
    new_lines = body["prj_conf"].strip().split("\n")
    for line in new_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            key = line.split("=")[0]
            if key not in existing:
                existing += "\n" + line
    
    conf_path.write_text(existing.strip() + "\n", encoding="utf-8")

    return jsonify({
        "saved": True,
        "overlay_path": str(overlay_path),
        "conf_path": str(conf_path),
    })


# ── Package Generator API ────────────────────────────────────────────

def _datasheet_to_json(info: DatasheetInfo) -> dict:
    """Serialise DatasheetInfo to a JSON-friendly dict for the frontend."""
    return {
        "device": {
            "soc": info.device.soc,
            "vendor": info.device.vendor,
            "flash_size_kb": info.device.flash_size_kb,
            "sram_size_kb": info.device.sram_size_kb,
            "clock_hz": info.device.clock_hz,
        },
        "packages": [
            {
                "name": pkg.name,
                "pin_count": pkg.pin_count,
                "pins": [
                    {
                        "number": p.number,
                        "name": p.name,
                        "port": p.port,
                        "gpio_num": p.gpio_num,
                        "kind": p.kind,
                    }
                    for p in pkg.pins
                ],
            }
            for pkg in info.packages
        ],
        "pin_mux_count": len(info.pin_mux),
        "pin_mux_total_funcs": sum(len(v) for v in info.pin_mux.values()),
        "pin_mux_sample": {
            k: [
                {
                    "function_id": e.function_id,
                    "function_name": e.function_name,
                    "peripheral": e.peripheral,
                    "signal": e.signal,
                    "direction": e.direction,
                }
                for e in entries
            ]
            for k, entries in list(info.pin_mux.items())[:5]
        },
    }


@app.route("/api/parse-pdf", methods=["POST"])
def parse_pdf():
    """
    Upload and parse an MCU datasheet PDF.

    Accepts multipart/form-data with field 'pdf'.
    Returns a job_id and the parsed summary.
    """
    if "pdf" not in request.files:
        return jsonify({"error": "No 'pdf' file in request"}), 400

    f = request.files["pdf"]
    if not f.filename or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "File must be a .pdf"}), 400

    # Save to temp
    safe_name = secure_filename(f.filename)
    job_id = uuid.uuid4().hex[:12]
    upload_path = _UPLOAD_DIR / f"{job_id}_{safe_name}"
    f.save(str(upload_path))

    try:
        info = parse_datasheet(str(upload_path), verbose=False)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        log.exception("PDF parsing failed")
        return jsonify({"error": f"PDF parsing failed: {exc}"}), 500

    # Store parsed result for later generation
    _PARSED_JOBS[job_id] = {
        "filename": safe_name,
        "upload_path": str(upload_path),
        "info": info,
    }

    return jsonify({
        "job_id": job_id,
        "filename": safe_name,
        "result": _datasheet_to_json(info),
    })


@app.route("/api/generate-package", methods=["POST"])
def generate_package():
    """
    Generate board definition .py file(s) from a previously parsed PDF.

    JSON body:
    {
      "job_id": "abc123...",
      "packages": ["QFP-48"],          // optional filter; omit for all
      "board_name": "lp_mspm0g3507",   // optional
      "dts_soc_include": "...",         // optional
      "dts_pinctrl_include": "...",     // optional
      "pinctrl_header": "...",          // optional
      "register": true                  // update boards/__init__.py
    }
    """
    body = request.get_json(force=True)
    job_id = body.get("job_id", "")

    if job_id not in _PARSED_JOBS:
        return jsonify({"error": f"Job '{job_id}' not found. Parse a PDF first."}), 404

    job = _PARSED_JOBS[job_id]
    info: DatasheetInfo = job["info"]

    # Optional package filter
    pkg_filter = body.get("packages")
    if pkg_filter:
        pkg_set = {p.upper().replace("-", "") for p in pkg_filter}
        info.packages = [
            p for p in info.packages
            if p.name.upper().replace("-", "") in pkg_set
        ]
        if not info.packages:
            return jsonify({"error": f"No matching packages. Available: "
                            f"{[p.name for p in _PARSED_JOBS[job_id]['info'].packages]}"}), 400

    boards_dir = _HERE / "boards"

    try:
        files = generate_board_files(
            info,
            output_dir=boards_dir,
            board_name=body.get("board_name"),
            dts_soc_include=body.get("dts_soc_include"),
            dts_pinctrl_include=body.get("dts_pinctrl_include"),
            pinctrl_header=body.get("pinctrl_header"),
            register_in_init=body.get("register", True),
        )
    except Exception as exc:
        log.exception("Package generation failed")
        return jsonify({"error": f"Generation failed: {exc}"}), 500

    # Reload BOARDS registry so the new board appears immediately
    _reload_boards()

    generated = []
    for fp in files:
        p = pathlib.Path(fp)
        generated.append({
            "filename": p.name,
            "path": str(p),
        })

    return jsonify({
        "success": True,
        "files": generated,
    })


@app.route("/api/generated-packages")
def list_generated_packages():
    """List all .py board definition files in the boards/ directory."""
    boards_dir = _HERE / "boards"
    files = []
    for p in sorted(boards_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        files.append({
            "filename": p.name,
            "module": p.stem,
            "size": p.stat().st_size,
        })
    return jsonify(files)


@app.route("/api/parse-jobs")
def list_parse_jobs():
    """List active parse jobs (PDF files that have been parsed)."""
    jobs = []
    for jid, job in _PARSED_JOBS.items():
        info = job["info"]
        jobs.append({
            "job_id": jid,
            "filename": job["filename"],
            "soc": info.device.soc,
            "packages": [p.name for p in info.packages],
            "pin_count": len(info.pin_mux),
        })
    return jsonify(jobs)


def _reload_boards():
    """Reload the boards module to pick up newly generated definitions."""
    import importlib
    import boards as boards_mod
    importlib.reload(boards_mod)
    global BOARDS
    from boards import BOARDS
    _BOARD_CACHE.clear()


# ── Module Configurator API ──────────────────────────────────────────

# LVGL Kconfig module definition tree.
# Each module has categories -> options.
_LVGL_MODULES = {
    "id": "lvgl",
    "name": "LVGL",
    "version": "9.2",
    "icon": "\U0001f3a8",
    "desc": "Light and Versatile Graphics Library — embedded GUI with advanced visual effects and low memory footprint.",
    "categories": [
        {
            "id": "general",
            "title": "General",
            "options": [
                {"key": "CONFIG_LVGL", "type": "bool", "default": True, "help": "Enable LVGL library"},
                {"key": "CONFIG_LV_Z_MEM_POOL_SIZE", "type": "int", "default": 16384, "help": "LVGL memory pool size in bytes"},
                {"key": "CONFIG_LV_COLOR_DEPTH", "type": "choice", "choices": ["1", "8", "16", "32"], "default": "16", "help": "Color depth (bits per pixel)"},
                {"key": "CONFIG_LV_DPI_DEF", "type": "int", "default": 130, "help": "Default display DPI"},
            ]
        },
        {
            "id": "display",
            "title": "Display",
            "options": [
                {"key": "CONFIG_LV_HOR_RES_MAX", "type": "int", "default": 320, "help": "Maximum horizontal resolution"},
                {"key": "CONFIG_LV_VER_RES_MAX", "type": "int", "default": 240, "help": "Maximum vertical resolution"},
                {"key": "CONFIG_LV_Z_FLUSH_THREAD", "type": "bool", "default": False, "help": "Use a dedicated flush thread for display"},
                {"key": "CONFIG_LV_Z_FULL_REFRESH", "type": "bool", "default": False, "help": "Always redraw the whole screen"},
                {"key": "CONFIG_LV_Z_VDB_SIZE", "type": "int", "default": 100, "help": "Display buffer size (% of screen)"},
                {"key": "CONFIG_LV_Z_DOUBLE_VDB", "type": "bool", "default": False, "help": "Use double display buffering"},
                {"key": "CONFIG_LV_Z_VBD_CUSTOM_SECTION", "type": "bool", "default": False, "help": "Place VDB in custom linker section"},
            ]
        },
        {
            "id": "input",
            "title": "Input Devices",
            "options": [
                {"key": "CONFIG_LV_Z_POINTER_INPUT", "type": "bool", "default": False, "help": "Enable pointer (touch) input device"},
                {"key": "CONFIG_LV_Z_POINTER_INPUT_MSGQ_COUNT", "type": "int", "default": 10, "help": "Pointer input message queue depth"},
                {"key": "CONFIG_LV_Z_BUTTON_INPUT", "type": "bool", "default": False, "help": "Enable button input device"},
                {"key": "CONFIG_LV_Z_ENCODER_INPUT", "type": "bool", "default": False, "help": "Enable rotary encoder input device"},
                {"key": "CONFIG_LV_Z_KEYPAD_INPUT", "type": "bool", "default": False, "help": "Enable keypad input device"},
            ]
        },
        {
            "id": "fonts",
            "title": "Fonts",
            "options": [
                {"key": "CONFIG_LV_FONT_MONTSERRAT_8", "type": "bool", "default": False, "help": "Montserrat 8px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_10", "type": "bool", "default": False, "help": "Montserrat 10px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_12", "type": "bool", "default": False, "help": "Montserrat 12px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_14", "type": "bool", "default": True, "help": "Montserrat 14px font (default)"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_16", "type": "bool", "default": False, "help": "Montserrat 16px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_18", "type": "bool", "default": False, "help": "Montserrat 18px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_20", "type": "bool", "default": False, "help": "Montserrat 20px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_22", "type": "bool", "default": False, "help": "Montserrat 22px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_24", "type": "bool", "default": False, "help": "Montserrat 24px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_28", "type": "bool", "default": False, "help": "Montserrat 28px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_32", "type": "bool", "default": False, "help": "Montserrat 32px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_36", "type": "bool", "default": False, "help": "Montserrat 36px font"},
                {"key": "CONFIG_LV_FONT_MONTSERRAT_48", "type": "bool", "default": False, "help": "Montserrat 48px font"},
                {"key": "CONFIG_LV_FONT_DEFAULT_MONTSERRAT_14", "type": "bool", "default": True, "help": "Use Montserrat 14 as default font"},
            ]
        },
        {
            "id": "themes",
            "title": "Themes & Styles",
            "options": [
                {"key": "CONFIG_LV_USE_THEME_DEFAULT", "type": "bool", "default": True, "help": "Enable default theme"},
                {"key": "CONFIG_LV_THEME_DEFAULT_DARK", "type": "bool", "default": False, "help": "Use dark variant of default theme"},
                {"key": "CONFIG_LV_USE_THEME_BASIC", "type": "bool", "default": False, "help": "Enable basic minimal theme"},
                {"key": "CONFIG_LV_USE_THEME_MONO", "type": "bool", "default": False, "help": "Enable monochrome theme"},
            ]
        },
        {
            "id": "widgets",
            "title": "Widgets",
            "options": [
                {"key": "CONFIG_LV_USE_ARC", "type": "bool", "default": True, "help": "Arc / circular gauge widget"},
                {"key": "CONFIG_LV_USE_BAR", "type": "bool", "default": True, "help": "Progress bar widget"},
                {"key": "CONFIG_LV_USE_BTN", "type": "bool", "default": True, "help": "Button widget"},
                {"key": "CONFIG_LV_USE_BTNMATRIX", "type": "bool", "default": True, "help": "Button matrix widget"},
                {"key": "CONFIG_LV_USE_CALENDAR", "type": "bool", "default": False, "help": "Calendar widget"},
                {"key": "CONFIG_LV_USE_CANVAS", "type": "bool", "default": False, "help": "Canvas / draw widget"},
                {"key": "CONFIG_LV_USE_CHART", "type": "bool", "default": False, "help": "Chart widget"},
                {"key": "CONFIG_LV_USE_CHECKBOX", "type": "bool", "default": True, "help": "Checkbox widget"},
                {"key": "CONFIG_LV_USE_DROPDOWN", "type": "bool", "default": True, "help": "Dropdown list widget"},
                {"key": "CONFIG_LV_USE_IMG", "type": "bool", "default": True, "help": "Image widget"},
                {"key": "CONFIG_LV_USE_IMGBTN", "type": "bool", "default": False, "help": "Image button widget"},
                {"key": "CONFIG_LV_USE_KEYBOARD", "type": "bool", "default": False, "help": "Virtual keyboard widget"},
                {"key": "CONFIG_LV_USE_LABEL", "type": "bool", "default": True, "help": "Label / text widget"},
                {"key": "CONFIG_LV_USE_LED", "type": "bool", "default": False, "help": "LED indicator widget"},
                {"key": "CONFIG_LV_USE_LINE", "type": "bool", "default": True, "help": "Line drawing widget"},
                {"key": "CONFIG_LV_USE_LIST", "type": "bool", "default": False, "help": "List widget"},
                {"key": "CONFIG_LV_USE_MENU", "type": "bool", "default": False, "help": "Menu widget"},
                {"key": "CONFIG_LV_USE_METER", "type": "bool", "default": False, "help": "Meter / gauge widget"},
                {"key": "CONFIG_LV_USE_MSGBOX", "type": "bool", "default": False, "help": "Message box widget"},
                {"key": "CONFIG_LV_USE_ROLLER", "type": "bool", "default": True, "help": "Roller (scrollable list) widget"},
                {"key": "CONFIG_LV_USE_SLIDER", "type": "bool", "default": True, "help": "Slider widget"},
                {"key": "CONFIG_LV_USE_SPAN", "type": "bool", "default": False, "help": "Rich text span widget"},
                {"key": "CONFIG_LV_USE_SPINBOX", "type": "bool", "default": False, "help": "Spinbox / number input widget"},
                {"key": "CONFIG_LV_USE_SPINNER", "type": "bool", "default": False, "help": "Spinner / loading widget"},
                {"key": "CONFIG_LV_USE_SWITCH", "type": "bool", "default": True, "help": "Toggle switch widget"},
                {"key": "CONFIG_LV_USE_TABLE", "type": "bool", "default": False, "help": "Table widget"},
                {"key": "CONFIG_LV_USE_TABVIEW", "type": "bool", "default": False, "help": "Tab view container widget"},
                {"key": "CONFIG_LV_USE_TEXTAREA", "type": "bool", "default": True, "help": "Text area / input widget"},
                {"key": "CONFIG_LV_USE_TILEVIEW", "type": "bool", "default": False, "help": "Tile view (swipeable pages)"},
                {"key": "CONFIG_LV_USE_WIN", "type": "bool", "default": False, "help": "Window widget"},
            ]
        },
        {
            "id": "memory",
            "title": "Memory & Performance",
            "options": [
                {"key": "CONFIG_LV_Z_MEM_POOL_NUMBER_BLOCKS", "type": "int", "default": 8, "help": "Number of memory pool blocks"},
                {"key": "CONFIG_LV_MEM_CUSTOM", "type": "bool", "default": False, "help": "Use custom memory allocator"},
                {"key": "CONFIG_LV_MEM_SIZE_KILOBYTES", "type": "int", "default": 32, "help": "Internal memory size (KB) when not using pool"},
                {"key": "CONFIG_LV_DRAW_BUF_ALIGN", "type": "int", "default": 4, "help": "Draw buffer alignment (bytes)"},
                {"key": "CONFIG_LV_USE_GPU", "type": "bool", "default": False, "help": "Enable GPU accelerated rendering"},
            ]
        },
        {
            "id": "debug",
            "title": "Logging & Debug",
            "options": [
                {"key": "CONFIG_LV_USE_LOG", "type": "bool", "default": False, "help": "Enable LVGL internal logging"},
                {"key": "CONFIG_LV_LOG_LEVEL_TRACE", "type": "bool", "default": False, "help": "Trace-level logging (most verbose)"},
                {"key": "CONFIG_LV_LOG_LEVEL_INFO", "type": "bool", "default": False, "help": "Info-level logging"},
                {"key": "CONFIG_LV_LOG_LEVEL_WARN", "type": "bool", "default": True, "help": "Warning-level logging"},
                {"key": "CONFIG_LV_LOG_LEVEL_ERROR", "type": "bool", "default": False, "help": "Error-only logging"},
                {"key": "CONFIG_LV_USE_ASSERT_NULL", "type": "bool", "default": True, "help": "Assert on NULL pointer dereference"},
                {"key": "CONFIG_LV_USE_ASSERT_MEM_INTEGRITY", "type": "bool", "default": False, "help": "Assert on memory integrity violation"},
                {"key": "CONFIG_LV_USE_ASSERT_STYLE", "type": "bool", "default": False, "help": "Assert on invalid style usage"},
                {"key": "CONFIG_LV_USE_PERF_MONITOR", "type": "bool", "default": False, "help": "Show FPS & CPU usage overlay"},
                {"key": "CONFIG_LV_USE_MEM_MONITOR", "type": "bool", "default": False, "help": "Show memory usage overlay"},
            ]
        },
    ]
}

@app.route("/api/lvgl-modules", methods=["GET"])
def get_lvgl_modules():
    """Return the LVGL module definition tree for the configurator UI."""
    return jsonify([_LVGL_MODULES])


@app.route("/api/generate-module-config", methods=["POST"])
def generate_module_config():
    """Generate prj.conf / Kconfig fragment from user selections.

    Expects JSON body: { "module": "lvgl", "values": { "CONFIG_KEY": value, ... } }
    Returns { "prj_conf": "...", "overlay_conf": "..." }
    """
    data = request.get_json(force=True)
    module_id = data.get("module")
    values = data.get("values", {})

    if module_id != "lvgl":
        return jsonify({"error": f"Unknown module '{module_id}'"}), 400

    # Build the Kconfig text – only emit values that differ from defaults
    mod = _LVGL_MODULES
    defaults = {}
    for cat in mod["categories"]:
        for opt in cat["options"]:
            defaults[opt["key"]] = opt["default"]

    lines_prj = [
        "# ─── LVGL module configuration ───────────────────────────────────",
        "# Generated by Zephyr Module Configurator",
        "",
    ]

    for cat in mod["categories"]:
        cat_lines = []
        for opt in cat["options"]:
            key = opt["key"]
            val = values.get(key, opt["default"])
            default = opt["default"]

            # Normalise types for comparison
            if opt["type"] == "bool":
                val = bool(val)
            elif opt["type"] == "int":
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = default
            else:
                val = str(val)

            if val != default:
                if opt["type"] == "bool":
                    cat_lines.append(f"{key}={'y' if val else 'n'}")
                elif opt["type"] == "choice":
                    cat_lines.append(f"{key}={val}")
                else:
                    cat_lines.append(f"{key}={val}")
            elif key == "CONFIG_LVGL" and val:
                # Always emit the master enable
                cat_lines.append(f"{key}=y")

        if cat_lines:
            lines_prj.append(f"# {cat['title']}")
            lines_prj.extend(cat_lines)
            lines_prj.append("")

    # Also generate full overlay (all values regardless of defaults)
    lines_overlay = [
        "# ─── LVGL full overlay configuration ─────────────────────────────",
        "# Generated by Zephyr Module Configurator",
        "",
    ]
    for cat in mod["categories"]:
        lines_overlay.append(f"# {cat['title']}")
        for opt in cat["options"]:
            key = opt["key"]
            val = values.get(key, opt["default"])
            if opt["type"] == "bool":
                val = bool(val)
                lines_overlay.append(f"{key}={'y' if val else 'n'}")
            elif opt["type"] == "int":
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = opt["default"]
                lines_overlay.append(f"{key}={val}")
            else:
                lines_overlay.append(f"{key}={val}")
        lines_overlay.append("")

    return jsonify({
        "prj_conf": "\n".join(lines_prj),
        "overlay_conf": "\n".join(lines_overlay),
    })


# ── Entry point ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zephyr Pin Configurator")
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n  Zephyr Pin Configurator")
    print(f"  http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
