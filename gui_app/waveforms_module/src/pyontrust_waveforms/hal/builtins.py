"""Registers built-in HAL plugins.

Importing this module should be safe on systems without vendor drivers.
"""

from . import file_replay  # noqa: F401
from . import simulated  # noqa: F401
from .dwf import dwf_hal  # noqa: F401
