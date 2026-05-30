"""Shared helpers for interface documentation code generators."""

from __future__ import annotations

import html as html_mod
import logging
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def get_jinja_env(**kwargs) -> Environment:
    """Create a Jinja2 environment with FileSystemLoader and custom filters."""
    defaults = dict(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    defaults.update(kwargs)
    env = Environment(**defaults)
    env.filters["upper_snake"] = upper_snake
    env.filters["ljust"] = lambda s, w: str(s).ljust(w)
    env.filters["hexf"] = lambda v, spec="#08x": format(int(v), spec)
    env.filters["esc"] = esc
    return env


# ── YAML helpers ─────────────────────────────────────────────────


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_types(deps: list[Path]) -> dict[str, dict]:
    """Merge all types from dependency files."""
    types: dict[str, dict] = {}
    for dep in deps:
        data = load_yaml(dep)
        types.update(data.get("types", {}))
    return types


def detect_hex_enum_types(paths: list[Path]) -> list[str]:
    """Return enum type names whose values are authored as hex literals.

    The YAML loader normalizes hex values into integers, so this scans the raw
    source text to preserve the author's intended formatting for generated code.
    """

    detected: OrderedDict[str, None] = OrderedDict()
    for path in paths:
        if not path.exists():
            continue

        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            match = re.match(r"^\s{2}([A-Za-z0-9_]+):\s*$", lines[index])
            if not match:
                index += 1
                continue

            type_name = match.group(1)
            index += 1
            block_lines: list[str] = []
            while index < len(lines) and not re.match(r"^\s{2}[A-Za-z0-9_]+:\s*$", lines[index]):
                block_lines.append(lines[index])
                index += 1

            if not any(re.match(r"^\s{4}format:\s*enum\s*$", line) for line in block_lines):
                continue

            values = _extract_enum_value_literals(block_lines)
            if values and all(_is_hex_literal(value) for value in values):
                detected[type_name] = None

    return list(detected.keys())


def _extract_enum_value_literals(block_lines: list[str]) -> list[str]:
    values: list[str] = []
    in_values = False
    for line in block_lines:
        if re.match(r"^\s{4}values:\s*$", line):
            in_values = True
            continue
        if not in_values:
            continue

        value_match = re.match(r"^\s{6}[A-Za-z0-9_]+:\s*([^\s#]+)", line)
        if value_match:
            values.append(value_match.group(1))
            continue

        if line.strip() == "":
            continue
        if re.match(r"^\s{4}[A-Za-z0-9_]+", line):
            break
    return values


def _is_hex_literal(value: str) -> bool:
    return bool(re.match(r"^0x[0-9a-fA-F]+$", value.strip()))


# ── Type mapping helpers ─────────────────────────────────────────


def c_type_name(yaml_type: str | dict) -> str:
    """Map a YAML type to a C type string."""
    if isinstance(yaml_type, dict):
        fmt = yaml_type.get("format", "uint")
        size = yaml_type.get("size", 32)
        if fmt == "int":
            return f"int{size}_t"
        return f"uint{size}_t"
    simple = {
        "string": "char*",
        "bytes": "uint8_t*",
        "uint8": "uint8_t",
        "uint16": "uint16_t",
        "uint32": "uint32_t",
        "int8": "int8_t",
        "int16": "int16_t",
        "int32": "int32_t",
        "float32": "float",
        "float64": "double",
        "bit1": "uint8_t",
        "uint4": "uint8_t",
        "uint12": "uint16_t",
    }
    if isinstance(yaml_type, str):
        if yaml_type.startswith("EXT__"):
            stem = yaml_type[5:]
            if stem.endswith("_tun"):
                return f"{stem}_t"
            if stem.endswith("_tst"):
                return f"{stem}_t"
            if stem.endswith("_ten"):
                return f"{stem}_t"
            return f"{stem}_t"
        return simple.get(yaml_type, yaml_type)
    return "uint32_t"


def py_type_name(yaml_type: str | dict) -> str:
    """Map a YAML type to a Python type hint."""
    if isinstance(yaml_type, dict):
        return "int"
    simple = {
        "string": "str",
        "bytes": "bytes",
        "uint8": "int",
        "uint16": "int",
        "uint32": "int",
        "int8": "int",
        "int16": "int",
        "int32": "int",
        "float32": "float",
        "float64": "float",
        "bit1": "int",
        "uint4": "int",
        "uint12": "int",
    }
    if isinstance(yaml_type, str):
        if yaml_type.startswith("EXT__"):
            return "int"
        return simple.get(yaml_type, "int")
    return "int"


def upper_snake(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", name).upper()


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def esc(s: str) -> str:
    """HTML-escape a string."""
    return html_mod.escape(str(s))
