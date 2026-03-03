from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DeviceInfo(BaseModel):
    device_id: str
    driver: str
    display_name: str
    meta: dict = Field(default_factory=dict)


SampleDType = Literal["complex64", "float32", "int16"]


class PortSpec(BaseModel):
    name: str
    dtype: SampleDType


class BlockSpec(BaseModel):
    id: str
    type: str
    params: dict = Field(default_factory=dict)


class EdgeSpec(BaseModel):
    src_block: str
    src_port: str
    dst_block: str
    dst_port: str


class GraphSpec(BaseModel):
    name: str = "untitled"
    blocks: list[BlockSpec] = Field(default_factory=list)
    edges: list[EdgeSpec] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class RxConfig(BaseModel):
    center_freq_hz: float = 100e6
    sample_rate_hz: float = 2e6
    gain_db: float = 20.0
    bandwidth_hz: Optional[float] = None
