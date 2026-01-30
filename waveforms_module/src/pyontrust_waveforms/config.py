from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class HalSelection(BaseModel):
    name: str = Field(default="simulated", description="HAL plugin name")
    config: dict = Field(default_factory=dict, description="HAL-specific config")


class UiConfig(BaseModel):
    fps_limit: int = Field(default=60, ge=1, le=240)
    display_points: int = Field(default=1200, ge=200, le=20000)
    default_view: Literal["scope", "spectrum", "split"] = "split"


class MalConfig(BaseModel):
    ring_frames: int = Field(default=8, ge=1, le=256)
    drop_policy: Literal["drop_old", "drop_new"] = "drop_old"


class WaveformsConfig(BaseModel):
    schema_version: int = Field(default=1, frozen=True)
    hal: HalSelection = Field(default_factory=HalSelection)
    mal: MalConfig = Field(default_factory=MalConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    offline: bool = False
    replay_path: Optional[str] = None
