"""CSV Plotter

########## ########## ########## 

Commit hash: d3fa80
Full commit hash: d3fa807141dda44ea975f5a8d438ec06b7454b4a
Commit date: Wed Feb 18 17:13:22 2026 +0100
Branch: feature/RD-464-dt-x-ace32-ct-detektor-hoz-bovitett-gui-keszitese
User name: Laszlo Ivanyi
User email: laszlo.ivanyi@mediso.com
Logged-in user: livanyi
         
Usage:
    csv_plotter
 
Options:
    -h --help         Show this screen.
    --version         Show version.
"""

__version__ = "0.0.1"
__description__ = "CSV Plotter"
__author__ = "Mediso Medical Imaging Systems"

import docopt
import os
import json
import socket
import sys
import subprocess
from pathlib import Path
import threading
import traceback
import datetime
import time
import webbrowser

import pandas as pd
import queue
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.widgets import SpanSelector

from data import find_newest_csv, read_any_csv, read_any_csv_arrow, read_csv_header, compute_timestamp_scale_for_df
from metrics import compute_signal_metrics
from ui.selector import SubplotSelector

from ui.menu import build_menu
from ui.help_content import show_help as show_help_dialog
from ui.help_content import show_about as show_about_dialog
from lang import t

try:
    from core.model import PlotState
    from core.protocol import CsvPlotterProtocol
except Exception:
    PlotState = None
    CsvPlotterProtocol = None


class _ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + 24
        except Exception:
            return
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(self._tip, text=self.text, relief=tk.SOLID, borderwidth=1)
        label.pack(ipadx=6, ipady=2)

    def _hide(self, _event=None):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

# Extracted responsibilities
from persistence.layout import (
    default_layout_path,
    build_layout_data,
    write_layout_json_atomic,
    save_layout_dialog,
    load_layout_dialog,
    load_layout_from_path,
    apply_layout_subplots,
)


def _open_path_in_default_app(path: Path) -> None:
    """Open a file/folder in the OS default handler."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])
from plots.plotting import plot_all as render_plot_all

class CSVPlotterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Subplot CSV Viewer")

        # Debug logging (writes next to this file). This is intentionally
        # lightweight and guarded so it won't crash the GUI.
        self._debug_enabled: bool = True
        try:
            self._debug_log_path = os.path.join(os.path.dirname(__file__), "csv_plotter_debug.log")
        except Exception:
            self._debug_log_path = None
        self._debug_log("=== app start ===")

        # Startup guard: prevent auto-load polling + autosave from clobbering an
        # existing layout.json before it is fully restored.
        self._startup_in_progress: bool = True
        self._watch_job = None

        # Ensure these exist even before the first async load finishes.
        self.df = pd.DataFrame()
        self.file_path = ""

        # UI theme (VSCode-like)
        self.ui_theme_var = tk.StringVar(value="dark")
        self._theme_palette: dict[str, str] = {}

        self._init_style()
        self.subplot_count = 0
        self.subplots = []
        self.plot_canvases = []
        self.all_axes = []
        self.updating_xlim = False  # used to prevent recursive zoom syncing
        # When the user clicks the Matplotlib toolbar Home button, we want to
        # return to the full series and clear any analysis window persistence.
        # Home triggers xlim callbacks; this flag prevents on_xlim_changed from
        # immediately re-saving a window.
        self._ignore_next_xlim_persist: bool = False
        # Home can trigger multiple xlim_changed events; ignore a few so we
        # don't accidentally re-save a zoom window right after clearing it.
        self._ignore_xlim_persist_count: int = 0
        # Also ignore persistence for a short time window after Home; some
        # backends can emit delayed xlim_changed events.
        self._ignore_xlim_persist_until: float = 0.0
        self._replot_job = None
        # Bulk-update guard: avoid triggering multiple expensive replots during
        # file loads / selector rebuilds.
        self._replot_suspend_count: int = 0
        self._replot_in_progress = False
        self._replot_pending = False
        # Plot highlight state: allow multi-select across subplots.
        # Keys are channel names (typically the CSV column name).
        self._highlighted_channels: set[str] = set()
        # Track stats tables created during rendering so we can update highlight without replot.
        self._stats_trees: list = []
        self._mousewheel_target: str | None = None
        self._span_selectors = []
        self._timestamp_scale_to_seconds: float = 1.0
        # Global timestep / timebase override.
        # If enabled, this defines seconds-per-x-unit used for duration/frequency.
        # Default requested: ms and 0.01 step.
        self.global_timestep_mode_var = tk.StringVar(value="fixed")  # fixed|auto
        self.global_timestep_unit_var = tk.StringVar(value="ms")  # s|ms|us
        self.global_timestep_step_var = tk.StringVar(value="0.01")
        # High-density rendering options
        self.use_datashader: bool = True
        self.datashader_threshold: int = 1_000_000

        # cache for additional CSVs used in multi-file overlays
        # path -> {mtime: float|None, df: DataFrame, scale_to_seconds: float}
        self._df_cache: dict[str, dict] = {}
        self._perspective_server = None
        self._perspective_thread = None
        self._perspective_port = 8089
        self._perspective_table = None
        self._perspective_table_name = "default"

        # Async file loading state
        self._load_in_progress: bool = False
        self._pending_load_path: str | None = None
        self._loading_dlg = None
        self._loading_bar = None
        self._loading_label_var = None
        self._bg_queue: queue.Queue = queue.Queue()
        self._bg_queue_job = None
        self._closing = False

        # UI: plots pane visibility (user requested left-only workflow)
        self._plots_visible: bool = True

        default_folder = "log"
        if Path("C:/temp_gui_reports/detector_curve_logs").exists():
            default_folder = "C:/temp_gui_reports/detector_curve_logs"

        self.current_folder = default_folder
        self.last_loaded_file = None

        self.core_state = PlotState(folder_path=self.current_folder) if PlotState is not None else None
        self.core_protocol = CsvPlotterProtocol(self.core_state) if CsvPlotterProtocol is not None and self.core_state is not None else None

        # table styling (set once)
        self._table_style_inited = False

        # file history (most-recent-first)
        self.file_history: list[str] = []
        self.history_index: int = -1
        self.history_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.current_file_var = tk.StringVar(value="File: (none)")
        self.current_folder_var = tk.StringVar(value=f"Folder: {self.current_folder}")
        self.df_shape_var = tk.StringVar(value="Rows: 0  Cols: 0")

        self.auto_reload_selected_enabled = tk.BooleanVar(value=False)
        self._last_loaded_mtime: float | None = None

        # Auto-refresh periods (seconds)
        self.auto_load_newest_period_s = tk.StringVar(value="1")
        self.auto_reload_selected_period_s = tk.StringVar(value="1")

        # Settings
        self.open_folder_recursive_enabled = tk.BooleanVar(value=False)

        self.auto_save_layout_enabled = tk.BooleanVar(value=True)
        self._autosave_job = None
        # Prevent auto-save from overwriting a previously saved layout during startup.
        self._suppress_autosave = True

        # Layout UI restoration
        self._pending_ui_sashes: dict | None = None
        self._pending_plots_pane_sashes: list | None = None
        self._skip_default_layout_tune = False
        # When loading a layout, CSV loading is async. Store the layout dict and
        # apply subplots after the file load completes to avoid being reset.
        self._pending_layout_data: dict | None = None

        self._create_menu()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Poll background-worker results safely on the Tk thread.
        try:
            self._bg_queue_job = self.root.after(50, self._process_bg_queue)
        except Exception:
            self._bg_queue_job = None

        # Start auto-load polling only after startup completes (after layout load).

        # Main split layout (resizable)
        self.main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # Left UI panel
        self.ui_frame = ttk.Frame(self.main_pane, padding=(10, 8, 10, 8))
        self.main_pane.add(self.ui_frame, weight=1)

        # Left side split: controls vs subplot selectors (draggable sash)
        self.left_pane = ttk.Panedwindow(self.ui_frame, orient=tk.VERTICAL)
        self.left_pane.pack(fill=tk.BOTH, expand=True)

        # Controls (top)
        self.controls_scroll_frame = ttk.Frame(self.left_pane)

        self.controls_canvas = tk.Canvas(self.controls_scroll_frame, bg='SystemWindow', highlightthickness=0)
        self.controls_scrollbar = ttk.Scrollbar(
            self.controls_scroll_frame,
            orient=tk.VERTICAL,
            command=self.controls_canvas.yview,
        )
        self.controls_canvas.configure(yscrollcommand=self.controls_scrollbar.set)
        self.controls_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.controls_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.controls_frame = ttk.Frame(self.controls_canvas)
        self._controls_window_id = self.controls_canvas.create_window(
            (0, 0),
            window=self.controls_frame,
            anchor='nw',
        )
        self.controls_frame.bind(
            "<Configure>",
            lambda _e: self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all")),
        )
        self.controls_canvas.bind("<Configure>", self._on_controls_canvas_configure)
        self.controls_canvas.bind("<Enter>", lambda _e: self._set_mousewheel_target("controls"))
        self.controls_canvas.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))
        self.controls_frame.bind("<Enter>", lambda _e: self._set_mousewheel_target("controls"))
        self.controls_frame.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))

        self.actions_frame = ttk.LabelFrame(self.controls_frame, text="Quick Actions")
        self.actions_frame.pack(pady=(0, 6), fill='x')

        self.button_frame = ttk.Frame(self.actions_frame)
        self.button_frame.pack(pady=(2, 4), fill='x')

        btn_open = ttk.Button(self.button_frame, text="Choose CSV File", command=self.choose_file)
        btn_open.pack(side=tk.LEFT, padx=5)
        btn_add = ttk.Button(self.button_frame, text="Add Subplot", command=self.add_subplot)
        btn_add.pack(side=tk.LEFT, padx=5)
        btn_plot = ttk.Button(self.button_frame, text="Plot All", command=self.plot_all)
        btn_plot.pack(side=tk.LEFT, padx=5)
        btn_folder = ttk.Button(self.button_frame, text="Choose Folder", command=self.choose_folder)
        btn_folder.pack(side=tk.LEFT, padx=5)
        btn_persp = ttk.Button(self.button_frame, text="Open Perspective", command=self.open_perspective_view)
        btn_persp.pack(side=tk.LEFT, padx=5)

        _ToolTip(btn_open, "Open a specific CSV file")
        _ToolTip(btn_add, "Add a new subplot selector")
        _ToolTip(btn_plot, "Render all plots now")
        _ToolTip(btn_folder, "Pick a folder and auto-load newest CSV")
        _ToolTip(btn_persp, "Open the Perspective viewer for this data")

        self.auto_frame = ttk.LabelFrame(self.controls_frame, text="Auto Refresh")
        self.auto_frame.pack(pady=(0, 6), fill='x')

        self.auto_check_enabled = tk.BooleanVar(value=True)  # default: ON
        auto_newest = ttk.Checkbutton(
            self.auto_frame,
            text="Auto-load newest CSV",
            variable=self.auto_check_enabled,
        )
        auto_newest.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.auto_frame, text="every").pack(side=tk.LEFT, padx=(6, 2))
        try:
            newest_spin = ttk.Spinbox(
                self.auto_frame,
                from_=1,
                to=3600,
                increment=1,
                width=5,
                textvariable=self.auto_load_newest_period_s,
                command=self._on_refresh_period_changed,
            )
        except Exception:
            newest_spin = ttk.Entry(self.auto_frame, width=5, textvariable=self.auto_load_newest_period_s)
        newest_spin.pack(side=tk.LEFT)
        newest_spin.bind("<FocusOut>", lambda _e: self._on_refresh_period_changed(), add="+")
        ttk.Label(self.auto_frame, text="s").pack(side=tk.LEFT, padx=(2, 8))

        auto_reload = ttk.Checkbutton(
            self.auto_frame,
            text="Auto-reload selected CSV",
            variable=self.auto_reload_selected_enabled,
        )
        auto_reload.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.auto_frame, text="every").pack(side=tk.LEFT, padx=(6, 2))
        try:
            reload_spin = ttk.Spinbox(
                self.auto_frame,
                from_=1,
                to=3600,
                increment=1,
                width=5,
                textvariable=self.auto_reload_selected_period_s,
                command=self._on_refresh_period_changed,
            )
        except Exception:
            reload_spin = ttk.Entry(self.auto_frame, width=5, textvariable=self.auto_reload_selected_period_s)
        reload_spin.pack(side=tk.LEFT)
        reload_spin.bind("<FocusOut>", lambda _e: self._on_refresh_period_changed(), add="+")
        ttk.Label(self.auto_frame, text="s").pack(side=tk.LEFT, padx=(2, 0))

        _ToolTip(auto_newest, "Periodically load the newest CSV in the folder")
        _ToolTip(auto_reload, "Reload current CSV if it changes on disk")
        _ToolTip(newest_spin, "Seconds between newest-file checks")
        _ToolTip(reload_spin, "Seconds between reload checks")

        self.info_frame = ttk.Frame(self.controls_frame)
        self.info_frame.pack(fill="x", pady=(4, 2))
        ttk.Label(self.info_frame, textvariable=self.current_file_var, style="Info.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(self.info_frame, textvariable=self.df_shape_var, style="Info.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(self.info_frame, textvariable=self.current_folder_var, style="Muted.TLabel").pack(side=tk.LEFT)

        # Status bar (bottom)
        self.statusbar = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief=tk.SUNKEN, style="Status.TLabel")
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Subplot selector section (scrollable + resizable panes)
        self.selector_scroll_frame = ttk.Frame(self.left_pane)

        try:
            self.left_pane.add(self.controls_scroll_frame, weight=1)
            self.left_pane.add(self.selector_scroll_frame, weight=5)
            try:
                self.left_pane.pane(self.controls_scroll_frame, minsize=100)
                self.left_pane.pane(self.selector_scroll_frame, minsize=600)
            except Exception:
                pass
        except Exception:
            # If Panedwindow add fails for any reason, fall back to old packing.
            self.controls_scroll_frame.pack(pady=5, fill='x')
            self.selector_scroll_frame.pack(pady=5, fill='both', expand=True)

        self.selector_canvas = tk.Canvas(self.selector_scroll_frame, bg='SystemWindow', highlightthickness=0)
        self.selector_scrollbar = ttk.Scrollbar(
            self.selector_scroll_frame,
            orient=tk.VERTICAL,
            command=self.selector_canvas.yview,
        )
        self.selector_canvas.configure(yscrollcommand=self.selector_scrollbar.set)
        self.selector_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.selector_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.selector_inner = ttk.Frame(self.selector_canvas)
        self._selector_window_id = self.selector_canvas.create_window(
            (0, 0),
            window=self.selector_inner,
            anchor='nw',
        )
        self.selector_inner.bind(
            "<Configure>",
            lambda _e: self.selector_canvas.configure(scrollregion=self.selector_canvas.bbox("all")),
        )
        self.selector_canvas.bind("<Configure>", self._on_selector_canvas_configure)
        self.selector_canvas.bind("<Enter>", lambda _e: self._set_mousewheel_target("selector"))
        self.selector_canvas.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))
        self.selector_inner.bind("<Enter>", lambda _e: self._set_mousewheel_target("selector"))
        self.selector_inner.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))

        # Use tk.PanedWindow so users can resize selector panes by dragging the sash/handle.
        self.container = tk.PanedWindow(
            self.selector_inner,
            orient=tk.VERTICAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            showhandle=True,
        )
        self.container.pack(pady=5, fill='both', expand=True)

        # Plotting Area (right pane)
        self.plot_scroll_frame = ttk.Frame(self.main_pane, padding=(10, 8, 10, 8))
        self.main_pane.add(self.plot_scroll_frame, weight=3)

        # Keep panes usable when resizing
        try:
            self.main_pane.pane(self.ui_frame, minsize=330)
            self.main_pane.pane(self.plot_scroll_frame, minsize=500)
        except Exception:
            pass

        self.canvas = tk.Canvas(self.plot_scroll_frame, bg='SystemWindow')
        self.scrollbar = ttk.Scrollbar(self.plot_scroll_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.plot_area = ttk.Frame(self.canvas)
        self._plot_window_id = self.canvas.create_window((0, 0), window=self.plot_area, anchor='nw')
        self.plot_area.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_plot_canvas_configure)
        self.canvas.bind("<Enter>", lambda _e: self._set_mousewheel_target("plot"))
        self.canvas.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))
        self.plot_area.bind("<Enter>", lambda _e: self._set_mousewheel_target("plot"))
        self.plot_area.bind("<Leave>", lambda _e: self._set_mousewheel_target(None))
        self.root.bind_all("<MouseWheel>", self.on_mousewheel)

        # Keyboard shortcuts
        self._bind_shortcuts()

        # Tune default pane sizes for 1920x1080 (and make 1 subplot expand nicely)
        try:
            self.root.after(150, self._tune_default_layout)
        except Exception:
            pass

        # Plot panels (each subplot resizable vertically)
        self.plots_pane = ttk.Panedwindow(self.plot_area, orient=tk.VERTICAL)
        self.plots_pane.pack(fill=tk.BOTH, expand=True)

        # Plots are visible by default.

        # Startup: prefer restoring layout.json if present. This avoids clobbering
        # an existing layout file with the default "newest CSV" state.
        try:
            default_layout = self._default_layout_path()
            if isinstance(default_layout, str) and default_layout and Path(default_layout).exists():
                # Mark as restored so _tune_default_layout won't override sash positions.
                self._skip_default_layout_tune = True
                ok = bool(self._load_layout_from_path(default_layout, silent=True))
                if ok:
                    # Layout loader triggers file load; ensure plots render.
                    try:
                        self.request_replot()
                    except Exception:
                        pass
                else:
                    # Fall back if layout couldn't be applied.
                    self.file_path = find_newest_csv(self.current_folder)
                    self.load_file(self.file_path)
            else:
                # Load default file
                self.file_path = find_newest_csv(self.current_folder)
                self.load_file(self.file_path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Apply any pending sash restore once widgets are realized.
        try:
            self._apply_pending_ui_sashes_async()
        except Exception:
            pass

        # End startup after the initial load/render has had a chance to finish.
        try:
            self.root.after(600, self._finish_startup)
        except Exception:
            self._finish_startup()

    def _finish_startup(self) -> None:
        # Keep autosave suppressed until after the first plot render to avoid
        # overwriting layout.json with a partially-initialized state.
        try:
            if bool(getattr(self, "_closing", False)):
                return
        except Exception:
            pass

        # If a file load is still in progress, retry shortly.
        try:
            if bool(getattr(self, "_load_in_progress", False)):
                self.root.after(300, self._finish_startup)
                return
        except Exception:
            pass

        # Apply any pending sash restore now that geometry likely exists.
        try:
            self._apply_pending_ui_sashes_async()
        except Exception:
            pass

        # Now it's safe to enable autosave and start polling.
        self._startup_in_progress = False
        self._suppress_autosave = False
        self._start_watch_for_new_file()

    def _parse_period_ms(self, value: str | None, *, default_ms: int = 1000) -> int:
        """Parse a seconds value into milliseconds, with clamping."""
        try:
            s = str(value or "").strip()
            v = float(s)
            if not (v > 0):
                return int(default_ms)
            v = max(0.2, min(3600.0, v))
            return int(v * 1000.0)
        except Exception:
            return int(default_ms)

    def _current_watch_interval_ms(self) -> int:
        """Return poll interval (ms) based on which auto mode is currently active."""
        try:
            if bool(self.auto_check_enabled.get()):
                return self._parse_period_ms(self.auto_load_newest_period_s.get(), default_ms=1000)
        except Exception:
            pass
        try:
            if bool(self.auto_reload_selected_enabled.get()):
                return self._parse_period_ms(self.auto_reload_selected_period_s.get(), default_ms=1000)
        except Exception:
            pass
        return 1000

    def _restart_watch_for_new_file(self) -> None:
        """Cancel and re-schedule the auto poller with current interval."""
        try:
            job = getattr(self, "_watch_job", None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
            self._watch_job = None
        except Exception:
            self._watch_job = None

        # Don't schedule during startup restore.
        try:
            if bool(getattr(self, "_startup_in_progress", False)):
                return
        except Exception:
            pass

        try:
            self._watch_job = self.root.after(self._current_watch_interval_ms(), self.watch_for_new_file)
        except Exception:
            self._watch_job = None

    def _on_refresh_period_changed(self) -> None:
        """Validate/clamp periods and apply immediately."""
        # Clamp to at least 1s for UI simplicity.
        try:
            ms = self._parse_period_ms(self.auto_load_newest_period_s.get(), default_ms=1000)
            self.auto_load_newest_period_s.set(str(max(1, int(round(ms / 1000.0)))))
        except Exception:
            pass
        try:
            ms = self._parse_period_ms(self.auto_reload_selected_period_s.get(), default_ms=1000)
            self.auto_reload_selected_period_s.set(str(max(1, int(round(ms / 1000.0)))))
        except Exception:
            pass

        try:
            self._restart_watch_for_new_file()
        except Exception:
            pass

    def _start_watch_for_new_file(self) -> None:
        if self._watch_job is not None:
            return
        try:
            self._watch_job = self.root.after(self._current_watch_interval_ms(), self.watch_for_new_file)
        except Exception:
            self._watch_job = None

    def _begin_bulk_update(self) -> None:
        try:
            self._replot_suspend_count = int(getattr(self, "_replot_suspend_count", 0)) + 1
        except Exception:
            self._replot_suspend_count = 1

    def _end_bulk_update(self) -> None:
        try:
            self._replot_suspend_count = max(0, int(getattr(self, "_replot_suspend_count", 0)) - 1)
        except Exception:
            self._replot_suspend_count = 0

    def _to_numeric_cached(self, df: pd.DataFrame, path: str, col: str) -> pd.Series:
        """Fast cached pd.to_numeric(df[col]) per (file, column).

        This is one of the hottest paths when plotting + histogramming + metrics.
        Cache is invalidated automatically when the file mtime changes because it
        lives under the same _df_cache entry.
        """
        try:
            ap = os.path.abspath(str(path)) if path else str(path)
        except Exception:
            ap = str(path)

        entry = None
        try:
            entry = self._df_cache.get(ap)
        except Exception:
            entry = None

        if not isinstance(entry, dict):
            entry = {}
            try:
                self._df_cache[ap] = entry
            except Exception:
                pass

        try:
            num = entry.setdefault("numeric", {})
        except Exception:
            num = {}
            try:
                entry["numeric"] = num
            except Exception:
                pass

        key = str(col)
        cached = num.get(key)
        if isinstance(cached, pd.Series) and len(cached) == len(df):
            return cached

        try:
            s = pd.to_numeric(df[key], errors="coerce")
        except Exception:
            s = pd.Series([], dtype=float)
        try:
            num[key] = s
        except Exception:
            pass
        return s

    def _cache_key_window(self, xwin: tuple[float, float] | None) -> tuple[float, float] | None:
        if xwin is None:
            return None
        try:
            lo, hi = xwin
            return (round(float(lo), 6), round(float(hi), 6))
        except Exception:
            return None

    def _cache_key_float(self, v: float | None, digits: int) -> float | None:
        if v is None:
            return None
        try:
            return round(float(v), int(digits))
        except Exception:
            return None

    def _get_cache_entry_for_path(self, path: str) -> dict:
        try:
            ap = os.path.abspath(str(path)) if path else str(path)
        except Exception:
            ap = str(path)
        entry = self._df_cache.get(ap)
        if not isinstance(entry, dict):
            entry = {}
            try:
                self._df_cache[ap] = entry
            except Exception:
                pass
        return entry

    def _cache_prune(self, cache: dict, max_items: int) -> None:
        try:
            overflow = int(len(cache) - int(max_items))
        except Exception:
            return
        if overflow <= 0:
            return
        try:
            for _ in range(overflow):
                cache.pop(next(iter(cache)))
        except Exception:
            pass

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
        entry = self._get_cache_entry_for_path(path)
        try:
            cache = entry.setdefault("metrics_cache", {})
        except Exception:
            cache = {}
            try:
                entry["metrics_cache"] = cache
            except Exception:
                pass

        key = (
            str(col),
            self._cache_key_window(xwin),
            str(x_align or ""),
            self._cache_key_float(x_shift_s, 6),
            self._cache_key_float(y_shift, 6),
            self._cache_key_float(scale_to_seconds, 12),
        )
        cached = cache.get(key)
        if isinstance(cached, tuple) and len(cached) == 10:
            return cached

        result = compute_signal_metrics(x, y)
        # Display tweak: show period in a friendly time format (d:hh:mm:ss:ms)
        # when it is a numeric seconds value.
        try:
            if isinstance(result, tuple) and len(result) == 10:
                period_raw = result[9]
                try:
                    period_seconds = float(str(period_raw).strip())
                except Exception:
                    period_seconds = None
                if period_seconds is not None:
                    result = (*result[:9], self._format_duration(period_seconds))
        except Exception:
            pass
        try:
            # Don't cache all-n/a results – they may be caused by a transient
            # state (e.g. stale window, data not yet loaded) and should be
            # recomputed on the next call.
            all_na = all(str(v).lower() in ("n/a", "na", "nan") for v in result)
            if not all_na:
                cache[key] = result
                self._cache_prune(cache, 250)
        except Exception:
            pass
        return result

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
    ) -> tuple[object, object]:
        """Return (counts, edges) for a histogram of `y`.

        Cached per file+column+window+bins+shifts, so repeated replots with the
        same window do not recompute binning.
        """
        entry = self._get_cache_entry_for_path(path)
        try:
            cache = entry.setdefault("hist_cache", {})
        except Exception:
            cache = {}
            try:
                entry["hist_cache"] = cache
            except Exception:
                pass

        key = (
            str(col),
            int(bins),
            self._cache_key_window(xwin),
            str(x_align or ""),
            self._cache_key_float(x_shift_s, 6),
            self._cache_key_float(y_shift, 6),
        )
        cached = cache.get(key)
        if isinstance(cached, tuple) and len(cached) == 2:
            return cached

        try:
            import numpy as np
        except Exception:
            # Fallback: no caching benefit, but keep behavior.
            return (None, None)

        try:
            yy = y.dropna().to_numpy(dtype=float)
        except Exception:
            yy = None

        if yy is None or len(yy) == 0:
            return (None, None)

        try:
            counts, edges = np.histogram(yy, bins=int(bins))
        except Exception:
            return (None, None)

        result = (counts, edges)
        try:
            cache[key] = result
            self._cache_prune(cache, 250)
        except Exception:
            pass
        return result

    def _compute_timestamp_scale_for_df(self, df: pd.DataFrame) -> float:
        return compute_timestamp_scale_for_df(df)

    def _init_style(self) -> None:
        """Apply ttk look + comfortable spacing."""
        try:
            style = ttk.Style(self.root)
        except Exception:
            return

        # Default fonts (Windows: Segoe UI) for a cleaner modern look.
        try:
            df = tkfont.nametofont("TkDefaultFont")
            df.configure(family="Segoe UI", size=9)
            tf = tkfont.nametofont("TkTextFont")
            tf.configure(family="Segoe UI", size=9)
            ff = tkfont.nametofont("TkFixedFont")
            ff.configure(family="Consolas", size=9)
        except Exception:
            pass

        # VSCode-like themes require a theme that supports custom colors.
        try:
            available = set(style.theme_names())
            if "clam" in available:
                style.theme_use("clam")
        except Exception:
            pass

        try:
            style.configure("TLabelframe", padding=(10, 8, 10, 10))
            style.configure("TFrame", padding=0)
            style.configure("TSeparator", background="#3c3c3c")
        except Exception:
            pass

        # Apply the selected theme.
        try:
            self.apply_theme(str(self.ui_theme_var.get() or "dark"))
        except Exception:
            pass

    def _get_vscode_palette(self, theme: str) -> dict[str, str]:
        tname = str(theme or "dark").strip().lower()
        if tname == "light":
            return {
                "bg": "#ffffff",
                "panel": "#f3f3f3",
                "panel2": "#e9e9e9",
                "fg": "#1e1e1e",
                "muted": "#616161",
                "border": "#d4d4d4",
                "accent": "#007acc",
                "selection": "#cce8ff",
                "hover": "#e5f1fb",
                "pressed": "#cce8ff",
                "entry_bg": "#ffffff",
            }
        return {
            "bg": "#1e1e1e",
            "panel": "#252526",
            "panel2": "#2d2d30",
            "fg": "#d4d4d4",
            "muted": "#9aa0a6",
            "border": "#3c3c3c",
            "accent": "#007acc",
            # VS Code list/tree selection is closer to #264f78
            "selection": "#264f78",
            "hover": "#2a2a2a",
            "pressed": "#333333",
            "entry_bg": "#2a2a2a",
        }

    def apply_theme(self, theme: str) -> None:
        # Keep state in sync
        try:
            self.ui_theme_var.set(str(theme or "dark"))
        except Exception:
            pass

        palette = self._get_vscode_palette(theme)
        self._theme_palette = dict(palette)
        try:
            style = ttk.Style(self.root)
        except Exception:
            return

        bg = palette["bg"]
        panel = palette["panel"]
        panel2 = palette.get("panel2", panel)
        fg = palette["fg"]
        border = palette["border"]
        sel = palette["selection"]
        hover = palette.get("hover", border)
        pressed = palette.get("pressed", border)
        entry_bg = palette["entry_bg"]

        try:
            self.root.configure(background=bg)
        except Exception:
            pass

        # Base styles
        try:
            style.configure(".", background=bg, foreground=fg)
            style.configure("TFrame", background=bg)
            style.configure("TLabelframe", background=bg, foreground=fg)
            style.configure("TLabelframe.Label", background=bg, foreground=fg)
            style.configure("TLabel", background=bg, foreground=fg)
            style.configure("Info.TLabel", background=bg, foreground=fg)
            style.configure("Muted.TLabel", background=bg, foreground=palette.get("muted", fg))
            style.configure("Status.TLabel", background=panel2, foreground=fg)
            style.configure(
                "TButton",
                background=panel2,
                foreground=fg,
                padding=(10, 6),
                borderwidth=1,
                relief="flat",
                focusthickness=1,
                focuscolor=border,
            )
            style.map(
                "TButton",
                background=[("pressed", pressed), ("active", hover)],
                foreground=[("disabled", palette.get("muted", fg))],
            )
            style.configure("TCheckbutton", background=bg, foreground=fg)
            style.map("TCheckbutton", background=[("active", bg)])
            style.configure("TRadiobutton", background=bg, foreground=fg)
            style.map("TRadiobutton", background=[("active", bg)])
            style.configure("TEntry", fieldbackground=entry_bg, background=entry_bg, foreground=fg)
            style.configure("TCombobox", fieldbackground=entry_bg, background=entry_bg, foreground=fg)
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", entry_bg), ("disabled", panel)],
                background=[("active", panel2)],
                foreground=[("disabled", palette.get("muted", fg))],
            )
            style.configure("TMenubutton", background=panel2, foreground=fg, padding=(10, 6))
            style.map("TMenubutton", background=[("active", hover), ("pressed", pressed)])
            style.configure("TSeparator", background=border)
        except Exception:
            pass

        try:
            self.selector_canvas.configure(bg=panel)
            self.canvas.configure(bg=panel)
            self.controls_canvas.configure(bg=panel)
        except Exception:
            pass

        # Scrollbars (clam supports these; other themes may ignore)
        try:
            style.configure(
                "Vertical.TScrollbar",
                background=panel2,
                troughcolor=panel,
                bordercolor=border,
                arrowcolor=fg,
                lightcolor=panel2,
                darkcolor=panel2,
            )
            style.configure(
                "Horizontal.TScrollbar",
                background=panel2,
                troughcolor=panel,
                bordercolor=border,
                arrowcolor=fg,
                lightcolor=panel2,
                darkcolor=panel2,
            )
        except Exception:
            pass

        # Treeview
        try:
            style.configure(
                "Treeview",
                background=bg,
                fieldbackground=bg,
                foreground=fg,
                bordercolor=border,
                rowheight=22,
            )
            style.map(
                "Treeview",
                background=[("selected", sel)],
                foreground=[("selected", fg)],
            )
            style.configure(
                "Treeview.Heading",
                background=panel2,
                foreground=fg,
                relief="flat",
                padding=(6, 4),
                font=("Segoe UI", 9, "bold"),
            )
            style.map(
                "Treeview.Heading",
                background=[("active", hover), ("pressed", pressed)],
            )
        except Exception:
            pass

        # Our stats table style (inherits, but keep explicit)
        try:
            style.configure("Stats.Treeview", background=bg, fieldbackground=bg, foreground=fg)
            style.map("Stats.Treeview", background=[("selected", sel)], foreground=[("selected", fg)])
            style.configure("Stats.Treeview.Heading", background=panel2, foreground=fg)
        except Exception:
            pass

        # Status bar
        try:
            style.configure("Status.TLabel", background=panel, foreground=fg)
            if hasattr(self, "statusbar"):
                self.statusbar.configure(style="Status.TLabel")
        except Exception:
            pass

        # Canvases
        try:
            if hasattr(self, "selector_canvas"):
                self.selector_canvas.configure(bg=panel, highlightthickness=0, borderwidth=0)
            if hasattr(self, "canvas"):
                self.canvas.configure(bg=panel, highlightthickness=0, borderwidth=0)
        except Exception:
            pass

        # Selector listboxes (Tk widgets)
        try:
            for s in list(getattr(self, "subplots", []) or []):
                try:
                    s.apply_theme(palette)
                except Exception:
                    pass
        except Exception:
            pass

        # Update plots to match theme (only if a CSV is loaded)
        try:
            if hasattr(self, "df") and getattr(self, "df") is not None:
                self.request_replot()
        except Exception:
            pass

    def _apply_mpl_theme(self, fig, axes=None) -> None:
        """Apply VSCode-like colors to a Matplotlib figure."""
        pal = getattr(self, "_theme_palette", {})
        if not isinstance(pal, dict) or not pal:
            return

        bg = pal.get("bg")
        panel = pal.get("panel")
        fg = pal.get("fg")
        border = pal.get("border")

        # Derive a grid color
        grid = border

        try:
            if bg:
                fig.patch.set_facecolor(str(bg))
        except Exception:
            pass

        ax_list = []
        try:
            if axes is None:
                ax_list = list(getattr(fig, "axes", []) or [])
            else:
                ax_list = list(axes)
        except Exception:
            ax_list = []

        for ax in ax_list:
            try:
                if panel:
                    ax.set_facecolor(str(panel))
            except Exception:
                pass
            try:
                if fg:
                    ax.tick_params(colors=str(fg), which="both")
                    ax.xaxis.label.set_color(str(fg))
                    ax.yaxis.label.set_color(str(fg))
                    ax.title.set_color(str(fg))
            except Exception:
                pass
            try:
                if border:
                    for sp in ax.spines.values():
                        sp.set_color(str(border))
            except Exception:
                pass
            try:
                if grid:
                    ax.grid(True, color=str(grid), alpha=0.35)
            except Exception:
                pass
            try:
                leg = ax.get_legend()
                if leg is not None:
                    if panel:
                        leg.get_frame().set_facecolor(str(panel))
                    if border:
                        leg.get_frame().set_edgecolor(str(border))
                    if fg:
                        for txt in leg.get_texts():
                            txt.set_color(str(fg))
            except Exception:
                pass

    def show_settings(self) -> None:
        # Single-instance dialog
        existing = getattr(self, "_settings_dialog", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.lift()
                existing.focus_set()
                return
        except Exception:
            pass

        dlg = tk.Toplevel(self.root)
        self._settings_dialog = dlg
        dlg.title("Settings")
        try:
            dlg.transient(self.root)
            dlg.grab_set()
        except Exception:
            pass

        try:
            dlg.configure(background=self._theme_palette.get("bg") or "#1e1e1e")
        except Exception:
            pass

        outer = ttk.Frame(dlg, padding=(12, 10, 12, 10))
        outer.pack(fill=tk.BOTH, expand=True)

        # Theme
        theme_box = ttk.LabelFrame(outer, text="Theme")
        theme_box.pack(fill="x", pady=(0, 10))

        ttk.Radiobutton(theme_box, text="Dark (VS Code)", variable=self.ui_theme_var, value="dark").pack(
            anchor="w", padx=8, pady=(6, 0)
        )
        ttk.Radiobutton(theme_box, text="Light (VS Code)", variable=self.ui_theme_var, value="light").pack(
            anchor="w", padx=8, pady=(2, 6)
        )

        # Options
        opt_box = ttk.LabelFrame(outer, text="Options")
        opt_box.pack(fill="x")
        ttk.Checkbutton(
            opt_box,
            text="Auto-save layout (layout.json)",
            variable=self.auto_save_layout_enabled,
        ).pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Checkbutton(
            opt_box,
            text="Open Folder scans subfolders (recursive)",
            variable=self.open_folder_recursive_enabled,
        ).pack(anchor="w", padx=8, pady=(2, 0))
        ttk.Checkbutton(
            opt_box,
            text="Auto-load newest CSV",
            variable=self.auto_check_enabled,
        ).pack(anchor="w", padx=8, pady=(2, 0))

        newest_row = ttk.Frame(opt_box)
        newest_row.pack(anchor="w", padx=26, pady=(0, 2), fill="x")
        ttk.Label(newest_row, text="Refresh period (s):").pack(side=tk.LEFT)
        try:
            newest_period = ttk.Spinbox(
                newest_row,
                from_=1,
                to=3600,
                increment=1,
                width=6,
                textvariable=self.auto_load_newest_period_s,
                command=self._on_refresh_period_changed,
            )
        except Exception:
            newest_period = ttk.Entry(newest_row, width=6, textvariable=self.auto_load_newest_period_s)
        newest_period.pack(side=tk.LEFT, padx=(6, 0))
        newest_period.bind("<FocusOut>", lambda _e: self._on_refresh_period_changed(), add="+")
        ttk.Checkbutton(
            opt_box,
            text="Auto-reload selected CSV",
            variable=self.auto_reload_selected_enabled,
        ).pack(anchor="w", padx=8, pady=(2, 8))

        reload_row = ttk.Frame(opt_box)
        reload_row.pack(anchor="w", padx=26, pady=(0, 8), fill="x")
        ttk.Label(reload_row, text="Refresh period (s):").pack(side=tk.LEFT)
        try:
            reload_period = ttk.Spinbox(
                reload_row,
                from_=1,
                to=3600,
                increment=1,
                width=6,
                textvariable=self.auto_reload_selected_period_s,
                command=self._on_refresh_period_changed,
            )
        except Exception:
            reload_period = ttk.Entry(reload_row, width=6, textvariable=self.auto_reload_selected_period_s)
        reload_period.pack(side=tk.LEFT, padx=(6, 0))
        reload_period.bind("<FocusOut>", lambda _e: self._on_refresh_period_changed(), add="+")

        # Timebase / timestep
        tb_box = ttk.LabelFrame(outer, text="Timebase")
        tb_box.pack(fill="x", pady=(10, 0))

        tb_mode_row = ttk.Frame(tb_box)
        tb_mode_row.pack(anchor="w", padx=8, pady=(6, 2), fill="x")
        ttk.Label(tb_mode_row, text="Global timestep:").pack(side=tk.LEFT)
        tb_mode = ttk.Combobox(
            tb_mode_row,
            textvariable=self.global_timestep_mode_var,
            state="readonly",
            values=["fixed", "auto"],
            width=8,
        )
        tb_mode.pack(side=tk.LEFT, padx=(6, 10))

        tb_row = ttk.Frame(tb_box)
        tb_row.pack(anchor="w", padx=26, pady=(0, 8), fill="x")
        ttk.Label(tb_row, text="Unit:").pack(side=tk.LEFT)
        tb_unit = ttk.Combobox(
            tb_row,
            textvariable=self.global_timestep_unit_var,
            state="readonly",
            values=["s", "ms", "us"],
            width=5,
        )
        tb_unit.pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(tb_row, text="Step:").pack(side=tk.LEFT)
        tb_step = ttk.Entry(tb_row, textvariable=self.global_timestep_step_var, width=10)
        tb_step.pack(side=tk.LEFT, padx=(6, 0))

        def _tb_enable_state() -> None:
            try:
                m = str(self.global_timestep_mode_var.get() or "fixed").strip().lower()
            except Exception:
                m = "fixed"
            enable = bool(m == "fixed")
            try:
                tb_unit.configure(state=("readonly" if enable else "disabled"))
            except Exception:
                pass
            try:
                tb_step.configure(state=("normal" if enable else "disabled"))
            except Exception:
                pass

        def _apply_timebase() -> None:
            # Update base scale immediately for duration formatting, etc.
            try:
                base = getattr(self, "last_loaded_file", None) or getattr(self, "file_path", "")
            except Exception:
                base = ""
            try:
                ap = os.path.abspath(str(base)) if base else ""
            except Exception:
                ap = str(base)
            try:
                entry = self._df_cache.get(ap) if ap else None
                auto_scale = entry.get("scale_auto_to_seconds") if isinstance(entry, dict) else None
            except Exception:
                auto_scale = None
            if ap:
                try:
                    self._timestamp_scale_to_seconds = float(
                        self._effective_scale_to_seconds_for_path(ap, selector=None, auto_scale_to_seconds=float(auto_scale or self._timestamp_scale_to_seconds))
                    )
                except Exception:
                    pass
            try:
                self.request_replot()
            except Exception:
                pass
            try:
                self._schedule_autosave(immediate=True)
            except Exception:
                pass

        def _tb_changed(_e=None) -> None:
            _tb_enable_state()
            _apply_timebase()

        try:
            tb_mode.bind("<<ComboboxSelected>>", _tb_changed)
            tb_unit.bind("<<ComboboxSelected>>", _tb_changed)
            tb_step.bind("<FocusOut>", _tb_changed, add="+")
            tb_step.bind("<Return>", _tb_changed, add="+")
        except Exception:
            pass
        _tb_enable_state()

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x", pady=(10, 0))

        def _apply_then_close(close: bool) -> None:
            try:
                self.apply_theme(str(self.ui_theme_var.get() or "dark"))
            except Exception:
                pass
            try:
                self._on_refresh_period_changed()
            except Exception:
                pass
            try:
                _apply_timebase()
            except Exception:
                pass
            # Respect auto-save setting
            try:
                self._schedule_autosave()
            except Exception:
                pass
            if close:
                try:
                    dlg.destroy()
                except Exception:
                    pass

        ttk.Button(btn_row, text="Apply", command=lambda: _apply_then_close(False)).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_row, text="Close", command=lambda: _apply_then_close(True)).pack(side=tk.RIGHT)

        try:
            dlg.resizable(False, False)
        except Exception:
            pass

        try:
            dlg.protocol("WM_DELETE_WINDOW", lambda: _apply_then_close(True))
        except Exception:
            pass

    def _bind_shortcuts(self) -> None:
        """Common shortcuts for faster workflow."""
        def _safe(callable_fn):
            try:
                callable_fn()
            except Exception:
                pass

        try:
            self.root.bind("<F1>", lambda _e: _safe(self.show_help))
            self.root.bind("<Control-o>", lambda _e: _safe(self.choose_file))
            self.root.bind("<Control-O>", lambda _e: _safe(self.open_folder_load_all))
            self.root.bind("<Control-s>", lambda _e: _safe(self.save_layout))
            self.root.bind("<Control-l>", lambda _e: _safe(self.load_layout))
            self.root.bind("<Control-Shift-L>", lambda _e: _safe(self.clear_layout))
            self.root.bind("<Control-n>", lambda _e: _safe(self.add_subplot))
            self.root.bind("<Control-r>", lambda _e: _safe(self.plot_all))
            self.root.bind("<Control-p>", lambda _e: _safe(lambda: self._set_plots_visible(not self._plots_visible)))
            self.root.bind("<Escape>", lambda _e: _safe(self.clear_highlights))
        except Exception:
            pass

    def _show_loading(self, text: str) -> None:
        try:
            if self._loading_dlg is not None and bool(self._loading_dlg.winfo_exists()):
                try:
                    if self._loading_label_var is not None:
                        self._loading_label_var.set(text)
                except Exception:
                    pass
                return
        except Exception:
            pass

        try:
            dlg = tk.Toplevel(self.root)
            dlg.title("Loading")
            dlg.transient(self.root)
            dlg.grab_set()
            dlg.resizable(False, False)
            dlg.attributes("-topmost", True)

            outer = ttk.Frame(dlg, padding=(14, 12, 14, 12))
            outer.pack(fill="both", expand=True)

            self._loading_label_var = tk.StringVar(value=text)
            ttk.Label(outer, textvariable=self._loading_label_var).pack(anchor="w")
            bar = ttk.Progressbar(outer, mode="indeterminate", length=260)
            bar.pack(fill="x", pady=(10, 0))
            try:
                bar.start(12)
            except Exception:
                pass

            self._loading_dlg = dlg
            self._loading_bar = bar

            try:
                dlg.update_idletasks()
                # Center on root
                rx = self.root.winfo_rootx()
                ry = self.root.winfo_rooty()
                rw = self.root.winfo_width()
                rh = self.root.winfo_height()
                dw = dlg.winfo_reqwidth()
                dh = dlg.winfo_reqheight()
                x = rx + max(0, (rw - dw) // 2)
                y = ry + max(0, (rh - dh) // 3)
                dlg.geometry(f"{dw}x{dh}+{x}+{y}")
            except Exception:
                pass
        except Exception:
            self._loading_dlg = None
            self._loading_bar = None
            self._loading_label_var = None

        try:
            self.root.configure(cursor="watch")
        except Exception:
            pass

        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def _hide_loading(self) -> None:
        try:
            self.root.configure(cursor="")
        except Exception:
            pass

        try:
            if self._loading_bar is not None:
                try:
                    self._loading_bar.stop()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if self._loading_dlg is not None and bool(self._loading_dlg.winfo_exists()):
                try:
                    self._loading_dlg.grab_release()
                except Exception:
                    pass
                try:
                    self._loading_dlg.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        self._loading_dlg = None
        self._loading_bar = None
        self._loading_label_var = None

    def clear_highlights(self) -> None:
        try:
            self._highlighted_channels.clear()
        except Exception:
            pass
        self._apply_highlight_state()

    def _parse_float(self, s: str, default: float = 0.0) -> float:
        try:
            txt = str(s or "").strip()
            if "," in txt and "." not in txt:
                txt = txt.replace(",", ".")
            return float(txt)
        except Exception:
            return float(default)

    def _timebase_unit_to_seconds(self, unit: str) -> float:
        u = str(unit or "").strip().lower()
        if u == "s":
            return 1.0
        if u == "us":
            return 1e-6
        return 1e-3

    def _get_global_timebase_scale_to_seconds(self) -> float | None:
        try:
            mode = str(self.global_timestep_mode_var.get() or "fixed").strip().lower()
        except Exception:
            mode = "fixed"
        if mode != "fixed":
            return None

        try:
            unit = str(self.global_timestep_unit_var.get() or "ms").strip().lower()
        except Exception:
            unit = "ms"
        if unit not in ("s", "ms", "us"):
            unit = "ms"

        step = self._parse_float(str(self.global_timestep_step_var.get() or "0.01"), default=0.01)
        if step <= 0:
            step = 0.01
        return float(step) * float(self._timebase_unit_to_seconds(unit))

    def _effective_scale_to_seconds_for_path(self, path: str, *, selector=None, auto_scale_to_seconds: float | None = None) -> float:
        try:
            auto_scale = float(auto_scale_to_seconds) if auto_scale_to_seconds is not None else 1.0
        except Exception:
            auto_scale = 1.0

        try:
            ap = os.path.abspath(str(path))
        except Exception:
            ap = str(path)

        cfg = None
        try:
            if selector is not None and hasattr(selector, "get_file_timebase"):
                tb = selector.get_file_timebase()  # type: ignore[attr-defined]
                if isinstance(tb, dict):
                    cfg = tb.get(ap) or tb.get(str(path))
        except Exception:
            cfg = None

        try:
            mode = str(cfg.get("mode", "global") if isinstance(cfg, dict) else "global").strip().lower()
        except Exception:
            mode = "global"
        if mode not in ("global", "auto", "fixed"):
            mode = "global"

        if mode == "auto":
            return float(auto_scale)

        if mode == "fixed":
            unit = "ms"
            step = 0.01
            try:
                unit = str(cfg.get("unit", "ms") or "ms").strip().lower() if isinstance(cfg, dict) else "ms"
            except Exception:
                unit = "ms"
            if unit not in ("s", "ms", "us"):
                unit = "ms"
            try:
                step = float(cfg.get("step", 0.01)) if isinstance(cfg, dict) else 0.01
            except Exception:
                step = 0.01
            if step <= 0:
                step = 0.01
            return float(step) * float(self._timebase_unit_to_seconds(unit))

        global_scale = self._get_global_timebase_scale_to_seconds()
        if global_scale is not None:
            return float(global_scale)
        return float(auto_scale)

    def _effective_timebase_mode_for_path(self, path: str, *, selector=None) -> str:
        """Return effective timebase mode for a path: 'fixed' or 'auto'.

        - 'fixed' means user-selected constant timestep should be used, and time should be interpreted as uniform samples.
        - 'auto' means use the file's timestamp axis (and the auto-detected scaling).
        """
        try:
            ap = os.path.abspath(str(path))
        except Exception:
            ap = str(path)

        cfg = None
        try:
            if selector is not None and hasattr(selector, "get_file_timebase"):
                tb = selector.get_file_timebase()  # type: ignore[attr-defined]
                if isinstance(tb, dict):
                    cfg = tb.get(ap) or tb.get(str(path))
        except Exception:
            cfg = None

        try:
            mode = str(cfg.get("mode", "global") if isinstance(cfg, dict) else "global").strip().lower()
        except Exception:
            mode = "global"
        if mode not in ("global", "auto", "fixed"):
            mode = "global"

        if mode == "fixed":
            return "fixed"
        if mode == "auto":
            return "auto"

        # Global
        return "fixed" if (self._get_global_timebase_scale_to_seconds() is not None) else "auto"

    def _get_df_for_path(self, path: str, selector=None) -> tuple[pd.DataFrame | None, float]:
        """Return (df, effective_scale_to_seconds) for a CSV, using cache when possible."""
        if not path:
            return None, 1.0
        try:
            ap = os.path.abspath(str(path))
        except Exception:
            ap = str(path)

        # Base (currently loaded) file
        try:
            if isinstance(self.last_loaded_file, str) and self.last_loaded_file and os.path.abspath(self.last_loaded_file) == ap:
                df = getattr(self, "df", None)
                if isinstance(df, pd.DataFrame):
                    auto_scale = None
                    try:
                        entry = self._df_cache.get(ap)
                        if isinstance(entry, dict):
                            auto_scale = entry.get("scale_auto_to_seconds")
                    except Exception:
                        auto_scale = None
                    if auto_scale is None:
                        auto_scale = float(getattr(self, "_timestamp_scale_to_seconds", 1.0) or 1.0)
                    eff = self._effective_scale_to_seconds_for_path(ap, selector=selector, auto_scale_to_seconds=float(auto_scale or 1.0))
                    return df, float(eff)
        except Exception:
            pass

        # Cache lookup
        mtime: float | None
        try:
            mtime = float(Path(ap).stat().st_mtime)
        except Exception:
            mtime = None
        cached = self._df_cache.get(ap)
        try:
            if isinstance(cached, dict) and (cached.get("mtime") == mtime) and isinstance(cached.get("df"), pd.DataFrame):
                auto_scale = cached.get("scale_auto_to_seconds", cached.get("scale_to_seconds", 1.0))
                eff = self._effective_scale_to_seconds_for_path(ap, selector=selector, auto_scale_to_seconds=float(auto_scale or 1.0))
                return cached["df"], float(eff)
        except Exception:
            pass

        # Load
        try:
            df = read_any_csv(ap)
        except Exception:
            return None, 1.0

        scale = self._compute_timestamp_scale_for_df(df)
        try:
            cols = [str(c) for c in list(df.columns)]
        except Exception:
            cols = []
        eff = self._effective_scale_to_seconds_for_path(ap, selector=selector, auto_scale_to_seconds=float(scale or 1.0))
        self._df_cache[ap] = {
            "mtime": mtime,
            "df": df,
            "scale_to_seconds": float(eff),
            "scale_auto_to_seconds": float(scale or 1.0),
            "columns": cols,
        }
        return df, float(eff)

    def _get_columns_for_path(self, path: str) -> list[str]:
        """Return CSV column names for a path, using cache and header-only reads."""
        if not path:
            return []
        try:
            ap = os.path.abspath(str(path))
        except Exception:
            ap = str(path)

        # Base (currently loaded) file
        try:
            if isinstance(self.last_loaded_file, str) and self.last_loaded_file and os.path.abspath(self.last_loaded_file) == ap:
                df = getattr(self, "df", None)
                if isinstance(df, pd.DataFrame):
                    return [str(c) for c in list(df.columns)]
        except Exception:
            pass

        try:
            mtime = float(Path(ap).stat().st_mtime)
        except Exception:
            mtime = None

        entry = None
        try:
            entry = self._df_cache.get(ap)
        except Exception:
            entry = None

        try:
            if isinstance(entry, dict) and entry.get("mtime") == mtime:
                cols = entry.get("columns")
                if isinstance(cols, list) and cols:
                    return [str(c) for c in cols]
                df = entry.get("df")
                if isinstance(df, pd.DataFrame):
                    cols2 = [str(c) for c in list(df.columns)]
                    try:
                        entry["columns"] = list(cols2)
                    except Exception:
                        pass
                    return cols2
        except Exception:
            pass

        try:
            cols, sep = read_csv_header(ap)
        except Exception:
            cols, sep = [], None

        try:
            if isinstance(entry, dict):
                entry["mtime"] = mtime
                entry["columns"] = list(cols)
                entry["sep"] = sep
            else:
                self._df_cache[ap] = {"mtime": mtime, "columns": list(cols), "sep": sep}
        except Exception:
            pass

        return [str(c) for c in list(cols or [])]

    def _compute_accessible_columns_for_selector(self, selector: SubplotSelector) -> list[str]:
        """Signals list = ordered union of columns across enabled overlay files."""
        try:
            files = list(selector.get_files() or [])
        except Exception:
            files = []

        out: list[str] = []
        seen: set[str] = set()

        for p in files:
            try:
                if hasattr(selector, "is_file_enabled") and (not bool(selector.is_file_enabled(str(p)))):
                    continue
            except Exception:
                pass
            try:
                cols = self._get_columns_for_path(str(p))
            except Exception:
                cols = []
            for c in cols:
                sc = str(c)
                if sc in seen:
                    continue
                seen.add(sc)
                out.append(sc)

        return out

    def _schedule_refresh_signals_for_selector(self, selector: SubplotSelector) -> None:
        """Debounced Signals refresh for a selector (overlay-driven)."""
        try:
            if not isinstance(getattr(self, "_signals_refresh_jobs", None), dict):
                self._signals_refresh_jobs = {}
        except Exception:
            self._signals_refresh_jobs = {}

        key = int(id(selector))
        old_job = self._signals_refresh_jobs.get(key)
        if old_job is not None:
            try:
                self.root.after_cancel(old_job)
            except Exception:
                pass

        def _do() -> None:
            try:
                selector.set_columns(self._compute_accessible_columns_for_selector(selector))
            except Exception:
                pass

        try:
            self._signals_refresh_jobs[key] = self.root.after(180, _do)
        except Exception:
            _do()

    def _on_add_files_for_selector(self, selector: SubplotSelector) -> None:
        paths = filedialog.askopenfilenames(
            initialdir=self.current_folder,
            filetypes=[("CSV files", "*.csv")],
            title="Select CSV file(s) to overlay",
        )
        if not paths:
            return
        try:
            selector.add_files(list(paths))
        except Exception:
            return

    def _refresh_selector_layout(self) -> None:
        """Force selector canvas/window geometry refresh.

        Tk's Canvas+create_window doesn't always update scrollregion/width on
        dynamic PanedWindow pane changes, so we refresh explicitly after add/remove.
        """
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        try:
            w = int(self.selector_canvas.winfo_width())
            if w > 1:
                self.selector_canvas.itemconfig(self._selector_window_id, width=w)
        except Exception:
            pass

        # If content is smaller than the viewport, force the inner window to
        # fill the viewport height so panes/plots expand instead of staying tiny.
        try:
            viewport_h = int(self.selector_canvas.winfo_height())
            req_h = int(self.selector_inner.winfo_reqheight())
            if viewport_h > 1:
                self.selector_canvas.itemconfig(self._selector_window_id, height=max(req_h, viewport_h))
        except Exception:
            pass
        try:
            self.selector_canvas.configure(scrollregion=self.selector_canvas.bbox("all"))
        except Exception:
            pass

        # Ensure each subplot selector pane is tall enough to show its full
        # internal controls. The selector area is already scrollable, so growing
        # panes avoids clipped widgets while preserving the ability to scroll.
        try:
            panes = []
            try:
                panes = list(self.container.panes())
            except Exception:
                panes = []

            # tk.PanedWindow.panes() typically returns Tcl widget path strings.
            try:
                pane_names = [str(p) for p in panes]
            except Exception:
                pane_names = []

            for sel in list(getattr(self, "subplots", []) or []):
                try:
                    f = getattr(sel, "frame", None)
                except Exception:
                    f = None
                if f is None:
                    continue
                try:
                    if pane_names and str(f) not in pane_names:
                        continue
                except Exception:
                    pass
                try:
                    f.update_idletasks()
                except Exception:
                    pass
                try:
                    req_h = int(f.winfo_reqheight())
                    cur_h = int(f.winfo_height())
                except Exception:
                    continue
                # Only grow (never shrink) so manual sash resizing is respected.
                if req_h > cur_h + 8:
                    try:
                        self.container.paneconfigure(f, height=req_h)
                    except Exception:
                        pass
        except Exception:
            pass

    def _ensure_table_style(self) -> None:
        if self._table_style_inited:
            return
        self._table_style_inited = True
        try:
            style = ttk.Style(self.root)
            # More readable headings/rows without hard-coded hex colors
            style.configure("Stats.Treeview", rowheight=20)
            style.configure("Stats.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        except Exception:
            pass

    def _update_timestamp_scale(self) -> None:
        """Update base-file scale, honoring global timebase settings."""
        try:
            df = getattr(self, "df", None)
        except Exception:
            df = None
        try:
            base_path = getattr(self, "last_loaded_file", None) or getattr(self, "file_path", "")
        except Exception:
            base_path = ""
        try:
            auto_scale = float(self._compute_timestamp_scale_for_df(df) or 1.0)
        except Exception:
            auto_scale = 1.0
        try:
            self._timestamp_scale_to_seconds = float(
                self._effective_scale_to_seconds_for_path(str(base_path or ""), selector=None, auto_scale_to_seconds=auto_scale)
            )
        except Exception:
            self._timestamp_scale_to_seconds = float(auto_scale or 1.0)

    def _format_duration(self, seconds: float) -> str:
        """Format elapsed seconds as day:hours:minutes:seconds:subsec (ms)."""
        try:
            total_ms = int(round(max(0.0, float(seconds)) * 1000.0))
        except Exception:
            return "n/a"

        ms = total_ms % 1000
        total_s = total_ms // 1000
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        total_h = total_m // 60
        h = total_h % 24
        d = total_h // 24
        return f"{d}:{h:02d}:{m:02d}:{s:02d}:{ms:03d}"

    def _on_span_selected(self, selector: SubplotSelector, xmin: float, xmax: float) -> None:
        try:
            if xmin is None or xmax is None:
                return
            if float(xmax) == float(xmin):
                return
            base_path = None
            try:
                files = selector.get_files()
                if isinstance(files, list) and files:
                    base_path = str(files[0])
            except Exception:
                base_path = None
            if not base_path:
                try:
                    base_path = str(getattr(self, "last_loaded_file", None) or getattr(self, "file_path", ""))
                except Exception:
                    base_path = ""
            _df_i, eff_scale = self._get_df_for_path(str(base_path), selector)
            dur_seconds = abs(float(xmax) - float(xmin)) * float(eff_scale or 1.0)
            selector.set_x_window(float(xmin), float(xmax), duration_text=self._format_duration(dur_seconds))
        except Exception:
            return
        # Recompute table/hist based on window
        self.request_replot()

    def _compute_signal_metrics(self, x: pd.Series, y: pd.Series) -> tuple[str, str, str, str, str, str, str, str, str, str]:
        return compute_signal_metrics(x, y)

    def _find_column_like(self, patterns: list[str]) -> str | None:
        if not hasattr(self, "df"):
            return None
        cols = [str(c) for c in list(self.df.columns)]
        lower = [c.lower() for c in cols]
        for pat in patterns:
            p = str(pat).lower()
            for i, c in enumerate(lower):
                if p in c:
                    return cols[i]
        return None

    def _nearest_index(self, x: pd.Series, value: float) -> int | None:
        try:
            xs = pd.to_numeric(x, errors="coerce").dropna()
            if len(xs) == 0:
                return None
            diffs = (xs - float(value)).abs()
            return int(diffs.idxmin())
        except Exception:
            return None

    def _ms1353_limits(self, n: int, *, target: float = 45.0, limit0: float = 1.0, limit1: float = 5.0,
                      point0: int = 175, point1: int = 1175):
        """Create per-index abs-range min/max and diff-max arrays using MS-1353 step-limit idea."""
        try:
            import numpy as np
            idx = np.arange(int(n), dtype=int)
            lim = np.where((idx >= int(point0)) & (idx <= int(point1)), float(limit0), float(limit1))
            rmin = float(target) - lim / 2.0
            rmax = float(target) + lim / 2.0
            dmax = lim
            return rmin, rmax, dmax
        except Exception:
            return None, None, None

    def on_xlim_changed(self, event_ax, selector: SubplotSelector | None = None):
        # Called from Matplotlib when the user pans/zooms on the main plot.
        if self.updating_xlim:
            return
        self.updating_xlim = True
        new_xlim = event_ax.get_xlim()

        # Home button should clear window/zoom persistence.
        skip_persist = False
        try:
            # Time-based ignore (covers delayed callbacks after Home).
            try:
                until = float(getattr(self, "_ignore_xlim_persist_until", 0.0) or 0.0)
            except Exception:
                until = 0.0
            if until and time.monotonic() < until:
                skip_persist = True

            # Newer behavior: ignore multiple callbacks after Home.
            cnt = int(getattr(self, "_ignore_xlim_persist_count", 0) or 0)
            if cnt > 0:
                setattr(self, "_ignore_xlim_persist_count", cnt - 1)
                skip_persist = True
            # Backwards compatible flag (single callback ignore).
            if bool(getattr(self, "_ignore_next_xlim_persist", False)):
                self._ignore_next_xlim_persist = False
                skip_persist = True
            if skip_persist and selector is not None:
                try:
                    selector.clear_x_window()
                except Exception:
                    pass
        except Exception:
            skip_persist = False

        # Persist zoom so it survives replots (until user clears/changes it).
        try:
            if (not skip_persist) and selector is not None and hasattr(self, "df"):
                xmin, xmax = float(new_xlim[0]), float(new_xlim[1])
                base_path = None
                try:
                    files = selector.get_files()
                    if isinstance(files, list) and files:
                        base_path = str(files[0])
                except Exception:
                    base_path = None
                if not base_path:
                    try:
                        base_path = str(getattr(self, "last_loaded_file", None) or getattr(self, "file_path", ""))
                    except Exception:
                        base_path = ""
                _df_i, eff_scale = self._get_df_for_path(str(base_path), selector)
                dur_seconds = abs(xmax - xmin) * float(eff_scale or 1.0)
                selector.set_x_window(xmin, xmax, duration_text=self._format_duration(dur_seconds))
                # Debounced persistence to layout.json.
                try:
                    self._schedule_autosave()
                except Exception:
                    pass

                # Recompute table/hist/check plots based on the new window.
                # This is debounced by request_replot(), so it won't replot on every mouse move.
                try:
                    self.request_replot()
                except Exception:
                    pass
        except Exception:
            pass

        # Sync other linked axes.
        for ax in self.all_axes:
            if ax != event_ax:
                ax.set_xlim(new_xlim)
        for canvas in self.plot_canvases:
            canvas.draw_idle()
        self.updating_xlim = False

    def _set_mousewheel_target(self, target: str | None) -> None:
        self._mousewheel_target = target

    def _on_selector_canvas_configure(self, event):
        try:
            self.selector_canvas.itemconfig(self._selector_window_id, width=event.width)
        except Exception:
            pass

    def _on_controls_canvas_configure(self, event):
        try:
            self.controls_canvas.itemconfig(self._controls_window_id, width=event.width)
        except Exception:
            pass

    def _on_plot_canvas_configure(self, event):
        # Keep the embedded plot window sized to the visible canvas.
        # Important: if we only set width (not height), the embedded frame can
        # remain ~1px tall on some Tk builds, so packed/expanded children never
        # become visible.
        try:
            self.canvas.itemconfig(self._plot_window_id, width=event.width)
        except Exception:
            return

        try:
            viewport_h = int(getattr(event, "height", 0) or 0)
        except Exception:
            viewport_h = 0

        try:
            self.plot_area.update_idletasks()
            req_h = int(self.plot_area.winfo_reqheight())
        except Exception:
            req_h = 0

        try:
            h = max(viewport_h, req_h, 1)
            self.canvas.itemconfig(self._plot_window_id, height=h)
        except Exception:
            pass

        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _tune_default_layout(self) -> None:
        """Set sensible default sash positions and pane sizes.

        Goal:
        - On 1920x1080, keep plots dominant.
        - When there is only 1 subplot, make selector + plot expand to fill space.
        """
        if bool(getattr(self, "_skip_default_layout_tune", False)):
            return
        try:
            self.root.update_idletasks()
        except Exception:
            return

        # Main left/right split (plots should dominate)
        try:
            w = int(self.root.winfo_width())
            if w > 200:
                # ~30% left, 70% right
                self.main_pane.sashpos(0, int(w * 0.32))
        except Exception:
            pass

        # Left controls vs selectors split
        try:
            h = int(self.root.winfo_height())
            if h > 200:
                # keep controls compact (~220px) so selectors get room
                self.left_pane.sashpos(0, min(260, max(180, int(h * 0.22))))
        except Exception:
            pass

        # If only one selector pane exists, size it to fill the selector viewport.
        try:
            panes = list(self.container.panes())
        except Exception:
            panes = []
        if len(panes) == 1:
            try:
                viewport_h = int(self.selector_canvas.winfo_height())
                if viewport_h > 100:
                    # Some margin for paddings/scrollbar
                    self.container.paneconfigure(panes[0], height=max(260, viewport_h - 20))
            except Exception:
                pass

    def _capture_ui_sashes(self) -> dict:
        """Capture current UI sash positions for persistence."""
        out: dict = {}

        # ttk.Panedwindow uses sashpos(index)
        try:
            if getattr(self, "main_pane", None) is not None:
                out["main_pane"] = {"sashpos": [int(self.main_pane.sashpos(0))]}
        except Exception:
            pass
        try:
            if getattr(self, "left_pane", None) is not None:
                out["left_pane"] = {"sashpos": [int(self.left_pane.sashpos(0))]}
        except Exception:
            pass

        # tk.PanedWindow uses sash_coord(i) -> (x, y)
        try:
            c = getattr(self, "container", None)
            if c is not None and hasattr(c, "sash_coord"):
                coords = []
                try:
                    panes = list(c.panes())
                except Exception:
                    panes = []
                for i in range(max(0, len(panes) - 1)):
                    try:
                        x, y = c.sash_coord(i)
                        coords.append([int(x), int(y)])
                    except Exception:
                        continue
                out["selector_container"] = {"sash_coord": coords}
        except Exception:
            pass

        # Plot panels Panedwindow (recreated on each plot_all)
        try:
            p = getattr(self, "plots_pane", None)
            if p is not None:
                coords = []
                try:
                    panes = list(p.panes())
                except Exception:
                    panes = []
                for i in range(max(0, len(panes) - 1)):
                    try:
                        coords.append(int(p.sashpos(i)))
                    except Exception:
                        continue
                out["plots_pane"] = {"sashpos": coords}
        except Exception:
            pass

        return out

    def _set_pending_ui_sashes(self, sashes: dict | None) -> None:
        """Receive persisted sash positions from layout load."""
        if not isinstance(sashes, dict):
            self._pending_ui_sashes = None
            return
        self._pending_ui_sashes = sashes

        # plots pane sashes are applied after plot_all rebuilds panes
        try:
            pp = sashes.get("plots_pane") if isinstance(sashes.get("plots_pane"), dict) else {}
            lst = pp.get("sashpos")
            if isinstance(lst, list):
                self._pending_plots_pane_sashes = lst
        except Exception:
            self._pending_plots_pane_sashes = None

        # Prevent default tuning from overriding restored layout.
        self._skip_default_layout_tune = True
        self._apply_pending_ui_sashes_async()

    def _apply_pending_ui_sashes_async(self) -> None:
        try:
            self.root.after(120, self._apply_pending_ui_sashes_now)
        except Exception:
            self._apply_pending_ui_sashes_now()

    def _apply_pending_ui_sashes_now(self) -> None:
        sashes = self._pending_ui_sashes
        if not isinstance(sashes, dict):
            return

        try:
            self.root.update_idletasks()
        except Exception:
            pass

        # main pane
        try:
            mp = sashes.get("main_pane") if isinstance(sashes.get("main_pane"), dict) else {}
            lst = mp.get("sashpos")
            if isinstance(lst, list) and lst:
                desired = int(lst[0])
                try:
                    w = int(self.root.winfo_width())
                except Exception:
                    w = 0
                # Clamp so the plots pane cannot be collapsed to near-zero width.
                if w > 0:
                    min_left = 320
                    min_right = 520
                    desired = max(min_left, min(desired, max(min_left, w - min_right)))
                self.main_pane.sashpos(0, int(desired))
        except Exception:
            pass

        # left pane
        try:
            lp = sashes.get("left_pane") if isinstance(sashes.get("left_pane"), dict) else {}
            lst = lp.get("sashpos")
            if isinstance(lst, list) and lst:
                desired = int(lst[0])
                try:
                    h = int(self.root.winfo_height())
                except Exception:
                    h = 0
                # Keep both controls and selectors visible.
                if h > 0:
                    min_controls = 160
                    min_selectors = 260
                    desired = max(min_controls, min(desired, max(min_controls, h - min_selectors)))
                self.left_pane.sashpos(0, int(desired))
        except Exception:
            pass

        # selector container (tk.PanedWindow)
        try:
            sc = sashes.get("selector_container") if isinstance(sashes.get("selector_container"), dict) else {}
            coords = sc.get("sash_coord")
            c = getattr(self, "container", None)
            if c is not None and isinstance(coords, list) and hasattr(c, "sash_place"):
                for i, xy in enumerate(coords):
                    if not (isinstance(xy, list) and len(xy) == 2):
                        continue
                    try:
                        c.sash_place(i, int(xy[0]), int(xy[1]))
                    except Exception:
                        continue
        except Exception:
            pass

        # plots pane sashes are applied in plot_all once panes are rebuilt.
        # Always ensure plots are visible after applying persisted UI.
        try:
            self._set_plots_visible(True)
        except Exception:
            pass

    def _clear_highlight(self, ax, canvas):
        # Backwards-compat: clear all highlight selections.
        try:
            self._highlighted_channels.clear()
        except Exception:
            pass
        self._apply_highlight_state()

    def _highlight_line(self, ax, canvas, selected: Line2D):
        # Toggle highlight for this channel and apply globally.
        key = None
        try:
            key = getattr(selected, "_csv_plotter_column", None) or selected.get_label()
            key = str(key) if key is not None else None
        except Exception:
            key = None

        if key:
            self._toggle_highlight_key(str(key))

        # Remember which series was last clicked for this subplot.
        try:
            sel = getattr(selected, "_csv_plotter_selector", None)
            col = getattr(selected, "_csv_plotter_column", None) or selected.get_label()
            if sel is not None and col:
                sel._active_series = str(col)
        except Exception:
            pass

        self._apply_highlight_state()

    def _toggle_highlight_key(self, key: str) -> None:
        """Toggle a channel highlight by key (column name) and refresh all views."""
        k = str(key or "").strip()
        if not k:
            return
        try:
            if k in self._highlighted_channels:
                self._highlighted_channels.remove(k)
            else:
                self._highlighted_channels.add(k)
        except Exception:
            pass
        self._apply_highlight_state()

    def _apply_highlight_state(self) -> None:
        """Apply current highlight set to all plots/legends."""
        highlights = set(self._highlighted_channels or [])
        pal = getattr(self, "_theme_palette", {})
        fg = str(pal.get("fg") or "black")
        muted = str(pal.get("muted") or "gray")
        accent = str(pal.get("accent") or fg)

        for c in list(getattr(self, "plot_canvases", []) or []):
            fig = getattr(c, "figure", None)
            if fig is None:
                continue
            for ax in list(getattr(fig, "axes", []) or []):
                lines = list(ax.get_lines() or [])
                patches = list(getattr(ax, "patches", []) or [])
                if not highlights:
                    for ln in lines:
                        try:
                            ln.set_alpha(1.0)
                            ln.set_linewidth(1.5)
                            ln.set_zorder(2)
                        except Exception:
                            pass
                    for p in patches:
                        try:
                            p.set_alpha(0.45)
                        except Exception:
                            pass
                else:
                    for ln in lines:
                        try:
                            k = getattr(ln, "_csv_plotter_column", None) or ln.get_label()
                            k = str(k) if k is not None else ""
                            if k in highlights:
                                ln.set_alpha(1.0)
                                ln.set_linewidth(3.0)
                                ln.set_zorder(10)
                            else:
                                ln.set_alpha(0.20)
                                ln.set_linewidth(1.0)
                                ln.set_zorder(1)
                        except Exception:
                            pass
                    # Histogram bars (patches)
                    for p in patches:
                        try:
                            k = getattr(p, "_csv_plotter_column", None)
                            k = str(k) if k is not None else ""
                            if k and k in highlights:
                                p.set_alpha(0.95)
                            else:
                                p.set_alpha(0.15)
                        except Exception:
                            pass

                legend = ax.get_legend()
                if legend is not None:
                    texts = list(legend.get_texts() or [])
                    handles = []
                    try:
                        handles = list(getattr(legend, "legend_handles", []) or [])
                    except Exception:
                        handles = []
                    if not handles:
                        try:
                            handles = list(legend.get_lines() or [])
                        except Exception:
                            handles = []
                    for i, t in enumerate(texts):
                        try:
                            label = str(t.get_text() or "")
                        except Exception:
                            label = ""

                        # Map legend text back to a channel key (supports multi-file labels like file:CH)
                        key = label
                        if ":" in label:
                            try:
                                key = label.split(":", 1)[1]
                            except Exception:
                                key = label

                        is_hi = bool(highlights and key in highlights)
                        try:
                            if not highlights:
                                t.set_fontweight("normal")
                                t.set_color(fg)
                                t.set_alpha(1.0)
                            elif is_hi:
                                t.set_fontweight("bold")
                                # Use handle color if possible
                                try:
                                    t.set_color(handles[i].get_color() if hasattr(handles[i], "get_color") else accent)
                                except Exception:
                                    t.set_color(accent)
                                t.set_alpha(1.0)
                            else:
                                t.set_fontweight("normal")
                                t.set_color(muted)
                                t.set_alpha(0.7)
                        except Exception:
                            pass

                        if i < len(handles):
                            try:
                                if not highlights:
                                    handles[i].set_alpha(1.0)
                                    handles[i].set_linewidth(1.5)
                                elif is_hi:
                                    handles[i].set_alpha(1.0)
                                    if hasattr(handles[i], "set_linewidth"):
                                        handles[i].set_linewidth(3.0)
                                else:
                                    handles[i].set_alpha(0.25)
                                    if hasattr(handles[i], "set_linewidth"):
                                        handles[i].set_linewidth(1.0)
                            except Exception:
                                pass

            try:
                c.draw_idle()
            except Exception:
                pass

        # Stats table highlighting (Treeviews)
        try:
            self._apply_stats_table_highlight_state(highlights)
        except Exception:
            pass

    def _apply_stats_table_highlight_state(self, highlights: set[str]) -> None:
        pal = getattr(self, "_theme_palette", {})
        fg = str(pal.get("fg") or "black")
        muted = str(pal.get("muted") or "gray")
        accent = str(pal.get("accent") or fg)

        # Build fonts for stronger highlight visibility.
        try:
            base_font = tkfont.nametofont("TkDefaultFont")
            bold_font = base_font.copy()
            bold_font.configure(weight="bold")
        except Exception:
            base_font = None
            bold_font = None

        trees = list(getattr(self, "_stats_trees", []) or [])
        for tree in trees:
            try:
                if not tree.winfo_exists():
                    continue
            except Exception:
                continue

            # Configure tags once per update (cheap)
            try:
                if not highlights:
                    tree.tag_configure("hi", foreground=fg, font=base_font)
                    tree.tag_configure("dim", foreground=fg, font=base_font)
                else:
                    tree.tag_configure("hi", foreground=accent, font=bold_font)
                    tree.tag_configure("dim", foreground=muted, font=base_font)
            except Exception:
                pass

            try:
                items = list(tree.get_children(""))
            except Exception:
                items = []

            for item in items:
                try:
                    vals = tree.item(item, "values")
                except Exception:
                    vals = None
                sig = ""
                try:
                    sig = str(vals[0]) if vals and len(vals) else ""
                except Exception:
                    sig = ""

                key = sig
                if ":" in sig:
                    try:
                        key = sig.split(":", 1)[1]
                    except Exception:
                        key = sig

                try:
                    base_tags = list(tree.item(item, "tags") or [])
                except Exception:
                    base_tags = []

                # Keep even/odd tags, replace hi/dim
                base_tags = [t for t in base_tags if t not in ("hi", "dim")]
                if not highlights:
                    base_tags.append("hi")
                else:
                    base_tags.append("hi" if key in highlights else "dim")
                try:
                    tree.item(item, tags=tuple(base_tags))
                except Exception:
                    pass

    def _on_pick(self, event, ax, canvas):
        # Guard: pick_event is connected once per axis, so the same event can
        # arrive multiple times. Mark handled to avoid double toggles.
        try:
            if bool(getattr(event, "_csv_plotter_handled", False)):
                return
        except Exception:
            pass

        artist = getattr(event, "artist", None)

        # Legend click: toggle selection (show/hide) for that channel.
        try:
            if getattr(artist, "_csv_plotter_action", None) == "toggle_selection":
                mouse = getattr(event, "mouseevent", None)
                if getattr(mouse, "button", None) != 1:
                    return
                sel = getattr(artist, "_csv_plotter_selector", None)
                col = getattr(artist, "_csv_plotter_column", None)
                if sel is not None and col:
                    # Fast path: avoid full replot; just toggle visibility.
                    self._toggle_selector_column(sel, str(col), notify=False)
                    self._apply_selector_visibility(sel)
                try:
                    event._csv_plotter_handled = True
                except Exception:
                    pass
                return
        except Exception:
            pass

        # Histogram bars (Rectangle patches) and other artists can also carry our column tag.
        try:
            k = getattr(artist, "_csv_plotter_column", None)
            if k is not None:
                self._toggle_highlight_key(str(k))
                try:
                    event._csv_plotter_handled = True
                except Exception:
                    pass
                return
        except Exception:
            pass

        if not isinstance(artist, Line2D):
            return
        if artist not in ax.get_lines():
            return

        mouse = getattr(event, "mouseevent", None)
        if getattr(mouse, "button", None) == 3:
            # Right-click: remove signal from selection and replot (line disappears)
            self._remove_line_from_selection(artist)
            try:
                event._csv_plotter_handled = True
            except Exception:
                pass
            return

        # Left-click: toggle highlight for this channel (multi-select)
        self._highlight_line(ax, canvas, artist)
        try:
            event._csv_plotter_handled = True
        except Exception:
            pass

    def _toggle_selector_column(self, selector, column: str, *, notify: bool = True) -> None:
        """Toggle whether `column` is selected in the given subplot selector.

        When notify=False, we update the listbox selection state but do not trigger
        a full replot (used for fast legend clicks).
        """
        name = str(column or "").strip()
        if not name:
            return
        lb = getattr(selector, "listbox", None)
        if lb is None:
            return

        idx = None
        try:
            for i in range(lb.size()):
                if str(lb.get(i)) == name:
                    idx = i
                    break
        except Exception:
            idx = None
        if idx is None:
            return

        try:
            selected = set(lb.curselection() or [])
        except Exception:
            selected = set()

        try:
            if idx in selected:
                lb.selection_clear(idx)
            else:
                lb.selection_set(idx)
        except Exception:
            return

        if not notify:
            return

        # Notify + replot (existing behavior)
        try:
            if hasattr(selector, "_handle_change"):
                selector._handle_change()
            else:
                self.request_replot()
        except Exception:
            self.request_replot()

    def _apply_selector_visibility(self, selector) -> None:
        """Apply selector selection state to already-rendered lines (show/hide).

        This avoids a full replot when toggling via legend.
        """
        lb = getattr(selector, "listbox", None)
        if lb is None:
            return

        selected_names: set[str] = set()
        try:
            for i in (lb.curselection() or []):
                try:
                    selected_names.add(str(lb.get(i)))
                except Exception:
                    pass
        except Exception:
            selected_names = set()

        pal = getattr(self, "_theme_palette", {})
        fg = str(pal.get("fg") or "black")
        muted = str(pal.get("muted") or "gray")

        for c in list(getattr(self, "plot_canvases", []) or []):
            fig = getattr(c, "figure", None)
            if fig is None:
                continue

            for ax in list(getattr(fig, "axes", []) or []):
                # Toggle line visibility
                try:
                    for ln in list(ax.get_lines() or []):
                        if getattr(ln, "_csv_plotter_selector", None) is not selector:
                            continue
                        col = getattr(ln, "_csv_plotter_column", None)
                        if not col:
                            continue
                        ln.set_visible(str(col) in selected_names)
                except Exception:
                    pass

                # Dim legend text for hidden lines (helps UX)
                try:
                    leg = ax.get_legend()
                except Exception:
                    leg = None
                if leg is not None:
                    try:
                        for txt in list(leg.get_texts() or []):
                            col = getattr(txt, "_csv_plotter_column", None)
                            if not col:
                                continue
                            is_on = str(col) in selected_names
                            if is_on:
                                txt.set_alpha(1.0)
                                txt.set_color(fg)
                            else:
                                txt.set_alpha(0.35)
                                txt.set_color(muted)
                    except Exception:
                        pass

            try:
                c.draw_idle()
            except Exception:
                pass

    def _remove_line_from_selection(self, line: Line2D) -> None:
        selector = getattr(line, "_csv_plotter_selector", None)
        column = getattr(line, "_csv_plotter_column", None) or line.get_label()
        if selector is None or not column:
            return
        try:
            selector.deselect_column(str(column))
        except Exception:
            # Fallback: if anything goes wrong, just replot without changing selection
            self.request_replot()

    def _on_button_press(self, event, ax, canvas):
        # Fallback path: right-click removal without relying on pick_event.
        # If toolbar zoom/pan is active, disable span selection so zoom works and
        # we don't trigger a replot (which would reset the zoom).
        if getattr(event, "button", None) == 1 and getattr(event, "inaxes", None) is ax:
            tb = getattr(canvas, "_csv_toolbar", None)
            mode = getattr(tb, "mode", "") if tb is not None else ""
            span = getattr(ax, "_csv_span", None)
            try:
                if span is not None:
                    span.set_active(bool(mode == ""))
            except Exception:
                pass

        if getattr(event, "button", None) != 3:
            return
        if getattr(event, "inaxes", None) is not ax:
            return

        # Prefer top-most visible line.
        for ln in reversed(ax.get_lines()):
            try:
                contains, _details = ln.contains(event)
            except Exception:
                continue
            if contains:
                self._remove_line_from_selection(ln)
                return

    def _create_menu(self):
        build_menu(self)

    def _on_close(self):
        try:
            self._closing = True
        except Exception:
            pass
        try:
            job = getattr(self, "_bg_queue_job", None)
            if job is not None:
                self.root.after_cancel(job)
        except Exception:
            pass
        # Ensure we persist the latest UI state on exit.
        try:
            self._startup_in_progress = False
            self._suppress_autosave = False
        except Exception:
            pass
        self._schedule_autosave(immediate=True)
        try:
            self.root.destroy()
        except Exception:
            pass

    # -------------------- Perspective Viewer --------------------
    def open_perspective_view(self) -> None:
        try:
            self._ensure_perspective_server()
            url = f"http://localhost:{self._perspective_port}"
            self._wait_for_port("127.0.0.1", int(self._perspective_port), timeout_s=2.5)
            webbrowser.open(url)
        except Exception as e:
            try:
                messagebox.showerror("Perspective", str(e))
            except Exception:
                pass

    def _install_perspective_deps(self) -> None:
        """Best-effort install for optional Perspective viewer dependencies."""
        pkgs = [
            "perspective-python",
            "starlette",
            "uvicorn[standard]",
        ]

        for extra_args in ([], ["--user"]):
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                *extra_args,
                *pkgs,
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True)
            except Exception as e:
                raise RuntimeError(f"Failed to run pip: {e}") from e

            if int(getattr(proc, "returncode", 1) or 1) == 0:
                return

            # If first attempt failed and it doesn't look like permissions,
            # don't bother retrying with --user.
            try:
                out = (proc.stdout or "")
                err = (proc.stderr or "")
                msg = (err + "\n" + out).strip()
            except Exception:
                msg = ""

            if extra_args:
                raise RuntimeError(f"pip install failed:\n{msg}")

            lowered = msg.lower()
            if (
                "permission" not in lowered
                and "access is denied" not in lowered
                and "winerror 5" not in lowered
            ):
                raise RuntimeError(f"pip install failed:\n{msg}")

    def _wait_for_port(self, host: str, port: int, *, timeout_s: float = 2.0) -> None:
        end = None
        try:
            end = float(timeout_s)
        except Exception:
            end = 2.0
        try:
            import time
            t0 = time.time()
        except Exception:
            t0 = 0.0
        while True:
            try:
                with socket.create_connection((host, int(port)), timeout=0.4):
                    return
            except Exception:
                pass
            try:
                import time
                if time.time() - t0 >= float(end):
                    return
                time.sleep(0.1)
            except Exception:
                return

    def _ensure_perspective_server(self) -> None:
        if self._perspective_server is not None:
            return

        def _try_import():
            from perspective import Server
            from perspective.handlers.starlette import PerspectiveStarletteHandler
            from starlette.applications import Starlette
            from starlette.responses import HTMLResponse
            from starlette.routing import Route, WebSocketRoute
            import uvicorn
            return Server, PerspectiveStarletteHandler, Starlette, HTMLResponse, Route, WebSocketRoute, uvicorn

        try:
            Server, PerspectiveStarletteHandler, Starlette, HTMLResponse, Route, WebSocketRoute, uvicorn = _try_import()
        except Exception:
            # Attempt auto-install once.
            try:
                self.status_var.set("Installing Perspective dependencies …")
                self.root.update_idletasks()
            except Exception:
                pass

            try:
                self._install_perspective_deps()
            except Exception as e:
                try:
                    self.status_var.set("")
                except Exception:
                    pass
                raise RuntimeError(
                    "Perspective dependencies missing and auto-install failed. "
                    "Try: pip install perspective-python starlette uvicorn[standard]"
                ) from e

            try:
                Server, PerspectiveStarletteHandler, Starlette, HTMLResponse, Route, WebSocketRoute, uvicorn = _try_import()
            except Exception as e:
                try:
                    self.status_var.set("")
                except Exception:
                    pass
                raise RuntimeError(
                    "Perspective dependencies still missing after install. Try restarting the app."
                ) from e

            try:
                self.status_var.set("")
            except Exception:
                pass

        server = Server()
        self._perspective_server = server

        def _get_table_data():
            df = getattr(self, "df", None)
            if df is None or getattr(df, "empty", False):
                return {"empty": []}
            try:
                tbl = df.attrs.get("_arrow_table")
            except Exception:
                tbl = None
            if tbl is not None:
                return tbl
            return df

        async def _index(_request):
            html = f"""
<!doctype html>
<html>
  <head>
    <script type="module" src="https://cdn.jsdelivr.net/npm/@finos/perspective@2.10.0/dist/esm/perspective.js"></script>
    <script type="module" src="https://cdn.jsdelivr.net/npm/@finos/perspective-viewer@2.10.0/dist/esm/perspective-viewer.js"></script>
    <script type="module" src="https://cdn.jsdelivr.net/npm/@finos/perspective-viewer-datagrid@2.10.0/dist/esm/perspective-viewer-datagrid.js"></script>
    <script type="module" src="https://cdn.jsdelivr.net/npm/@finos/perspective-viewer-d3fc@2.10.0/dist/esm/perspective-viewer-d3fc.js"></script>
  </head>
  <body style="margin:0">
    <perspective-viewer style="width:100vw;height:100vh;"></perspective-viewer>
    <script type="module">
      const viewer = document.querySelector('perspective-viewer');
            const websocket = await window.perspective.websocket("ws://localhost:{self._perspective_port}/ws");
            const table = await websocket.open("{self._perspective_table_name}");
      viewer.load(table);
    </script>
  </body>
</html>
"""
            return HTMLResponse(html)

        async def _websocket(websocket):
            handler = PerspectiveStarletteHandler(server)
            await handler(websocket)

        app = Starlette(routes=[Route("/", _index), WebSocketRoute("/ws", _websocket)])

        def _run():
            uvicorn.run(app, host="0.0.0.0", port=self._perspective_port, log_level="warning")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        try:
            data = _get_table_data()
            self._perspective_table = server.table(data, name=self._perspective_table_name)
        except Exception:
            self._perspective_table = None

    def _update_perspective_table(self, df: pd.DataFrame) -> None:
        if self._perspective_server is None:
            return
        if df is None:
            return
        try:
            tbl = df.attrs.get("_arrow_table")
        except Exception:
            tbl = None
        data = tbl if tbl is not None else df
        try:
            if self._perspective_table is None:
                self._perspective_table = self._perspective_server.table(data, name=self._perspective_table_name)
                return
            try:
                self._perspective_table.clear()
            except Exception:
                pass
            self._perspective_table.update(data)
        except Exception:
            try:
                self._perspective_table = self._perspective_server.table(data, name=self._perspective_table_name)
            except Exception:
                self._perspective_table = None

    def clear_file_history(self):
        self.file_history.clear()
        self.history_index = -1
        # Keep the currently loaded file visible in internal state.
        try:
            self.history_var.set(self.last_loaded_file or "")
        except Exception:
            pass
        self.status_var.set("History cleared")
        self._schedule_autosave()

    def _populate_history_menu(self, menu: tk.Menu) -> None:
        # Rebuild each time the menu is opened so it's always up to date.
        try:
            menu.delete(0, tk.END)
        except Exception:
            return

        has_any = bool(self.file_history)
        menu.add_command(
            label=t(self, "menu.history.prev"),
            command=self.history_prev,
            state=(tk.NORMAL if has_any else tk.DISABLED),
        )
        menu.add_command(
            label=t(self, "menu.history.next"),
            command=self.history_next,
            state=(tk.NORMAL if has_any else tk.DISABLED),
        )
        menu.add_separator()
        menu.add_command(
            label=t(self, "menu.history.clear"),
            command=self.clear_file_history,
            state=(tk.NORMAL if has_any else tk.DISABLED),
        )
        menu.add_separator()

        if not has_any:
            menu.add_command(label=t(self, "menu.history.empty"), state=tk.DISABLED)
            return

        # Show up to 15 recent files (most-recent-first)
        for p in self.file_history[:15]:
            try:
                label = os.path.basename(str(p)) or str(p)
            except Exception:
                label = str(p)
            menu.add_command(label=label, command=lambda path=p: self.open_history_path(path))

    def _default_layout_path(self) -> str:
        return default_layout_path(__file__)

    def _build_layout_data(self) -> dict:
        return build_layout_data(self)

    def _schedule_autosave(self, immediate: bool = False) -> None:
        if bool(getattr(self, "_suppress_autosave", False)):
            return
        if not bool(self.auto_save_layout_enabled.get()):
            return
        if self._autosave_job is not None:
            try:
                self.root.after_cancel(self._autosave_job)
            except Exception:
                pass
            self._autosave_job = None
        delay = 1 if immediate else 500
        self._autosave_job = self.root.after(delay, self._auto_save_layout)

    def _auto_save_layout(self) -> None:
        self._autosave_job = None
        if not bool(self.auto_save_layout_enabled.get()):
            return
        if bool(getattr(self, "_suppress_autosave", False)):
            return
        try:
            data = self._build_layout_data()
        except Exception:
            return
        path = self._default_layout_path()
        try:
            write_layout_json_atomic(path, data)
        except Exception:
            # Avoid modal errors during normal use; just skip.
            pass

    def _clear_x_window_in_default_layout_file(self) -> None:
        """Clear only the persisted x-window in the default layout.json.

        This is intentionally independent of Auto-save layout, so a user clicking
        Matplotlib toolbar Home can reliably return to full-range view even after
        restarting the app, without needing to enable autosave.

        If the default layout file doesn't exist, this is a no-op.
        """
        try:
            path = self._default_layout_path()
            p = Path(path)
            if not p.exists():
                return
        except Exception:
            return

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(data, dict):
            return
        subplots = data.get("subplots")
        if not isinstance(subplots, list):
            return

        changed = False
        for s in subplots:
            if not isinstance(s, dict):
                continue
            if s.get("x_window") is not None:
                s["x_window"] = None
                changed = True

        if not changed:
            return

        try:
            write_layout_json_atomic(str(p), data)
        except Exception:
            pass

    def save_layout(self):
        save_layout_dialog(self)

    def export_plots_png(self) -> None:
        self._export_plots_dialog(fmt="png")

    def export_plots_svg(self) -> None:
        self._export_plots_dialog(fmt="svg")

    def export_plots_combined_png(self) -> None:
        self._export_plots_combined_dialog()

    def export_plots_combined_svg(self) -> None:
        self._export_plots_combined_svg_dialog()

    def _export_plots_combined_dialog(self) -> None:
        # Combined export is a screenshot of the plots section (Tk widgets + Matplotlib).
        try:
            widget = getattr(self, "canvas", None) or getattr(self, "plot_scroll_frame", None)
        except Exception:
            widget = None
        if widget is None:
            try:
                messagebox.showerror("Error", "Plots section not available yet.")
            except Exception:
                pass
            return

        try:
            initial_dir = str(Path(self._default_layout_path()).parent)
        except Exception:
            initial_dir = str(Path.cwd())

        path = filedialog.asksaveasfilename(
            initialfile="plots_combined.png",
            initialdir=initial_dir,
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            title="Export plots section as PNG (combined)",
        )
        if not path:
            return

        try:
            self._export_widget_screenshot_png(widget, path)
            try:
                self.status_var.set(f"Exported: {os.path.basename(str(path))}")
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror(
                    "Error",
                    "Failed to export combined PNG.\n\n"
                    "Note: this export needs Pillow (PIL) and captures the on-screen plots area.\n\n"
                    f"Details: {e}",
                )
            except Exception:
                pass

    def _export_plots_combined_svg_dialog(self) -> None:
        # Combined SVG is an SVG wrapper containing an embedded raster screenshot.
        try:
            widget = getattr(self, "canvas", None) or getattr(self, "plot_scroll_frame", None)
        except Exception:
            widget = None
        if widget is None:
            try:
                messagebox.showerror("Error", "Plots section not available yet.")
            except Exception:
                pass
            return

        try:
            initial_dir = str(Path(self._default_layout_path()).parent)
        except Exception:
            initial_dir = str(Path.cwd())

        path = filedialog.asksaveasfilename(
            initialfile="plots_combined.svg",
            initialdir=initial_dir,
            defaultextension=".svg",
            filetypes=[("SVG", "*.svg")],
            title="Export plots section as SVG (combined)",
        )
        if not path:
            return

        try:
            self._export_widget_screenshot_svg(widget, path)
            try:
                self.status_var.set(f"Exported: {os.path.basename(str(path))}")
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror(
                    "Error",
                    "Failed to export combined SVG.\n\n"
                    "Note: this export embeds a raster screenshot inside an SVG file and needs Pillow (PIL).\n\n"
                    f"Details: {e}",
                )
            except Exception:
                pass

    def _export_widget_screenshot_png(self, widget, path: str) -> None:
        # Screenshot-based export: captures the visible portion of the plots section.
        # Requires Pillow on Windows.
        try:
            from PIL import ImageGrab  # type: ignore
        except Exception as e:
            raise RuntimeError("Pillow is required for combined export (pip install pillow)") from e

        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

        try:
            x = int(widget.winfo_rootx())
            y = int(widget.winfo_rooty())
            w = int(widget.winfo_width())
            h = int(widget.winfo_height())
        except Exception as e:
            raise RuntimeError("Failed to locate plots widget on screen") from e

        if w <= 2 or h <= 2:
            raise RuntimeError("Plots widget size is too small to capture")

        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        img.save(str(path), format="PNG")

    def _export_widget_screenshot_svg(self, widget, path: str) -> None:
        # Capture a screenshot then embed it in an SVG wrapper.
        try:
            from PIL import ImageGrab  # type: ignore
        except Exception as e:
            raise RuntimeError("Pillow is required for combined export (pip install pillow)") from e

        try:
            import base64
            import io
        except Exception as e:
            raise RuntimeError("Python base64/io unavailable") from e

        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

        try:
            x = int(widget.winfo_rootx())
            y = int(widget.winfo_rooty())
            w = int(widget.winfo_width())
            h = int(widget.winfo_height())
        except Exception as e:
            raise RuntimeError("Failed to locate plots widget on screen") from e

        if w <= 2 or h <= 2:
            raise RuntimeError("Plots widget size is too small to capture")

        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <image x="0" y="0" width="{w}" height="{h}" '
            f'xlink:href="data:image/png;base64,{png_b64}" />\n'
            '</svg>\n'
        )

        try:
            Path(path).write_text(svg, encoding="utf-8")
        except Exception as e:
            raise RuntimeError("Failed to write SVG") from e

    def _export_plots_dialog(self, *, fmt: str) -> None:
        fmt = str(fmt or "png").lower().strip()
        if fmt not in ("png", "svg"):
            fmt = "png"

        canvases = [c for c in (getattr(self, "plot_canvases", None) or []) if hasattr(c, "figure")]
        if not canvases:
            try:
                messagebox.showerror("Error", "No plots to export yet.")
            except Exception:
                pass
            return

        try:
            initial_dir = str(Path(self._default_layout_path()).parent)
        except Exception:
            initial_dir = str(Path.cwd())

        default_name = f"plots.{fmt}"
        path = filedialog.asksaveasfilename(
            initialfile=default_name,
            initialdir=initial_dir,
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")],
            title=f"Export plots as {fmt.upper()}",
        )
        if not path:
            return

        try:
            self._export_canvases_to_path(canvases, path, fmt=fmt)
        except Exception as e:
            try:
                messagebox.showerror("Error", f"Failed to export plots:\n{e}")
            except Exception:
                pass

    def _export_canvases_to_path(self, canvases: list, path: str, *, fmt: str) -> None:
        from pathlib import Path

        def _safe_name(s: str) -> str:
            s = (s or "").strip()
            if not s:
                return "figure"
            out = []
            for ch in s:
                if ch.isalnum() or ch in ("-", "_", "."):
                    out.append(ch)
                elif ch.isspace():
                    out.append("_")
            cleaned = "".join(out).strip("_.")
            return cleaned or "figure"

        def _fig_label(fig) -> str:
            try:
                axes = list(getattr(fig, "axes", []) or [])
            except Exception:
                axes = []
            for ax in axes:
                try:
                    title = str(ax.get_title() or "").strip()
                except Exception:
                    title = ""
                if title:
                    return title
            return "figure"

        p = Path(path)
        fmt = str(fmt or "png").lower().strip()
        if p.suffix.lower() != f".{fmt}":
            p = p.with_suffix(f".{fmt}")

        # Prefer exporting main plots first (those have a toolbar attached).
        def _prio(c):
            return 0 if hasattr(c, "_csv_toolbar") else 1

        ordered = sorted(list(canvases), key=_prio)

        if len(ordered) == 1:
            fig = ordered[0].figure
            fig.savefig(str(p), format=fmt, bbox_inches="tight")
            try:
                self.status_var.set(f"Exported: {p.name}")
            except Exception:
                pass
            return

        stem = p.stem
        used: dict[str, int] = {}
        out_dir = p.parent

        for i, c in enumerate(ordered, start=1):
            fig = c.figure
            label = _safe_name(_fig_label(fig))
            key = label.lower()
            used[key] = used.get(key, 0) + 1
            suffix = f"_{used[key]}" if used[key] > 1 else ""
            out_name = f"{stem}_{i:02d}_{label}{suffix}.{fmt}"
            out_path = out_dir / out_name
            fig.savefig(str(out_path), format=fmt, bbox_inches="tight")

        try:
            self.status_var.set(f"Exported {len(ordered)} plots to: {out_dir}")
        except Exception:
            pass

    def _clear_subplots(self):
        # Remove panes from the selector panedwindow
        try:
            panes = list(self.container.panes())
        except Exception:
            panes = []
        for p in panes:
            try:
                self.container.forget(p)
            except Exception:
                pass
            try:
                w = self.root.nametowidget(p)
                w.destroy()
            except Exception:
                pass

        # Also destroy any tracked selector frames (covers non-pane fallback cases).
        for s in list(self.subplots):
            try:
                s.frame.destroy()
            except Exception:
                pass
        self.subplots.clear()
        self.subplot_count = 0
        self._refresh_selector_layout()

    def load_layout(self):
        load_layout_dialog(self)

    def _load_layout_from_path(self, path: str, *, silent: bool) -> bool:
        return load_layout_from_path(self, path, silent=silent)

    def show_help(self):
        show_help_dialog(self)

    def show_about(self):
        show_about_dialog(self)

    def _bundled_docs_dir(self) -> Path:
        return Path(__file__).resolve().parent / "docs"

    def _open_bundled_doc(self, relative_path: str) -> None:
        docs_dir = self._bundled_docs_dir()
        path = (docs_dir / relative_path).resolve()

        if not docs_dir.exists() or not path.exists():
            try:
                messagebox.showerror(
                    t(self, "dialog.docs_missing.title", default="Docs not found"),
                    t(
                        self,
                        "dialog.docs_missing.text",
                        default="Bundled docs were not found at:\n{path}",
                        path=str(path),
                    ),
                )
            except Exception:
                pass
            return

        try:
            _open_path_in_default_app(path)
        except Exception as e:
            try:
                messagebox.showerror(
                    t(self, "dialog.docs_open_failed.title", default="Open failed"),
                    t(
                        self,
                        "dialog.docs_open_failed.text",
                        default="Could not open:\n{path}\n\n{error}",
                        path=str(path),
                        error=str(e),
                    ),
                )
            except Exception:
                pass

    def open_user_guide(self) -> None:
        self._open_bundled_doc("UserGuide.md")

    def open_developer_guide(self) -> None:
        self._open_bundled_doc("DeveloperGuide.md")

    def open_docs_folder(self) -> None:
        docs_dir = self._bundled_docs_dir()
        if not docs_dir.exists():
            self._open_bundled_doc("README.md")
            return
        try:
            _open_path_in_default_app(docs_dir)
        except Exception as e:
            try:
                messagebox.showerror(
                    t(self, "dialog.docs_open_failed.title", default="Open failed"),
                    t(
                        self,
                        "dialog.docs_open_failed.text",
                        default="Could not open:\n{path}\n\n{error}",
                        path=str(docs_dir),
                        error=str(e),
                    ),
                )
            except Exception:
                pass

    def clear_layout(self) -> None:
        # Reset UI and delete default layout.json. Also disable auto-save to avoid
        # immediately recreating the file (especially on exit).
        try:
            ok = messagebox.askyesno(
                t(self, "dialog.clear_layout.title"),
                t(self, "dialog.clear_layout.text"),
            )
        except Exception:
            ok = False
        if not ok:
            return

        # Turn off autosave and cancel any pending autosave.
        try:
            self.auto_save_layout_enabled.set(False)
        except Exception:
            pass
        try:
            if self._autosave_job is not None:
                self.root.after_cancel(self._autosave_job)
                self._autosave_job = None
        except Exception:
            pass

        # Delete the default layout file.
        path = self._default_layout_path()
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
        except Exception:
            pass

        # Reset subplot configuration to a single default subplot.
        try:
            self._clear_subplots()
        except Exception:
            pass
        try:
            if hasattr(self, "df"):
                self.add_subplot()
        except Exception:
            pass

        try:
            self.plot_all()
        except Exception:
            pass

        try:
            self.status_var.set("Layout cleared")
        except Exception:
            pass
    def choose_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.current_folder,
            filetypes=[("CSV files", "*.csv")],
            title="Select a CSV file"
        )
        if file_path:
            # manual selection should not be immediately overridden by auto-load
            self.auto_check_enabled.set(False)
            self.load_file(file_path)
            self._schedule_autosave()

    def _push_history(self, path: str) -> None:
        abs_path = os.path.abspath(path)
        if abs_path in self.file_history:
            self.file_history.remove(abs_path)
        self.file_history.insert(0, abs_path)
        # keep history manageable
        self.file_history = self.file_history[:50]
        self.history_index = 0
        try:
            self.history_var.set(abs_path)
        except Exception:
            pass

    def open_history_path(self, path: str) -> None:
        if not path:
            return
        self.auto_check_enabled.set(False)
        try:
            self.history_index = self.file_history.index(os.path.abspath(str(path)))
        except Exception:
            # Keep history_index as-is if not found
            pass
        self.load_file(str(path))
        self._schedule_autosave()

    def _scan_folder_csv_paths(self, folder_path: str) -> list[str]:
        try:
            folder = Path(str(folder_path))
        except Exception:
            return []
        if not folder.exists():
            return []

        try:
            recursive = bool(self.open_folder_recursive_enabled.get())
        except Exception:
            recursive = False

        try:
            items = list(folder.rglob("*.csv")) if recursive else list(folder.glob("*.csv"))
        except Exception:
            items = []

        def _mtime(p: Path) -> float:
            try:
                return float(p.stat().st_mtime)
            except Exception:
                return 0.0

        try:
            items.sort(key=_mtime, reverse=True)
        except Exception:
            pass

        out: list[str] = []
        for p in items:
            try:
                out.append(str(p.resolve()))
            except Exception:
                try:
                    out.append(str(p))
                except Exception:
                    pass
        return out

    def open_folder_load_all(self) -> None:
        folder_path = filedialog.askdirectory(title="Open Folder (load all CSVs)")
        if not folder_path:
            return

        # Manual selection should not be immediately overridden by auto-load
        try:
            self.auto_check_enabled.set(False)
        except Exception:
            pass

        self.current_folder = folder_path

        csv_paths = self._scan_folder_csv_paths(folder_path)

        if not csv_paths:
            messagebox.showerror("Error", "No CSV files found in selected folder")
            return

        # Store so overlay selectors can pre-populate with all found files.
        self._folder_overlay_csv_paths = list(csv_paths)

        # Replace history with this folder's CSV list
        self.file_history = [os.path.abspath(p) for p in csv_paths]
        self.file_history = self.file_history[:50]
        self.history_index = 0
        try:
            self.history_var.set(self.file_history[0])
        except Exception:
            pass

        # Load newest file (first in list)
        try:
            self.load_file(self.file_history[0])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load newest CSV:\n{e}")

    def on_history_selected(self, _event=None):
        selected = self.history_var.get()
        if selected:
            self.auto_check_enabled.set(False)
            try:
                self.history_index = self.file_history.index(selected)
            except ValueError:
                self.history_index = -1
            self.load_file(selected)
            self._schedule_autosave()

    def history_prev(self):
        if not self.file_history:
            return
        if self.history_index < 0:
            self.history_index = 0
        nxt = min(len(self.file_history) - 1, self.history_index + 1)
        self.history_index = nxt
        self.auto_check_enabled.set(False)
        self.history_var.set(self.file_history[self.history_index])
        self.load_file(self.file_history[self.history_index])
        self._schedule_autosave()

    def history_next(self):
        if not self.file_history:
            return
        if self.history_index < 0:
            self.history_index = 0
        nxt = max(0, self.history_index - 1)
        self.history_index = nxt
        self.auto_check_enabled.set(False)
        self.history_var.set(self.file_history[self.history_index])
        self.load_file(self.file_history[self.history_index])
        self._schedule_autosave()
    

    def load_file(self, path):
        if not path:
            return

        # If a load is already running, remember the most recent requested file.
        if bool(getattr(self, "_load_in_progress", False)):
            try:
                self._pending_load_path = str(path)
                self.status_var.set(f"Queued: {os.path.basename(str(path))}")
            except Exception:
                pass
            return

        self._load_in_progress = True
        self._pending_load_path = None

        try:
            self._show_loading(f"Loading {os.path.basename(str(path))} …")
        except Exception:
            pass

        try:
            self.status_var.set(f"Loading: {os.path.basename(str(path))}")
        except Exception:
            pass

        # Prevent stale Signals list while the async load is in progress.
        try:
            for sel in list(getattr(self, "subplots", []) or []):
                try:
                    sel.set_columns([])
                except Exception:
                    pass
                try:
                    sel.clear_selection()
                except Exception:
                    pass
                try:
                    sel.set_stats_text("")
                except Exception:
                    pass
        except Exception:
            pass

        def _worker(p: str):
            try:
                df = None
                mtime = None
                if getattr(self, "core_protocol", None) is not None:
                    try:
                        self.core_protocol.load_file(p)
                        df = self.core_state.df if self.core_state is not None else None
                        mtime = self.core_state.last_loaded_mtime if self.core_state is not None else None
                    except Exception:
                        df = None
                        mtime = None
                # If the core protocol produced an empty/no-column dataframe,
                # treat it as "not loaded" and fall back to direct CSV parsing.
                try:
                    if isinstance(df, pd.DataFrame) and len(list(df.columns)) == 0:
                        df = None
                except Exception:
                    pass
                if df is None:
                    df = read_any_csv(p)
                    try:
                        ap = os.path.abspath(str(p))
                    except Exception:
                        ap = str(p)
                    try:
                        mtime = float(Path(ap).stat().st_mtime)
                    except Exception:
                        mtime = None
                scale = compute_timestamp_scale_for_df(df)
                # Never touch Tk from a worker thread; push to a queue instead.
                try:
                    self._bg_queue.put((p, df, scale, mtime, None))
                except Exception:
                    pass
            except Exception as e:
                try:
                    self._bg_queue.put((p, None, 1.0, None, e))
                except Exception:
                    pass

        try:
            threading.Thread(target=_worker, args=(str(path),), daemon=True).start()
        except Exception as e:
            try:
                self._hide_loading()
            except Exception:
                pass
            self._load_in_progress = False
            messagebox.showerror("Error", f"Failed to start loading thread:\n{e}")

    def _process_bg_queue(self) -> None:
        if bool(getattr(self, "_closing", False)):
            return

        try:
            while True:
                try:
                    p, df, scale, mtime, err = self._bg_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._finish_load_file(p, df, float(scale or 1.0), mtime, err)
                except Exception as e:
                    # Never let the poller die, but don't hide exceptions.
                    try:
                        self.status_var.set(f"Render error: {e}")
                    except Exception:
                        pass
                    try:
                        traceback.print_exc()
                    except Exception:
                        pass
        finally:
            try:
                self._bg_queue_job = self.root.after(50, self._process_bg_queue)
            except Exception:
                self._bg_queue_job = None

    def _finish_load_file(self, path: str, new_df: pd.DataFrame | None, scale_to_seconds: float, mtime: float | None, err: Exception | None) -> None:
        try:
            if err is not None or not isinstance(new_df, pd.DataFrame):
                try:
                    self._hide_loading()
                except Exception:
                    pass
                self._load_in_progress = False
                messagebox.showerror("Error", f"Failed to load file:\n{err}")
                return

            self._begin_bulk_update()
            try:
                new_columns = list(new_df.columns)
                old_columns = list(self.df.columns) if hasattr(self, "df") else None

                pending_layout = getattr(self, "_pending_layout_data", None)

                self.df = new_df
                self.file_path = path
                try:
                    _cols = getattr(self.df, "columns", None)
                    _ncols = int(len(_cols)) if _cols is not None else 0
                except Exception:
                    _ncols = 0
                self._debug_log(
                    f"finish_load_file path={path!r} df_shape={getattr(self.df, 'shape', None)} "
                    f"cols={_ncols} subplots={len(getattr(self, 'subplots', []) or [])}"
                )
                try:
                    if self.core_state is not None:
                        self.core_state.file_path = str(path or "")
                        self.core_state.set_df(self.df)
                        self.core_state.last_loaded_mtime = mtime
                except Exception:
                    pass
                try:
                    auto_scale = float(scale_to_seconds or 1.0)
                    self._timestamp_scale_to_seconds = float(
                        self._effective_scale_to_seconds_for_path(path, selector=None, auto_scale_to_seconds=auto_scale)
                    )
                except Exception:
                    self._timestamp_scale_to_seconds = 1.0

                # Keep _df_cache synced for the base file too (enables numeric + derived caches).
                try:
                    ap = os.path.abspath(str(path))
                except Exception:
                    ap = str(path)
                try:
                    self._df_cache[ap] = {
                        "mtime": mtime,
                        "df": self.df,
                        "scale_to_seconds": float(getattr(self, "_timestamp_scale_to_seconds", 1.0) or 1.0),
                        "scale_auto_to_seconds": float(scale_to_seconds or 1.0),
                        "numeric": {},
                        "metrics_cache": {},
                        "hist_cache": {},
                    }
                except Exception:
                    pass

                # Track file modification time for auto-reload
                try:
                    self._last_loaded_mtime = float(Path(path).stat().st_mtime)
                except Exception:
                    self._last_loaded_mtime = None

                # Only reset subplot selectors if column layout changed
                if old_columns != new_columns:
                    if isinstance(pending_layout, dict):
                        # Layout will rebuild subplots after the load completes.
                        self.status_var.set(f"Loaded: {os.path.basename(path)}")
                    else:
                        self._clear_subplots()
                        self.status_var.set(f"Loaded: {os.path.basename(path)}")
                        self.add_subplot()
                else:
                    self.status_var.set(f"Switched to: {os.path.basename(path)}")

                self.last_loaded_file = os.path.abspath(path)
                self._push_history(path)
                try:
                    self._update_info_labels()
                except Exception:
                    pass

                # Push updated data to Perspective if it's running
                try:
                    self._update_perspective_table(self.df)
                except Exception:
                    pass

                # Apply any pending layout now that we have the dataframe.
                if isinstance(pending_layout, dict):
                    # Restore highlight set before rendering, so plot_all applies it.
                    try:
                        hl = pending_layout.get("highlighted_channels")
                        if isinstance(hl, list):
                            self._highlighted_channels = set(str(x) for x in hl if x is not None)
                    except Exception:
                        pass
                    try:
                        apply_layout_subplots(self, pending_layout)
                    finally:
                        try:
                            self._pending_layout_data = None
                        except Exception:
                            pass

                # Ensure each subplot has a base file set (first entry). Preserve extra files and their shifts if possible.
                for sel in list(self.subplots):
                    try:
                        old_files = sel.get_files()
                        old_shifts = sel.get_file_shifts()
                    except Exception:
                        old_files = []
                        old_shifts = {}

                    new_files: list[str] = [self.last_loaded_file]

                    # If the user opened a folder (optionally recursive), pre-populate
                    # overlay list with all found CSVs.
                    try:
                        folder_paths = getattr(self, "_folder_overlay_csv_paths", None)
                    except Exception:
                        folder_paths = None
                    if isinstance(folder_paths, list) and folder_paths:
                        try:
                            base_abs = os.path.abspath(str(self.last_loaded_file))
                        except Exception:
                            base_abs = str(self.last_loaded_file)
                        try:
                            root_abs = os.path.abspath(str(self.current_folder)) if getattr(self, "current_folder", None) else ""
                        except Exception:
                            root_abs = ""

                        # Only apply the folder list when the loaded file is under current_folder.
                        if root_abs and base_abs.lower().startswith(root_abs.lower()):
                            for p in folder_paths:
                                try:
                                    ap2 = os.path.abspath(str(p))
                                except Exception:
                                    ap2 = str(p)
                                if ap2 and ap2 != self.last_loaded_file and ap2 not in new_files:
                                    new_files.append(ap2)

                    for p in (old_files[1:] if isinstance(old_files, list) else []):
                        try:
                            ap2 = os.path.abspath(str(p))
                        except Exception:
                            ap2 = str(p)
                        if ap2 and ap2 != self.last_loaded_file and ap2 not in new_files:
                            new_files.append(ap2)
                    try:
                        sel.set_files(new_files)
                        sel.set_file_shifts(old_shifts)
                    except Exception:
                        pass

                    # Refresh Signals from enabled overlay files (base + overlays).
                    try:
                        sel.set_columns(self._compute_accessible_columns_for_selector(sel))
                    except Exception:
                        pass

                self._refresh_selector_layout()

                try:
                    if self._loading_label_var is not None:
                        self._loading_label_var.set("Rendering plots …")
                    self.root.update_idletasks()
                except Exception:
                    pass

                self.plot_all()
                if not bool(getattr(self, "_startup_in_progress", False)):
                    self._schedule_autosave()
            finally:
                self._end_bulk_update()
        finally:
            try:
                self._hide_loading()
            except Exception:
                pass
            self._load_in_progress = False

            # If something requested another load while we were busy, run the latest one now.
            pending = getattr(self, "_pending_load_path", None)
            self._pending_load_path = None
            if isinstance(pending, str) and pending and os.path.abspath(str(pending)) != os.path.abspath(str(path)):
                try:
                    self.root.after(0, lambda p=pending: self.load_file(p))
                except Exception:
                    pass

    def _update_info_labels(self) -> None:
        try:
            file_name = os.path.basename(self.last_loaded_file) if isinstance(self.last_loaded_file, str) and self.last_loaded_file else "(none)"
            # Add file size info
            file_size_str = ""
            try:
                if isinstance(self.last_loaded_file, str) and self.last_loaded_file:
                    size_bytes = Path(self.last_loaded_file).stat().st_size
                    if size_bytes >= 1_073_741_824:
                        file_size_str = f" ({size_bytes / 1_073_741_824:.1f} GB)"
                    elif size_bytes >= 1_048_576:
                        file_size_str = f" ({size_bytes / 1_048_576:.1f} MB)"
                    elif size_bytes >= 1024:
                        file_size_str = f" ({size_bytes / 1024:.1f} KB)"
                    else:
                        file_size_str = f" ({size_bytes} B)"
            except Exception:
                file_size_str = ""
            self.current_file_var.set(f"File: {file_name}{file_size_str}")
        except Exception:
            pass
        try:
            rows = len(self.df) if hasattr(self, "df") else 0
            cols = len(self.df.columns) if hasattr(self, "df") else 0
            self.df_shape_var.set(f"Rows: {rows:,}  Cols: {cols}")
        except Exception:
            pass
        try:
            self.current_folder_var.set(f"Folder: {self.current_folder}")
        except Exception:
            pass


    def watch_for_new_file(self):
        # Reschedule first, then do work (keeps polling robust even on exceptions).
        try:
            if bool(getattr(self, "_closing", False)):
                return
        except Exception:
            pass

        try:
            self._watch_job = self.root.after(self._current_watch_interval_ms(), self.watch_for_new_file)
        except Exception:
            self._watch_job = None

        # Don't auto-load during startup restore.
        if bool(getattr(self, "_startup_in_progress", False)):
            return

        if self.auto_check_enabled.get():
            try:
                newest = find_newest_csv(self.current_folder)
                abs_newest = os.path.abspath(newest)
                if self.last_loaded_file != abs_newest:
                    self.load_file(abs_newest)
            except Exception:
                pass  # Ignore if no CSVs found
        elif self.auto_reload_selected_enabled.get():
            # Reload the currently selected file if it has changed.
            try:
                if isinstance(self.last_loaded_file, str) and self.last_loaded_file and Path(self.last_loaded_file).exists():
                    mtime = float(Path(self.last_loaded_file).stat().st_mtime)
                    if self._last_loaded_mtime is None or mtime > self._last_loaded_mtime:
                        self.load_file(self.last_loaded_file)
            except Exception:
                pass


    def choose_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder Containing CSV Files")
        if folder_path:
            self.current_folder = folder_path
            try:
                if self.core_state is not None:
                    self.core_state.folder_path = str(folder_path)
            except Exception:
                pass
            try:
                self._update_info_labels()
            except Exception:
                pass
            try:
                csv_paths = self._scan_folder_csv_paths(folder_path)
                if not csv_paths:
                    raise ValueError("No CSV files found")

                # Store so overlay selectors can pre-populate with all found files.
                self._folder_overlay_csv_paths = list(csv_paths)

                newest_file = csv_paths[0]
                self.load_file(newest_file)
                self._schedule_autosave()
            except Exception as e:
                messagebox.showerror("Error", f"No valid CSV file found:\n{e}")

    def add_subplot(self):
        self.subplot_count += 1
        selector = SubplotSelector(
            self.container,
            list(self.df.columns),
            self.subplot_count,
            on_change=None,
            on_close=self.remove_subplot,
            on_add_files=self._on_add_files_for_selector,
            on_duplicate=self._duplicate_subplot,
        )

        # Wrap the selector's on_change so we can resync Signals when overlay files change.
        try:
            selector._on_change = lambda sel=selector: self._on_subplot_selector_change(sel)
        except Exception:
            pass
        try:
            selector.apply_theme(getattr(self, "_theme_palette", {}) or {})
        except Exception:
            pass
        # Initialize with base file
        self._begin_bulk_update()
        try:
            try:
                base = os.path.abspath(self.last_loaded_file) if isinstance(self.last_loaded_file, str) and self.last_loaded_file else os.path.abspath(self.file_path)
                init_files = [base]
                try:
                    folder_paths = getattr(self, "_folder_overlay_csv_paths", None)
                except Exception:
                    folder_paths = None
                if isinstance(folder_paths, list) and folder_paths:
                    try:
                        root_abs = os.path.abspath(str(self.current_folder)) if getattr(self, "current_folder", None) else ""
                    except Exception:
                        root_abs = ""
                    if root_abs and base.lower().startswith(root_abs.lower()):
                        for p in folder_paths:
                            try:
                                ap = os.path.abspath(str(p))
                            except Exception:
                                ap = str(p)
                            if ap and ap != base and ap not in init_files:
                                init_files.append(ap)
                selector.set_files(init_files)
            except Exception:
                pass
        finally:
            self._end_bulk_update()
        self.subplots.append(selector)
        # Some Tk builds don't support the 'stretch' option (raises TclError), so fall back.
        # Also, give each pane a sane initial height so the listbox is visible.
        # Initial size: prefer filling visible selector area when there are only
        # a few subplots; otherwise fall back to a reasonable default.
        initial_pane_height = 380
        try:
            viewport_h = int(self.selector_canvas.winfo_height())
            if viewport_h > 120:
                # Leave a bit of margin so the sash remains easy to grab.
                if len(self.subplots) <= 1:
                    initial_pane_height = max(340, viewport_h - 20)
                else:
                    initial_pane_height = min(420, max(260, int(viewport_h / max(1, len(self.subplots)))))
        except Exception:
            pass

        # Make sure the pane is tall enough for its content (prevents clipped controls).
        try:
            selector.frame.update_idletasks()
            req = int(selector.frame.winfo_reqheight())
            if req > 0:
                initial_pane_height = max(initial_pane_height, req)
        except Exception:
            pass
        added = False
        try:
            self.container.add(selector.frame, stretch='always', height=initial_pane_height)
            added = True
        except Exception:
            try:
                self.container.add(selector.frame, height=initial_pane_height)
                added = True
            except Exception:
                added = False

        # Ensure the pane has a sensible minimum size so it doesn't collapse to 0 height.
        if added:
            try:
                self.container.paneconfigure(selector.frame, minsize=220)
            except Exception:
                pass
        else:
            # Last-resort fallback: keep it visible even if PanedWindow.add fails.
            try:
                selector.frame.pack(in_=self.selector_inner, pady=5, fill='x')
            except Exception:
                pass

        self._refresh_selector_layout()
        self._schedule_autosave()
        # One replot for the new subplot.
        self.request_replot()

    def _duplicate_subplot(self, source_selector: SubplotSelector) -> None:
        """Duplicate a subplot: create a new one with the same config."""
        try:
            cfg = source_selector.get_full_config()
        except Exception:
            cfg = {}
        self.add_subplot()
        try:
            self.subplots[-1].apply_full_config(cfg)
        except Exception:
            pass
        self.status_var.set(f"Duplicated subplot")
        self.request_replot()

    def remove_subplot(self, selector: SubplotSelector):
        # Remove selector UI
        try:
            self.container.forget(selector.frame)
        except Exception:
            pass
        try:
            selector.frame.destroy()
        except Exception:
            pass

        # Remove from model
        try:
            self.subplots.remove(selector)
        except ValueError:
            pass

        # Clean up overlay-change signature tracking for this selector.
        try:
            sigs = getattr(self, "_selector_overlay_sigs", None)
            if isinstance(sigs, dict):
                sigs.pop(int(id(selector)), None)
        except Exception:
            pass

        # Re-index remaining selectors
        for i, s in enumerate(self.subplots, start=1):
            try:
                s.frame.configure(text=f"Subplot {i}")
            except Exception:
                pass
        self.subplot_count = len(self.subplots)

        # Replot to remove corresponding plot
        self.request_replot()
        self._refresh_selector_layout()
        self._schedule_autosave()

    def request_replot(self):
        self._debug_log(
            f"request_replot suspend={getattr(self, '_replot_suspend_count', None)} "
            f"in_progress={getattr(self, '_replot_in_progress', None)}"
        )
        try:
            if int(getattr(self, "_replot_suspend_count", 0)) > 0:
                return
        except Exception:
            pass
        try:
            if bool(getattr(self, "_replot_in_progress", False)):
                self._replot_pending = True
                return
        except Exception:
            pass
        # Debounce frequent selection events (shift-click range selection can fire many times)
        if self._replot_job is not None:
            try:
                self.root.after_cancel(self._replot_job)
            except Exception:
                pass
        self._replot_job = self.root.after(250, self._do_replot)
        self._schedule_autosave()

    def _overlay_signature_for_selector(self, selector: SubplotSelector) -> tuple:
        """Return a stable signature representing overlay configuration.

        Used to detect overlay changes (add/remove/toggle/shift/alignment) so we
        can refresh Signals without doing it on every normal signal selection.
        """
        files = ()
        enabled_items = ()
        # Only include file list + enable/disable in the signature.
        # Shifts/alignment don't change which Signals exist and may update frequently.
        try:
            files = tuple(selector.get_files() or [])
        except Exception:
            files = ()
        try:
            enabled = selector.get_file_enabled() or {}
            enabled_items = tuple(sorted((str(k), bool(v)) for k, v in enabled.items()))
        except Exception:
            enabled_items = ()
        return (files, enabled_items)

    def _on_subplot_selector_change(self, selector: SubplotSelector) -> None:
        """Handle any selector event.

        - Always requests a (debounced) replot.
        - If the overlay file configuration changed, also refresh the Signals list.
        """
        try:
            if not isinstance(getattr(self, "_selector_overlay_sigs", None), dict):
                self._selector_overlay_sigs = {}
        except Exception:
            self._selector_overlay_sigs = {}

        sig = None
        try:
            sig = self._overlay_signature_for_selector(selector)
        except Exception:
            sig = None

        changed = False
        try:
            key = int(id(selector))
            old = self._selector_overlay_sigs.get(key)
            if sig is not None and sig != old:
                self._selector_overlay_sigs[key] = sig
                changed = True
        except Exception:
            changed = False

        if changed:
            try:
                self._schedule_refresh_signals_for_selector(selector)
            except Exception:
                pass

            # Overlay add/remove/toggle should be reflected in layout.json promptly.
            # Regular selector changes are already auto-saved via request_replot().
            try:
                self._schedule_autosave(immediate=True)
            except Exception:
                pass

        self.request_replot()

    def _do_replot(self):
        self._replot_job = None
        self._debug_log("_do_replot")
        try:
            if bool(getattr(self, "_replot_in_progress", False)):
                self._replot_pending = True
                self._replot_job = self.root.after(200, self._do_replot)
                return
        except Exception:
            pass
        self._replot_in_progress = True
        try:
            self.plot_all()
        finally:
            self._replot_in_progress = False
        if bool(getattr(self, "_replot_pending", False)):
            self._replot_pending = False
            self.request_replot()

    def on_mousewheel(self, event):
        delta = int(-1 * (event.delta / 120))

        # If the mouse is over a scrollable child (listbox / treeview), scroll that widget.
        try:
            w = event.widget
            cls = w.winfo_class()
        except Exception:
            w = None
            cls = ""

        if cls in ("Listbox", "Treeview") and w is not None:
            try:
                w.yview_scroll(delta, "units")
                return "break"
            except Exception:
                pass

        # If the mouse is over an entry/combobox, don't scroll the selector canvas.
        if cls in ("Entry", "TEntry", "TCombobox"):
            return "break"

        target = self._mousewheel_target or "plot"
        if target == "selector":
            self.selector_canvas.yview_scroll(delta, "units")
        elif target == "controls":
            self.controls_canvas.yview_scroll(delta, "units")
        else:
            self.canvas.yview_scroll(delta, "units")

        return "break"

    def _debug_log(self, msg: str) -> None:
        try:
            if not bool(getattr(self, "_debug_enabled", False)):
                return
        except Exception:
            return

        try:
            p = getattr(self, "_debug_log_path", None)
            if not isinstance(p, str) or not p:
                return
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"{ts} {msg}\n")
        except Exception:
            pass

    def plot_all(self):
        try:
            self._stats_trees = []
        except Exception:
            pass
        # Ensure plots are visible when rendering.
        try:
            self._set_plots_visible(True)
        except Exception:
            pass

        try:
            psf = getattr(self, "plot_scroll_frame", None)
            pa = getattr(self, "plot_area", None)
            self._debug_log(
                "plot_all start "
                f"plots_visible={getattr(self, '_plots_visible', None)} "
                f"subplots={len(getattr(self, 'subplots', []) or [])} "
                f"df_shape={getattr(getattr(self, 'df', None), 'shape', None)} "
                f"plot_scroll_size={(psf.winfo_width(), psf.winfo_height()) if psf is not None else None} "
                f"plot_area_size={(pa.winfo_width(), pa.winfo_height()) if pa is not None else None}"
            )
        except Exception:
            pass
        try:
            render_plot_all(self)
        except Exception as e:
            try:
                self.status_var.set(f"Plot error: {e}")
            except Exception:
                pass
            try:
                traceback.print_exc()
            except Exception:
                pass
            self._debug_log(f"plot_all exception: {e!r}")
            return

        try:
            pa = getattr(self, "plot_area", None)
            nchildren = len(pa.winfo_children()) if pa is not None else None
            self._debug_log(f"plot_all done plot_area_children={nchildren}")
        except Exception:
            pass
        # Re-apply highlight state after replot so it persists.
        try:
            self._apply_highlight_state()
        except Exception:
            pass

    def _set_plots_visible(self, visible: bool) -> None:
        """Show/hide the entire right-side plots pane."""
        self._plots_visible = bool(visible)
        pane = getattr(self, "main_pane", None)
        frame = getattr(self, "plot_scroll_frame", None)
        if pane is None or frame is None:
            return

        try:
            panes = list(pane.panes())
        except Exception:
            panes = []

        is_present = False
        try:
            is_present = frame in panes
        except Exception:
            # Some Tk builds return string widget names.
            try:
                is_present = str(frame) in [str(x) for x in panes]
            except Exception:
                is_present = False

        if self._plots_visible:
            if not is_present:
                try:
                    pane.add(frame, weight=3)
                except Exception:
                    pass
        else:
            if is_present:
                try:
                    pane.forget(frame)
                except Exception:
                    pass


def main():
    root = tk.Tk()
    root.configure(bg="white")
    # Start maximized (Windows). This is the closest to "fullscreen" without hiding the taskbar.
    try:
        root.state('zoomed')
    except Exception:
        try:
            root.attributes('-zoomed', True)
        except Exception:
            pass
    app = CSVPlotterApp(root)
    root.mainloop()

if __name__ == "__main__":
    # `docopt` is imported as a module, so call the function as `docopt.docopt`.
    # If `--help` or `--version` is passed, docopt will print and exit.
    docopt.docopt(__doc__, version=__version__)
    main()
