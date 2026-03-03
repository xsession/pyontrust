from __future__ import annotations

from pydantic import BaseModel


class UiConfig(BaseModel):
    fps_limit: int = 30
    fft_bins: int = 1024
    waterfall_bins: int = 256
    waterfall_rows: int = 200
    max_scope_points: int = 1024


class RuntimeConfig(BaseModel):
    chunk_size: int = 4096
    ring_chunks: int = 32


class SdrConfig(BaseModel):
    ui: UiConfig = UiConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    default_driver: str = "sim"
