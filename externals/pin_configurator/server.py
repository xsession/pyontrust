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
  GET  /api/modules             – list all Zephyr module definitions
  POST /api/generate-module-config – generate prj.conf from module selections
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
from dts_generator import ExternalDeviceConfig, PinAssignment, PeripheralConfig, generate
from pdf_parser import parse_datasheet, DatasheetInfo
from package_generator import generate_board_files
from overlay_parser import parse_import, import_result_to_json
from datasheet_fetcher import identify_vendor, download_datasheet, fetch_and_parse
from driver_generator import (
    DriverSpec, DRIVER_TYPES, generate_driver, driver_to_json, spec_from_json,
)
from sensor_parser import (
    parse_sensor_datasheet, SensorDatasheetInfo,
    sensor_info_to_json, sensor_info_from_json,
    identify_sensor, generate_register_header, generate_register_defines,
)


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


def _find_board(board_ref: str):
    """Resolve a board by registry id or runtime board name."""
    if not board_ref:
        return None

    board = _get_board(board_ref)
    if board is not None:
        return board

    for board_id in BOARDS:
        candidate = _get_board(board_id)
        if candidate and candidate.board == board_ref:
            return candidate

    return None


def _match_alt_function(board, pin_name: str, peripheral: str, signal: str, function_id: int):
    if board is None:
        return None

    for pin in board.pins:
        if pin.name != pin_name:
            continue
        for alt in pin.alt_functions:
            if (
                alt.peripheral == peripheral
                and alt.signal == signal
                and alt.function_id == function_id
            ):
                return alt
    return None


# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/boards")
def list_boards():
    return jsonify([
        {
            "id": k,
            "name": _get_board(k).soc,
            "board": _get_board(k).board,
            "package": _get_board(k).package,
            "pin_count": _get_board(k).pin_count,
        }
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
    board = _find_board(body.get("board_id") or body.get("board", ""))
    targets = body.get("targets") or ["zephyr", "arduino", "baremetal"]

    assignments = [
        PinAssignment(
            pin_name=a["pin_name"],
            pincm=a["pincm"],
            function_id=a["function_id"],
            af_name=a.get("af_name", ""),
            peripheral=a["peripheral"],
            signal=a["signal"],
            direction=a.get("direction", "io"),
            zephyr_pinmux=a.get("zephyr_pinmux", "") or (
                matched.zephyr_pinmux if (matched := _match_alt_function(
                    board,
                    a["pin_name"],
                    a["peripheral"],
                    a["signal"],
                    a["function_id"],
                )) else ""
            ),
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
            core_id=p.get("core_id", ""),
        )
        for p in body.get("peripherals", [])
    ]

    external_devices = [
        ExternalDeviceConfig(
            id=str(device.get("id", "")).strip(),
            display=str(device.get("display", device.get("id", ""))).strip(),
            category=str(device.get("category", "device")),
            bus=str(device.get("bus", "")),
            compatible=str(device.get("compatible", "")),
            address=str(device.get("address", "")),
            required_signals=[str(signal) for signal in device.get("required_signals", [])],
            frameworks=[str(framework) for framework in device.get("frameworks", [])],
            notes=str(device.get("notes", "")),
        )
        for device in body.get("external_devices", [])
        if isinstance(device, dict) and str(device.get("id", "")).strip()
    ]

    result = generate(
        assignments,
        periphs,
        board_name=body.get("board", "custom"),
        targets=[str(target) for target in targets] if isinstance(targets, list) else None,
        external_devices=external_devices,
    )

    return jsonify({
        "overlay": result.overlay,
        "prj_conf": result.prj_conf,
        "targets": result.targets,
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


# ── Project File (save / load full editor state) ─────────────────────

PROJECT_FILE_VERSION = 1

@app.route("/api/project-file/save", methods=["POST"])
def project_file_save():
    """
    Save the full editor state (board, pin assignments, peripheral enables)
    to a JSON project file (.zpinproj) so it can be reloaded later.

    Body:
    {
      "file_path": "C:/path/to/my_config.zpinproj",
      "board_id": "lp_mspm0g3507",
      "pin_states": { "1": { "af": { ... }, "props": { ... } }, ... },
      "periph_states": { "uart0": true, "spi0": false, ... },
            "periph_core_states": { "uart0": "core0", "spi0": "core1" },
      "generated_overlay": "...",   // optional
      "generated_conf": "..."       // optional
    }
    """
    body = request.get_json(force=True)
    file_path = body.get("file_path", "").strip()

    if not file_path:
        return jsonify({"error": "Missing file_path"}), 400

    # Ensure .zpinproj extension
    fp = pathlib.Path(file_path)
    if fp.suffix.lower() != ".zpinproj":
        fp = fp.with_suffix(".zpinproj")

    # Ensure parent directory exists
    fp.parent.mkdir(parents=True, exist_ok=True)

    project = {
        "version": PROJECT_FILE_VERSION,
        "board_id": body.get("board_id", ""),
        "pin_states": body.get("pin_states", {}),
        "periph_states": body.get("periph_states", {}),
        "periph_core_states": body.get("periph_core_states", {}),
        "external_device_states": body.get("external_device_states", {}),
        "generated_overlay": body.get("generated_overlay", ""),
        "generated_conf": body.get("generated_conf", ""),
        "sensor_jobs": body.get("sensor_jobs", []),
        "sensor_selected": body.get("sensor_selected", ""),
        "mcu_jobs": body.get("mcu_jobs", []),
        "mcu_selected": body.get("mcu_selected", ""),
    }

    fp.write_text(json.dumps(project, indent=2), encoding="utf-8")

    return jsonify({"saved": True, "file_path": str(fp)})


@app.route("/api/project-file/load", methods=["POST"])
def project_file_load():
    """
    Load a previously saved .zpinproj project file.

    Body:
        { "file_path": "C:/path/to/my_config.zpinproj" }

    Returns the full project state for the frontend to restore.
    """
    body = request.get_json(force=True)
    file_path = body.get("file_path", "").strip()

    if not file_path:
        return jsonify({"error": "Missing file_path"}), 400

    fp = pathlib.Path(file_path)
    if not fp.is_file():
        return jsonify({"error": f"File not found: {fp}"}), 404

    try:
        project = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return jsonify({"error": f"Invalid project file: {exc}"}), 400

    return jsonify(project)


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
            "external_devices": [{...}],       // optional external Zephyr/Arduino devices
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
    external_devices = body.get("external_devices")
    if not isinstance(external_devices, list):
        external_devices = []

    try:
        files = generate_board_files(
            info,
            output_dir=boards_dir,
            board_name=body.get("board_name"),
            dts_soc_include=body.get("dts_soc_include"),
            dts_pinctrl_include=body.get("dts_pinctrl_include"),
            pinctrl_header=body.get("pinctrl_header"),
            external_devices=external_devices,
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

from module_registry import get_all_modules, get_module
from peripheral_registry import (
    get_all_peripheral_templates,
    get_peripheral_template,
    build_peripheral_instances,
    generate_peripheral_config,
)
from clock_registry import (
    get_all_clock_trees,
    get_clock_tree,
    compute_frequencies,
    generate_clock_config,
)


@app.route("/api/modules", methods=["GET"])
def api_get_modules():
    """Return all available Zephyr module definitions."""
    return jsonify(get_all_modules())


@app.route("/api/generate-module-config", methods=["POST"])
def generate_module_config():
    """Generate prj.conf / Kconfig fragment from user selections.

    Expects JSON body:
        {
          "modules": {
            "<module_id>": { "CONFIG_KEY": value, ... },
            ...
          }
        }
    Returns { "prj_conf": "...", "overlay_conf": "..." }
    """
    data = request.get_json(force=True)

    # Support both old single-module format and new multi-module format
    if "module" in data and "values" in data:
        # Legacy single-module format
        modules_map = {data["module"]: data["values"]}
    else:
        modules_map = data.get("modules", {})

    if not modules_map:
        return jsonify({"error": "No module configuration provided"}), 400

    lines_prj = [
        "# ─── Zephyr module configuration ─────────────────────────────────",
        "# Generated by Zephyr Module Configurator",
        "",
    ]
    lines_overlay = [
        "# ─── Zephyr full overlay configuration ───────────────────────────",
        "# Generated by Zephyr Module Configurator",
        "",
    ]

    for module_id, values in modules_map.items():
        mod = get_module(module_id)
        if not mod:
            continue

        # Collect defaults
        defaults = {}
        for cat in mod["categories"]:
            for opt in cat["options"]:
                defaults[opt["key"]] = opt["default"]

        # Detect the "master enable" key – first boolean option in first category
        master_key = None
        if mod["categories"] and mod["categories"][0]["options"]:
            first = mod["categories"][0]["options"][0]
            if first["type"] == "bool":
                master_key = first["key"]

        # ── prj.conf: only changed values ──
        lines_prj.append(f"# ── {mod['name']} {'─' * max(1, 52 - len(mod['name']))}")
        for cat in mod["categories"]:
            cat_lines = []
            for opt in cat["options"]:
                key = opt["key"]
                val = _normalise_value(opt, values.get(key, opt["default"]))
                default = opt["default"]

                if val != default:
                    cat_lines.append(_format_kconfig(opt, val))
                elif key == master_key and val:
                    cat_lines.append(f"{key}=y")

            if cat_lines:
                lines_prj.append(f"# {cat['title']}")
                lines_prj.extend(cat_lines)
        lines_prj.append("")

        # ── overlay: all values ──
        lines_overlay.append(f"# ── {mod['name']} {'─' * max(1, 52 - len(mod['name']))}")
        for cat in mod["categories"]:
            lines_overlay.append(f"# {cat['title']}")
            for opt in cat["options"]:
                key = opt["key"]
                val = _normalise_value(opt, values.get(key, opt["default"]))
                lines_overlay.append(_format_kconfig(opt, val))
        lines_overlay.append("")

    return jsonify({
        "prj_conf": "\n".join(lines_prj),
        "overlay_conf": "\n".join(lines_overlay),
    })


def _normalise_value(opt: dict, val):
    """Coerce a value to the correct Python type for comparison."""
    if opt["type"] == "bool":
        return bool(val)
    elif opt["type"] == "int":
        try:
            return int(val)
        except (ValueError, TypeError):
            return opt["default"]
    return str(val)


def _format_kconfig(opt: dict, val) -> str:
    """Format a single CONFIG line."""
    key = opt["key"]
    if opt["type"] == "bool":
        return f"{key}={'y' if val else 'n'}"
    return f"{key}={val}"


# ── Peripheral Configurator API ──────────────────────────────────────


@app.route("/api/peripheral-templates", methods=["GET"])
def api_get_peripheral_templates():
    """Return all available peripheral configuration templates."""
    return jsonify(get_all_peripheral_templates())


@app.route("/api/peripheral-instances/<board_name>", methods=["GET"])
def api_get_peripheral_instances(board_name: str):
    """Return board peripherals enriched with configuration templates.

    Merges board-specific peripheral instances (UART 0, SPI 1, etc.) with
    the generic configuration templates to produce a full list of
    configurable instances.
    """
    brd = _get_board(board_name)
    if brd is None:
        return jsonify({"error": f"Board '{board_name}' not found"}), 404

    frontend = board_to_frontend(brd)
    instances = build_peripheral_instances(frontend["peripherals"])
    return jsonify({
        "board": board_name,
        "soc": frontend["soc"],
        "package": frontend.get("package", ""),
        "instances": instances,
    })


@app.route("/api/generate-peripheral-config", methods=["POST"])
def api_generate_peripheral_config():
    """Generate DTS overlay + prj.conf from peripheral instance values.

    Expects JSON body:
    {
        "board": "mspm0g3507_48qfp",
        "instances": {
            "uart0": { "current-speed": 115200, "status": "okay", ... },
            "spi0":  { "clock-frequency": 4000000, ... },
            ...
        }
    }
    Returns: { "overlay": "...", "prj_conf": "..." }
    """
    data = request.get_json(force=True)
    board_name = data.get("board")
    inst_values = data.get("instances", {})

    if not board_name:
        return jsonify({"error": "Missing 'board' field"}), 400
    if not inst_values:
        return jsonify({"error": "No peripheral instances provided"}), 400

    brd = _get_board(board_name)
    if brd is None:
        return jsonify({"error": f"Board '{board_name}' not found"}), 404

    frontend = board_to_frontend(brd)
    result = generate_peripheral_config(inst_values, frontend["peripherals"])
    return jsonify(result)


# ── Clock System Configurator API ────────────────────────────────────


@app.route("/api/clock-trees", methods=["GET"])
def api_get_clock_trees():
    """Return summary list of all available clock trees."""
    return jsonify(get_all_clock_trees())


@app.route("/api/clock-tree/<tree_id>", methods=["GET"])
def api_get_clock_tree(tree_id: str):
    """Return the full clock tree definition for a given SoC."""
    tree = get_clock_tree(tree_id)
    if tree is None:
        return jsonify({"error": f"Clock tree '{tree_id}' not found"}), 404
    return jsonify(tree)


@app.route("/api/clock-frequencies", methods=["POST"])
def api_compute_clock_frequencies():
    """Compute resulting frequencies for a clock tree given user values.

    Expects JSON body:
        { "tree": "mspm0g3507", "values": { "sysosc-freq": 32000000, ... } }
    Returns: { "frequencies": { "node_id": freq_hz, ... } }
    """
    data = request.get_json(force=True)
    tree_id = data.get("tree")
    values = data.get("values", {})

    if not tree_id:
        return jsonify({"error": "Missing 'tree' field"}), 400

    freqs = compute_frequencies(tree_id, values)
    if not freqs:
        return jsonify({"error": f"Clock tree '{tree_id}' not found"}), 404
    return jsonify({"frequencies": freqs})


@app.route("/api/generate-clock-config", methods=["POST"])
def api_generate_clock_config():
    """Generate DTS overlay + prj.conf for clock configuration.

    Expects JSON body:
        { "tree": "mspm0g3507", "values": { "sysosc-freq": 32000000, ... } }
    Returns: { "overlay": "...", "prj_conf": "...", "frequencies": {...} }
    """
    data = request.get_json(force=True)
    tree_id = data.get("tree")
    values = data.get("values", {})

    if not tree_id:
        return jsonify({"error": "Missing 'tree' field"}), 400

    result = generate_clock_config(tree_id, values)
    if not result["overlay"] and not result["prj_conf"]:
        return jsonify({"error": f"Clock tree '{tree_id}' not found"}), 404
    return jsonify(result)


# ── Import / Parse existing overlay + conf ────────────────────────────

@app.route("/api/import-config", methods=["POST"])
def import_config():
    """
    Parse existing .overlay and prj.conf files back into pin configurator state.

    Accepts either JSON body:
        { "overlay": "...", "conf": "...", "board_name": "lp_mspm0g3507" }
    or multipart/form-data with files named 'overlay' and/or 'conf'.

    Returns the parsed pin assignments, peripherals, and Kconfig entries.
    """
    overlay_text = ""
    conf_text = ""
    board_name = ""

    if request.is_json:
        body = request.get_json(force=True)
        overlay_text = body.get("overlay", "")
        conf_text = body.get("conf", "")
        board_name = body.get("board_name", "")
    else:
        # Multipart file upload
        if "overlay" in request.files:
            overlay_text = request.files["overlay"].read().decode("utf-8", errors="replace")
            if not board_name:
                fname = request.files["overlay"].filename or ""
                board_name = fname.replace(".overlay", "").split("/")[-1].split("\\")[-1]
        if "conf" in request.files:
            conf_text = request.files["conf"].read().decode("utf-8", errors="replace")
        board_name = request.form.get("board_name", board_name)

    if not overlay_text and not conf_text:
        return jsonify({"error": "No overlay or conf content provided"}), 400

    result = parse_import(overlay_text, conf_text, board_name)
    return jsonify(import_result_to_json(result))


@app.route("/api/scan-project", methods=["POST"])
def scan_project():
    """
    Scan a Zephyr project directory for existing overlay and conf files.

    JSON body:
        { "project_path": "C:/path/to/app" }

    Finds all .overlay and .conf files in the project and its boards/ subdir.
    Returns a list of discovered files that can be imported.
    """
    body = request.get_json(force=True)
    project = pathlib.Path(body.get("project_path", ""))

    if not project.is_dir():
        return jsonify({"error": f"Directory does not exist: {project}"}), 400

    found = []

    # Search project root and boards/ subdirectory
    search_dirs = [project]
    boards_dir = project / "boards"
    if boards_dir.is_dir():
        search_dirs.append(boards_dir)

    for d in search_dirs:
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix in (".overlay", ".conf"):
                rel = f.relative_to(project)
                found.append({
                    "path": str(f),
                    "relative": str(rel),
                    "name": f.name,
                    "type": f.suffix.lstrip("."),
                    "size": f.stat().st_size,
                    "content": f.read_text(encoding="utf-8", errors="replace"),
                })

    # Also check for prj.conf in root
    prj_conf = project / "prj.conf"
    if prj_conf.is_file() and not any(f["name"] == "prj.conf" for f in found):
        found.append({
            "path": str(prj_conf),
            "relative": "prj.conf",
            "name": "prj.conf",
            "type": "conf",
            "size": prj_conf.stat().st_size,
            "content": prj_conf.read_text(encoding="utf-8", errors="replace"),
        })

    return jsonify({"files": found})


# ── Datasheet auto-fetch for unknown MCUs ─────────────────────────────

@app.route("/api/identify-mcu", methods=["POST"])
def api_identify_mcu():
    """
    Identify vendor and get datasheet URLs for an MCU part number.

    JSON body:
        { "part_number": "MSPM0G3507" }

    Returns vendor info and candidate datasheet URLs without downloading.
    """
    body = request.get_json(force=True)
    pn = body.get("part_number", "").strip()

    if not pn:
        return jsonify({"error": "No part_number provided"}), 400

    # First check if we already have this board
    pn_lower = pn.lower().replace("-", "").replace("_", "")
    existing = None
    for bid in BOARDS:
        if bid.lower().replace("-", "").replace("_", "") == pn_lower:
            existing = bid
            break

    result = identify_vendor(pn)
    return jsonify({
        "part_number": pn,
        "known": result is not None,
        "existing_board": existing,
        "vendor": result.vendor if result else None,
        "vendor_name": result.vendor_name if result else None,
        "family": result.family if result else None,
        "datasheet_urls": result.datasheet_urls if result else [],
    })


@app.route("/api/fetch-datasheet", methods=["POST"])
def api_fetch_datasheet():
    """
    Download and parse a datasheet PDF for an MCU part number.

    JSON body:
        { "part_number": "MSPM0G3507", "url": "..."/optional }

    If url is provided, downloads from that URL directly.
    Otherwise auto-detects vendor and tries known URL patterns.
    After download, parses the PDF and stores the result as a parse job.
    """
    body = request.get_json(force=True)
    pn = body.get("part_number", "").strip()
    url = body.get("url", "").strip() or None

    if not pn:
        return jsonify({"error": "No part_number provided"}), 400

    upload_dir = _UPLOAD_DIR

    try:
        info, message = fetch_and_parse(pn, output_dir=upload_dir, url=url)
    except Exception as exc:
        log.exception("Datasheet fetch/parse failed for %s", pn)
        return jsonify({"error": f"Failed: {exc}"}), 500

    if info is None:
        return jsonify({"error": message}), 404

    # Store as a parse job so it can be used for package generation
    job_id = uuid.uuid4().hex[:12]
    _PARSED_JOBS[job_id] = {
        "filename": f"{pn}_datasheet.pdf",
        "upload_path": "",
        "info": info,
    }

    return jsonify({
        "job_id": job_id,
        "message": message,
        "part_number": pn,
        "result": _datasheet_to_json(info),
    })


# ── Driver Generator ─────────────────────────────────────────────────

@app.route("/api/driver-templates", methods=["GET"])
def api_driver_templates():
    """List available driver scaffolding templates."""
    templates = []
    for dt in DRIVER_TYPES:
        templates.append({
            "type": dt,
            "description": {
                "sensor": "Sensor API (sample_fetch / channel_get)",
                "gpio": "GPIO controller driver",
                "i2c": "I2C bus device driver",
                "spi": "SPI bus device driver",
                "uart": "UART serial driver",
                "pwm": "PWM output driver",
                "adc": "ADC channel driver",
                "custom": "Bare DEVICE_DT_INST_DEFINE skeleton",
            }.get(dt, dt),
        })
    return jsonify(templates)


@app.route("/api/generate-driver", methods=["POST"])
def api_generate_driver():
    """Generate Zephyr driver boilerplate from a specification.

    Request JSON:
        name:          str   driver name (e.g. "my_sensor")
        driver_type:   str   one of DRIVER_TYPES
        compatible:    str   DT compatible (e.g. "vendor,my-sensor")
        bus:           str   "i2c" | "spi" | "none"
        description:   str   human-readable description
        has_interrupt: bool  include IRQ boilerplate
        registers:     list  [{name, address, size, rw}, ...]
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    try:
        spec = spec_from_json(data)
        drv = generate_driver(spec)
        return jsonify(driver_to_json(drv))
    except Exception as exc:
        log.exception("Driver generation failed")
        return jsonify({"error": str(exc)}), 500


# ── Sensor datasheet parsing ─────────────────────────────────────────

_SENSOR_JOBS: dict[str, dict] = {}


@app.route("/api/parse-sensor-pdf", methods=["POST"])
def parse_sensor_pdf():
    """Upload and parse a sensor/IC datasheet PDF for register map extraction.

    Accepts multipart/form-data with field 'pdf'.
    Returns the sensor info including register map, addresses, and device summary.
    """
    if "pdf" not in request.files:
        return jsonify({"error": "No 'pdf' file in request"}), 400

    f = request.files["pdf"]
    if not f.filename or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "File must be a .pdf"}), 400

    safe_name = secure_filename(f.filename)
    job_id = uuid.uuid4().hex[:12]
    upload_path = _UPLOAD_DIR / f"{job_id}_{safe_name}"
    f.save(str(upload_path))

    try:
        info = parse_sensor_datasheet(str(upload_path), verbose=False)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        log.exception("Sensor PDF parsing failed")
        return jsonify({"error": f"Sensor PDF parsing failed: {exc}"}), 500

    _SENSOR_JOBS[job_id] = {
        "filename": safe_name,
        "upload_path": str(upload_path),
        "info": info,
    }

    return jsonify({
        "job_id": job_id,
        "filename": safe_name,
        "result": sensor_info_to_json(info),
    })


@app.route("/api/sensor-jobs")
def list_sensor_jobs():
    """List all parsed sensor datasheet jobs."""
    jobs = []
    for jid, jdata in _SENSOR_JOBS.items():
        info: SensorDatasheetInfo = jdata["info"]
        jobs.append({
            "job_id": jid,
            "filename": jdata["filename"],
            "part_number": info.summary.part_number,
            "vendor": info.summary.vendor_name,
            "sensor_type": info.summary.sensor_type,
            "register_count": len(info.register_map.registers),
            "i2c_addresses": [f"0x{a:02X}" for a in info.address.i2c_addresses],
            "protocol": info.address.protocol,
        })
    return jsonify(jobs)


@app.route("/api/sensor-job/<job_id>")
def get_sensor_job(job_id: str):
    """Get full parsed result for a sensor datasheet job."""
    if job_id not in _SENSOR_JOBS:
        return jsonify({"error": "Job not found"}), 404
    info = _SENSOR_JOBS[job_id]["info"]
    return jsonify({
        "job_id": job_id,
        "filename": _SENSOR_JOBS[job_id]["filename"],
        "result": sensor_info_to_json(info),
    })


@app.route("/api/sensor-job/<job_id>/header")
def get_sensor_header(job_id: str):
    """Generate C register-map header for a parsed sensor."""
    if job_id not in _SENSOR_JOBS:
        return jsonify({"error": "Job not found"}), 404
    info: SensorDatasheetInfo = _SENSOR_JOBS[job_id]["info"]
    prefix = request.args.get("prefix", "").strip()
    header_code = generate_register_header(info, prefix)
    return jsonify({
        "job_id": job_id,
        "filename": f"{(info.summary.part_number or 'sensor').lower()}_regs.h",
        "code": header_code,
    })


@app.route("/api/sensor-job/<job_id>/driver", methods=["POST"])
def generate_sensor_driver_from_job(job_id: str):
    """Generate a complete Zephyr driver from a parsed sensor datasheet.

    Merges the extracted register map into a driver_generator DriverSpec
    and returns the full generated driver.

    JSON body (all optional, overrides auto-detected values):
        name:          str  driver name (default: part_number)
        compatible:    str  DT compatible (default: "vendor,part")
        bus:           str  "i2c" | "spi" (default: auto-detected)
        has_interrupt:  bool  include IRQ boilerplate
    """
    if job_id not in _SENSOR_JOBS:
        return jsonify({"error": "Job not found"}), 404

    sensor: SensorDatasheetInfo = _SENSOR_JOBS[job_id]["info"]
    data = request.get_json(force=True) or {}

    # Auto-derive from sensor info
    part = sensor.summary.part_number or "sensor"
    vendor = sensor.summary.vendor or "vendor"
    drv_name = data.get("name", part.lower().replace("-", "_"))
    compat = data.get("compatible", f"{vendor},{part.lower()}")

    # Bus auto-detection
    bus = data.get("bus", "")
    if not bus:
        proto = sensor.address.protocol
        if "i2c" in proto:
            bus = "i2c"
        elif "spi" in proto:
            bus = "spi"
        else:
            bus = "i2c"  # safe default

    # Convert sensor registers to driver RegisterDef list
    from driver_generator import RegisterDef
    reg_defs = [
        RegisterDef(name=r.c_name, address=r.address, size=r.size, rw=r.access)
        for r in sensor.register_map.registers
    ]

    try:
        spec = DriverSpec(
            name=drv_name,
            driver_type="sensor",
            compatible=compat,
            bus=bus,
            description=sensor.summary.description or f"{part} {sensor.summary.sensor_type} driver",
            vendor=vendor,
            has_interrupt=data.get("has_interrupt", False),
            registers=reg_defs,
        )
        drv = generate_driver(spec)
        result = driver_to_json(drv)
        # Also include the register header
        result["register_header"] = generate_register_header(sensor)
        result["register_defines"] = generate_register_defines(sensor)
        return jsonify(result)
    except Exception as exc:
        log.exception("Driver generation from sensor job failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/identify-sensor", methods=["POST"])
def api_identify_sensor():
    """Identify sensor vendor from a part number.

    JSON body: { "part_number": "BME280" }
    """
    body = request.get_json(force=True)
    pn = body.get("part_number", "").strip()
    if not pn:
        return jsonify({"error": "No part_number provided"}), 400

    result = identify_sensor(pn)
    return jsonify({
        "part_number": pn,
        "known": result is not None,
        "vendor": result[0] if result else None,
        "vendor_name": result[1] if result else None,
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
