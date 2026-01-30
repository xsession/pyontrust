from __future__ import annotations

from typing import Any

from nicegui import ui


def render_stats(table: ui.table, stats: dict[str, Any]) -> None:
    rows = []
    for col, st in (stats or {}).items():
        rows.append(
            {
                "signal": col,
                "min": st.get("min"),
                "max": st.get("max"),
                "mean": st.get("mean"),
                "median": st.get("median"),
                "p2p": st.get("p2p"),
            }
        )
    table.rows = rows
    table.update()
