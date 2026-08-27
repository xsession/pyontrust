"""Service layer — orchestrates core domain objects for the gateway.

Each service is a thin stateful façade around the core models, HAL
protocols, and analysis functions.  Services never import Flask — they
are framework-agnostic and can be used from CLI scripts or tests.
"""
from __future__ import annotations

from .test_service import TestService
from .log_service import LogService
from .artifact_service import ArtifactService
from .bench_service import BenchService
from .config_service import ConfigService

try:
    from .aoi_service import AOIService
except Exception:
    AOIService = None

try:
    from .thermal_service import ThermalService
except Exception:
    ThermalService = None

__all__ = [
    "TestService",
    "LogService",
    "ArtifactService",
    "BenchService",
    "ConfigService",
    "AOIService",
    "ThermalService",
]
