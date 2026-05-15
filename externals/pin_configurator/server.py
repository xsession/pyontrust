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
import datetime as dt
import sys
import threading
import base64
import io
import re
import urllib.error
import urllib.request
import uuid
import shutil
import mimetypes

from flask import Flask, jsonify, redirect, request, send_file, send_from_directory, Response
import pdfplumber
from werkzeug.utils import secure_filename

# Ensure package is importable when run directly
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_FRONTEND_DIST_DIR = _HERE / "frontend" / "dist"
_FRONTEND_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}

from board_schema import board_to_frontend
from boards import BOARDS
from demo_app_generator import materialize_demo_app
from dts_generator import ExternalDeviceConfig, PinAssignment, PeripheralConfig, generate
from pdf_parser import parse_datasheet, DatasheetInfo
from package_generator import generate_board_files
from overlay_parser import parse_import, import_result_to_json
from datasheet_fetcher import identify_vendor, download_datasheet, fetch_and_parse, search_datasheet_candidates
from driver_generator import (
    DriverSpec, DRIVER_TYPES, generate_driver, driver_to_json, spec_from_json,
)
from project_model import build_project_document, normalize_project_document
from sensor_parser import (
    parse_sensor_datasheet, SensorDatasheetInfo,
    sensor_info_to_json, sensor_info_from_json,
    identify_sensor, generate_register_header, generate_register_defines,
)
from zephyr_catalog import load_zephyr_catalog


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
_BOARD_EDITOR_DRAFT_DIR = _HERE / ".board-editor-drafts"
_BOARD_EDITOR_DRAFT_DIR.mkdir(exist_ok=True)

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


LVGL_LAYOUT_FILE_VERSION = 1


def _ensure_board_editor_draft_dir() -> pathlib.Path:
    _BOARD_EDITOR_DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    return _BOARD_EDITOR_DRAFT_DIR


def _normalize_draft_filename(filename: str | None, board: dict | None = None) -> str:
    candidate = (filename or "").strip()
    if not candidate and isinstance(board, dict):
        candidate = str(board.get("board") or board.get("soc") or "board_draft").strip()
    candidate = secure_filename(candidate or "board_draft")
    if not candidate.lower().endswith(".json"):
        candidate = f"{candidate}.json"
    return candidate


def _draft_file_path(filename: str) -> pathlib.Path:
    draft_dir = _ensure_board_editor_draft_dir()
    normalized = _normalize_draft_filename(filename)
    path = (draft_dir / normalized).resolve()
    if path.parent != draft_dir.resolve():
        raise ValueError("Invalid draft filename")
    return path


def _draft_metadata(path: pathlib.Path) -> dict:
    stat = path.stat()
    return {
        "filename": path.name,
        "size": stat.st_size,
        "updated_at": dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat(),
    }


def _normalize_dialog_filetypes(filetypes: object) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    if not isinstance(filetypes, list):
        return normalized

    for entry in filetypes:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("name") or "Files").strip() or "Files"
        patterns = entry.get("patterns")
        if isinstance(patterns, str):
            pattern_text = patterns.strip()
        elif isinstance(patterns, list):
            parts = [str(pattern).strip() for pattern in patterns if str(pattern).strip()]
            pattern_text = " ".join(parts)
        else:
            pattern_text = ""
        if pattern_text:
            normalized.append((label, pattern_text))

    return normalized


def _resolve_dialog_initial_values(dialog_kind: str, initial_path: str) -> dict[str, str]:
    if not initial_path:
        return {}

    candidate = pathlib.Path(initial_path).expanduser()

    if dialog_kind == "directory":
        directory = candidate if candidate.is_dir() else candidate.parent
        return {"initialdir": str(directory)} if directory.exists() else {}

    if candidate.exists() and candidate.is_dir():
        return {"initialdir": str(candidate)}

    directory = candidate.parent
    values: dict[str, str] = {}
    if directory.exists():
        values["initialdir"] = str(directory)
    if candidate.name:
        values["initialfile"] = candidate.name
    return values


def _open_native_path_dialog(
    dialog_kind: str,
    *,
    title: str = "",
    initial_path: str = "",
    filetypes: object = None,
    default_extension: str = "",
) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Native file dialogs are unavailable: {exc}") from exc

    if dialog_kind not in {"open-file", "save-file", "directory"}:
        raise ValueError("Unsupported dialog_kind")

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    options: dict[str, object] = {}
    if title:
        options["title"] = title
    options.update(_resolve_dialog_initial_values(dialog_kind, initial_path))

    selection = ""
    try:
        if dialog_kind == "directory":
            selection = filedialog.askdirectory(**options)
        else:
            normalized_filetypes = _normalize_dialog_filetypes(filetypes)
            if normalized_filetypes:
                options["filetypes"] = normalized_filetypes
            if default_extension:
                options["defaultextension"] = default_extension
            if dialog_kind == "open-file":
                selection = filedialog.askopenfilename(**options)
            else:
                selection = filedialog.asksaveasfilename(**options)
    finally:
        root.destroy()

    return str(selection or "")

_EXTERNAL_WIDGET_TYPE_MAP = {
    "button": "button",
    "btn": "button",
    "textbutton": "button",
    "iconbutton": "button",
    "label": "label",
    "text": "label",
    "textlabel": "label",
    "statictext": "label",
    "container": "container",
    "group": "container",
    "flexcontainer": "container",
    "panel": "panel",
    "rectangle": "panel",
    "card": "panel",
    "slider": "slider",
    "scale": "slider",
    "bar": "bar",
    "progress": "bar",
    "progressbar": "bar",
    "image": "image",
    "bitmap": "image",
    "picture": "image",
}


def _slugify_identifier(value: object, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        raw = fallback
    cleaned = [ch if ch.isalnum() else "_" for ch in raw]
    collapsed = "".join(cleaned).strip("_") or fallback
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed


def _int_value(value: object, default: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _color_value(value: object, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if text.startswith("#"):
        return text
    if text.startswith("0x") and len(text) in (8, 10):
        return f"#{text[2:8]}"
    return default


def _extract_external_text(widget: dict[str, object], fallback: str) -> str:
    for key in ("text", "label", "caption", "title", "asset", "src", "source"):
        value = widget.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _extract_external_style_values(style_like: object) -> tuple[dict[str, object], list[str]]:
    values = {}
    refs = []
    if isinstance(style_like, dict):
        values["bg"] = _color_value(style_like.get("background") or style_like.get("bg") or style_like.get("fillColor"), "")
        values["color"] = _color_value(style_like.get("color") or style_like.get("textColor") or style_like.get("fg"), "")
        radius_raw = style_like.get("radius") or style_like.get("borderRadius")
        if radius_raw is not None:
            values["radius"] = _int_value(radius_raw, 0)
        ref = style_like.get("id") or style_like.get("name") or style_like.get("style")
        if ref:
            refs.append(_slugify_identifier(ref, "style"))
    elif isinstance(style_like, str) and style_like.strip():
        refs.append(_slugify_identifier(style_like, "style"))
    cleaned = {key: value for key, value in values.items() if value not in ("", None)}
    return cleaned, refs


def _convert_external_shared_styles(payload: dict[str, object]) -> list[dict[str, object]]:
    shared_styles = []
    for index, style in enumerate(payload.get("styles") or [], start=1):
        if not isinstance(style, dict):
            continue
        style_id = _slugify_identifier(style.get("id") or style.get("name"), f"style_{index}")
        values, _ = _extract_external_style_values(style)
        shared_styles.append({
            "id": style_id,
            "name": str(style.get("name") or style.get("id") or style_id),
            "part": str(style.get("part") or "LV_PART_MAIN"),
            "state": str(style.get("state") or "default"),
            "values": values,
        })
    return shared_styles


def _map_external_widget_type(raw_type: object) -> str:
    normalized = _slugify_identifier(raw_type, "panel").replace("_", "")
    return _EXTERNAL_WIDGET_TYPE_MAP.get(normalized, "panel")


def _convert_external_widget(widget: dict[str, object], screen_index: int, widget_index: int) -> list[dict[str, object]]:
    widget_type = _map_external_widget_type(widget.get("type") or widget.get("kind") or widget.get("widgetType"))
    base_name = _slugify_identifier(widget.get("name") or widget.get("id") or widget.get("label"), f"{widget_type}_{widget_index}")
    style_values, inline_refs = _extract_external_style_values(widget.get("style"))
    explicit_values, explicit_refs = _extract_external_style_values(widget.get("styles"))
    style_refs = []
    for ref in [*(inline_refs or []), *(explicit_refs or []), *[_slugify_identifier(value, "style") for value in (widget.get("styleId"), widget.get("styleName")) if value]]:
        if ref and ref not in style_refs:
            style_refs.append(ref)

    node = {
        "id": f"{widget_type}_{screen_index}_{widget_index}",
        "type": widget_type,
        "name": base_name,
        "text": _extract_external_text(widget, base_name.replace("_", " ").title()),
        "x": _int_value(widget.get("x") or widget.get("left"), 16),
        "y": _int_value(widget.get("y") or widget.get("top"), 16),
        "w": _int_value(widget.get("width") or widget.get("w"), 160 if widget_type != "label" else 180),
        "h": _int_value(widget.get("height") or widget.get("h"), 56 if widget_type == "button" else 44),
        "bg": _color_value(widget.get("background") or widget.get("bg") or style_values.get("bg") or explicit_values.get("bg"), "#334155" if widget_type != "button" else "#2563eb"),
        "color": _color_value(widget.get("color") or widget.get("textColor") or style_values.get("color") or explicit_values.get("color"), "#f8fafc"),
        "radius": _int_value(widget.get("radius") or widget.get("borderRadius") or style_values.get("radius") or explicit_values.get("radius"), 14),
        "action": "none",
        "targetScreenId": "",
        "transition": "move_left",
        "transitionDuration": 220,
        "styleMode": "shared" if style_refs else "local",
        "styleRefs": style_refs,
        "styles": {},
    }

    navigation = widget.get("navigation") if isinstance(widget.get("navigation"), dict) else {}
    target = widget.get("targetScreenId") or widget.get("targetPage") or navigation.get("target") or navigation.get("page")
    if target:
        node["action"] = "goto"
        node["targetScreenId"] = _slugify_identifier(target, "screen_root")
        transition = widget.get("transition") or navigation.get("transition")
        if transition:
            node["transition"] = _slugify_identifier(transition, "move_left")
        duration = widget.get("transitionDuration") or navigation.get("duration")
        if duration is not None:
            node["transitionDuration"] = _int_value(duration, 220)

    children = []
    for child_index, child in enumerate(widget.get("children") or widget.get("widgets") or [], start=1):
        if isinstance(child, dict):
            children.extend(_convert_external_widget(child, screen_index, widget_index * 100 + child_index))

    return [node, *children]


def _convert_external_pages_schema(payload: dict[str, object]) -> dict[str, object]:
    pages = payload.get("pages") or payload.get("screens")
    if not isinstance(pages, list) or not pages:
        raise ValueError("External GUI schema must contain a non-empty pages array")

    default_width = _int_value(payload.get("width") or payload.get("displayWidth"), 480)
    default_height = _int_value(payload.get("height") or payload.get("displayHeight"), 272)
    screens = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        screen_id = _slugify_identifier(page.get("id") or page.get("name"), f"screen_{index}")
        widgets = []
        for widget_index, widget in enumerate(page.get("widgets") or page.get("children") or [], start=1):
            if isinstance(widget, dict):
                widgets.extend(_convert_external_widget(widget, index, widget_index))
        screens.append({
            "id": screen_id,
            "type": "screen",
            "name": screen_id,
            "text": str(page.get("title") or page.get("name") or f"Screen {index}"),
            "x": 0,
            "y": 0,
            "w": _int_value(page.get("width") or page.get("w"), default_width),
            "h": _int_value(page.get("height") or page.get("h"), default_height),
            "bg": _color_value(page.get("background") or page.get("bg"), "#0f172a"),
            "color": _color_value(page.get("color") or page.get("textColor"), "#f8fafc"),
            "radius": _int_value(page.get("radius") or page.get("borderRadius"), 24),
            "entryActionName": str(page.get("entryActionName") or ""),
            "styleRefs": [],
            "styles": {},
            "nodes": widgets,
        })

    if not screens:
        raise ValueError("External GUI schema did not produce any importable pages")

    startup = payload.get("startupPage") or payload.get("startupScreenId") or payload.get("initialPage") or screens[0]["id"]
    startup_id = _slugify_identifier(startup, screens[0]["id"])
    if not any(screen["id"] == startup_id for screen in screens):
        startup_id = screens[0]["id"]

    preset = "dashboard"
    if default_width <= 260 and default_height <= 260:
        preset = "watch"
    elif default_width >= 760:
        preset = "panel"
    elif default_width <= 380 and default_height >= 500:
        preset = "phone"

    return {
        "preset": preset,
        "currentScreenId": startup_id,
        "startupScreenId": startup_id,
        "selectedId": startup_id,
        "selectedStyleId": "",
        "styleSchemaVersion": 1,
        "sharedStyles": _convert_external_shared_styles(payload),
        "simulation": {
            "running": False,
            "activeScreenId": startup_id,
            "log": ["Simulation is idle."],
        },
        "screens": screens,
    }


def _extract_lvgl_layout(payload):
    """Extract an LVGL layout from supported wrapper formats."""
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object containing an LVGL layout")

    if isinstance(payload.get("lvgl_layout"), dict):
        return _extract_lvgl_layout(payload["lvgl_layout"])

    if isinstance(payload.get("layout"), dict):
        return _extract_lvgl_layout(payload["layout"])

    if isinstance(payload.get("state"), dict):
        return _extract_lvgl_layout(payload["state"])

    if isinstance(payload.get("pages"), list):
        return _convert_external_pages_schema(payload)

    if isinstance(payload.get("screens"), list) or isinstance(payload.get("nodes"), list):
        return payload

    raise ValueError("JSON does not contain an LVGL layout. Expected lvgl_layout, layout, state, screens, or nodes.")


def _read_lvgl_import_text(body: dict[str, object]) -> tuple[str, str]:
    text = str(body.get("text", "") or "").strip()
    if text:
        return text, "pasted JSON"

    file_path = str(body.get("file_path", "") or "").strip()
    if file_path:
        path = pathlib.Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8"), str(path)

    url = str(body.get("url", "") or "").strip()
    if url:
        with urllib.request.urlopen(url, timeout=8) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset), url

    raise ValueError("Provide text, file_path, or url")


def _scan_zephyr_project_files(project: pathlib.Path) -> list[dict[str, str]]:
    found = []
    search_dirs = [project]
    boards_dir = project / "boards"
    if boards_dir.is_dir():
        search_dirs.append(boards_dir)

    for directory in search_dirs:
        for file_path in sorted(directory.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in (".overlay", ".conf", ".dts", ".dtsi"):
                found.append({
                    "path": str(file_path),
                    "relative": str(file_path.relative_to(project)),
                    "content": file_path.read_text(encoding="utf-8", errors="replace"),
                })

    prj_conf = project / "prj.conf"
    if prj_conf.is_file() and not any(item["relative"] == "prj.conf" for item in found):
        found.insert(0, {
            "path": str(prj_conf),
            "relative": "prj.conf",
            "content": prj_conf.read_text(encoding="utf-8", errors="replace"),
        })

    return found


def _read_zephyr_import_text(body: dict[str, object]) -> tuple[str, str]:
    text = str(body.get("text", "") or "").strip()
    if text:
        return text, "pasted Zephyr text"

    file_path = str(body.get("file_path", "") or body.get("project_path", "") or "").strip()
    if file_path:
        path = pathlib.Path(file_path)
        if path.is_dir():
            files = _scan_zephyr_project_files(path)
            if not files:
                raise ValueError(f"No Zephyr config files found in project: {path}")
            combined = []
            for item in files:
                combined.append(f"# FILE: {item['relative']}")
                combined.append(item["content"])
                combined.append("")
            return "\n".join(combined).strip(), f"Zephyr project {path}"
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_text(encoding="utf-8"), str(path)

    url = str(body.get("url", "") or "").strip()
    if url:
        with urllib.request.urlopen(url, timeout=8) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset), url

    raise ValueError("Provide Zephyr text, a file path, a project path, or a URL")


def _read_lvgl_import_bytes(body: dict[str, object]) -> tuple[bytes, str]:
    encoded = str(body.get("binary_base64", "") or "").strip()
    if encoded:
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError("Invalid base64 payload") from exc
        source = str(body.get("filename", "") or "uploaded PDF").strip() or "uploaded PDF"
        return data, source

    file_path = str(body.get("file_path", "") or "").strip()
    if file_path:
        path = pathlib.Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_bytes(), str(path)

    url = str(body.get("url", "") or "").strip()
    if url:
        with urllib.request.urlopen(url, timeout=8) as response:
            return response.read(), url

    raise ValueError("Provide binary_base64, file_path, or url")


def _lvgl_preset_for_resolution(width: int, height: int) -> str:
    if width <= 260 and height <= 260:
        return "watch"
    if width >= 760:
        return "panel"
    if width <= 380 and height >= 500:
        return "phone"
    return "dashboard"


def _build_display_seed_layout(width: int, height: int, source: str, title: str = "Imported Display", details: dict | None = None) -> dict[str, object]:
    preset = _lvgl_preset_for_resolution(width, height)
    return {
        "preset": preset,
        "currentScreenId": "screen_root",
        "startupScreenId": "screen_root",
        "selectedId": "screen_root",
        "selectedStyleId": "",
        "styleSchemaVersion": 1,
        "sharedStyles": [],
        "simulation": {
            "running": False,
            "activeScreenId": "screen_root",
            "log": [f"Imported display seed from {source}."],
        },
        "importMeta": {
            "source": source,
            "kind": "display-seed",
            **(details or {}),
        },
        "screens": [
            {
                "id": "screen_root",
                "type": "screen",
                "name": "screen_main",
                "text": title,
                "x": 0,
                "y": 0,
                "w": width,
                "h": height,
                "bg": "#0f172a",
                "color": "#f8fafc",
                "radius": 24,
                "entryActionName": "",
                "styleRefs": [],
                "styles": {},
                "nodes": [],
            }
        ],
    }


def _first_resolution_value(text: str, patterns: list[str]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _int_value(match.group(1), 0) or None
    return None


def _extract_zephyr_display_label(text: str, source: str) -> str:
    compatible = re.search(r'compatible\s*=\s*"([^"]+)"', text, re.IGNORECASE)
    if compatible:
        return compatible.group(1)

    enabled_driver = re.search(r'CONFIG_([A-Z0-9_]*(?:ILI|ST|SSD|GC9|RM6|HX|JD)[A-Z0-9_]*)\s*=\s*y', text, re.IGNORECASE)
    if enabled_driver:
        return enabled_driver.group(1)

    return pathlib.Path(source).stem if source and source != "pasted JSON" else "Zephyr display"


def _extract_lvgl_layout_from_zephyr(text: str, source: str) -> dict[str, object]:
    width = _first_resolution_value(text, [
        r'CONFIG_LV_HOR_RES_MAX\s*=\s*(\d+)',
        r'CONFIG_LV_HOR_RES\s*=\s*(\d+)',
        r'\bx-resolution\s*=\s*<(\d+)>',
        r'\bwidth\s*=\s*<(\d+)>',
        r'\bhorizontal[-_ ]resolution\s*=\s*<(\d+)>',
    ])
    height = _first_resolution_value(text, [
        r'CONFIG_LV_VER_RES_MAX\s*=\s*(\d+)',
        r'CONFIG_LV_VER_RES\s*=\s*(\d+)',
        r'\by-resolution\s*=\s*<(\d+)>',
        r'\bheight\s*=\s*<(\d+)>',
        r'\bvertical[-_ ]resolution\s*=\s*<(\d+)>',
    ])

    if not width or not height:
        pair = re.search(r'(?:resolution|display|panel|screen)[^\n\r]{0,48}?(\d{2,5})\s*[x×]\s*(\d{2,5})', text, re.IGNORECASE)
        if pair:
            width = width or _int_value(pair.group(1), 0)
            height = height or _int_value(pair.group(2), 0)

    if not width or not height:
        raise ValueError("Could not infer display resolution from Zephyr text. Include LVGL resolution Kconfig or display width/height properties.")

    label = _extract_zephyr_display_label(text, source)
    return _build_display_seed_layout(width, height, source, title=f"{label} display", details={
        "kind": "zephyr-display",
        "display": {
            "label": label,
            "width": width,
            "height": height,
        },
    })


def _extract_display_pdf_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = []
        for page in pdf.pages[:12]:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _score_resolution_context(context: str) -> int:
    score = 0
    lowered = context.lower()
    for keyword in ("resolution", "pixel", "pixels", "dot", "dots", "display", "lcd", "tft", "panel", "rgb"):
        if keyword in lowered:
            score += 3
    for keyword in ("active area", "graphic", "screen"):
        if keyword in lowered:
            score += 1
    return score


def _extract_display_resolution_from_text(text: str) -> tuple[int, int]:
    candidates: list[tuple[int, int, int]] = []
    patterns = [
        r'(\d{2,5})\s*(?:RGB)?\s*[x×]\s*(\d{2,5})',
        r'(\d{2,5})\s*(?:\([A-Z]+\))?\s*[x×]\s*(\d{2,5})',
    ]
    seen_matches: set[tuple[int, int, int]] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            width = _int_value(match.group(1), 0)
            height = _int_value(match.group(2), 0)
            match_key = (match.start(), width, height)
            if match_key in seen_matches:
                continue
            seen_matches.add(match_key)
            if min(width, height) < 32 or max(width, height) > 4096:
                continue
            start = max(0, match.start() - 64)
            end = min(len(text), match.end() + 64)
            context = text[start:end]
            score = _score_resolution_context(context)
            candidates.append((score, width * height, candidates.__len__()))
            candidates[-1] = (score, width * height, candidates[-1][2], width, height)

    if not candidates:
        raise ValueError("Could not infer display resolution from the PDF. Use a datasheet page that contains the panel resolution.")

    best = max(candidates, key=lambda item: (item[0], item[1]))
    return best[3], best[4]


def _extract_display_pdf_label(text: str, source: str) -> str:
    for pattern in (
        r'\b((?:ILI|ST|SSD|GC9|RM6|HX|JD)\d{2,5}[A-Z]*)\b',
        r'\b([A-Z]{2,6}\d{2,5}[A-Z0-9-]*)\b',
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return pathlib.Path(source).stem or "Display PDF"


def _extract_lvgl_layout_from_display_pdf(pdf_bytes: bytes, source: str) -> dict[str, object]:
    text = _extract_display_pdf_text(pdf_bytes)
    width, height = _extract_display_resolution_from_text(text)
    label = _extract_display_pdf_label(text, source)
    return _build_display_seed_layout(width, height, source, title=f"{label} display", details={
        "kind": "display-pdf",
        "display": {
            "label": label,
            "width": width,
            "height": height,
        },
    })


# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/app")


def _serve_frontend_asset(asset_path: str = "index.html"):
    dist_dir = _FRONTEND_DIST_DIR
    if not dist_dir.is_dir():
        return Response(
            "Frontend bundle not found. Build the React workspace under frontend/ first.",
            status=404,
            mimetype="text/plain",
        )

    requested = (dist_dir / asset_path).resolve()
    dist_root = dist_dir.resolve()
    if requested != dist_root and dist_root not in requested.parents:
        return Response(status=404)

    if requested.is_file():
        mime_type = _FRONTEND_MIME_TYPES.get(requested.suffix.lower())
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(requested))
        return send_file(
            requested,
            mimetype=mime_type,
            as_attachment=False,
        )

    return send_file(dist_root / "index.html", mimetype="text/html")


@app.route("/app")
@app.route("/app/<path:asset_path>")
def frontend_app(asset_path: str = "index.html"):
    return _serve_frontend_asset(asset_path)


@app.route("/favicon.ico")
def favicon():
    icon = pathlib.Path(app.static_folder) / "favicon.ico"
    if icon.is_file():
        return send_from_directory(app.static_folder, "favicon.ico")
    return Response(status=204)


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


@app.route("/api/board-editor/drafts")
def list_board_editor_drafts():
    draft_dir = _ensure_board_editor_draft_dir()
    drafts = [_draft_metadata(path) for path in sorted(draft_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)]
    return jsonify({"drafts": drafts})


@app.route("/api/board-editor/draft/<filename>")
def load_board_editor_draft(filename: str):
    try:
        path = _draft_file_path(filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not path.is_file():
        return jsonify({"error": f"Draft '{path.name}' not found."}), 404

    try:
        board = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return jsonify({"error": f"Invalid draft '{path.name}': {exc}"}), 400

    return jsonify({"filename": path.name, "board": board})


@app.route("/api/board-editor/save", methods=["POST"])
def save_board_editor_draft():
    body = request.get_json(force=True)
    board = body.get("board")
    if not isinstance(board, dict):
        return jsonify({"error": "Provide a board object to save."}), 400

    filename = _normalize_draft_filename(body.get("filename"), board)
    path = _draft_file_path(filename)
    path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    return jsonify({"filename": path.name})


@app.route("/api/board-editor/delete", methods=["POST"])
def delete_board_editor_draft():
    body = request.get_json(force=True)
    filename = str(body.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "Provide a draft filename to delete."}), 400

    try:
        path = _draft_file_path(filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not path.is_file():
        return jsonify({"error": f"Draft '{path.name}' not found."}), 404

    path.unlink()
    return jsonify({"filename": path.name})


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

    project = build_project_document(body)

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
        project = normalize_project_document(json.loads(fp.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return jsonify({"error": f"Invalid project file: {exc}"}), 400

    return jsonify(project)


@app.route("/api/demo-app/export", methods=["POST"])
def export_demo_app():
    body = request.get_json(force=True)
    output_dir = pathlib.Path(str(body.get("output_dir") or "").strip())
    if not str(output_dir):
        return jsonify({"error": "Missing output_dir"}), 400

    overwrite = bool(body.get("overwrite"))
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        return jsonify({"error": f"Output directory is not empty: {output_dir}"}), 400

    if output_dir.exists() and overwrite:
        shutil.rmtree(output_dir)

    project_payload = body.get("project") if isinstance(body.get("project"), dict) else body
    project = normalize_project_document(project_payload)
    testbench_cmake = (_HERE / "testbench" / "CMakeLists.txt").read_text(encoding="utf-8")
    result = materialize_demo_app(project, output_dir, testbench_cmake=testbench_cmake)
    return jsonify({"saved": True, **result})


@app.route("/api/path-dialog", methods=["POST"])
def path_dialog():
    body = request.get_json(force=True)
    dialog_kind = str(body.get("dialog_kind") or "").strip().lower()

    if dialog_kind not in {"open-file", "save-file", "directory"}:
        return jsonify({"error": "Unsupported dialog_kind. Use open-file, save-file, or directory."}), 400

    try:
        path = _open_native_path_dialog(
            dialog_kind,
            title=str(body.get("title") or "").strip(),
            initial_path=str(body.get("initial_path") or "").strip(),
            filetypes=body.get("filetypes"),
            default_extension=str(body.get("default_extension") or "").strip(),
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        log.exception("Native path dialog failed")
        return jsonify({"error": f"Failed to open native path dialog: {exc}"}), 500

    return jsonify({
        "path": path,
        "cancelled": not bool(path),
    })


@app.route("/api/zephyr/catalog", methods=["GET"])
def zephyr_catalog():
    zephyr_root = request.args.get("zephyr_root", "").strip() or None
    refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}

    try:
        catalog = load_zephyr_catalog(zephyr_root, refresh=refresh)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Failed to load Zephyr catalog: {exc}"}), 400

    return jsonify(catalog)


@app.route("/api/lvgl/import", methods=["POST"])
def lvgl_import_layout():
    """Import an LVGL layout from JSON, Zephyr display config, or a display datasheet PDF."""
    body = request.get_json(force=True)
    source_kind = str(body.get("source_kind") or "json").strip().lower().replace("_", "-")

    try:
        if source_kind == "json":
            raw_text, source = _read_lvgl_import_text(body)
            payload = json.loads(raw_text)
            layout = _extract_lvgl_layout(payload)
        elif source_kind == "zephyr":
            raw_text, source = _read_zephyr_import_text(body)
            layout = _extract_lvgl_layout_from_zephyr(raw_text, source)
        elif source_kind in {"pdf", "display-pdf"}:
            pdf_bytes, source = _read_lvgl_import_bytes(body)
            layout = _extract_lvgl_layout_from_display_pdf(pdf_bytes, source)
        else:
            raise ValueError("Unsupported LVGL import source. Use json, zephyr, or display-pdf.")
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except urllib.error.URLError as exc:
        return jsonify({"error": f"Unable to fetch source: {exc}"}), 400
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "source": source,
        "layout": layout,
    })


@app.route("/api/lvgl/export", methods=["POST"])
def lvgl_export_layout():
    """Save the current LVGL layout to a reusable JSON file."""
    body = request.get_json(force=True)
    file_path = str(body.get("file_path", "") or "").strip()
    layout = body.get("layout")

    if not file_path:
        return jsonify({"error": "Missing file_path"}), 400
    if not isinstance(layout, dict):
        return jsonify({"error": "Missing layout"}), 400

    fp = pathlib.Path(file_path)
    if not fp.suffix:
        fp = pathlib.Path(f"{fp}.lvgl.json")
    fp.parent.mkdir(parents=True, exist_ok=True)

    document = {
        "version": LVGL_LAYOUT_FILE_VERSION,
        "kind": "lvgl-layout",
        "lvgl_layout": layout,
    }
    fp.write_text(json.dumps(document, indent=2), encoding="utf-8")

    return jsonify({"saved": True, "file_path": str(fp)})


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
    try:
        search_candidates = search_datasheet_candidates(pn, result, max_results=5)
    except Exception as exc:
        log.warning("Datasheet search preview failed for %s: %s", pn, exc)
        search_candidates = []

    return jsonify({
        "part_number": pn,
        "known": result is not None,
        "existing_board": existing,
        "vendor": result.vendor if result else None,
        "vendor_name": result.vendor_name if result else None,
        "family": result.family if result else None,
        "datasheet_urls": result.datasheet_urls if result else [],
        "search_candidates": search_candidates,
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
