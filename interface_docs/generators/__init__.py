"""Shared helpers for interface documentation code generators."""

from __future__ import annotations

import html as html_mod
import logging
import re
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
