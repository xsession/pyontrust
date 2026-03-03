from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pandas as pd

try:
    from data import find_newest_csv, read_any_csv_arrow, read_any_csv
except Exception:  # pragma: no cover
    find_newest_csv = None
    read_any_csv_arrow = None
    read_any_csv = None

from .model import PlotState


class CsvPlotterProtocol:
    def __init__(self, state: PlotState, on_state_change: Callable[[PlotState], None] | None = None) -> None:
        self.state = state
        self._on_state_change = on_state_change

    def _notify(self) -> None:
        if self._on_state_change is None:
            return
        try:
            self._on_state_change(self.state)
        except Exception:
            pass

    def set_folder(self, folder: str) -> None:
        self.state.folder_path = str(folder or "")
        self._notify()

    def set_selected_columns(self, columns: list[str]) -> None:
        self.state.selected_columns = list(columns or [])
        self._notify()

    def load_newest_in_folder(self, folder: str | None = None) -> None:
        if find_newest_csv is None:
            raise RuntimeError("csv_plotter.data not available")
        path = str(folder or self.state.folder_path)
        newest = find_newest_csv(path)
        self.load_file(newest)

    def load_file(self, path: str) -> None:
        path = str(path or "")
        if not path:
            raise ValueError("CSV path is empty")
        if not Path(path).exists():
            raise FileNotFoundError(path)
        df = self._read_csv(path)
        self.state.file_path = path
        self.state.set_df(df)
        try:
            self.state.last_loaded_mtime = float(Path(path).stat().st_mtime)
        except Exception:
            self.state.last_loaded_mtime = None
        self.state.status = f"Loaded: {os.path.basename(path)}"
        self._notify()

    def reload_if_changed(self) -> bool:
        path = str(self.state.file_path or "")
        if not path:
            return False
        try:
            mtime = float(Path(path).stat().st_mtime)
        except Exception:
            return False
        if self.state.last_loaded_mtime is None or mtime > float(self.state.last_loaded_mtime):
            self.load_file(path)
            return True
        return False

    def _read_csv(self, path: str) -> pd.DataFrame:
        if read_any_csv_arrow is not None:
            try:
                return read_any_csv_arrow(path)
            except Exception:
                pass
        if read_any_csv is not None:
            return read_any_csv(path)
        raise RuntimeError("CSV reader not available")
