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
from domain.floefd_features import floefd_project, FloEFDProject  # noqa: E402

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
#  FloEFD-style API endpoints
# ═══════════════════════════════════════════════════════════════════════════

# ── FloEFD Project Summary ────────────────────────────────────────────

@app.route("/api/floefd/summary")
def api_floefd_summary():
    return jsonify(floefd_project.summary())


@app.route("/api/floefd/reset", methods=["POST"])
def api_floefd_reset():
    """Reset the FloEFD project state."""
    global floefd_project
    from domain.floefd_features import FloEFDProject as FP
    floefd_project = FP()
    # Update the module-level reference too
    import domain.floefd_features as ff_mod
    ff_mod.floefd_project = floefd_project
    return jsonify({"success": True, "id": floefd_project.id})


# ── L2: Geometry Preparation ─────────────────────────────────────────

@app.route("/api/floefd/geometry")
def api_floefd_geometry_list():
    return jsonify([g.to_dict() for g in floefd_project.geometry_parts])


@app.route("/api/floefd/geometry", methods=["POST"])
def api_floefd_geometry_add():
    body = request.get_json(force=True)
    part = floefd_project.add_geometry(
        name=body.get("name", "Part"),
        file_path=body.get("file_path", ""),
        file_type=body.get("file_type", ""),
    )
    # Update optional fields
    for key in ("num_faces", "num_vertices", "is_fluid_region",
                "is_solid_region", "color", "transparency",
                "file_origin", "cad_source", "tags"):
        if key in body:
            setattr(part, key, body[key])
    if "bounding_box" in body:
        part.bounding_box = body["bounding_box"]
    return jsonify(part.to_dict())


@app.route("/api/floefd/geometry/<part_id>", methods=["DELETE"])
def api_floefd_geometry_delete(part_id):
    if floefd_project.remove_geometry(part_id):
        return jsonify({"success": True})
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>", methods=["PUT"])
def api_floefd_geometry_update(part_id):
    body = request.get_json(force=True)
    part = floefd_project.update_geometry(part_id, body)
    if part:
        return jsonify(part.to_dict())
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>/suppress", methods=["POST"])
def api_floefd_geometry_suppress(part_id):
    body = request.get_json(force=True)
    part = floefd_project.suppress_geometry(part_id, body.get("suppress", True))
    if part:
        return jsonify(part.to_dict())
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>/disable", methods=["POST"])
def api_floefd_geometry_disable(part_id):
    body = request.get_json(force=True)
    part = floefd_project.disable_geometry(part_id, body.get("disabled", True))
    if part:
        return jsonify(part.to_dict())
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>/replace", methods=["POST"])
def api_floefd_geometry_replace(part_id):
    body = request.get_json(force=True)
    part = floefd_project.replace_geometry(part_id, body.get("replacement_note", ""))
    if part:
        return jsonify(part.to_dict())
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>/diagnostics", methods=["POST"])
def api_floefd_geometry_diagnostics(part_id):
    result = floefd_project.run_import_diagnostics(part_id)
    if result:
        return jsonify(result.to_dict())
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>/heal", methods=["POST"])
def api_floefd_geometry_heal(part_id):
    result = floefd_project.heal_geometry(part_id)
    return jsonify(result)


@app.route("/api/floefd/geometry/<part_id>/lid", methods=["POST"])
def api_floefd_geometry_lid_add(part_id):
    body = request.get_json(force=True)
    lid = floefd_project.add_lid(
        part_id,
        name=body.get("name", "Lid"),
        opening_type=body.get("opening_type", "inlet"),
    )
    if lid:
        return jsonify(lid)
    return jsonify({"error": "Part not found"}), 404


@app.route("/api/floefd/geometry/<part_id>/lid/<lid_id>", methods=["DELETE"])
def api_floefd_geometry_lid_delete(part_id, lid_id):
    if floefd_project.remove_lid(part_id, lid_id):
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/floefd/geometry/check-all", methods=["POST"])
def api_floefd_geometry_check_all():
    result = floefd_project.check_all_geometry()
    return jsonify(result)


# ── L3: Analysis Setup ───────────────────────────────────────────────

@app.route("/api/floefd/analysis-setup")
def api_floefd_analysis_setup():
    return jsonify({
        "analysis_type": floefd_project.analysis_type,
        "heat_transfer": floefd_project.heat_transfer.to_dict(),
        "computational_domain": floefd_project.computational_domain.to_dict(),
        "config": floefd_project.analysis_config.to_dict(),
    })


@app.route("/api/floefd/analysis-setup", methods=["PUT"])
def api_floefd_analysis_setup_save():
    body = request.get_json(force=True)
    if "analysis_type" in body:
        floefd_project.analysis_type = body["analysis_type"]
        floefd_project.analysis_config.analysis_type = body["analysis_type"]

    ht = body.get("heat_transfer", {})
    for key in ("conduction_enabled", "convection_enabled", "radiation_enabled",
                "radiation_model", "default_solid_conductivity", "default_htc",
                "default_emissivity", "heat_conduction_in_solids",
                "heat_conduction_solids_only", "radiation_environment",
                "radiation_solar", "radiation_absorption", "radiation_spectrum"):
        if key in ht:
            setattr(floefd_project.heat_transfer, key, ht[key])

    cd = body.get("computational_domain", {})
    for key in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max",
                "symmetry_x", "symmetry_y", "symmetry_z"):
        if key in cd:
            setattr(floefd_project.computational_domain, key, cd[key])

    cfg = body.get("config", {})
    ac = floefd_project.analysis_config
    for key in ("exclude_cavities", "exclude_internal_space", "reference_axis",
                "time_dependent", "gravity_enabled", "gravity_x", "gravity_y",
                "gravity_z", "rotation_enabled", "rotation_rpm", "rotation_axis",
                "unit_system", "temperature_unit", "fluid_type", "selected_fluids",
                "selected_solids", "flow_options_cavitation", "flow_options_humidity",
                "wall_thermal_condition", "wall_radiative_surface",
                "wall_outer_radiative", "wall_roughness",
                "ic_pressure", "ic_temperature", "ic_velocity_x", "ic_velocity_y",
                "ic_velocity_z", "ic_turbulence_intensity", "ic_turbulence_length",
                "ic_solid_temperature", "ic_definition",
                "result_resolution_level", "manual_gap_size", "min_gap_size",
                "manual_wall_thickness", "min_wall_thickness",
                "narrow_channel_refinement", "optimize_thin_walls",
                "project_name", "project_comments", "configuration_name"):
        if key in cfg:
            setattr(ac, key, cfg[key])

    return jsonify({"success": True})


# ── L4: Boundary Conditions (FloEFD-style) ───────────────────────────

@app.route("/api/floefd/boundary-conditions")
def api_floefd_bc_list():
    return jsonify([bc.to_dict() for bc in floefd_project.boundary_conditions])


@app.route("/api/floefd/boundary-conditions", methods=["POST"])
def api_floefd_bc_add():
    body = request.get_json(force=True)
    bc = floefd_project.add_bc(
        name=body.get("name", "BC"),
        bc_type=body.get("bc_type", "wall"),
    )
    # Set optional fields
    for key in ("velocity", "mass_flow_rate", "volume_flow_rate",
                "pressure", "temperature", "wall_thermal", "wall_heat_flux",
                "wall_htc", "wall_temperature", "wall_roughness", "emissivity"):
        if key in body:
            setattr(bc, key, body[key])
    return jsonify(bc.to_dict())


@app.route("/api/floefd/boundary-conditions/<bc_id>", methods=["PUT"])
def api_floefd_bc_update(bc_id):
    body = request.get_json(force=True)
    bc = floefd_project.update_bc(bc_id, body)
    if bc:
        return jsonify(bc.to_dict())
    return jsonify({"error": "BC not found"}), 404


@app.route("/api/floefd/boundary-conditions/<bc_id>", methods=["DELETE"])
def api_floefd_bc_delete(bc_id):
    if floefd_project.remove_bc(bc_id):
        return jsonify({"success": True})
    return jsonify({"error": "BC not found"}), 404


# ── L5: Meshing ──────────────────────────────────────────────────────

from domain.floefd_features import LocalMeshRegion, MeshStudyEntry

@app.route("/api/floefd/mesh")
def api_floefd_mesh_settings():
    return jsonify(floefd_project.mesh_settings.to_dict())


@app.route("/api/floefd/mesh", methods=["PUT"])
def api_floefd_mesh_save():
    body = request.get_json(force=True)
    ms = floefd_project.mesh_settings
    # Accept ALL mesh setting fields dynamically
    for k, v in body.items():
        if hasattr(ms, k) and k not in ("local_meshes", "mesh_study_entries",
                                         "control_planes", "display_selected_components"):
            setattr(ms, k, v)
    # Handle nested lists specially
    if "control_planes" in body:
        ms.control_planes = body["control_planes"]
    if "display_selected_components" in body:
        ms.display_selected_components = body["display_selected_components"]
    return jsonify({"success": True})


@app.route("/api/floefd/mesh/generate", methods=["POST"])
def api_floefd_mesh_generate():
    result = floefd_project.generate_mesh()
    return jsonify(result)


# ── L5: Local Initial Meshes ─────────────────────────────────────────

@app.route("/api/floefd/mesh/local-meshes")
def api_floefd_local_meshes_list():
    return jsonify([lm if isinstance(lm, dict) else lm.to_dict()
                    for lm in floefd_project.mesh_settings.local_meshes])


@app.route("/api/floefd/mesh/local-meshes", methods=["POST"])
def api_floefd_local_meshes_add():
    body = request.get_json(force=True)
    import uuid
    lm = LocalMeshRegion(id=uuid.uuid4().hex[:8])
    for k, v in body.items():
        if hasattr(lm, k) and k != "id":
            setattr(lm, k, v)
    floefd_project.mesh_settings.local_meshes.append(lm)
    return jsonify(lm.to_dict())


@app.route("/api/floefd/mesh/local-meshes/<lm_id>", methods=["PUT"])
def api_floefd_local_meshes_update(lm_id):
    body = request.get_json(force=True)
    for lm in floefd_project.mesh_settings.local_meshes:
        obj = lm if not isinstance(lm, dict) else None
        if obj and obj.id == lm_id:
            for k, v in body.items():
                if hasattr(obj, k) and k != "id":
                    setattr(obj, k, v)
            return jsonify(obj.to_dict())
    return jsonify({"error": "Not found"}), 404


@app.route("/api/floefd/mesh/local-meshes/<lm_id>", methods=["DELETE"])
def api_floefd_local_meshes_delete(lm_id):
    ms = floefd_project.mesh_settings
    before = len(ms.local_meshes)
    ms.local_meshes = [lm for lm in ms.local_meshes
                       if (lm.id if not isinstance(lm, dict) else lm.get("id")) != lm_id]
    if len(ms.local_meshes) < before:
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/floefd/mesh/local-meshes/delete-all", methods=["POST"])
def api_floefd_local_meshes_delete_all():
    floefd_project.mesh_settings.local_meshes = []
    return jsonify({"success": True})


# ── L5: Control Planes ───────────────────────────────────────────────

@app.route("/api/floefd/mesh/control-planes")
def api_floefd_control_planes_list():
    return jsonify(floefd_project.mesh_settings.control_planes)


@app.route("/api/floefd/mesh/control-planes", methods=["PUT"])
def api_floefd_control_planes_save():
    body = request.get_json(force=True)
    floefd_project.mesh_settings.control_planes = body.get("planes", [])
    return jsonify({"success": True})


# ── L5: Mesh Study / Sensitivity ─────────────────────────────────────

@app.route("/api/floefd/mesh/study")
def api_floefd_mesh_study_list():
    return jsonify([e if isinstance(e, dict) else e.to_dict()
                    for e in floefd_project.mesh_settings.mesh_study_entries])


@app.route("/api/floefd/mesh/study", methods=["POST"])
def api_floefd_mesh_study_add():
    body = request.get_json(force=True)
    entry = MeshStudyEntry(
        mesh_count=body.get("mesh_count", 0),
        dp_value=body.get("dp_value", 0.0),
        percent_delta=body.get("percent_delta", 0.0),
    )
    floefd_project.mesh_settings.mesh_study_entries.append(entry)
    return jsonify(entry.to_dict())


@app.route("/api/floefd/mesh/study/run", methods=["POST"])
def api_floefd_mesh_study_run():
    """Simulate a mesh sensitivity study — run 4-5 refinement levels."""
    import math
    ms = floefd_project.mesh_settings
    ms.mesh_study_entries = []
    base_dp = 420000.0
    base_cells = 145000
    for i, mult in enumerate([1, 2.6, 6.8, 10.0, 15.0]):
        cells = int(base_cells * mult)
        dp = base_dp * (0.85 ** i) + (5000 * math.sin(i * 0.5))
        pct = 0.0 if i == 0 else abs(dp - prev_dp) / prev_dp * 100
        ms.mesh_study_entries.append(MeshStudyEntry(
            mesh_count=cells, dp_value=round(dp, 1), percent_delta=round(pct, 1)
        ))
        prev_dp = dp
    return jsonify([e.to_dict() for e in ms.mesh_study_entries])


# ── L5: Mesh Summary ─────────────────────────────────────────────────

@app.route("/api/floefd/mesh/summary")
def api_floefd_mesh_summary():
    ms = floefd_project.mesh_settings
    return jsonify({
        "settings": ms.to_dict(),
        "local_mesh_count": len(ms.local_meshes),
        "control_plane_count": len(ms.control_planes),
        "study_entries": len(ms.mesh_study_entries),
        "has_mesh": ms.total_cells > 0,
    })


# ── L4b / L6: Goals ──────────────────────────────────────────────────

@app.route("/api/floefd/goals")
def api_floefd_goals_list():
    return jsonify([g.to_dict() for g in floefd_project.goals])


@app.route("/api/floefd/goals", methods=["POST"])
def api_floefd_goals_add():
    body = request.get_json(force=True)
    goal = floefd_project.add_goal(
        name=body.get("name", "Goal"),
        goal_type=body.get("goal_type", "surface"),
        parameter=body.get("parameter", "temperature"),
    )
    # Set ALL optional L4b fields from body
    _GOAL_FIELDS = (
        "component", "use_for_convergence", "target_value", "delta_criteria",
        "faces", "bodies", "point_x", "point_y", "point_z", "point_method",
        "use_min", "use_av", "use_max", "use_bulk_av",
        "name_template", "convergence_mode", "tolerance_value",
        "expression", "dimensionality", "equation_parameters",
        "filter_out_of_domain", "filter_outer_faces", "filter_fluid_contacting",
        "keep_outer_and_fluid", "is_associated", "source_feature_type", "source_feature_id",
    )
    for key in _GOAL_FIELDS:
        if key in body:
            setattr(goal, key, body[key])
    return jsonify(goal.to_dict())


@app.route("/api/floefd/goals/<goal_id>", methods=["PUT"])
def api_floefd_goals_update(goal_id):
    body = request.get_json(force=True)
    for g in floefd_project.goals:
        if g.id == goal_id:
            for k, v in body.items():
                if hasattr(g, k) and k != "id":
                    setattr(g, k, v)
            return jsonify(g.to_dict())
    return jsonify({"error": "Goal not found"}), 404


@app.route("/api/floefd/goals/<goal_id>", methods=["DELETE"])
def api_floefd_goals_delete(goal_id):
    if floefd_project.remove_goal(goal_id):
        return jsonify({"success": True})
    return jsonify({"error": "Goal not found"}), 404


# ── L4b: Goals Summary (grouped by type) ─────────────────────────────

@app.route("/api/floefd/goals/summary")
def api_floefd_goals_summary():
    goals = floefd_project.goals
    by_type = {}
    for gt in ("global", "point", "surface", "volume", "equation"):
        by_type[gt] = [g.to_dict() for g in goals if g.goal_type == gt]
    return jsonify({
        "goals": [g.to_dict() for g in goals],
        "by_type": by_type,
        "total": len(goals),
        "converged": sum(1 for g in goals if g.is_converged),
        "for_convergence": sum(1 for g in goals if g.use_for_convergence),
        "finish_conditions": floefd_project.finish_conditions.to_dict(),
        "associated_goals_config": floefd_project.associated_goals_config.to_dict(),
    })


# ── L4b: Finish Conditions ───────────────────────────────────────────

@app.route("/api/floefd/goals/finish-conditions")
def api_floefd_finish_conditions_get():
    return jsonify(floefd_project.finish_conditions.to_dict())


@app.route("/api/floefd/goals/finish-conditions", methods=["PUT"])
def api_floefd_finish_conditions_put():
    body = request.get_json(force=True)
    fc = floefd_project.finish_conditions
    for k, v in body.items():
        if hasattr(fc, k):
            setattr(fc, k, v)
    return jsonify(fc.to_dict())


# ── L4b: Associated Goals Config ─────────────────────────────────────

@app.route("/api/floefd/goals/associated-config")
def api_floefd_associated_goals_get():
    return jsonify(floefd_project.associated_goals_config.to_dict())


@app.route("/api/floefd/goals/associated-config", methods=["PUT"])
def api_floefd_associated_goals_put():
    body = request.get_json(force=True)
    ag = floefd_project.associated_goals_config
    for k, v in body.items():
        if hasattr(ag, k):
            setattr(ag, k, v)
    return jsonify(ag.to_dict())


# ── L4b: Goal Parameters List (reference data) ───────────────────────

GOAL_PARAMETERS = [
    # Left column from slide
    {"name": "Static Pressure",        "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Total Pressure",         "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Dynamic Pressure",       "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Temperature (Fluid)",    "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Mean Radiant Temperature","global": True, "surface": True, "volume": True, "point": True},
    {"name": "Operative Temperature",  "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Draught Rate",           "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Density (Fluid)",        "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Mass (Fluid)",           "global": False, "surface": False, "volume": True, "point": False},
    {"name": "Mass Flow Rate",         "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Velocity",               "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Velocity (X)",           "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Velocity (Y)",           "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Velocity (Z)",           "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Mach Number",            "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Turbulent Viscosity",    "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Turbulent Time",         "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Turbulence Length",      "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Turbulence Intensity",   "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Turbulent Energy",       "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Turbulent Dissipation",  "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Heat Flux",              "global": True, "surface": True, "volume": True, "point": True},
    # Right column from slide
    {"name": "Heat Flux (X)",          "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Heat Flux (Y)",          "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Heat Flux (Z)",          "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Heat Transfer Rate",     "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Total Enthalpy Rate",    "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Normal Force",           "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Normal Force (X)",       "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Normal Force (Y)",       "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Normal Force (Z)",       "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Force",                  "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Force (X)",              "global": False, "surface": True, "volume": True, "point": False},
    {"name": "Force (Y)",              "global": False, "surface": True, "volume": True, "point": False},
    {"name": "Force (Z)",              "global": False, "surface": True, "volume": True, "point": False},
    {"name": "Friction Force",         "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Friction Force (X)",     "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Friction Force (Y)",     "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Friction Force (Z)",     "global": False, "surface": True, "volume": False, "point": False},
    {"name": "Torque (X)",             "global": False, "surface": True, "volume": True, "point": False},
    {"name": "Torque (Y)",             "global": False, "surface": True, "volume": True, "point": False},
    {"name": "Torque (Z)",             "global": False, "surface": True, "volume": True, "point": False},
    {"name": "Temperature (Solid)",    "global": True, "surface": True, "volume": True, "point": True},
    {"name": "Mass (Solid)",           "global": False, "surface": False, "volume": True, "point": False},
]

@app.route("/api/floefd/goals/parameters")
def api_floefd_goal_parameters():
    """Return the full parameter matrix from the Goals/Parameters slide."""
    return jsonify(GOAL_PARAMETERS)


# ── L6: Solver ───────────────────────────────────────────────────────

@app.route("/api/floefd/solver")
def api_floefd_solver_config():
    return jsonify(floefd_project.solver_config.to_dict())


@app.route("/api/floefd/solver", methods=["PUT"])
def api_floefd_solver_save():
    body = request.get_json(force=True)
    sc = floefd_project.solver_config
    for key in ("max_iterations", "auto_convergence", "convergence_criterion",
                "finish_conditions", "turbulence_model", "wall_function",
                "velocity_relaxation", "pressure_relaxation", "temperature_relaxation"):
        if key in body:
            setattr(sc, key, body[key])
    return jsonify({"success": True})


@app.route("/api/floefd/solver/run", methods=["POST"])
def api_floefd_solver_run():
    """Run N iterations of the mock solver."""
    body = request.get_json(force=True)
    n = min(body.get("iterations", 10), 200)
    floefd_project.solver_config.convergence_status = "converging"

    results = []
    for _ in range(n):
        entry = floefd_project.simulate_iteration()
        results.append(entry)
        if floefd_project.solver_config.convergence_status in ("converged", "diverging"):
            break

    return jsonify({
        "iterations_run": len(results),
        "status": floefd_project.solver_config.convergence_status,
        "current_iteration": floefd_project.solver_config.current_iteration,
        "latest": results[-1] if results else None,
    })


@app.route("/api/floefd/solver/reset", methods=["POST"])
def api_floefd_solver_reset():
    floefd_project.reset_solver()
    return jsonify({"success": True})


@app.route("/api/floefd/solver/history")
def api_floefd_solver_history():
    return jsonify(floefd_project.iteration_history)


# ── L7: Post Processing ──────────────────────────────────────────────

@app.route("/api/floefd/post/cut-plots")
def api_floefd_cut_plots():
    return jsonify([p.to_dict() for p in floefd_project.cut_plots])


@app.route("/api/floefd/post/cut-plots", methods=["POST"])
def api_floefd_cut_plot_add():
    body = request.get_json(force=True)
    plot = floefd_project.add_cut_plot(
        name=body.get("name", "Cut Plot"),
        parameter=body.get("parameter", "temperature"),
        plane=body.get("plane", "XY"),
    )
    for key in ("offset", "show_contours", "show_isolines", "show_vectors",
                "min_value", "max_value", "num_levels", "color_map"):
        if key in body:
            setattr(plot, key, body[key])
    return jsonify(plot.to_dict())


@app.route("/api/floefd/post/surface-plots")
def api_floefd_surface_plots():
    return jsonify([p.to_dict() for p in floefd_project.surface_plots])


@app.route("/api/floefd/post/surface-plots", methods=["POST"])
def api_floefd_surface_plot_add():
    body = request.get_json(force=True)
    plot = floefd_project.add_surface_plot(
        name=body.get("name", "Surface Plot"),
        parameter=body.get("parameter", "temperature"),
        surface_name=body.get("surface_name", ""),
    )
    return jsonify(plot.to_dict())


# ── L8: Parametric Study ─────────────────────────────────────────────

@app.route("/api/floefd/parametric")
def api_floefd_parametric_list():
    return jsonify([s.to_dict() for s in floefd_project.parametric_studies])


@app.route("/api/floefd/parametric", methods=["POST"])
def api_floefd_parametric_create():
    body = request.get_json(force=True)
    study = floefd_project.create_parametric_study(
        name=body.get("name", "Parametric Study"),
    )
    if "parameters" in body:
        study.parameters = body["parameters"]
    return jsonify(study.to_dict())


@app.route("/api/floefd/parametric/<study_id>/variant", methods=["POST"])
def api_floefd_parametric_add_variant(study_id):
    body = request.get_json(force=True)
    variant = floefd_project.add_variant(
        study_id=study_id,
        name=body.get("name", "Variant"),
        parameters=body.get("parameters", {}),
    )
    if variant:
        return jsonify(variant.to_dict())
    return jsonify({"error": "Study not found"}), 404


@app.route("/api/floefd/parametric/<study_id>/clone", methods=["POST"])
def api_floefd_parametric_clone(study_id):
    body = request.get_json(force=True)
    variant = floefd_project.clone_variant(
        study_id=study_id,
        variant_id=body.get("variant_id", ""),
        new_name=body.get("name", "Clone"),
    )
    if variant:
        return jsonify(variant.to_dict())
    return jsonify({"error": "Study or variant not found"}), 404


@app.route("/api/floefd/parametric/<study_id>/run", methods=["POST"])
def api_floefd_parametric_run(study_id):
    """Simulate running all variants in a parametric study."""
    import time as _time
    for study in floefd_project.parametric_studies:
        if study.id == study_id:
            for v in study.variants:
                obj = v if not isinstance(v, dict) else None
                if obj:
                    obj.status = "running"
                    # Reset and run a short simulation for each variant
                    floefd_project.reset_solver()
                    for _ in range(30):
                        floefd_project.simulate_iteration()
                    obj.status = floefd_project.solver_config.convergence_status
                    obj.mesh_cells = floefd_project.mesh_settings.total_cells
                    # Collect goal results
                    for g in floefd_project.goals:
                        obj.goals_results[g.name] = round(g.current_value, 4)
            return jsonify(study.to_dict())
    return jsonify({"error": "Study not found"}), 404


# ═══════════════════════════════════════════════════════════════════════════
#  L4a: Standard FloEFD Features — CRUD endpoints
# ═══════════════════════════════════════════════════════════════════════════

# Helper: import all feature classes
from domain.floefd_features import (
    ComponentControl, FluidSubdomain, RotatingRegion, SolidMaterial,
    FanFeature, HeatSourceFeature, RadiativeSurface, RadiationSource,
    ContactResistance, ThermoelectricCooler, HeatSinkSimulation,
    PorousMedia, PerforatedPlate, ThermalJoint, InitialConditionLocal,
)

# Feature registry: (url_segment, collection_name, dataclass)
_FEATURE_REGISTRY = [
    ("component-controls",     "component_controls",      ComponentControl),
    ("fluid-subdomains",       "fluid_subdomains",        FluidSubdomain),
    ("rotating-regions",       "rotating_regions",        RotatingRegion),
    ("solid-materials",        "solid_materials",         SolidMaterial),
    ("fan-features",           "fan_features",            FanFeature),
    ("heat-source-features",   "heat_source_features",    HeatSourceFeature),
    ("radiative-surfaces",     "radiative_surfaces",      RadiativeSurface),
    ("radiation-sources",      "radiation_sources",       RadiationSource),
    ("contact-resistances",    "contact_resistances",     ContactResistance),
    ("thermoelectric-coolers", "thermoelectric_coolers",  ThermoelectricCooler),
    ("heatsink-simulations",   "heatsink_simulations",    HeatSinkSimulation),
    ("porous-media",           "porous_media",            PorousMedia),
    ("perforated-plates",      "perforated_plates",       PerforatedPlate),
    ("thermal-joints",         "thermal_joints",          ThermalJoint),
    ("initial-conditions-local","initial_conditions_local", InitialConditionLocal),
]

def _register_feature_routes():
    """Dynamically register GET/POST/PUT/DELETE for each L4a feature type."""
    for url_seg, col_name, cls in _FEATURE_REGISTRY:
        base = f"/api/floefd/features/{url_seg}"

        # LIST
        def make_list(cn=col_name):
            def handler():
                return jsonify([o.to_dict() for o in getattr(floefd_project, cn)])
            return handler

        # ADD
        def make_add(cn=col_name, c=cls):
            def handler():
                body = request.get_json(force=True)
                obj = floefd_project._add_feature(cn, c, body)
                return jsonify(obj.to_dict())
            return handler

        # UPDATE
        def make_update(cn=col_name):
            def handler(fid):
                body = request.get_json(force=True)
                obj = floefd_project._update_feature(cn, fid, body)
                if obj:
                    return jsonify(obj.to_dict())
                return jsonify({"error": "Not found"}), 404
            return handler

        # DELETE
        def make_delete(cn=col_name):
            def handler(fid):
                if floefd_project._remove_feature(cn, fid):
                    return jsonify({"success": True})
                return jsonify({"error": "Not found"}), 404
            return handler

        # Register routes
        app.add_url_rule(base, f"feat_list_{url_seg}", make_list(), methods=["GET"])
        app.add_url_rule(base, f"feat_add_{url_seg}", make_add(), methods=["POST"])
        app.add_url_rule(f"{base}/<fid>", f"feat_update_{url_seg}", make_update(), methods=["PUT"])
        app.add_url_rule(f"{base}/<fid>", f"feat_delete_{url_seg}", make_delete(), methods=["DELETE"])


_register_feature_routes()


# ── Engineering Database endpoint ─────────────────────────────────────

@app.route("/api/floefd/features/engineering-database")
def api_floefd_eng_db():
    return jsonify(floefd_project.engineering_database.to_dict())


# ── L4a: Features summary (all feature counts + items) ───────────────

@app.route("/api/floefd/features/summary")
def api_floefd_features_summary():
    data = {}
    total = 0
    for url_seg, col_name, cls in _FEATURE_REGISTRY:
        items = [o.to_dict() for o in getattr(floefd_project, col_name)]
        data[col_name] = items
        total += len(items)
    # Also include BCs (existing routes) and engineering DB
    bc_items = [o.to_dict() for o in floefd_project.boundary_conditions]
    data["boundary_conditions"] = bc_items
    total += len(bc_items)
    data["engineering_database"] = floefd_project.engineering_database.to_dict()
    data["total_count"] = total
    return jsonify(data)


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
