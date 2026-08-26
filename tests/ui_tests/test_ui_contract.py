"""Static UI contract tests for the gateway's browser surfaces.

These tests intentionally use only the Python standard library.  They catch
broken navigation targets, missing packaged assets, duplicate IDs, and lost
accessibility landmarks without requiring Flask, Selenium, or physical lab
hardware.
"""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "src" / "pyontrust" / "gateway" / "web"

PAGES = {
    "shell": WEB_ROOT / "shell" / "index.html",
    "diagnostic": WEB_ROOT / "diagnostic" / "index.html",
    "hil": WEB_ROOT / "hil" / "index.html",
    "csv": WEB_ROOT / "csv" / "index.html",
    "bench": WEB_ROOT / "bench" / "index.html",
    "flowlab": WEB_ROOT / "flowlab" / "index.html",
    "can": WEB_ROOT / "can" / "index.html",
    "thermal": WEB_ROOT / "thermal" / "index.html",
    "ifdoc": WEB_ROOT / "ifdoc" / "index.html",
    "artifacts": WEB_ROOT / "artifacts" / "index.html",
    "config": WEB_ROOT / "config" / "index.html",
}

EXPECTED_SHELL_ROUTES = {
    "diag": "/diag/",
    "hil": "/hil/",
    "csv": "/csv/",
    "bench": "/bench/",
    "flowlab": "/flowlab/",
    "can": "/can/",
    "thermal": "/thermal/",
    "ifdoc": "/ifdoc/",
    "artifacts": "/artifacts/",
    "config": "/config/",
}


class UiParser(HTMLParser):
    """Collect the small subset of HTML needed by the static contract."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.ids: list[str] = []
        self.h1_count = 0
        self.main_count = 0
        self.title_depth = 0
        self.title_text: list[str] = []
        self.assets: list[str] = []
        self.nav_routes: dict[str, str] = {}
        self.active_tools: list[str] = []
        self.iframe_src: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = values.get("lang")
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "h1":
            self.h1_count += 1
        if tag == "main":
            self.main_count += 1
        if tag == "title":
            self.title_depth += 1
        if tag == "link" and "stylesheet" in values.get("rel", ""):
            self.assets.append(values.get("href", ""))
        if tag == "script" and values.get("src"):
            self.assets.append(values["src"])
        if tag == "a" and values.get("data-tool"):
            tool = values["data-tool"]
            self.nav_routes[tool] = values.get("href", "")
            classes = set(values.get("class", "").split())
            if "active" in classes or values.get("aria-current") == "page":
                self.active_tools.append(tool)
        if tag == "iframe" and values.get("id") == "tool-frame":
            self.iframe_src = values.get("src")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_text.append(data)


def parse(path: Path) -> UiParser:
    parser = UiParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def resolve_asset(url: str) -> Path | None:
    path = urlsplit(url).path
    if path.startswith("/static/shell/"):
        return WEB_ROOT / "shell" / path.removeprefix("/static/shell/")
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[1] == "static":
        return WEB_ROOT / parts[0] / Path(*parts[2:])
    return None


def test_all_primary_pages_exist() -> None:
    missing = [name for name, path in PAGES.items() if not path.is_file()]
    assert not missing, f"Missing primary UI pages: {missing}"


def test_pages_have_single_landmarks_and_unique_ids() -> None:
    failures: list[str] = []
    for name, path in PAGES.items():
        document = parse(path)
        duplicates = [element_id for element_id, count in Counter(document.ids).items() if count > 1]
        if document.lang != "en":
            failures.append(f"{name}: html lang is {document.lang!r}")
        if not "".join(document.title_text).strip():
            failures.append(f"{name}: missing document title")
        if document.h1_count != 1:
            failures.append(f"{name}: expected one h1, got {document.h1_count}")
        if document.main_count != 1:
            failures.append(f"{name}: expected one main, got {document.main_count}")
        if duplicates:
            failures.append(f"{name}: duplicate IDs {duplicates}")
    assert not failures, "\n".join(failures)


def test_all_local_styles_and_scripts_exist() -> None:
    failures: list[str] = []
    for name, path in PAGES.items():
        for url in parse(path).assets:
            if url.startswith(("http://", "https://", "//")):
                failures.append(f"{name}: required remote asset {url}")
                continue
            target = resolve_asset(url)
            if target is not None and not target.is_file():
                failures.append(f"{name}: missing asset {url} -> {target}")
    assert not failures, "\n".join(failures)


def test_every_page_uses_shared_accessibility_foundation() -> None:
    failures = []
    for name, path in PAGES.items():
        assets = set(parse(path).assets)
        if "/static/shell/ui-foundation.css" not in assets:
            failures.append(f"{name}: missing ui-foundation.css")
        if "/static/shell/ui-foundation.js" not in assets:
            failures.append(f"{name}: missing ui-foundation.js")
    assert not failures, "\n".join(failures)


def test_shell_routes_and_default_state_match_content() -> None:
    shell = parse(PAGES["shell"])
    assert shell.nav_routes == EXPECTED_SHELL_ROUTES
    assert shell.active_tools == ["diag"]
    assert shell.iframe_src == "/diag/"


def test_management_destinations_have_real_interfaces() -> None:
    shell_source = PAGES["shell"].read_text(encoding="utf-8")
    assert 'href="/artifacts/"' in shell_source
    assert 'href="/config/"' in shell_source
    assert "/config/api/profiles" not in shell_source

    artifacts_bp = (REPO_ROOT / "src/pyontrust/gateway/blueprints/artifacts.py").read_text(encoding="utf-8")
    config_bp = (REPO_ROOT / "src/pyontrust/gateway/blueprints/config.py").read_text(encoding="utf-8")
    for source in (artifacts_bp, config_bp):
        assert '@bp.route("/")' in source
        assert 'static_url_path="/static"' in source
        assert 'send_from_directory' in source


def test_hil_dashboard_has_no_required_chart_cdn() -> None:
    source = PAGES["hil"].read_text(encoding="utf-8").lower()
    assert "cdn.plot.ly" not in source
    assert "new tracechart" in source
