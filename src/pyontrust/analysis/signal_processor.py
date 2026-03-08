"""Signal processor — time/frequency domain analysis.

Migrated from pyontrust_packages/utils/signal_processor/signal_processor.py.
Wraps numpy/scipy/pandas for CSV-based signal analysis.
"""

from __future__ import annotations

import json
from typing import Tuple

import numpy as np
import pandas as pd


class SignalLoader:
    """Load/save signals from CSV and analysis results to JSON."""

    @staticmethod
    def from_csv(file_path: str, time_col: str = "time", value_col: str = "value") -> Tuple[np.ndarray, np.ndarray]:
        df = pd.read_csv(file_path)
        return df[time_col].values, df[value_col].values

    @staticmethod
    def to_csv(file_path: str, time: np.ndarray, value: np.ndarray) -> None:
        df = pd.DataFrame({"time": time, "value": value})
        df.to_csv(file_path, index=False)

    @staticmethod
    def save_analysis_json(file_path: str, analysis_results: list[dict]) -> None:
        with open(file_path, "w") as f:
            json.dump(analysis_results, f, indent=4)
