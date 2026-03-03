from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd


@dataclass
class PlotState:
    file_path: str = ""
    folder_path: str = "log"
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    columns: list[str] = field(default_factory=list)
    selected_columns: list[str] = field(default_factory=list)
    status: str = ""
    last_loaded_mtime: float | None = None

    def set_df(self, df: pd.DataFrame) -> None:
        self.df = df if df is not None else pd.DataFrame()
        try:
            self.columns = [str(c) for c in list(self.df.columns)]
        except Exception:
            self.columns = []
        if not self.selected_columns:
            self.selected_columns = list(self.columns[:4])

    def clear(self) -> None:
        self.df = pd.DataFrame()
        self.columns = []
        self.selected_columns = []
        self.file_path = ""
        self.status = ""
        self.last_loaded_mtime = None
