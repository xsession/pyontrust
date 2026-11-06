from typing import List, Tuple, Optional
import numpy as np
from scipy.interpolate import interp1d
from .signal_processor import SignalLoader


class TimeAlignedSignalAnalyzer:
    def __init__(self, threshold: float = 0.1):
        self.threshold = threshold

    def detect_ramp_up(
        self, time: np.ndarray, signal: np.ndarray
    ) -> Optional[Tuple[int, int, float]]:
        signal = np.asarray(signal)
        time = np.asarray(time)
        max_val = np.max(signal)
        threshold_val = self.threshold * max_val

        above_threshold = np.where(signal >= threshold_val)[0]
        if len(above_threshold) == 0:
            return None

        start_idx = above_threshold[0]
        end_idx = start_idx
        for i in range(start_idx, len(signal)):
            if signal[i] >= 0.95 * max_val:
                end_idx = i
                break

        duration = time[end_idx] - time[start_idx]
        return start_idx, end_idx, duration

    def align_to_ramp_start(
        self, time: np.ndarray, signal: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        ramp = self.detect_ramp_up(time, signal)
        if ramp is None:
            raise ValueError("No ramp detected in signal.")
        start_time = time[ramp[0]]
        return time - start_time, signal

    def resample_signals(
        self,
        signals: List[Tuple[np.ndarray, np.ndarray]],
        resolution: float = 0.1,
        duration: Optional[float] = None,
    ) -> Tuple[np.ndarray, List[np.ndarray]]:
        aligned_signals = [self.align_to_ramp_start(t, s) for t, s in signals]

        if duration is None:
            duration = min(t[-1] for t, _ in aligned_signals)

        common_time = np.arange(0, duration, resolution)

        resampled_signals = []
        for t, s in aligned_signals:
            interp_func = interp1d(t, s, bounds_error=False, fill_value="extrapolate")
            resampled_signals.append(interp_func(common_time))

        return common_time, resampled_signals

    def batch_analysis(self, file_paths: List[str]) -> List[dict]:
        results = []
        for file_path in file_paths:
            time, value = SignalLoader.from_csv(file_path)
            ramp = self.detect_ramp_up(time, value)
            if ramp:
                results.append({
                    "file": file_path,
                    "ramp_start_time": float(time[ramp[0]]),
                    "ramp_end_time": float(time[ramp[1]]),
                    "ramp_duration": float(ramp[2])
                })
            else:
                results.append({
                    "file": file_path,
                    "error": "No ramp detected"
                })
        return results
    
if __name__ == "__main__":
    # Example usage
    analyzer = TimeAlignedSignalAnalyzer()
    time, signal = SignalLoader.from_csv("example.csv")
    aligned_time, aligned_signal = analyzer.align_to_ramp_start(time, signal)
    print("Aligned Time:", aligned_time)
    print("Aligned Signal:", aligned_signal)
    resampled_time, resampled_signals = analyzer.resample_signals([(time, signal)], resolution=0.1)
    print("Resampled Time:", resampled_time)
    print("Resampled Signals:", resampled_signals)