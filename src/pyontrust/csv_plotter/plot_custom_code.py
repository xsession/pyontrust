"""Restricted helpers for the CSV Plotter custom-code panel.

This is a convenience guard, not a hardened sandbox. It is suitable for
trusted local users and mirrors the existing desktop app behavior.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


MAX_CODE_LENGTH: int = 50_000

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "range": range,
    "float": float,
    "int": int,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "enumerate": enumerate,
    "zip": zip,
    "sorted": sorted,
    "round": round,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "type": type,
    "print": print,
    "True": True,
    "False": False,
    "None": None,
}

_BLOCKED_PATTERNS: list[str] = [
    "__import__",
    "__builtins__",
    "__subclasses__",
    "__globals__",
]


def _safe_exec(code: str) -> dict[str, Any]:
    if not code or not code.strip():
        return {}

    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(
            f"Custom code exceeds maximum length ({len(code):,} > {MAX_CODE_LENGTH:,} chars)"
        )

    for pattern in _BLOCKED_PATTERNS:
        if pattern in code:
            raise ValueError(f"Blocked pattern found in custom code: {pattern!r}")

    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore[assignment]

    safe_builtins = dict(_SAFE_BUILTINS)
    safe_builtins["__import__"] = __builtins__["__import__"] if isinstance(__builtins__, dict) else getattr(__builtins__, "__import__")

    globals_ns: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "pd": pd,
        "np": np,
    }
    locals_ns: dict[str, Any] = {}
    exec(compile(code, "<custom-plot>", "exec"), globals_ns, locals_ns)
    merged = dict(globals_ns)
    merged.update(locals_ns)
    return merged


def _normalize_output(out: Any, *, index: pd.Index, x: pd.Series) -> dict[str, pd.Series]:
    if out is None:
        return {}

    if isinstance(out, dict):
        result: dict[str, pd.Series] = {}
        for key, value in out.items():
            name = str(key)
            if isinstance(value, pd.Series):
                series = value
            else:
                try:
                    series = pd.Series(value, index=index)
                except Exception:
                    continue
            result[name] = series
        return result

    if isinstance(out, pd.Series):
        return {"out": out}

    try:
        numeric = float(out)
        return {"out": pd.Series([numeric] * len(index), index=index)}
    except Exception:
        pass

    try:
        return {"out": pd.Series(out, index=index)}
    except Exception:
        return {}