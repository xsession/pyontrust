#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BaramFlow Web — Flask backend.

Serves the SPA from  web/  and exposes a REST + WebSocket API that wraps
the *existing* baramFlow domain modules (CoreDB, CaseGenerator, Solver, etc.)
with zero modifications to those modules.

Architecture
────────────
Browser (index.html + main.js)
   │  fetch() / WebSocket
   ▼
Flask  (/api/* JSON, /ws/* WebSocket)
   │  imports
   ▼
baramFlow domain  (coredb, openfoam, backends — reused as-is)
"""

import json
import logging
import pathlib
import sys
import uuid

from flask import Flask, jsonify, request, send_from_directory

# ---------------------------------------------------------------------------
# Add the baram project root to sys.path so we can import baramFlow modules
# ---------------------------------------------------------------------------
_HERE = pathlib.Path(__file__).resolve().parent
_BARAM_ROOT = _HERE.parent  # …/baram
if str(_BARAM_ROOT) not in sys.path:
    sys.path.insert(0, str(_BARAM_ROOT))

# ---------------------------------------------------------------------------
# PySide6 shim — install BEFORE any baramFlow import so the Qt resource
# system and QCoreApplication.translate() don't require the real Qt lib.
# ---------------------------------------------------------------------------
_SHIM_DIR = _HERE / "_pyside6_shim"
if str(_SHIM_DIR) not in sys.path:
    sys.path.insert(0, str(_SHIM_DIR))

try:
    import PySide6  # noqa: check if real PySide6 exists
except ImportError:
    # Real PySide6 not installed — register our lightweight shim
    import importlib, types
    _shim_pkg_path = str(_SHIM_DIR)
    # Create the fake PySide6 package from our shim
    import _pyside6_shim
    sys.modules["PySide6"] = _pyside6_shim
    # Create PySide6.QtCore sub-module
    from _pyside6_shim import QtCore as _QtCoreMod
    _qtcore_module = types.ModuleType("PySide6.QtCore")
    for _attr in dir(_QtCoreMod):
        if not _attr.startswith("__"):
            setattr(_qtcore_module, _attr, getattr(_QtCoreMod, _attr))
    # Also copy top-level re-exports
    for _attr in ("QCoreApplication", "QObject", "QLocale", "QRect", "Signal"):
        setattr(_qtcore_module, _attr, getattr(_pyside6_shim, _attr))
    _qtcore_module.qRegisterResourceData = _pyside6_shim._QtCore.qRegisterResourceData
    _qtcore_module.qUnregisterResourceData = _pyside6_shim._QtCore.qUnregisterResourceData
    sys.modules["PySide6.QtCore"] = _qtcore_module
    logging.getLogger("baram-web").info("PySide6 shim installed (headless mode)")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    static_folder=str(_HERE / "web"),
    static_url_path="",
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB (CFD meshes)

log = logging.getLogger("baram-web")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

# ---------------------------------------------------------------------------
# Optional WebSocket support (flask-sock)
# ---------------------------------------------------------------------------
try:
    from flask_sock import Sock
    sock = Sock(app)
    _HAS_SOCK = True
except ImportError:
    _HAS_SOCK = False
    log.warning("flask-sock not installed — WebSocket endpoints disabled. "
                "Install with: pip install flask-sock")

# ---------------------------------------------------------------------------
# Domain singletons
# ---------------------------------------------------------------------------
from domain.project_manager import project_manager  # noqa: E402
from domain.solver_monitor import SolverMonitor, SolverState  # noqa: E402
from domain.cfd_schema import (  # noqa: E402
    project_summary,
    general_to_dict,
    models_to_dict,
    material_list_to_dict,
    bc_list_to_dict,
    bc_detail_to_dict,
    monitors_to_dict,
    numerical_to_dict,
    initialization_to_dict,
    run_conditions_to_dict,
)

_solver_monitor = SolverMonitor()

# Upload directory
_UPLOAD_DIR = _HERE / "_uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
#  Static SPA
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ═══════════════════════════════════════════════════════════════════════════
#  Project endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/project")
def api_project():
    """Current project summary (or null if none open)."""
    if not project_manager.is_open:
        return jsonify(None)
    return jsonify(project_summary(project_manager))


@app.route("/api/project/open", methods=["POST"])
def api_project_open():
    body = request.get_json(force=True)
    path = body.get("path")
    if not path:
        return jsonify({"error": "path is required"}), 400
    try:
        project_manager.open(path)
        return jsonify(project_summary(project_manager))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/project/new", methods=["POST"])
def api_project_new():
    body = request.get_json(force=True)
    path = body.get("path")
    if not path:
        return jsonify({"error": "path is required"}), 400
    try:
        project_manager.create(path)
        return jsonify(project_summary(project_manager))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/project/save", methods=["POST"])
def api_project_save():
    try:
        project_manager.save()
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/project/recent")
def api_project_recent():
    return jsonify(project_manager.list_recent())


# ═══════════════════════════════════════════════════════════════════════════
#  Wizard — apply multi-step project settings
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/wizard/apply", methods=["POST"])
def api_wizard_apply():
    """Apply wizard settings to the currently open project.

    Expects a JSON body with fields matching the wizard steps:
      projectName, analysisType, heatConduction, radiation,
      timeDependent, gravity, rotation, freeSurface,
      selectedFluids, flowType, wallThermalCondition, wallRoughness,
      initPressure, initTemperature, initVelX, initVelY, initVelZ,
      turbulenceIntensity, turbulenceLengthScale
    """
    body = request.get_json(force=True)
    db = project_manager.coredb
    if db is None:
        return jsonify({"error": "no project is open"}), 400

    errors = []

    def _safe_set(xpath, value, label="wizard"):
        try:
            db.setValue(xpath, str(value), label)
        except Exception as exc:
            errors.append(f"{xpath}: {exc}")

    # -- Analysis type (models) -----------------------------------------------
    analysis = body.get("analysisType", "internal")

    # -- Physical features (models) -------------------------------------------
    # Energy equation (implied by heat conduction or radiation)
    energy_on = body.get("heatConduction", False) or body.get("radiation", False)
    _safe_set("/models/energyModels/include", "true" if energy_on else "false")
    _safe_set("/models/radiationModels/include", "true" if body.get("radiation") else "false")

    # Gravity
    if body.get("gravity"):
        gx = body.get("gravityX", 0)
        gy = body.get("gravityY", -9.81)
        gz = body.get("gravityZ", 0)
        _safe_set("/operatingConditions/gravity/direction/x", str(gx))
        _safe_set("/operatingConditions/gravity/direction/y", str(gy))
        _safe_set("/operatingConditions/gravity/direction/z", str(gz))
        # magnitude = sqrt(x² + y² + z²)
        import math
        mag = math.sqrt(float(gx)**2 + float(gy)**2 + float(gz)**2)
        _safe_set("/operatingConditions/gravity/magnitude", str(mag))

    # Time-dependent
    is_transient = body.get("timeDependent", False)

    # Turbulence / flow type
    flow_type = body.get("flowType", "laminarAndTurbulent")
    if flow_type == "laminar":
        _safe_set("/models/turbulenceModels/model", "laminar")
    elif flow_type == "turbulent":
        _safe_set("/models/turbulenceModels/model", "k-epsilon")
    else:
        _safe_set("/models/turbulenceModels/model", "k-epsilon")

    # -- Initial conditions ----------------------------------------------------
    _safe_set("/initialization/initialValues/pressure", str(body.get("initPressure", 101325)))
    _safe_set("/initialization/initialValues/temperature", str(body.get("initTemperature", 293.2)))
    _safe_set("/initialization/initialValues/velocity/x", str(body.get("initVelX", 0)))
    _safe_set("/initialization/initialValues/velocity/y", str(body.get("initVelY", 0)))
    _safe_set("/initialization/initialValues/velocity/z", str(body.get("initVelZ", 0)))

    # -- Save the project after applying all settings ---------------------------
    try:
        project_manager.save()
    except Exception as exc:
        errors.append(f"save: {exc}")

    if errors:
        logging.warning("Wizard apply had %d non-fatal errors: %s", len(errors), errors)
        return jsonify({"success": True, "warnings": errors})
    return jsonify({"success": True})

@app.route("/api/coredb")
def api_coredb_read():
    """Read one or more XPath values.  ?xpath=...&xpath=..."""
    xpaths = request.args.getlist("xpath")
    if not xpaths:
        return jsonify({"error": "provide at least one ?xpath= parameter"}), 400
    db = project_manager.coredb
    result = {}
    for xp in xpaths:
        try:
            result[xp] = db.getValue(xp)
        except Exception as exc:
            result[xp] = {"error": str(exc)}
    return jsonify(result)


@app.route("/api/coredb", methods=["PUT"])
def api_coredb_write():
    """Transactional batch write.  Body: { "writes": [ {xpath, value, label?}, … ] }"""
    body = request.get_json(force=True)
    writes = body.get("writes", [])
    if not writes:
        return jsonify({"error": "empty writes list"}), 400

    db = project_manager.coredb
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    writer = CoreDBWriter()
    for w in writes:
        writer.append(w["xpath"], str(w["value"]), w.get("label", ""))
    error_count = writer.write()
    if error_count:
        first = writer.firstError()
        return jsonify({
            "error": f"{error_count} validation error(s)",
            "first_error": str(first.toMessage()) if first else None,
        }), 422
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════════════
#  Page-level typed endpoints  (replaces ContentPage .ui + .py)
# ═══════════════════════════════════════════════════════════════════════════

# ── General ──────────────────────────────────────────────────────────────

@app.route("/api/pages/general")
def api_page_general():
    return jsonify(general_to_dict(project_manager.coredb))


@app.route("/api/pages/general", methods=["PUT"])
def api_page_general_save():
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    from baramFlow.coredb.general_db import GeneralDB

    writer = CoreDBWriter()
    gx = GeneralDB.GENERAL_XPATH
    ox = GeneralDB.OPERATING_CONDITIONS_XPATH

    if "solver_type" in body:
        writer.append(gx + "/solverType", body["solver_type"], "Solver Type")
    if "time_transient" in body:
        writer.append(gx + "/timeTransient",
                      "true" if body["time_transient"] else "false", "Time")
    if "flow_type" in body:
        writer.append(gx + "/flowType", body["flow_type"], "Flow Type")
    if "gravity" in body:
        g = body["gravity"]
        writer.append(gx + "/gravity/direction/x", str(g[0]), "Gravity X")
        writer.append(gx + "/gravity/direction/y", str(g[1]), "Gravity Y")
        writer.append(gx + "/gravity/direction/z", str(g[2]), "Gravity Z")
    if "operating_pressure" in body:
        writer.append(ox + "/pressure", str(body["operating_pressure"]),
                      "Operating Pressure")

    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ── Models ───────────────────────────────────────────────────────────────

@app.route("/api/pages/models")
def api_page_models():
    return jsonify(models_to_dict(project_manager.coredb))


@app.route("/api/pages/models", methods=["PUT"])
def api_page_models_save():
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    from baramFlow.coredb.models_db import ModelsDB

    writer = CoreDBWriter()
    mx = ModelsDB.MODELS_XPATH
    if "multiphase_model" in body:
        writer.append(mx + "/multiphaseModels/model", body["multiphase_model"],
                      "Multiphase Model")
    if "energy_model" in body:
        writer.append(mx + "/energyModels",
                      "on" if body["energy_model"] else "off", "Energy Model")
    if "species_model" in body:
        writer.append(mx + "/speciesModels", body["species_model"],
                      "Species Model")

    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ── Materials ────────────────────────────────────────────────────────────

@app.route("/api/pages/materials")
def api_page_materials():
    return jsonify(material_list_to_dict(project_manager.coredb))


@app.route("/api/pages/materials/<mid>", methods=["PUT"])
def api_page_material_save(mid):
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    from baramFlow.coredb.material_db import MaterialDB

    xpath = MaterialDB.getXPath(mid)
    writer = CoreDBWriter()
    for key, value in body.items():
        writer.append(f"{xpath}/{key}", str(value), key)
    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ── Boundary Conditions ──────────────────────────────────────────────────

@app.route("/api/boundary-conditions")
def api_bc_list():
    return jsonify(bc_list_to_dict(project_manager.coredb))


@app.route("/api/boundary-conditions/<bcid>")
def api_bc_detail(bcid):
    try:
        return jsonify(bc_detail_to_dict(project_manager.coredb, bcid))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/boundary-conditions/<bcid>", methods=["PUT"])
def api_bc_update(bcid):
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    from baramFlow.coredb.boundary_db import BoundaryDB

    xpath = BoundaryDB.getXPath(bcid)
    writer = CoreDBWriter()
    # Flat key-value writes relative to the BC xpath
    for key, value in body.get("writes", []):
        writer.append(f"{xpath}/{key}", str(value), key)

    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ── Monitors ─────────────────────────────────────────────────────────────

@app.route("/api/monitors")
def api_monitors():
    return jsonify(monitors_to_dict(project_manager.coredb))


# ── Numerical Conditions ─────────────────────────────────────────────────

@app.route("/api/pages/numerical")
def api_page_numerical():
    return jsonify(numerical_to_dict(project_manager.coredb))


@app.route("/api/pages/numerical", methods=["PUT"])
def api_page_numerical_save():
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    from baramFlow.coredb.numerical_db import NumericalDB

    writer = CoreDBWriter()
    nx = NumericalDB.NUMERICAL_CONDITIONS_XPATH
    for key, value in body.items():
        writer.append(f"{nx}/{key}", str(value), key)
    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ── Initialization ───────────────────────────────────────────────────────

@app.route("/api/pages/initialization")
def api_page_initialization():
    return jsonify(initialization_to_dict(project_manager.coredb))


@app.route("/api/pages/initialization", methods=["PUT"])
def api_page_initialization_save():
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter

    writer = CoreDBWriter()
    for w in body.get("writes", []):
        writer.append(w["xpath"], str(w["value"]), w.get("label", ""))
    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ── Run Conditions ───────────────────────────────────────────────────────

@app.route("/api/pages/run-conditions")
def api_page_run_conditions():
    return jsonify(run_conditions_to_dict(project_manager.coredb))


@app.route("/api/pages/run-conditions", methods=["PUT"])
def api_page_run_conditions_save():
    body = request.get_json(force=True)
    from baramFlow.coredb.coredb_writer import CoreDBWriter
    from baramFlow.coredb.run_calculation_db import RunCalculationDB

    writer = CoreDBWriter()
    rx = RunCalculationDB.RUN_CALCULATION_XPATH
    for key, value in body.items():
        writer.append(f"{rx}/{key}", str(value), key)
    error_count = writer.write()
    if error_count:
        return jsonify({"error": f"{error_count} validation error(s)"}), 422
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════════════
#  Solver lifecycle
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/solver/status")
def api_solver_status():
    return jsonify(_solver_monitor.get_status())


@app.route("/api/solver/initialize", methods=["POST"])
def api_solver_initialize():
    """Generate OpenFOAM case files + initialise fields."""
    try:
        project_manager.ensure_open()
        # We import lazily because these modules require CoreDB to exist
        from baramFlow.openfoam.case_generator import CaseGenerator
        from baramFlow.openfoam.file_system import FileSystem

        FileSystem.deleteCalculationResults()
        gen = CaseGenerator()

        # CaseGenerator.setupCase() is async (for qasync), but we run it
        # synchronously here since Flask routes are sync by default.
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(gen.setupCase())
        loop.close()

        return jsonify({"success": True, "message": "Case initialised"})
    except Exception as exc:
        log.exception("solver/initialize failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/solver/start", methods=["POST"])
def api_solver_start():
    """Launch the solver process."""
    try:
        project_manager.ensure_open()
        from baramFlow.backends.factory import get_backend
        from baramFlow.backends.base import BackendContext
        from baramFlow.openfoam.file_system import FileSystem
        from baramFlow.coredb.project import Project

        prj = Project.instance()
        backend = get_backend()
        ctx = BackendContext(
            case_path=FileSystem.caseRoot(),
            project_uuid=str(prj.uuid),
            parallel=prj.parallelEnvironment(),
            extra_env={},
        )
        pid, create_time = backend.launch_live(ctx)
        _solver_monitor.attach(pid, create_time, str(FileSystem.caseRoot()))
        return jsonify({"status": "running", "pid": pid})
    except Exception as exc:
        log.exception("solver/start failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/solver/stop", methods=["POST"])
def api_solver_stop():
    _solver_monitor.stop()
    return jsonify({"status": "stopped"})


@app.route("/api/solver/residuals")
def api_solver_residuals():
    """Return accumulated residual data for the chart."""
    return jsonify(_solver_monitor.residual_history)


# ═══════════════════════════════════════════════════════════════════════════
#  WebSocket — live solver log
# ═══════════════════════════════════════════════════════════════════════════

if _HAS_SOCK:
    @sock.route("/ws/solver-log")
    def ws_solver_log(ws):
        """Stream solver stdout line-by-line to the browser."""
        while True:
            line = _solver_monitor.read_next_log_line(timeout=1.0)
            if line is None:
                # Check if solver is still running
                status = _solver_monitor.get_status()
                if status["state"] in (SolverState.FINISHED.value,
                                        SolverState.ERROR.value,
                                        SolverState.IDLE.value):
                    ws.send(json.dumps({"type": "end", "state": status["state"]}))
                    break
                continue
            ws.send(json.dumps({"type": "log", "text": line}))


# ═══════════════════════════════════════════════════════════════════════════
#  Heat Sources & Fans
# ═══════════════════════════════════════════════════════════════════════════

# In-memory stores (will be persisted to CoreDB later)
_heat_sources = []
_fans = []


@app.route("/api/heat-sources")
def api_heat_sources_list():
    return jsonify(_heat_sources)


@app.route("/api/heat-sources", methods=["POST"])
def api_heat_sources_add():
    body = request.get_json(force=True)
    _heat_sources.append(body)
    return jsonify({"success": True, "count": len(_heat_sources)})


@app.route("/api/fans")
def api_fans_list():
    return jsonify(_fans)


@app.route("/api/fans", methods=["POST"])
def api_fans_add():
    body = request.get_json(force=True)
    _fans.append(body)
    return jsonify({"success": True, "count": len(_fans)})


# ═══════════════════════════════════════════════════════════════════════════
#  Engineering Database
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/engineering-db/<category>")
def api_engineering_db(category):
    """Return engineering database items for a category.
    The full database is client-side for now; this stub allows future
    server-side persistence and custom user items."""
    return jsonify({
        "category": category,
        "message": "Engineering database is client-side for now",
        "items": [],
    })


# ═══════════════════════════════════════════════════════════════════════════
#  Mesh upload
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/mesh/upload", methods=["POST"])
def api_mesh_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    job_id = uuid.uuid4().hex[:12]
    filename = f"{job_id}_{f.filename}"
    path = _UPLOAD_DIR / filename
    f.save(str(path))
    return jsonify({"job_id": job_id, "filename": f.filename, "path": str(path)})


@app.route("/api/mesh/import-path", methods=["POST"])
def api_mesh_import_path():
    """Import a geometry file (or all files in a folder) from a local path."""
    data = request.get_json(force=True)
    src = data.get("path", "").strip()
    if not src:
        return jsonify({"error": "No path provided"}), 400

    import shutil
    src_path = pathlib.Path(src)
    if not src_path.exists():
        return jsonify({"error": f"Path does not exist: {src}"}), 400

    _GEO_EXTS = {".stl", ".step", ".stp", ".iges", ".igs", ".brep", ".brp", ".obj"}
    imported = []

    def _import_file(fp):
        if fp.suffix.lower() not in _GEO_EXTS:
            return
        job_id = uuid.uuid4().hex[:12]
        dest = _UPLOAD_DIR / f"{job_id}_{fp.name}"
        shutil.copy2(str(fp), str(dest))
        imported.append({"name": fp.name, "size": fp.stat().st_size, "dest": str(dest)})

    if src_path.is_file():
        _import_file(src_path)
    elif src_path.is_dir():
        for child in sorted(src_path.iterdir()):
            if child.is_file():
                _import_file(child)

    if not imported:
        return jsonify({"error": f"No geometry files found at: {src}"}), 400
    return jsonify({"imported": imported, "count": len(imported)})


@app.route("/api/mesh/geometries")
def api_mesh_geometries():
    """List uploaded geometry files."""
    files = []
    for p in _UPLOAD_DIR.iterdir():
        if p.suffix.lower() in (".stl", ".step", ".stp", ".iges", ".igs", ".brep", ".brp", ".obj"):
            files.append({"name": p.name, "size": p.stat().st_size})
    return jsonify(files)


@app.route("/api/mesh/geometries/<name>", methods=["DELETE"])
def api_mesh_delete(name):
    """Delete an uploaded geometry file."""
    target = _UPLOAD_DIR / name
    if target.exists():
        target.unlink()
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404


@app.route("/api/browse")
def api_browse():
    """Browse the local filesystem — returns entries in a directory.

    Query params:
        path  – directory to list (default: user home)
        filter – comma-separated extensions to highlight (e.g. .stl,.step)
    """
    base = request.args.get("path", "").strip()
    if not base:
        base = str(pathlib.Path.home())
    p = pathlib.Path(base).resolve()
    if not p.is_dir():
        return jsonify({"error": f"Not a directory: {base}"}), 400

    ext_filter = set()
    filt = request.args.get("filter", "")
    if filt:
        ext_filter = {e.strip().lower() for e in filt.split(",") if e.strip()}

    entries = []
    try:
        for child in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
            try:
                is_dir = child.is_dir()
                entry = {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": is_dir,
                }
                if not is_dir:
                    entry["size"] = child.stat().st_size
                    entry["match"] = child.suffix.lower() in ext_filter if ext_filter else True
                entries.append(entry)
            except PermissionError:
                pass
    except PermissionError:
        return jsonify({"error": f"Permission denied: {base}"}), 403

    # Parent directory for navigation
    parent = str(p.parent) if p.parent != p else None
    return jsonify({"path": str(p), "parent": parent, "entries": entries})


# ═══════════════════════════════════════════════════════════════════════════
#  Error handler
# ═══════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    # If it looks like an API call, return JSON
    if request.path.startswith("/api/") or request.path.startswith("/ws/"):
        return jsonify({"error": "Not found"}), 404
    # Otherwise serve the SPA (client-side routing)
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100, debug=True)
