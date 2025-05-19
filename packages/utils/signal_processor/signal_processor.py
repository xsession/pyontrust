import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from scipy.interpolate import interp1d
import json


class SignalLoader:
    @staticmethod
    def from_csv(file_path: str, time_col: str = "time", value_col: str = "value") -> Tuple[np.ndarray, np.ndarray]:
        df = pd.read_csv(file_path)
        return df[time_col].values, df[value_col].values

    @staticmethod
    def to_csv(file_path: str, time: np.ndarray, value: np.ndarray):
        df = pd.DataFrame({"time": time, "value": value})
        df.to_csv(file_path, index=False)

    @staticmethod
    def save_analysis_json(file_path: str, analysis_results: List[dict]):
        with open(file_path, "w") as f:
            json.dump(analysis_results, f, indent=4)

if __name__ == "__main__":
    # Example usage
    signal_loader = SignalLoader()
    time, signal = signal_loader.from_csv("example.csv")