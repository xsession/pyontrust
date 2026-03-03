"""Structured logging for the CSV Plotter application.

Provides a centralized, configurable logger that replaces the ad-hoc
``_debug_log`` calls and silent ``except Exception: pass`` patterns
throughout the codebase.

Usage::

    from core.logger import get_logger
    log = get_logger(__name__)

    log.info("Loaded %d rows from %s", len(df), path)
    log.warning("Window mask produced empty result, falling back to full series")
    log.error("Failed to compute metrics for %s", col, exc_info=True)

The logger writes to both stderr (for IDE / terminal visibility) and an
optional rotating log file (``csv_plotter.log`` next to the main script).
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional


_LOG_FORMAT = "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s"
_LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_LOG_FILE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_LOG_FILE_BACKUP_COUNT = 3

_configured = False


def configure_logging(
    *,
    level: int = logging.INFO,
    log_dir: Optional[str | Path] = None,
    log_file: str = "csv_plotter.log",
    enable_file: bool = True,
) -> None:
    """Set up the root ``csv_plotter`` logger.

    Safe to call multiple times — only the first call has effect.

    Args:
        level: Minimum log level (default: INFO; set DEBUG for verbose output).
        log_dir: Directory for the log file.  Defaults to the directory
            containing ``csv_plotter.py``.
        log_file: Log file name.
        enable_file: Whether to write a rotating log file (disable for tests).
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("csv_plotter")
    root.setLevel(level)
    root.propagate = False

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FMT))
    root.addHandler(console)

    # File handler (rotating)
    if enable_file:
        try:
            if log_dir is None:
                log_dir = Path(__file__).resolve().parent.parent
            log_path = Path(log_dir) / log_file
            fh = logging.handlers.RotatingFileHandler(
                str(log_path),
                maxBytes=_LOG_FILE_MAX_BYTES,
                backupCount=_LOG_FILE_BACKUP_COUNT,
                encoding="utf-8",
            )
            fh.setLevel(logging.DEBUG)  # file always captures debug
            fh.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FMT))
            root.addHandler(fh)
        except Exception:
            root.warning("Could not set up file logging to %s", log_path, exc_info=True)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``csv_plotter`` namespace.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance.

    Example::

        log = get_logger(__name__)
        log.debug("Cache hit for key=%s", key)
    """
    # Ensure the root logger is configured at least at default level.
    configure_logging()
    # Prefix with csv_plotter. if not already present.
    if not name.startswith("csv_plotter"):
        name = f"csv_plotter.{name}"
    return logging.getLogger(name)
