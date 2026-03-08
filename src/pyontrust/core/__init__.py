"""Core domain models and execution engine.

Re-exports all public types for convenient imports::

    from pyontrust.core import PowerSample, PowerTrace, PowerTestRunner
"""

from pyontrust.core.models import (
    PowerSample,
    PowerSummary,
    PowerTrace,
    TestArtifacts,
    TestContext,
    TestStep,
    PowerTest,
)
from pyontrust.core.runner import PowerTestRunner
from pyontrust.core.lab_bench import LabBench, InstrumentConfig, CalibrationData
from pyontrust.core.limits import Verdict, Limit, LimitResult, TestSpec, TestVerdict, evaluate
from pyontrust.core.events import EventBus, Channel, TimestampedEvent
from pyontrust.core.reporting import write_power_trace_csv, write_summary_json, write_report_md

__all__ = [
    "PowerSample",
    "PowerSummary",
    "PowerTrace",
    "TestArtifacts",
    "TestContext",
    "TestStep",
    "PowerTest",
    "PowerTestRunner",
    "LabBench",
    "InstrumentConfig",
    "CalibrationData",
    "Verdict",
    "Limit",
    "LimitResult",
    "TestSpec",
    "TestVerdict",
    "evaluate",
    "EventBus",
    "Channel",
    "TimestampedEvent",
    "write_power_trace_csv",
    "write_summary_json",
    "write_report_md",
]
