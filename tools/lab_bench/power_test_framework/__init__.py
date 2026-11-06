"""Power consumption test framework.

This package is intentionally dependency-light (standard library only for core)
so it can be used in lab PCs without complex Python environments.

Instrument drivers for specific hardware (PPK2, AD3, SK120, etc.) lazy-import
their optional dependencies only when actually instantiated.
"""

from .core import (
    PowerSample,
    PowerTrace,
    PowerSummary,
    TestArtifacts,
    TestContext,
    TestStep,
    PowerTest,
    PowerTestRunner,
)

from .recorders.base import Recorder
from .lab_bench import LabBench, InstrumentConfig, CalibrationData
from .limits import Verdict, Limit, LimitResult, TestSpec, TestVerdict, evaluate
