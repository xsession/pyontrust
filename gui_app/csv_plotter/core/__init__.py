"""CSV Plotter core infrastructure.

This package provides the foundational building blocks that are
**independent of the Tkinter GUI**:

- :mod:`core.interfaces` — Typed Protocol classes for the app and selectors.
- :mod:`core.logger` — Structured logging with rotating file output.
- :mod:`core.model` — Lightweight data-transfer objects (``PlotState``).
- :mod:`core.plotting` — Headless PNG rendering for CI / export.
- :mod:`core.protocol` — Legacy protocol (kept for compatibility).
"""

from core.interfaces import PlotterApp, SubplotSelectorLike  # noqa: F401
from core.logger import configure_logging, get_logger  # noqa: F401
