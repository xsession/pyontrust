"""Gateway security: cross-site blocking, station token, headers, safe expressions."""
from __future__ import annotations

import pytest

pytest.importorskip("flask")

from pyontrust.gateway.safe_expr import ExprError, safe_eval  # noqa: E402

LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
REMOTE = {"REMOTE_ADDR": "192.168.1.50"}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from pyontrust.gateway.app import create_app

    monkeypatch.setenv("PYONTRUST_TOKEN", "s3cret-station-token")
    monkeypatch.delenv("PYONTRUST_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("PYONTRUST_REMOTE_NO_AUTH", raising=False)
    monkeypatch.chdir(tmp_path)
    return create_app(artifacts_root=str(tmp_path / "a"), extra_config={"TESTING": True})


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


# ── cross-site ─────────────────────────────────────────────────────────

def test_same_origin_and_plain_clients_work(client):
    assert client.get("/api/health", environ_base=LOCAL).status_code == 200
    r = client.post("/flowlab/api/execute", json={"blocks": [], "connections": []},
                    headers={"Origin": "http://localhost"}, environ_base=LOCAL)
    assert r.status_code == 200, r.get_json()


@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"},
    {"Origin": "null"},
    {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors"},
    {"Referer": "https://evil.example/page"},
])
def test_cross_site_requests_are_blocked(client, headers):
    r = client.post("/flowlab/api/execute", json={"blocks": [], "connections": []},
                    headers=headers, environ_base=LOCAL)
    assert r.status_code == 403
    assert "Access-Control-Allow-Origin" not in r.headers


def test_cross_site_link_navigation_still_allowed(client):
    r = client.get("/", headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"},
                   environ_base=LOCAL)
    assert r.status_code == 200


def test_allowlisted_origin_gets_cors(tmp_path, monkeypatch):
    from pyontrust.gateway.app import create_app

    monkeypatch.setenv("PYONTRUST_ALLOWED_ORIGINS", "https://dash.lab.local")
    app = create_app(artifacts_root=str(tmp_path / "a"))
    with app.test_client() as c:
        r = c.get("/api/health", headers={"Origin": "https://dash.lab.local"}, environ_base=LOCAL)
        assert r.status_code == 200
        assert r.headers["Access-Control-Allow-Origin"] == "https://dash.lab.local"


# ── station token ──────────────────────────────────────────────────────

def test_remote_clients_need_the_token(client):
    assert client.get("/api/health", environ_base=REMOTE).status_code == 401
    assert client.get("/", environ_base=REMOTE).status_code == 401          # login page
    ok = client.get("/api/health", headers={"Authorization": "Bearer s3cret-station-token"},
                    environ_base=REMOTE)
    assert ok.status_code == 200
    bad = client.get("/api/health", headers={"Authorization": "Bearer nope"}, environ_base=REMOTE)
    assert bad.status_code == 401


def test_token_link_sets_cookie_and_strips_token(client):
    r = client.get("/thermal/?token=s3cret-station-token&x=1", environ_base=REMOTE)
    assert r.status_code == 302
    assert "token=" not in r.headers["Location"] and "x=1" in r.headers["Location"]
    assert "pyontrust_token=" in r.headers["Set-Cookie"] and "HttpOnly" in r.headers["Set-Cookie"]
    assert client.get("/api/health", environ_base=REMOTE).status_code == 200   # cookie now sent


def test_security_headers(client):
    h = client.get("/api/health", environ_base=LOCAL).headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in h["Content-Security-Policy"]


# ── FlowLab: unsafe blocks are off by default ──────────────────────────

def test_shell_block_disabled_by_default(monkeypatch):
    from pyontrust.gateway import flowlab_engine as fe

    monkeypatch.delenv("PYONTRUST_FLOWLAB_UNSAFE", raising=False)
    logs = []
    ctx = type("Ctx", (), {"log": lambda self, m: logs.append(m), "elapsed": 0.0})()
    out = fe._blk_shell_cmd({"command": "echo pwned > /tmp/should_not_exist"}, {}, ctx)
    assert out["exit_code"] == -1 and any("disabled" in m for m in logs)


# ── safe expressions ───────────────────────────────────────────────────

@pytest.mark.parametrize("expr,expected", [
    ("a + b", 5), ("a * 2 ** 3", 16), ("max(a, b) - min(a, b)", 1), ("round(math.sqrt(b), 3)", 1.732),
    ("pi > 3", True), ("'hot' if b > 2 else 'ok'", "hot"), ("[a, b][1]", 3), ("abs(-a) == a and not False", True),
    ("sum(range(4))", 6), ("{'x': a}['x']", 2), ("1 < a < b", True),
])
def test_safe_eval_allows_formulas(expr, expected):
    assert safe_eval(expr, {"a": 2, "b": 3}) == expected


@pytest.mark.parametrize("expr", [
    "().__class__.__base__.__subclasses__()",          # classic sandbox escape
    "a.__class__", "__import__('os')", "open('/etc/passwd')",
    "[x for x in range(3)]", "(lambda: 1)()", "getattr(a, 'real')",
    "math.__dict__", "9 ** 9 ** 9", "'x' * 10**9", "range(10**12)", "f'{a}'",
])
def test_safe_eval_rejects_escapes_and_bombs(expr):
    with pytest.raises(ExprError):
        safe_eval(expr, {"a": 2})
