"""Power consumption test framework.

This package is intentionally dependency-light (standard library only) so it can be used in lab PCs without complex Python environments.
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
