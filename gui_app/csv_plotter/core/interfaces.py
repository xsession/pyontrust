"""Typed interface contracts for the CSV Plotter application.

These ``Protocol`` classes define the API surface that plot renderers,
persistence modules, and UI components rely on, **without** requiring
them to import the 4 000-line ``CSVPlotterApp`` class directly.

This enables:
- Static type-checking with ``mypy`` / ``pyright``.
- Unit-testable modules that accept a mock implementing the protocol.
- Clear documentation of what each subsystem actually needs from the app.

Usage in a module that currently takes an untyped ``app`` parameter::

    from core.interfaces import PlotterApp

    def build_main_plot(app: PlotterApp, selector: SubplotSelectorLike, ...) -> ...:
        df = app.df
        ...
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

import pandas as pd

if TYPE_CHECKING:
    import tkinter as tk


# ---------------------------------------------------------------------------
# SubplotSelector-like protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class SubplotSelectorLike(Protocol):
    """Minimal interface of a subplot selector consumed by plot renderers."""

    def get_selected_columns(self, all_columns: Any = None) -> list[str]: ...
    def get_plot_mode(self) -> str: ...
    def get_x_window(self) -> tuple[float, float] | None: ...
    def get_files(self) -> list[str]: ...
    def get_file_shifts(self) -> dict[str, dict[str, float]]: ...
    def get_x_alignment_mode(self) -> str: ...
    def get_ylim_config(self) -> dict: ...
    def get_display_config(self) -> dict: ...
    def get_barrier_config(self) -> dict: ...
    def get_custom_code(self) -> str: ...
    def set_stats_text(self, text: str) -> None: ...
    def is_file_enabled(self, path: str) -> bool: ...


# ---------------------------------------------------------------------------
# Plotter app protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class PlotterApp(Protocol):
    """Typed interface for the CSV Plotter application object.

    Every module that currently receives an untyped ``app`` parameter
    should type it as ``PlotterApp`` instead.  This documents exactly
    which attributes and methods the module depends on and enables
    static analysis and mock-based testing.
    """

    # -- Data ---------------------------------------------------------------
    @property
    def df(self) -> pd.DataFrame:
        """The currently loaded DataFrame (may be empty)."""
        ...

    @property
    def last_loaded_file(self) -> str:
        """Absolute path of the most recently loaded CSV file."""
        ...

    @property
    def subplots(self) -> list[SubplotSelectorLike]:
        """Active subplot selectors."""
        ...

    # -- Status / UI --------------------------------------------------------
    @property
    def status_var(self) -> Any:
        """A ``tk.StringVar``-like object with ``.get()`` / ``.set()``."""
        ...

    @property
    def language(self) -> str:
        """Current i18n language code (e.g. ``"en"``)."""
        ...

    # -- Caching / helpers --------------------------------------------------

    def _to_numeric_cached(self, df: pd.DataFrame, path: str, col: str) -> pd.Series:
        """Return ``pd.to_numeric(df[col], errors='coerce')`` with caching."""
        ...

    def _get_df_for_path(
        self, path: str, selector: SubplotSelectorLike
    ) -> tuple[pd.DataFrame, float]:
        """Load and cache the DataFrame for *path*, returning ``(df, scale_to_seconds)``."""
        ...

    def _compute_signal_metrics_cached(
        self,
        *,
        path: str,
        col: str,
        x: pd.Series,
        y: pd.Series,
        xwin: tuple[float, float] | None,
        x_align: str,
        x_shift_s: float,
        y_shift: float,
        scale_to_seconds: float,
    ) -> tuple[str, str, str, str, str, str, str, str, str, str]:
        """Cached signal metrics (min, max, avg, med, p2p, std, rms, crest, freq, period)."""
        ...

    def _histogram_cached(
        self,
        *,
        path: str,
        col: str,
        y: pd.Series,
        bins: int,
        xwin: tuple[float, float] | None,
        x_align: str,
        x_shift_s: float,
        y_shift: float,
    ) -> Any:
        """Cached histogram computation."""
        ...

    def request_replot(self) -> None:
        """Schedule a debounced replot."""
        ...

    # -- Optional extended attributes (accessed via getattr with defaults) ---
    # These are NOT required by every consumer — use ``getattr(app, ..., default)``
    # for them.  Documenting them here for discoverability.

    # file_history: list[str]
    # use_datashader: bool
    # datashader_threshold: int
    # mpl_max_points: int
    # _theme_palette: dict
    # _highlight_keys: set[str]


# ---------------------------------------------------------------------------
# Cache entry typing
# ---------------------------------------------------------------------------

class CacheEntry(dict):
    """Type-safe wrapper for ``_df_cache`` entries.

    Keys:
        ``"df"``            — ``pd.DataFrame``
        ``"mtime"``         — ``float``
        ``"metrics_cache"`` — ``dict[tuple, tuple[str, ...]]``
        ``"hist_cache"``    — ``dict[tuple, Any]``
        ``"numeric_cache"`` — ``dict[str, pd.Series]``
    """
    pass
