from __future__ import annotations

from typing import Any

from nicegui import ui


def render_chart(chart: ui.echart, data: dict[str, Any], x_col: str, y_cols: list[str]) -> None:
    x: list[float] = data.get("x", [])
    series_map: dict[str, list[float]] = data.get("series", {})

    series = []
    for col in y_cols:
        y = series_map.get(col, [])
        points = [[float(xi), float(yi)] for xi, yi in zip(x, y)]
        series.append({"name": col, "type": "line", "showSymbol": False, "data": points})

    chart.options = {
        "animation": False,
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll"},
        "xAxis": {"type": "value", "name": x_col},
        "yAxis": {"type": "value"},
        "series": series,
        "dataZoom": [
            {"type": "inside", "xAxisIndex": 0},
            {"type": "slider", "xAxisIndex": 0},
        ],
    }
    chart.update()
