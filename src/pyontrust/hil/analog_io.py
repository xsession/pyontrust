"""Analog I/O interface for AD3.

Provides high-level analog input (oscilloscope) and output (waveform generator)
operations using the AD3's 2 analog input and 2 analog output channels.
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Iterator, Optional, Sequence

if TYPE_CHECKING:
    from pyontrust.hil.ad3_interface import AD3Interface


class WaveformType(IntEnum):
    """Waveform types for analog output."""
    DC = 0
    SINE = 1
    SQUARE = 2
    TRIANGLE = 3
    RAMP_UP = 4
    RAMP_DOWN = 5
    NOISE = 6
    PULSE = 7
    TRAPEZIUM = 8
    SINE_POWER = 9
    CUSTOM = 30
    PLAY = 31


class TriggerSource(IntEnum):
    """Trigger sources for acquisition."""
    NONE = 0
    PC = 1
    DETECTOR_ANALOG_IN = 2
    DETECTOR_DIGITAL_IN = 3
    ANALOG_IN = 4
    DIGITAL_IN = 5
    DIGITAL_OUT = 6
    ANALOG_OUT1 = 7
    ANALOG_OUT2 = 8
    ANALOG_OUT3 = 9
    ANALOG_OUT4 = 10
    EXTERNAL1 = 11
    EXTERNAL2 = 12
    EXTERNAL3 = 13
    EXTERNAL4 = 14


class AcquisitionState(IntEnum):
    """Acquisition states."""
    READY = 0
    ARMED = 1
    DONE = 2
    TRIGGERED = 3
    CONFIG = 4
    PREFILL = 5
    WAIT = 7


@dataclass
class AnalogSample:
    """A single analog sample."""
    timestamp_s: float
    channel: int
    voltage_v: float


@dataclass
class AnalogIO:
    """Analog I/O interface for AD3.
    
    Provides access to:
    - 2 analog input channels (oscilloscope/voltmeter)
    - 2 analog output channels (waveform generator)
    
    Example:
        ad3 = AD3Interface()
        ad3.open()
        
        # Read voltage
        voltage = ad3.analog.read_voltage(0)
        
        # Configure and start waveform
        ad3.analog.set_waveform(0, WaveformType.SINE, 1000, 1.0)
        ad3.analog.output_enable(0, True)
        
        # Capture waveform
        samples = list(ad3.analog.capture(0, duration_s=0.1))
    """
    
    ad3: "AD3Interface"
    
    # Default configuration
    _sample_rate: float = field(default=1_000_000.0, init=False)
    _buffer_size: int = field(default=8192, init=False)
    _channel_range: dict = field(default_factory=lambda: {0: 5.0, 1: 5.0}, init=False)
    _channel_offset: dict = field(default_factory=lambda: {0: 0.0, 1: 0.0}, init=False)
    
    # ========== Analog Input (Oscilloscope) ==========
    
    def configure_input(
        self,
        channel: int,
        range_v: float = 5.0,
        offset_v: float = 0.0,
        sample_rate_hz: Optional[float] = None,
        buffer_size: Optional[int] = None,
    ) -> None:
        """Configure an analog input channel.
        
        Args:
            channel: Analog input channel (0 or 1)
            range_v: Input voltage range (±range_v)
            offset_v: Input offset voltage
            sample_rate_hz: Sample rate in Hz (default: 1 MHz)
            buffer_size: Acquisition buffer size (default: 8192)
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        if sample_rate_hz is not None:
            self._sample_rate = sample_rate_hz
        if buffer_size is not None:
            self._buffer_size = buffer_size
        
        self._channel_range[channel] = range_v
        self._channel_offset[channel] = offset_v
        
        # Enable channel
        dwf.FDwfAnalogInChannelEnableSet(hdwf, ctypes.c_int(channel), ctypes.c_int(1))
        
        # Set range and offset
        dwf.FDwfAnalogInChannelRangeSet(hdwf, ctypes.c_int(channel), ctypes.c_double(range_v))
        dwf.FDwfAnalogInChannelOffsetSet(hdwf, ctypes.c_int(channel), ctypes.c_double(offset_v))
        
        # Set sample rate and buffer
        dwf.FDwfAnalogInFrequencySet(hdwf, ctypes.c_double(self._sample_rate))
        dwf.FDwfAnalogInBufferSizeSet(hdwf, ctypes.c_int(self._buffer_size))
    
    def read_voltage(self, channel: int) -> float:
        """Read a single voltage sample from an analog input.
        
        This performs a quick single-sample acquisition.
        
        Args:
            channel: Analog input channel (0 or 1)
            
        Returns:
            Voltage in volts
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        # Start acquisition
        dwf.FDwfAnalogInConfigure(hdwf, ctypes.c_int(1), ctypes.c_int(1))
        
        # Wait briefly for sample
        time.sleep(0.001)
        
        # Read status and sample
        status = ctypes.c_int()
        dwf.FDwfAnalogInStatus(hdwf, ctypes.c_int(1), ctypes.byref(status))
        
        voltage = ctypes.c_double()
        dwf.FDwfAnalogInStatusSample(hdwf, ctypes.c_int(channel), ctypes.byref(voltage))
        
        return voltage.value
    
    def read_voltages(self) -> tuple[float, float]:
        """Read voltages from both analog input channels.
        
        Returns:
            Tuple of (channel0_voltage, channel1_voltage)
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        # Start acquisition
        dwf.FDwfAnalogInConfigure(hdwf, ctypes.c_int(1), ctypes.c_int(1))
        
        time.sleep(0.001)
        
        status = ctypes.c_int()
        dwf.FDwfAnalogInStatus(hdwf, ctypes.c_int(1), ctypes.byref(status))
        
        v0 = ctypes.c_double()
        v1 = ctypes.c_double()
        dwf.FDwfAnalogInStatusSample(hdwf, ctypes.c_int(0), ctypes.byref(v0))
        dwf.FDwfAnalogInStatusSample(hdwf, ctypes.c_int(1), ctypes.byref(v1))
        
        return (v0.value, v1.value)
    
    def capture(
        self,
        channel: int,
        duration_s: float,
        sample_rate_hz: Optional[float] = None,
    ) -> Iterator[AnalogSample]:
        """Capture analog samples over a duration.
        
        Args:
            channel: Analog input channel (0 or 1)
            duration_s: Capture duration in seconds
            sample_rate_hz: Optional sample rate override
            
        Yields:
            AnalogSample objects
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        rate = sample_rate_hz or self._sample_rate
        dwf.FDwfAnalogInFrequencySet(hdwf, ctypes.c_double(rate))
        
        # Start acquisition
        dwf.FDwfAnalogInConfigure(hdwf, ctypes.c_int(1), ctypes.c_int(1))
        
        start_time = time.perf_counter()
        t = 0.0
        dt = 1.0 / rate
        
        voltage = ctypes.c_double()
        status = ctypes.c_int()
        
        while t < duration_s:
            dwf.FDwfAnalogInStatus(hdwf, ctypes.c_int(1), ctypes.byref(status))
            dwf.FDwfAnalogInStatusSample(hdwf, ctypes.c_int(channel), ctypes.byref(voltage))
            
            yield AnalogSample(
                timestamp_s=t,
                channel=channel,
                voltage_v=voltage.value
            )
            
            time.sleep(max(0, dt))
            t = time.perf_counter() - start_time
    
    def capture_buffer(
        self,
        channel: int,
        num_samples: int,
        sample_rate_hz: Optional[float] = None,
        timeout_s: float = 5.0,
    ) -> list[float]:
        """Capture a buffer of samples.
        
        Args:
            channel: Analog input channel (0 or 1)
            num_samples: Number of samples to capture
            sample_rate_hz: Optional sample rate override
            timeout_s: Timeout in seconds
            
        Returns:
            List of voltage values
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        rate = sample_rate_hz or self._sample_rate
        dwf.FDwfAnalogInFrequencySet(hdwf, ctypes.c_double(rate))
        dwf.FDwfAnalogInBufferSizeSet(hdwf, ctypes.c_int(num_samples))
        
        # Start acquisition
        dwf.FDwfAnalogInConfigure(hdwf, ctypes.c_int(0), ctypes.c_int(1))
        
        # Wait for acquisition to complete
        status = ctypes.c_int()
        start = time.perf_counter()
        
        while True:
            dwf.FDwfAnalogInStatus(hdwf, ctypes.c_int(1), ctypes.byref(status))
            if status.value == AcquisitionState.DONE:
                break
            if time.perf_counter() - start > timeout_s:
                raise TimeoutError("Analog acquisition timeout")
            time.sleep(0.001)
        
        # Read data
        data = (ctypes.c_double * num_samples)()
        dwf.FDwfAnalogInStatusData(hdwf, ctypes.c_int(channel), data, ctypes.c_int(num_samples))
        
        return list(data)
    
    # ========== Analog Output (Waveform Generator) ==========
    
    def set_dc(self, channel: int, voltage_v: float) -> None:
        """Set a DC voltage on an analog output.
        
        Args:
            channel: Analog output channel (0 or 1)
            voltage_v: Output voltage in volts
        """
        self.set_waveform(channel, WaveformType.DC, 0, voltage_v, offset_v=voltage_v)
    
    def set_waveform(
        self,
        channel: int,
        waveform: WaveformType,
        frequency_hz: float,
        amplitude_v: float,
        offset_v: float = 0.0,
    ) -> None:
        """Configure a waveform on an analog output.
        
        Args:
            channel: Analog output channel (0 or 1)
            waveform: Waveform type
            frequency_hz: Waveform frequency in Hz
            amplitude_v: Waveform amplitude in volts (peak)
            offset_v: DC offset in volts
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        # Node 0 = carrier
        node = 0
        
        # Enable the node
        dwf.FDwfAnalogOutNodeEnableSet(hdwf, ctypes.c_int(channel), ctypes.c_int(node), ctypes.c_int(1))
        
        # Set waveform parameters
        dwf.FDwfAnalogOutNodeFunctionSet(hdwf, ctypes.c_int(channel), ctypes.c_int(node), ctypes.c_int(waveform))
        dwf.FDwfAnalogOutNodeFrequencySet(hdwf, ctypes.c_int(channel), ctypes.c_int(node), ctypes.c_double(frequency_hz))
        dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, ctypes.c_int(channel), ctypes.c_int(node), ctypes.c_double(amplitude_v))
        dwf.FDwfAnalogOutNodeOffsetSet(hdwf, ctypes.c_int(channel), ctypes.c_int(node), ctypes.c_double(offset_v))
    
    def output_enable(self, channel: int, enable: bool = True) -> None:
        """Enable or disable an analog output.
        
        Args:
            channel: Analog output channel (0 or 1)
            enable: True to enable, False to disable
        """
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        dwf.FDwfAnalogOutConfigure(hdwf, ctypes.c_int(channel), ctypes.c_int(1 if enable else 0))
    
    def output_disable(self, channel: int) -> None:
        """Disable an analog output.
        
        Args:
            channel: Analog output channel (0 or 1)
        """
        self.output_enable(channel, False)
    
    # ========== PWM Measurement Helpers ==========
    
    def measure_pwm(
        self,
        channel: int,
        num_periods: int = 10,
        sample_rate_hz: float = 1_000_000.0,
        threshold_v: Optional[float] = None,
    ) -> dict:
        """Measure PWM signal parameters.
        
        Args:
            channel: Analog input channel
            num_periods: Minimum number of periods to capture
            sample_rate_hz: Sample rate for measurement
            threshold_v: Threshold for high/low detection (None = auto)
            
        Returns:
            Dictionary with 'frequency_hz', 'duty_cycle', 'period_s',
            'high_time_s', 'low_time_s'
        """
        # Capture enough samples to see multiple periods
        # Start with a rough estimate and adjust
        samples = self.capture_buffer(
            channel,
            num_samples=min(8192, int(sample_rate_hz * 0.1)),  # 100ms max
            sample_rate_hz=sample_rate_hz,
        )
        
        if len(samples) < 10:
            raise ValueError("Not enough samples captured")
        
        # Auto-threshold if not specified
        if threshold_v is None:
            min_v = min(samples)
            max_v = max(samples)
            threshold_v = (min_v + max_v) / 2
        
        # Find edges
        high_samples = 0
        low_samples = 0
        rising_edges = []
        falling_edges = []
        prev_high = samples[0] > threshold_v
        
        for i, v in enumerate(samples):
            is_high = v > threshold_v
            if is_high:
                high_samples += 1
            else:
                low_samples += 1
            
            if is_high and not prev_high:
                rising_edges.append(i)
            elif not is_high and prev_high:
                falling_edges.append(i)
            prev_high = is_high
        
        if len(rising_edges) < 2:
            raise ValueError("Could not detect PWM signal (not enough edges)")
        
        # Calculate period from rising edges
        periods = []
        for i in range(1, len(rising_edges)):
            period_samples = rising_edges[i] - rising_edges[i-1]
            periods.append(period_samples / sample_rate_hz)
        
        avg_period = sum(periods) / len(periods)
        frequency = 1.0 / avg_period if avg_period > 0 else 0
        
        # Calculate duty cycle
        duty_cycle = high_samples / (high_samples + low_samples)
        
        return {
            "frequency_hz": frequency,
            "duty_cycle": duty_cycle,
            "period_s": avg_period,
            "high_time_s": avg_period * duty_cycle,
            "low_time_s": avg_period * (1 - duty_cycle),
            "min_v": min(samples),
            "max_v": max(samples),
            "threshold_v": threshold_v,
        }
    
    # ========== Convenience methods for board pins ==========
    
    def read_pin_voltage(self, pin_name: str) -> float:
        """Read voltage from a pin by its board pin name.
        
        Args:
            pin_name: Board pin name (e.g., 'PA7')
            
        Returns:
            Voltage in volts
            
        Raises:
            ValueError: If pin is not mapped to AD3 analog input
        """
        channel = self.ad3.get_pin_ain(pin_name)
        if channel is None:
            raise ValueError(f"Pin {pin_name} is not mapped to AD3 analog input")
        return self.read_voltage(channel)
    
    def set_pin_voltage(self, pin_name: str, voltage_v: float) -> None:
        """Set DC voltage on a pin by its board pin name.
        
        Args:
            pin_name: Board pin name (e.g., 'PA15')
            voltage_v: Voltage to output
            
        Raises:
            ValueError: If pin is not mapped to AD3 analog output
        """
        channel = self.ad3.get_pin_aout(pin_name)
        if channel is None:
            raise ValueError(f"Pin {pin_name} is not mapped to AD3 analog output")
        self.set_dc(channel, voltage_v)
        self.output_enable(channel, True)
