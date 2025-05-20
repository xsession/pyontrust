import numpy as np
import pandas as pd
from scipy import signal
from typing import Tuple

class SignalGenerator:
    @staticmethod
    def generate_square_wave(
        duration: float = 1.0,       # seconds
        frequency: float = 1.0,      # Hz
        duty: float = 0.5,           # 0.0–1.0
        sample_rate: float = 1000,   # Hz
        phase_shift: float = 0.0     # seconds
    ) -> Tuple[np.ndarray, np.ndarray]:
        t = np.arange(0, duration, 1 / sample_rate)
        wave = signal.square(2 * np.pi * frequency * (t - phase_shift), duty=duty)
        return t, wave
    
    def generate_sine_wave(
        duration: float = 1.0,       # seconds
        frequency: float = 1.0,      # Hz
        sample_rate: float = 1000,   # Hz
        phase_shift: float = 0.0     # seconds
    ) -> Tuple[np.ndarray, np.ndarray]:
        t = np.arange(0, duration, 1 / sample_rate)
        wave = np.sin(2 * np.pi * frequency * (t - phase_shift))
        return t, wave
    
    def generate_triangle_wave(
        duration: float = 1.0,       # seconds
        frequency: float = 1.0,      # Hz
        sample_rate: float = 1000,   # Hz
        phase_shift: float = 0.0     # seconds
    ) -> Tuple[np.ndarray, np.ndarray]:
        t = np.arange(0, duration, 1 / sample_rate)
        wave = signal.sawtooth(2 * np.pi * frequency * (t - phase_shift), 0.5)
        return t, wave
    
    def generate_sawtooth_wave(
        duration: float = 1.0,       # seconds
        frequency: float = 1.0,      # Hz
        sample_rate: float = 1000,   # Hz
        phase_shift: float = 0.0     # seconds
    ) -> Tuple[np.ndarray, np.ndarray]:
        t = np.arange(0, duration, 1 / sample_rate)
        wave = signal.sawtooth(2 * np.pi * frequency * (t - phase_shift))
        return t, wave
    
    def generate_noise(
        duration: float = 1.0,       # seconds
        sample_rate: float = 1000,   # Hz
        noise_level: float = 0.1     # standard deviation
    ) -> Tuple[np.ndarray, np.ndarray]:
        t = np.arange(0, duration, 1 / sample_rate)
        noise = np.random.normal(0, noise_level, len(t))
        return t, noise
    
    def generate_custom_waveform(
        duration: float = 1.0,       # seconds
        frequency: float = 1.0,      # Hz
        sample_rate: float = 1000,   # Hz
        waveform_func: callable = None,
        phase_shift: float = 0.0     # seconds
    ) -> Tuple[np.ndarray, np.ndarray]:
        t = np.arange(0, duration, 1 / sample_rate)
        if waveform_func is None:
            raise ValueError("No waveform function provided.")
        wave = waveform_func(2 * np.pi * frequency * (t - phase_shift))
        return t, wave
    
    @staticmethod
    def save_to_csv(file_path: str, time: np.ndarray, value: np.ndarray):
        df = pd.DataFrame({'time': time, 'value': value})
        df.to_csv(file_path, index=False)
        print(f"Saved: {file_path}")
        
if __name__ == "__main__":
    t, wave = SignalGenerator.generate_square_wave(duration=5, frequency=1, duty=0.5)
    SignalGenerator.save_to_csv("square_wave.csv", t, wave)