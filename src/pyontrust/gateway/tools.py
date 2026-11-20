"""Tool registry — the single source of truth for the gateway's tools.

Every tool (id, title, icon, description, navigation group, URL, blueprint,
web directory, activity provider) is declared once here.  Consumers:

* :mod:`pyontrust.gateway.app`             registers the blueprints from it;
* the shell blueprint renders the navigation from it (server-side);
* ``GET /api/tools`` and ``GET /api/activity`` expose it to the browser;
* the UI contract tests enumerate pages / routes from it.

Pure Python on purpose (no Flask import at module level) so the static UI
contract tests can use it without the web stack.
"""
from __future__ import annotations

import html
import importlib
import logging
from dataclasses import asdict, dataclass
from typing import Any, Callable

logger = logging.getLogger("pyontrust.gateway.tools")


@dataclass(frozen=True)
class Tool:
    id: str                 # URL prefix and shell deep-link (#id)
    title: str              # full title (shell header, <title>)
    nav_label: str          # short label in the sidebar
    icon: str
    description: str
    group: str              # key of GROUPS
    blueprint: str          # "module:attr"
    web_dir: str            # folder under gateway/web holding index.html
    activity: str | None = None   # "module:function" -> {"state", "label"} | None
    selftest: str | None = None   # "module:function" -> [{"name", "status", "detail"}]

    @property
    def url(self) -> str:
        return f"/{self.id}/"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("blueprint"); d.pop("activity"); d.pop("selftest")
        d["has_selftest"] = self.selftest is not None
        d["url"] = self.url
        return d


GROUPS: list[tuple[str, str]] = [
    ("operate", "Operate"),
    ("analyse", "Analyse & design"),
    ("manage", "Manage"),
]

_BP = "pyontrust.gateway.blueprints"

TOOLS: list[Tool] = [
    Tool("diag", "Hardware Diagnostic", "Diagnostic", "⌁",
         "Inspect sensors, interfaces, and generated diagnostic reports",
         "operate", f"{_BP}.diagnostic:bp", "diagnostic"),
    Tool("hil", "HIL Dashboard", "HIL Dashboard", "◉",
         "Run and monitor hardware-in-the-loop profiles",
         "operate", f"{_BP}.hil:bp", "hil", activity="pyontrust.gateway.tools:hil_activity",
         selftest="pyontrust.gateway.selftests:hil"),
    Tool("bench", "Lab Bench", "Lab Bench", "▦",
         "Configure and operate connected lab equipment",
         "operate", f"{_BP}.bench:bp", "bench"),
    Tool("can", "CAN Bus", "CAN Bus", "⇄",
         "Capture, transmit, decode, and replay CAN traffic",
         "operate", f"{_BP}.can_diag:bp", "can", activity="pyontrust.gateway.tools:can_activity",
         selftest="pyontrust.gateway.selftests:can"),
    Tool("thermal", "Thermal", "Thermal", "♨",
         "Live thermal image, regions, measurements and long-term tracking",
         "operate", f"{_BP}.thermal_measurement:bp", "thermal",
         activity="pyontrust.gateway.tools:thermal_activity",
         selftest="pyontrust.gateway.selftests:thermal"),
    Tool("micro", "Microscopy", "Microscopy", "🔬",
         "Focus stacking, depth-from-focus, and surface height maps",
         "operate", f"{_BP}.microscopy:bp", "micro",
         selftest="pyontrust.gateway.selftests:micro"),
    Tool("scan3d", "3D Scan", "3D Scan", "⬡",
         "Stereo depth, disparity, and point-cloud analysis",
         "operate", f"{_BP}.scan3d:bp", "scan3d"),
    Tool("spec", "Spectroscopy", "Spectroscopy", "🌈",
         "Slit-image spectrometer: calibrated spectra and emission-line detection",
         "operate", f"{_BP}.spectroscopy:bp", "spec"),
    Tool("waveforms", "Waveforms", "Waveforms", "∿",
         "Oscilloscope, spectrum analyzer and signal generator over Digilent WaveForms hardware",
         "operate", f"{_BP}.waveforms:bp", "waveforms",
         selftest="pyontrust.gateway.selftests:waveforms"),
    Tool("csv", "CSV Plotter", "CSV Plotter", "📈",
         "Explore, compare, and export recorded signals",
         "analyse", f"{_BP}.csv_plotter:bp", "csv"),
    Tool("flowlab", "FlowLab", "FlowLab", "◇",
         "Build executable test workflows as connected blocks",
         "analyse", f"{_BP}.flowlab:bp", "flowlab",
         selftest="pyontrust.gateway.selftests:flowlab"),
    Tool("ifdoc", "Interface Documentation", "Interfaces", "≡",
         "Browse registers, messages, and interface contracts",
         "analyse", f"{_BP}.ifdoc:bp", "ifdoc"),
    Tool("artifacts", "Artifacts", "Artifacts", "▣",
         "Search, inspect, download, and remove test run artifacts",
         "manage", f"{_BP}.artifacts:bp", "artifacts"),
    Tool("config", "Configuration", "Configuration", "⚙",
         "Manage profiles, benches, and reusable limit sets",
         "manage", f"{_BP}.config:bp", "config"),
    Tool("station", "Station", "Station", "🛡",
         "Station health, operator & DUT, instrument calibration, run history, audit trail",
         "manage", f"{_BP}.station:bp", "station",
         activity="pyontrust.gateway.tools:station_activity"),
]

DEFAULT_TOOL = "diag"


def get(tool_id: str) -> Tool:
    for t in TOOLS:
        if t.id == tool_id:
            return t
    raise KeyError(tool_id)


def load(ref: str) -> Any:
    module, _, attr = ref.partition(":")
    return getattr(importlib.import_module(module), attr)


# ═══════════════════════════════════════════════════════════════════════
#  Activity — "what is running on the bench right now", one call per tool
# ═══════════════════════════════════════════════════════════════════════


def activity() -> dict[str, dict[str, str]]:
    """``{tool_id: {"state": "running"|"error", "label": "…"}}`` for busy tools only.

    A provider that raises (or whose module is not loaded) is skipped: the
    activity view must never break the shell.
    """
    out: dict[str, dict[str, str]] = {}
    for t in TOOLS:
        if not t.activity:
            continue
        try:
            fn: Callable[[], dict[str, str] | None] = load(t.activity)
            state = fn()
        except Exception:
            logger.debug("activity provider for %s failed", t.id, exc_info=True)
            continue
        if state:
            out[t.id] = state
    return out


def hil_activity() -> dict[str, str] | None:
    from flask import current_app

    svc = current_app.extensions.get("test_service")
    if svc is None:
        return None
    st = svc.status()
    state = str(st.get("state", "idle")).lower()
    if state in ("running", "stopping"):
        return {"state": "running", "label": f"HIL {state}" + (f" · {st['profile']}" if st.get("profile") else "")}
    if state == "error":
        return {"state": "error", "label": "HIL run error"}
    return None


def thermal_activity() -> dict[str, str] | None:
    import sys

    tm = sys.modules.get(f"{_BP}.thermal_measurement")
    if tm is None:
        return None
    if tm._job.running:
        return {"state": "running", "label": "Thermal measurement"}
    if tm._tracking.running:
        return {"state": "running", "label": f"Thermal tracking · {tm._tracking.samples} samples"}
    return None


def station_activity() -> dict[str, str] | None:
    """Overdue calibration is a station-level problem: flag it in the nav."""
    from pyontrust.gateway.blueprints.station import instruments

    overdue = instruments().summary()["overdue"]
    if overdue:
        return {"state": "error", "label": f"{overdue} instrument(s) overdue calibration"}
    return None


def can_activity() -> dict[str, str] | None:
    import sys

    can = sys.modules.get(f"{_BP}.can_diag")
    svc = getattr(can, "_service", None) if can else None   # never create it just to ask
    if svc is not None and svc.is_running:
        return {"state": "running", "label": "CAN capture"}
    return None


# ═══════════════════════════════════════════════════════════════════════
#  Shell navigation (rendered server-side from the registry)
# ═══════════════════════════════════════════════════════════════════════


def render_nav(active: str = DEFAULT_TOOL) -> str:
    """Sidebar navigation HTML — the only place nav entries are produced."""
    parts: list[str] = []
    for key, heading in GROUPS:
        tools = [t for t in TOOLS if t.group == key]
        if not tools:
            continue
        parts.append(f'<p class="nav-heading">{html.escape(heading)}</p>')
        for t in tools:
            current = ' class="active" aria-current="page"' if t.id == active else ""
            parts.append(
                f'<a{current} href="{t.url}" data-tool="{t.id}" '
                f'data-title="{html.escape(t.title, quote=True)}" '
                f'data-description="{html.escape(t.description, quote=True)}">'
                f'<span class="nav-icon" aria-hidden="true">{html.escape(t.icon)}</span>'
                f'<span class="nav-label">{html.escape(t.nav_label)}</span>'
                f'<span class="nav-activity" aria-hidden="true"></span></a>')
    return "\n        ".join(parts)


def render_shell(template: str) -> str:
    """Fill the shell template's placeholders from the registry."""
    default = get(DEFAULT_TOOL)
    return (template
            .replace("{{NAV}}", render_nav(DEFAULT_TOOL))
            .replace("{{DEFAULT_URL}}", default.url)
            .replace("{{DEFAULT_TITLE}}", html.escape(default.title))
            .replace("{{DEFAULT_DESCRIPTION}}", html.escape(default.description)))
