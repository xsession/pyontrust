from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppState:
    csv_path: str = ""
    columns: list[str] = field(default_factory=list)
    x_col: str = ""
    y_cols: list[str] = field(default_factory=list)
    max_points: int = 5000
