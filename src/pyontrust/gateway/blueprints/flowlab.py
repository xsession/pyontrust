"""FlowLab blueprint — LabVIEW-style visual dataflow experiment designer.

Mounts at ``/flowlab/`` and provides:

- ``GET  /flowlab/``              → block-diagram SPA
- ``POST /flowlab/api/execute``   → execute a diagram (topological sort)
- ``POST /flowlab/api/save``      → persist diagram JSON
- ``GET  /flowlab/api/load``      → retrieve saved diagram
- ``POST /flowlab/api/stop``      → request execution abort
- ``GET  /flowlab/api/blocks``    → available block types
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from pyontrust.gateway.flowlab_engine import FlowLabEngine
from pyontrust.gateway.hil_flowlab_converter import diagram_to_hil, hil_to_diagram
from pyontrust.gateway.flowlab_codegen import diagram_to_python, extract_diagram_from_python

logger = logging.getLogger("pyontrust.gateway.flowlab")

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "flowlab"
_SAVE_DIR = pathlib.Path(".") / "flowlab_diagrams"
_HIL_DIR = pathlib.Path(".") / "profiles"
_EDITOR_CORE_DIR = pathlib.Path(".") / "externals" / "editor-core"
_EDITOR_CORE_LIB_DIR = _EDITOR_CORE_DIR / "editor-core"

bp = Blueprint(
    "flowlab",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/static",
)

# Shared engine instance per process
_engine: FlowLabEngine | None = None
_lock = threading.Lock()

_FLOWLAB_PORT_COLORS = [
    "#89b4fa",
    "#a6e3a1",
    "#f9e2af",
    "#f38ba8",
    "#cba6f7",
    "#94e2d5",
]


def _ec_default_settings() -> dict[str, Any]:
    return {
        "grid": {
            "visible": True,
            "snap": False,
            "spacing": 20,
            "majorEvery": 5,
            "opacity": 0.25,
        },
        "defaultRouting": {
            "pattern": "orthogonal",
            "clearance": 8,
            "grid": 20,
            "leadIn": 16,
            "requestedRadius": 8,
            "minimumSegment": 8,
            "bendPenalty": 1,
            "crossingPenalty": 2,
            "proximityPenalty": 1,
            "reversePenalty": 1,
            "previousRouteStability": 0,
            "maxSearchNodes": 500,
            "allowCrossings": True,
            "preferSharedChannels": False,
            "constraints": [],
        },
        "labelGap": 6,
        "hitTolerancePx": 8,
        "portTargetSizePx": 12,
        "componentHandleSizePx": 10,
        "wireBridgeRadius": 4,
        "preserveManualRoutesOnMove": True,
        "reflowLabelsOnEdit": True,
        "reduceMotion": False,
    }


def _ec_default_component_layout() -> dict[str, Any]:
    return {
        "minimumSize": {"width": 150, "height": 90},
        "padding": {"top": 10, "right": 10, "bottom": 10, "left": 10},
        "headerHeight": 24,
        "footerHeight": 0,
        "rowHeight": 18,
        "rowGap": 2,
        "bankGap": 10,
        "autoWidth": False,
        "autoHeight": False,
        "preserveManualSize": False,
        "portLeadIn": 10,
        "obstaclePadding": 4,
        "labelGap": 4,
    }


def _ec_default_wire_style(index: int) -> dict[str, Any]:
    color = _FLOWLAB_PORT_COLORS[index % len(_FLOWLAB_PORT_COLORS)]
    return {
        "pattern": {"kind": "solid", "color": color},
        "width": 2,
        "outlineWidth": 1,
        "opacity": 1,
        "lineCap": "round",
        "lineJoin": "round",
        "zIndex": 1,
    }


def _normalise_port_name(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _discover_flowlab_ports(block_id: str, wires: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    inputs: list[str] = []
    outputs: list[str] = []
    for wire in wires:
        to_ep = wire.get("to") or {}
        from_ep = wire.get("from") or {}
        if str(to_ep.get("block")) == block_id:
            port_name = _normalise_port_name(to_ep.get("port"), "in")
            if port_name not in inputs:
                inputs.append(port_name)
        if str(from_ep.get("block")) == block_id:
            port_name = _normalise_port_name(from_ep.get("port"), "out")
            if port_name not in outputs:
                outputs.append(port_name)
    if not outputs:
        outputs = ["out"]
    return inputs, outputs


def _ec_port_id(block_id: str, direction: str, name: str) -> str:
    safe_name = str(name).replace(" ", "_")
    return f"{block_id}:{direction}:{safe_name}"


def _flowlab_to_editor_core(diagram: dict[str, Any]) -> dict[str, Any]:
    blocks = list(diagram.get("blocks") or [])
    wires = list(diagram.get("wires") or [])

    components: dict[str, Any] = {}
    component_order: list[str] = []

    for idx, block in enumerate(blocks):
        block_id = str(block.get("id") or f"b{idx + 1}")
        block_type = str(block.get("type") or "unknown")
        x = float(block.get("x", 0))
        y = float(block.get("y", 0))
        params = block.get("params") if isinstance(block.get("params"), dict) else {}

        input_ports, output_ports = _discover_flowlab_ports(block_id, wires)
        ports: list[dict[str, Any]] = []
        input_port_ids: list[str] = []
        output_port_ids: list[str] = []

        for order, name in enumerate(input_ports):
            pid = _ec_port_id(block_id, "in", name)
            input_port_ids.append(pid)
            ports.append(
                {
                    "id": pid,
                    "label": name,
                    "side": "west",
                    "order": order,
                    "visible": True,
                    "electricalClass": "signal-input",
                    "connectionPolicy": {
                        "maximumConnections": 32,
                        "allowSelfConnection": False,
                    },
                }
            )

        for order, name in enumerate(output_ports):
            pid = _ec_port_id(block_id, "out", name)
            output_port_ids.append(pid)
            ports.append(
                {
                    "id": pid,
                    "label": name,
                    "side": "east",
                    "order": order,
                    "visible": True,
                    "electricalClass": "signal-output",
                    "connectionPolicy": {
                        "maximumConnections": 32,
                        "allowSelfConnection": False,
                    },
                }
            )

        port_rows = max(1, max(len(input_ports), len(output_ports)))
        component_id = f"cmp_{block_id}"
        component_order.append(component_id)
        components[component_id] = {
            "id": component_id,
            "kind": "device",
            "designator": block_type.upper()[:24],
            "labels": {
                "title": block_type,
                "subtitle": block_id,
            },
            "position": {"x": x, "y": y},
            "size": {"width": 180, "height": max(96, 36 + port_rows * 20)},
            "rotation": 0,
            "mirrorX": False,
            "mirrorY": False,
            "ports": ports,
            "pinBanks": [
                {
                    "id": "inputs",
                    "side": "west",
                    "portIds": input_port_ids,
                    "flow": "forward",
                    "rowGap": 2,
                    "edgePadding": 8,
                    "collapseEmpty": True,
                    "header": "In",
                },
                {
                    "id": "outputs",
                    "side": "east",
                    "portIds": output_port_ids,
                    "flow": "forward",
                    "rowGap": 2,
                    "edgePadding": 8,
                    "collapseEmpty": True,
                    "header": "Out",
                },
            ],
            "layout": _ec_default_component_layout(),
            "locked": False,
            "hidden": False,
            "zIndex": idx,
            "metadata": {
                "flowlab": {
                    "block_id": block_id,
                    "type": block_type,
                    "params": params,
                    "inputs": input_ports,
                    "outputs": output_ports,
                }
            },
        }

    wire_map: dict[str, Any] = {}
    wire_order: list[str] = []
    for idx, wire in enumerate(wires):
        wire_id = str(wire.get("id") or f"w{idx + 1}")
        from_ep = wire.get("from") or {}
        to_ep = wire.get("to") or {}
        from_block = str(from_ep.get("block") or "")
        to_block = str(to_ep.get("block") or "")
        from_port = _normalise_port_name(from_ep.get("port"), "out")
        to_port = _normalise_port_name(to_ep.get("port"), "in")

        source_component = f"cmp_{from_block}"
        target_component = f"cmp_{to_block}"
        if source_component not in components or target_component not in components:
            continue

        editor_wire_id = f"wire_{wire_id}"
        wire_order.append(editor_wire_id)
        wire_map[editor_wire_id] = {
            "id": editor_wire_id,
            "kind": "discrete",
            "source": {
                "kind": "port",
                "componentId": source_component,
                "portId": _ec_port_id(from_block, "out", from_port),
            },
            "target": {
                "kind": "port",
                "componentId": target_component,
                "portId": _ec_port_id(to_block, "in", to_port),
            },
            "routing": {
                "pattern": "orthogonal",
                "clearance": 8,
                "grid": 20,
                "leadIn": 16,
                "requestedRadius": 8,
                "minimumSegment": 8,
                "bendPenalty": 1,
                "crossingPenalty": 2,
                "proximityPenalty": 1,
                "reversePenalty": 1,
                "previousRouteStability": 0,
                "maxSearchNodes": 500,
                "allowCrossings": True,
                "preferSharedChannels": False,
                "constraints": [],
            },
            "style": _ec_default_wire_style(idx),
            "locked": False,
            "hidden": False,
            "metadata": {
                "flowlab": {
                    "wire_id": wire_id,
                    "from_block": from_block,
                    "to_block": to_block,
                    "from_port": from_port,
                    "to_port": to_port,
                }
            },
        }

    return {
        "schemaVersion": 1,
        "id": f"flowlab-{diagram.get('name', 'document')}",
        "revision": 1,
        "settings": _ec_default_settings(),
        "components": components,
        "wires": wire_map,
        "labels": {},
        "componentOrder": component_order,
        "wireOrder": wire_order,
        "labelOrder": [],
        "metadata": {
            "source": "flowlab",
            "flowlab_version": int(diagram.get("version", 1) or 1),
        },
    }


def _ordered_map_values(items: dict[str, Any], order: list[str]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in order:
        if key in items and isinstance(items[key], dict):
            values.append(items[key])
            seen.add(key)
    for key, value in items.items():
        if key not in seen and isinstance(value, dict):
            values.append(value)
    return values


def _extract_port_name_from_id(port_id: str, fallback: str) -> str:
    parts = str(port_id).split(":")
    if len(parts) >= 3:
        return _normalise_port_name(parts[-1].replace("_", " "), fallback)
    return fallback


def _editor_core_to_flowlab(document: dict[str, Any]) -> dict[str, Any]:
    components = document.get("components") if isinstance(document.get("components"), dict) else {}
    wires = document.get("wires") if isinstance(document.get("wires"), dict) else {}

    component_order = document.get("componentOrder") if isinstance(document.get("componentOrder"), list) else []
    wire_order = document.get("wireOrder") if isinstance(document.get("wireOrder"), list) else []

    blocks: list[dict[str, Any]] = []
    component_to_block: dict[str, str] = {}
    port_name_maps: dict[str, dict[str, str]] = {}

    ordered_components = _ordered_map_values(components, component_order)
    for idx, component in enumerate(ordered_components):
        metadata = component.get("metadata") if isinstance(component.get("metadata"), dict) else {}
        flowlab_meta = metadata.get("flowlab") if isinstance(metadata.get("flowlab"), dict) else {}

        component_id = str(component.get("id") or f"cmp_{idx + 1}")
        block_id = str(flowlab_meta.get("block_id") or component_id.replace("cmp_", ""))
        block_type = str(flowlab_meta.get("type") or component.get("designator") or component.get("id") or "constant").lower()
        params = flowlab_meta.get("params") if isinstance(flowlab_meta.get("params"), dict) else {}

        position = component.get("position") if isinstance(component.get("position"), dict) else {}
        x = float(position.get("x", 0))
        y = float(position.get("y", 0))

        blocks.append(
            {
                "id": block_id,
                "type": block_type,
                "x": round(x),
                "y": round(y),
                "params": params,
            }
        )
        component_to_block[component_id] = block_id

        port_map: dict[str, str] = {}
        for port in component.get("ports") or []:
            if not isinstance(port, dict):
                continue
            port_id = str(port.get("id") or "")
            label = _normalise_port_name(port.get("label"), _extract_port_name_from_id(port_id, "port"))
            if port_id:
                port_map[port_id] = label
        port_name_maps[component_id] = port_map

    flow_wires: list[dict[str, Any]] = []
    ordered_wires = _ordered_map_values(wires, wire_order)
    for idx, wire in enumerate(ordered_wires):
        source = wire.get("source") if isinstance(wire.get("source"), dict) else {}
        target = wire.get("target") if isinstance(wire.get("target"), dict) else {}
        if source.get("kind") != "port" or target.get("kind") != "port":
            continue

        source_component = str(source.get("componentId") or "")
        target_component = str(target.get("componentId") or "")
        if source_component not in component_to_block or target_component not in component_to_block:
            continue

        source_port_id = str(source.get("portId") or "")
        target_port_id = str(target.get("portId") or "")

        metadata = wire.get("metadata") if isinstance(wire.get("metadata"), dict) else {}
        flowlab_meta = metadata.get("flowlab") if isinstance(metadata.get("flowlab"), dict) else {}
        wire_id = str(flowlab_meta.get("wire_id") or wire.get("id") or f"w{idx + 1}")
        from_port = _normalise_port_name(
            flowlab_meta.get("from_port"),
            port_name_maps.get(source_component, {}).get(source_port_id, _extract_port_name_from_id(source_port_id, "out")),
        )
        to_port = _normalise_port_name(
            flowlab_meta.get("to_port"),
            port_name_maps.get(target_component, {}).get(target_port_id, _extract_port_name_from_id(target_port_id, "in")),
        )

        flow_wires.append(
            {
                "id": wire_id,
                "from": {
                    "block": component_to_block[source_component],
                    "port": from_port,
                },
                "to": {
                    "block": component_to_block[target_component],
                    "port": to_port,
                },
            }
        )

    return {
        "version": 1,
        "blocks": blocks,
        "wires": flow_wires,
    }


def _get_engine() -> FlowLabEngine:
    global _engine
    if _engine is None:
        _engine = FlowLabEngine()
    return _engine


# ── SPA ──────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/editor-core")
def open_editor_core():
    """Open local xsession/editor-core if present.

    This endpoint intentionally serves a local checkout to avoid bundling
    third-party source directly into pyontrust.
    """
    candidates = [
        _EDITOR_CORE_DIR / "index.html",
        _EDITOR_CORE_DIR / "editor-core" / "index.html",
        _EDITOR_CORE_DIR / "dist" / "index.html",
    ]
    for index_file in candidates:
        if index_file.exists():
            return send_from_directory(str(index_file.parent), index_file.name)

    if _EDITOR_CORE_LIB_DIR.exists():
        host_html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>FlowLab Editor Core Workspace</title>
  <style>
        body { font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #10141f; color: #d8dee9; }
        .wrap { padding: 18px; display: grid; gap: 12px; }
        .card { background: #1a1f2e; border: 1px solid #30384f; border-radius: 10px; padding: 14px; }
        h1 { margin: 0 0 8px 0; font-size: 22px; }
        .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        button { border: 1px solid #3c4b69; background: #24324f; color: #d8dee9; border-radius: 8px; padding: 6px 10px; cursor: pointer; }
        button:hover { background: #2d3f64; }
        input { border: 1px solid #2b3247; background: #0f1320; color: #d8dee9; border-radius: 8px; padding: 6px 10px; }
    p { line-height: 1.45; }
    pre { background: #0f1320; border: 1px solid #2b3247; padding: 12px; border-radius: 8px; overflow: auto; }
        textarea { width: 100%; min-height: 440px; background: #0f1320; color: #d8dee9; border: 1px solid #2b3247; border-radius: 8px; padding: 10px; font-family: Consolas, monospace; font-size: 12px; }
        .muted { color: #9aa7c7; font-size: 12px; }
        .ok { color: #a6e3a1; }
        .err { color: #f38ba8; }
  </style>
</head>
<body>
    <div class=\"wrap\">
        <div class=\"card\">
            <h1>FlowLab + editor-core</h1>
            <p class=\"muted\">Round-trip bridge: FlowLab autosave JSON ↔ editor-core document JSON.</p>
            <div class=\"row\">
                <label for=\"name\">Diagram name:</label>
                <input id=\"name\" value=\"autosave\" />
                <button id=\"load\">Load from FlowLab</button>
                <button id=\"save\">Save to FlowLab</button>
                <button id=\"open-flowlab\">Open FlowLab</button>
            </div>
            <p id=\"status\" class=\"muted\">Ready.</p>
            <p class=\"muted\">editor-core exports detected: <span id=\"export-count\">0</span></p>
        </div>
        <div class=\"card\">
            <textarea id=\"doc\" spellcheck=\"false\"></textarea>
        </div>
  </div>

  <script type=\"module\">
    import * as editorCore from '/flowlab/editor-core/assets/index.js';
        const statusEl = document.getElementById('status');
        const docEl = document.getElementById('doc');
        const nameEl = document.getElementById('name');
        const exportCountEl = document.getElementById('export-count');
        exportCountEl.textContent = String(Object.keys(editorCore).length);

        function setStatus(msg, ok = true) {
            statusEl.textContent = msg;
            statusEl.className = ok ? 'ok' : 'err';
        }

        async function loadFromFlowlab() {
            const name = encodeURIComponent(nameEl.value || 'autosave');
            const res = await fetch('/flowlab/api/editor_core/export?name=' + name);
            const payload = await res.json();
            if (payload.error) {
                setStatus(payload.error, false);
                return;
            }
            docEl.value = JSON.stringify(payload.document, null, 2);
            setStatus('Loaded editor-core document from FlowLab diagram ' + (payload.name || 'autosave'));
        }

        async function saveToFlowlab() {
            let parsed;
            try {
                parsed = JSON.parse(docEl.value);
            } catch (err) {
                setStatus('Invalid JSON: ' + err.message, false);
                return;
            }
            const res = await fetch('/flowlab/api/editor_core/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document: parsed, name: nameEl.value || 'autosave' }),
            });
            const payload = await res.json();
            if (payload.error) {
                setStatus(payload.error, false);
                return;
            }
            setStatus('Saved FlowLab diagram to ' + payload.path);
        }

        document.getElementById('load').addEventListener('click', () => loadFromFlowlab().catch(err => setStatus(String(err), false)));
        document.getElementById('save').addEventListener('click', () => saveToFlowlab().catch(err => setStatus(String(err), false)));
        document.getElementById('open-flowlab').addEventListener('click', () => {
            window.open('/flowlab/', '_blank', 'noopener');
        });

        await loadFromFlowlab();
  </script>
</body>
</html>
"""
        return host_html, 200, {"Content-Type": "text/html; charset=utf-8"}

    return (
        "<h3>editor-core not found</h3>"
        "<p>Clone https://github.com/xsession/editor-core into externals/editor-core "
        "and refresh this page.</p>",
        404,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@bp.route("/editor-core/assets/<path:asset_path>")
def editor_core_assets(asset_path: str):
    """Serve local editor-core JS assets for the bridge page."""
    if not _EDITOR_CORE_LIB_DIR.exists():
        return jsonify({"error": "editor-core assets not found"}), 404
    return send_from_directory(str(_EDITOR_CORE_LIB_DIR), asset_path)


@bp.route("/api/editor_core/export")
def editor_core_export():
    """Export a FlowLab diagram into an editor-core document model."""
    name = request.args.get("name", "autosave")
    path = _SAVE_DIR / f"{name}.json"
    if not path.exists():
        return jsonify({"error": f"Diagram not found: {path}"}), 404
    try:
        diagram = json.loads(path.read_text(encoding="utf-8"))
        document = _flowlab_to_editor_core(diagram)
        return jsonify({"name": name, "document": document})
    except Exception as exc:
        return jsonify({"error": f"Failed to export editor-core document: {exc}"}), 500


@bp.route("/api/editor_core/import", methods=["POST"])
def editor_core_import():
    """Import an editor-core document model into a FlowLab diagram JSON."""
    body = request.get_json(force=True, silent=True) or {}
    document = body.get("document")
    if not isinstance(document, dict):
        return jsonify({"error": "Request must include 'document' object"}), 400

    name = str(body.get("name") or "autosave")
    try:
        diagram = _editor_core_to_flowlab(document)
        _SAVE_DIR.mkdir(parents=True, exist_ok=True)
        path = _SAVE_DIR / f"{name}.json"
        path.write_text(json.dumps(diagram, indent=2), encoding="utf-8")
        return jsonify({"name": name, "path": str(path), "diagram": diagram})
    except Exception as exc:
        return jsonify({"error": f"Failed to import editor-core document: {exc}"}), 500


# ── Execute diagram ──────────────────────────────────────────────────

@bp.route("/api/execute", methods=["POST"])
def execute():
    body = request.get_json(force=True)
    if not body or "blocks" not in body:
        return jsonify({"error": "Invalid diagram — missing 'blocks'"}), 400

    engine = _get_engine()
    with _lock:
        result = engine.execute(body)
    return jsonify(result)


@bp.route("/api/stop", methods=["POST"])
def stop():
    engine = _get_engine()
    engine.request_stop()
    return jsonify({"stopped": True})


# ── Save / Load ──────────────────────────────────────────────────────

@bp.route("/api/save", methods=["POST"])
def save():
    body = request.get_json(force=True)
    name = body.get("name", "autosave")
    diagram = body.get("diagram", {})

    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = _SAVE_DIR / f"{name}.json"
    path.write_text(json.dumps(diagram, indent=2), encoding="utf-8")
    logger.info("FlowLab diagram saved: %s", path)
    return jsonify({"success": True, "path": str(path)})


@bp.route("/api/load")
def load():
    name = request.args.get("name", "autosave")
    path = _SAVE_DIR / f"{name}.json"
    if not path.exists():
        return jsonify({"diagram": None})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return jsonify({"diagram": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/list")
def list_diagrams():
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(_SAVE_DIR.glob("*.json"))
    return jsonify({"diagrams": [f.stem for f in files]})


# ── Block catalogue (mirror of JS catalogue for tooling) ─────────────

@bp.route("/api/blocks")
def block_types():
    engine = _get_engine()
    return jsonify({"blocks": list(engine.block_registry.keys())})


# ── Export as Python source ──────────────────────────────────────────

@bp.route("/api/export_python", methods=["POST"])
def export_python():
    """Convert the current FlowLab diagram to a standalone Python script.

    Accepts:
        {"diagram": {...}, "name": "optional_script_name"}
    Returns:
        {"source": "#!/usr/bin/env python3\\n..."}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    name = body.get("name", "flowlab_export")

    try:
        source = diagram_to_python(diagram, script_name=name)
        return jsonify({"source": source, "name": name})
    except Exception as exc:
        logger.exception("Python export failed")
        return jsonify({"error": str(exc)}), 500


# ── Import diagram from file ────────────────────────────────────────

@bp.route("/api/import_diagram", methods=["POST"])
def import_diagram():
    """Import a FlowLab diagram from a JSON file or Python script.

    Accepts multipart/form-data with a ``file`` field, or JSON body:
        - ``{"source": "...python source..."}`` — extract embedded diagram
        - ``{"diagram": {...}}`` — direct diagram JSON
    Returns:
        {"diagram": {...FlowLab diagram...}}
    """
    # Handle file upload (multipart)
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file uploaded"}), 400

        text = f.read().decode("utf-8", errors="replace")
        fname = f.filename or ""

        if fname.endswith(".py"):
            diagram = extract_diagram_from_python(text)
            if not diagram:
                return jsonify({"error": "No embedded FlowLab diagram found in .py file"}), 400
            return jsonify({"diagram": diagram, "source": "python"})

        elif fname.endswith(".json"):
            try:
                data = json.loads(text)
                # Could be a direct diagram or a wrapper
                if "blocks" in data:
                    return jsonify({"diagram": data, "source": "json"})
                elif "diagram" in data:
                    return jsonify({"diagram": data["diagram"], "source": "json"})
                else:
                    return jsonify({"error": "JSON file does not contain a FlowLab diagram (no 'blocks' key)"}), 400
            except json.JSONDecodeError as exc:
                return jsonify({"error": f"Invalid JSON: {exc}"}), 400

        else:
            return jsonify({"error": f"Unsupported file type: {fname}. Use .py or .json"}), 400

    # Handle JSON body
    body = request.get_json(force=True, silent=True) or {}

    # Direct diagram JSON
    if body.get("diagram") and body["diagram"].get("blocks"):
        return jsonify({"diagram": body["diagram"], "source": "json"})

    # Python source string
    source = body.get("source", "")
    if source:
        diagram = extract_diagram_from_python(source)
        if diagram:
            return jsonify({"diagram": diagram, "source": "python"})
        return jsonify({"error": "No embedded FlowLab diagram found in Python source"}), 400

    # Load from saved diagrams by name
    name = body.get("name", "")
    if name:
        path = _SAVE_DIR / f"{name}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return jsonify({"diagram": data, "source": "saved"})
            except Exception as exc:
                return jsonify({"error": f"Failed to load: {exc}"}), 500
        return jsonify({"error": f"Diagram not found: {name}"}), 404

    return jsonify({"error": "Provide a file upload, 'source' (Python), 'diagram' (JSON), or 'name'"}), 400


# ── HIL ↔ FlowLab conversion ─────────────────────────────────────────

@bp.route("/api/export_hil", methods=["POST"])
def export_hil():
    """Convert the current FlowLab diagram to a HIL test profile JSON.

    Accepts:
        {"diagram": {...}, "name": "optional_name"}
    Returns:
        {"profile": {...HIL profile JSON...}}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    # Allow overriding name
    name = body.get("name", "flowlab_export")
    diagram["name"] = name

    try:
        profile = diagram_to_hil(diagram)
        return jsonify({"profile": profile})
    except Exception as exc:
        logger.exception("HIL export failed")
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/save_hil", methods=["POST"])
def save_hil():
    """Export diagram as HIL profile and save to profiles/ directory.

    Accepts:
        {"diagram": {...}, "name": "profile_name"}
    Returns:
        {"success": true, "path": "profiles/profile_name.json", "profile": {...}}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    name = body.get("name", "flowlab_export")

    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    diagram["name"] = name

    try:
        profile = diagram_to_hil(diagram)

        _HIL_DIR.mkdir(parents=True, exist_ok=True)
        path = _HIL_DIR / f"{name}.json"
        path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        logger.info("HIL profile saved: %s", path)
        return jsonify({"success": True, "path": str(path), "profile": profile})
    except Exception as exc:
        logger.exception("HIL save failed")
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/import_hil", methods=["POST"])
def import_hil():
    """Import a HIL test profile and convert to a FlowLab diagram.

    Accepts:
        {"profile": {...HIL profile JSON...}}
      OR
        {"name": "profile_name"}  (load from profiles/ directory)
    Returns:
        {"diagram": {...FlowLab diagram...}}
    """
    body = request.get_json(force=True)

    profile = body.get("profile")
    if not profile:
        # Try loading from file
        name = body.get("name", "")
        if not name:
            return jsonify({"error": "Provide 'profile' JSON or 'name' to load from disk"}), 400

        path = _HIL_DIR / f"{name}.json"
        if not path.exists():
            return jsonify({"error": f"Profile not found: {path}"}), 404
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return jsonify({"error": f"Failed to load profile: {exc}"}), 500

    try:
        diagram = hil_to_diagram(profile)
        return jsonify({"diagram": diagram})
    except Exception as exc:
        logger.exception("HIL import failed")
        return jsonify({"error": str(exc)}), 500


@bp.route("/api/hil_profiles")
def list_hil_profiles():
    """List available HIL profile JSON files from profiles/ directory."""
    _HIL_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(_HIL_DIR.glob("*.json"))
    profiles = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles.append({
                "name": f.stem,
                "description": data.get("description", ""),
                "steps": len(data.get("steps", data.get("actions", []))),
            })
        except Exception:
            profiles.append({"name": f.stem, "description": "(parse error)", "steps": 0})
    return jsonify({"profiles": profiles})


@bp.route("/api/run_hil", methods=["POST"])
def run_hil():
    """Export diagram to HIL, then execute via /hil/api/start.

    Accepts:
        {"diagram": {...}}
    Returns:
        {"profile": {...}, "execution": "started"|"error"}
    """
    body = request.get_json(force=True)
    diagram = body.get("diagram")
    if not diagram or not diagram.get("blocks"):
        return jsonify({"error": "Empty or invalid diagram"}), 400

    try:
        # Convert diagram to profile
        name = body.get("name", "flowlab_hil_run")
        diagram["name"] = name
        profile = diagram_to_hil(diagram)

        # Save as temp profile
        _HIL_DIR.mkdir(parents=True, exist_ok=True)
        path = _HIL_DIR / f"_flowlab_run.json"
        path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        # Try to start via test service
        try:
            from pyontrust.services.test_service import TestService
            svc = current_app.config.get("test_service")
            if svc and isinstance(svc, TestService):
                result = svc.start_profile(str(path))
                return jsonify({
                    "profile": profile,
                    "execution": "started",
                    "run_id": result.get("run_id") if isinstance(result, dict) else str(result),
                })
            else:
                return jsonify({
                    "profile": profile,
                    "execution": "no_test_service",
                    "message": "Profile exported but TestService not available. Use /hil/ to run manually.",
                    "profile_path": str(path),
                })
        except Exception as exc:
            logger.warning("Could not auto-start HIL run: %s", exc)
            return jsonify({
                "profile": profile,
                "execution": "saved_only",
                "message": f"Profile saved to {path}. Start via HIL dashboard.",
                "profile_path": str(path),
            })

    except Exception as exc:
        logger.exception("Run as HIL failed")
        return jsonify({"error": str(exc)}), 500
