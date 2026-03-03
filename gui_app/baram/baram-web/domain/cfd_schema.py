#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CoreDB → JSON serialisation helpers.

Each function reads from the baramFlow CoreDB (lxml + XSD) using the exact
same XPath constants as the desktop UI, and returns a plain dict suitable
for ``flask.jsonify()``.

These functions are the **only bridge** between the existing domain modules
and the REST API — the domain modules are NOT modified.
"""

from __future__ import annotations
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Project
# ═══════════════════════════════════════════════════════════════════════════

def project_summary(pm) -> dict:
    """Produce a JSON-safe project summary from a ProjectManager."""
    if not pm.is_open:
        return {}
    return {
        "path": str(pm.current.path),
        "name": pm.current.name,
        "uuid": pm.current.uuid,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  General page
# ═══════════════════════════════════════════════════════════════════════════

def general_to_dict(db) -> dict:
    """Mirrors GeneralPage._load() — reads gravity, solver type, etc."""
    from baramFlow.coredb.general_db import GeneralDB
    gx = GeneralDB.GENERAL_XPATH
    ox = GeneralDB.OPERATING_CONDITIONS_XPATH

    return {
        "solver_type": db.getValue(gx + "/solverType"),
        "time_transient": db.getValue(gx + "/timeTransient") == "true",
        "flow_type": db.getValue(gx + "/flowType"),
        "gravity": [
            _float(db.getValue(gx + "/gravity/direction/x")),
            _float(db.getValue(gx + "/gravity/direction/y")),
            _float(db.getValue(gx + "/gravity/direction/z")),
        ],
        "gravity_magnitude": _float(db.getValue(gx + "/gravity/magnitude")),
        "operating_pressure": _float(db.getValue(ox + "/pressure")),
        "reference_pressure_location": [
            _float(db.getValue(ox + "/referencePressureLocation/x")),
            _float(db.getValue(ox + "/referencePressureLocation/y")),
            _float(db.getValue(ox + "/referencePressureLocation/z")),
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Models page
# ═══════════════════════════════════════════════════════════════════════════

def models_to_dict(db) -> dict:
    from baramFlow.coredb.models_db import ModelsDB
    mx = ModelsDB.MODELS_XPATH
    return {
        "multiphase_model": db.getValue(mx + "/multiphaseModels/model"),
        "energy_model": db.getValue(mx + "/energyModels") == "on",
        "species_model": db.getValue(mx + "/speciesModels"),
        "turbulence": _safe_subtree(db, mx + "/turbulenceModels"),
        "radiation": _safe_subtree(db, mx + "/radiationModels"),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Materials
# ═══════════════════════════════════════════════════════════════════════════

def material_list_to_dict(db) -> list[dict]:
    """List all materials — mirrors MaterialPage._load()."""
    materials = []
    try:
        from baramFlow.coredb.material_db import MaterialDB, MATERIAL_XPATH
        for elem in db.getElements(MATERIAL_XPATH):
            mid = elem.attrib.get("mid", "")
            materials.append({
                "mid": mid,
                "name": db.getValue(MaterialDB.getXPath(mid) + "/name"),
                "phase": db.getValue(MaterialDB.getXPath(mid) + "/phase"),
                "type": db.getValue(MaterialDB.getXPath(mid) + "/type"),
                "formula": _safe_get(db, MaterialDB.getXPath(mid) + "/chemicalFormula"),
            })
    except Exception as exc:
        log.warning("material_list_to_dict: %s", exc)
    return materials


# ═══════════════════════════════════════════════════════════════════════════
#  Boundary Conditions
# ═══════════════════════════════════════════════════════════════════════════

def bc_list_to_dict(db) -> list[dict]:
    """List boundary conditions across all regions."""
    bcs = []
    try:
        regions = db.getRegions()
        for rname in regions:
            for bcid, bcname, bctype in db.getBoundaryConditions(rname):
                bcs.append({
                    "bcid": str(bcid),
                    "name": bcname,
                    "type": bctype,
                    "region": rname,
                })
    except Exception as exc:
        log.warning("bc_list_to_dict: %s", exc)
    return bcs


def bc_detail_to_dict(db, bcid: str) -> dict:
    """Return the full BC subtree as a dict — type-specific fields included."""
    from baramFlow.coredb.boundary_db import BoundaryDB, BoundaryType
    xpath = BoundaryDB.getXPath(bcid)
    physical_type = db.getValue(xpath + "/physicalType")

    result = {
        "bcid": bcid,
        "name": db.getValue(xpath + "/name"),
        "physical_type": physical_type,
        "geometrical_type": _safe_get(db, xpath + "/geometricalType"),
    }

    # Read the type-specific subtree
    bt = BoundaryType(physical_type)
    type_xpath = xpath + "/" + physical_type
    result["type_data"] = _safe_subtree(db, type_xpath)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Monitors
# ═══════════════════════════════════════════════════════════════════════════

def monitors_to_dict(db) -> dict:
    from baramFlow.coredb.monitor_db import MonitorDB

    def _list_monitors(parent_xpath: str, child_tag: str) -> list[dict]:
        monitors = []
        try:
            for elem in db.getElements(f"{parent_xpath}/{child_tag}"):
                name = _elem_text(elem, "name")
                monitors.append({
                    "name": name,
                    "type": child_tag,
                })
        except Exception:
            pass
        return monitors

    return {
        "force_monitors": _list_monitors(MonitorDB.FORCE_MONITORS_XPATH, "forceMonitor"),
        "point_monitors": _list_monitors(MonitorDB.POINT_MONITORS_XPATH, "pointMonitor"),
        "surface_monitors": _list_monitors(MonitorDB.SURFACE_MONITORS_XPATH, "surfaceMonitor"),
        "volume_monitors": _list_monitors(MonitorDB.VOLUME_MONITORS_XPATH, "volumeMonitor"),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Numerical Conditions
# ═══════════════════════════════════════════════════════════════════════════

def numerical_to_dict(db) -> dict:
    from baramFlow.coredb.numerical_db import NumericalDB
    nx = NumericalDB.NUMERICAL_CONDITIONS_XPATH
    return {
        "pressure_velocity_coupling": _safe_get(db, nx + "/pressureVelocityCouplingScheme"),
        "discretization_momentum": _safe_get(db, nx + "/discretizationSchemes/momentum"),
        "discretization_pressure": _safe_get(db, nx + "/discretizationSchemes/pressure"),
        "discretization_energy": _safe_get(db, nx + "/discretizationSchemes/energy"),
        "under_relaxation_pressure": _safe_get(db, nx + "/underRelaxationFactors/pressure"),
        "under_relaxation_momentum": _safe_get(db, nx + "/underRelaxationFactors/momentum"),
        "under_relaxation_energy": _safe_get(db, nx + "/underRelaxationFactors/energy"),
        "under_relaxation_turbulence": _safe_get(db, nx + "/underRelaxationFactors/turbulentKineticEnergy"),
        "max_iterations_per_step": _safe_get(db, nx + "/maxIterationsPerTimeStep"),
        "convergence_criteria": _safe_subtree(db, NumericalDB.CONVERGENCE_CRITERIA_XPATH),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Initialization
# ═══════════════════════════════════════════════════════════════════════════

def initialization_to_dict(db) -> dict:
    regions = {}
    try:
        from baramFlow.coredb.initialization_db import InitializationDB
        from baramFlow.coredb.region_db import RegionDB
        for rname in db.getRegions():
            ix = InitializationDB.getXPath(rname)
            regions[rname] = {
                "velocity": [
                    _safe_get(db, ix + "/initialValues/velocity/x"),
                    _safe_get(db, ix + "/initialValues/velocity/y"),
                    _safe_get(db, ix + "/initialValues/velocity/z"),
                ],
                "pressure": _safe_get(db, ix + "/initialValues/pressure"),
                "temperature": _safe_get(db, ix + "/initialValues/temperature"),
                "scale_of_velocity": _safe_get(db, ix + "/initialValues/scaleOfVelocity"),
                "turb_intensity": _safe_get(db, ix + "/initialValues/turbulentIntensity"),
                "turb_viscosity_ratio": _safe_get(db, ix + "/initialValues/turbulentViscosity"),
            }
    except Exception as exc:
        log.warning("initialization_to_dict: %s", exc)
    return {"regions": regions}


# ═══════════════════════════════════════════════════════════════════════════
#  Run Conditions
# ═══════════════════════════════════════════════════════════════════════════

def run_conditions_to_dict(db) -> dict:
    from baramFlow.coredb.run_calculation_db import RunCalculationDB
    rx = RunCalculationDB.RUN_CALCULATION_XPATH
    return {
        "time_stepping_method": _safe_get(db, rx + "/timeSteppingMethod"),
        "time_step_size": _safe_get(db, rx + "/timeStepSize"),
        "max_courant_number": _safe_get(db, rx + "/maxCourantNumber"),
        "end_time": _safe_get(db, rx + "/endTime"),
        "num_iterations": _safe_get(db, rx + "/numberOfIterations"),
        "report_interval": _safe_get(db, rx + "/reportIntervalSteps"),
        "save_interval": _safe_get(db, rx + "/saveIntervalSteps"),
        "retain_only_last": _safe_get(db, rx + "/retainOnlyMostRecentFiles"),
        "data_write_format": _safe_get(db, rx + "/dataWriteFormat"),
        "data_write_precision": _safe_get(db, rx + "/dataWritePrecision"),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════

def _float(s) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _safe_get(db, xpath: str) -> str | None:
    try:
        return db.getValue(xpath)
    except Exception:
        return None


def _safe_subtree(db, xpath: str) -> dict | None:
    """Try to read an XML subtree as a dict via getBulk()."""
    try:
        return db.getBulk(xpath)
    except Exception:
        return None


def _elem_text(elem, child_tag: str) -> str:
    """Read text of a child element from an lxml element."""
    try:
        child = elem.find(f"{{{elem.nsmap[None]}}}{child_tag}" if elem.nsmap.get(None)
                          else child_tag)
        return child.text if child is not None else ""
    except Exception:
        return ""
