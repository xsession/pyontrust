
from numpy import fft, abs, angle

from typing import List, Tuple
import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import find_peaks
from scipy import signal
from .signal_processor import SignalLoader
from .signal_generator import SignalGenerator
from scipy.stats import linregress
from scipy import stats
from typing import Dict, Any
import json
import pandas as pd
import os


class FrequencyDomainPropertiesAnalyzer:
    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold

    def detect_ramp_up(self, time: np.ndarray, signal: np.ndarray) -> Tuple[int, int, float]:
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
    
    def fft_analysis(
        self, time: np.ndarray, signal: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        N = len(signal)
        T = time[1] - time[0]
        yf = fft.fft(signal)
        xf = fft.fftfreq(N, T)[:N // 2]
        return xf, 2.0 / N * abs(yf[:N // 2])
    
    def find_peaks(
        self, x: np.ndarray, y: np.ndarray, height: float = 0.05
    ) -> Tuple[np.ndarray, np.ndarray]:
        peaks, _ = find_peaks(y, height=height)
        return x[peaks], y[peaks]
    
    def calculate_rms(self, signal: np.ndarray) -> float:
        return np.sqrt(np.mean(signal**2))
    
    def calculate_mean(self, signal: np.ndarray) -> float:
        return np.mean(signal)
    
    def calculate_std(self, signal: np.ndarray) -> float:
        return np.std(signal)
    
    