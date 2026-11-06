"""Microphone capture."""
from .capture import MicStream, MultiMicCapture, mic_stream_from_termux

__all__ = ["MicStream", "MultiMicCapture", "mic_stream_from_termux"]
