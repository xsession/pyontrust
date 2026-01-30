from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_strings_json() -> dict[str, dict[str, str]]:
    """Load i18n/constants from strings.json next to this module.

    Keeps the app working even if the JSON file is missing or invalid.
    """
    try:
        base = Path(__file__).resolve().parent
        path = base / "strings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"en": {}}


STRINGS: dict[str, dict[str, str]] = _load_strings_json()


def t(app: Any | None, key: str, *, default: str | None = None, **fmt: object) -> str:
    """Translate a key using app.language (default 'en').

    - Falls back to English, then `default`, then the key itself.
    - Supports basic format placeholders via **fmt.
    """
    lang = getattr(app, "language", None) if app is not None else None
    if not isinstance(lang, str) or not lang:
        lang = "en"

    value = STRINGS.get(lang, {}).get(key)
    if value is None:
        value = STRINGS.get("en", {}).get(key)
    if value is None:
        value = default if default is not None else key

    if fmt:
        try:
            return value.format(**fmt)
        except Exception:
            return value
    return value
