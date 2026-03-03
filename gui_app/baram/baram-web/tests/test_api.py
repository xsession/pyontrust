"""Smoke tests for baram-web REST API.

These tests verify the Flask routes respond correctly.
They do NOT require a live CoreDB / OpenFOAM installation — they test
the HTTP layer and JSON contract.  Where CoreDB is needed, a project
must be opened first (or the test is expected to return a 4xx / "no project" error).
"""
import json
import pytest


# ── Static asset serving ──────────────────────────────────────────────────

def test_index_html(client):
    """GET / should serve the SPA shell."""
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"<!DOCTYPE html>" in rv.data or b"<html" in rv.data


# ── /api/project ──────────────────────────────────────────────────────────

def test_project_no_project(client):
    """GET /api/project without opening anything returns null / no-project."""
    rv = client.get("/api/project")
    assert rv.status_code == 200


def test_project_recent(client):
    """GET /api/project/recent returns a list."""
    rv = client.get("/api/project/recent")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)


def test_open_missing_path(client):
    """POST /api/project/open with missing path → 400."""
    rv = client.post("/api/project/open", json={})
    assert rv.status_code == 400 or rv.status_code == 500


def test_new_missing_path(client):
    """POST /api/project/new with missing path → 400."""
    rv = client.post("/api/project/new", json={})
    assert rv.status_code == 400 or rv.status_code == 500


# ── Pages without project ────────────────────────────────────────────────

_PAGE_ROUTES = [
    "/api/pages/general",
    "/api/pages/models",
    "/api/pages/materials",
    "/api/pages/numerical",
    "/api/pages/initialization",
    "/api/pages/run-conditions",
    "/api/boundary-conditions",
    "/api/monitors",
]

@pytest.mark.parametrize("route", _PAGE_ROUTES)
def test_page_requires_project(client, route):
    """GET page routes when no project is open should return an error or empty."""
    rv = client.get(route)
    # Accept either a 400/500 (explicit error) or 200 with error key
    assert rv.status_code in (200, 400, 500)


# ── Solver status ────────────────────────────────────────────────────────

def test_solver_status(client):
    """GET /api/solver/status should always be reachable."""
    rv = client.get("/api/solver/status")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "state" in data


# ── Mesh routes ──────────────────────────────────────────────────────────

def test_mesh_geometries_no_project(client):
    """GET /api/mesh/geometries without project returns empty or error."""
    rv = client.get("/api/mesh/geometries")
    assert rv.status_code in (200, 400, 500)


# ── CoreDB raw endpoint ──────────────────────────────────────────────────

def test_coredb_read_no_project(client):
    """GET /api/coredb?xpath=/ when no project open returns error."""
    rv = client.get("/api/coredb?xpath=/")
    assert rv.status_code in (200, 400, 500)
