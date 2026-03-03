import os

import tkinter as tk
from tkinter import ttk


class SubplotSelector:
    def __init__(self, parent, columns, subplot_id, *, on_change=None, on_close=None, on_add_files=None, on_duplicate=None):
        self.frame = ttk.LabelFrame(parent, text=f"Subplot {subplot_id}")
        self._on_change = on_change
        self._on_close = on_close
        self._on_add_files = on_add_files
        self._on_duplicate = on_duplicate
        self._all_columns: list[str] = list(columns or [])

        self._use_ylim_var = tk.BooleanVar(value=False)
        self._ymin_var = tk.StringVar(value="")
        self._ymax_var = tk.StringVar(value="")
        self._stats_var = tk.StringVar(value="")
        self._show_table_var = tk.BooleanVar(value=True)
        self._show_hist_var = tk.BooleanVar(value=False)
        self._show_abs_check_var = tk.BooleanVar(value=False)
        self._show_rel_change_var = tk.BooleanVar(value=False)
        self._show_custom_var = tk.BooleanVar(value=False)
        self._hist_bins_var = tk.StringVar(value="30")

        # Custom python code plot
        self._custom_code: str = (
            "# Define either:\n"
            "# 1) a function transform(x, signals, df) -> Series | dict[str, Series] | scalar\n"
            "# 2) OR set variable out = ...\n"
            "\n"
            "def transform(x, signals, df):\n"
            "    # Example: average of selected signals\n"
            "    import pandas as pd\n"
            "    if not signals:\n"
            "        return pd.Series([], dtype=float)\n"
            "    return pd.concat(signals.values(), axis=1).mean(axis=1)\n"
        )

        # Barriers for check plots (piecewise limits by index)
        # Keep the original variable names as the ABS-check barrier settings.
        self._barriers_enabled_var = tk.BooleanVar(value=False)
        self._bar_target_var = tk.StringVar(value="45")
        self._bar_limit_in_var = tk.StringVar(value="1")
        self._bar_limit_out_var = tk.StringVar(value="5")
        self._bar_start_idx_var = tk.StringVar(value="175")
        self._bar_end_idx_var = tk.StringVar(value="1175")

        # REL-change has independent barrier settings.
        self._rel_barriers_enabled_var = tk.BooleanVar(value=False)
        self._rel_bar_target_var = tk.StringVar(value="45")
        self._rel_bar_limit_in_var = tk.StringVar(value="1")
        self._rel_bar_limit_out_var = tk.StringVar(value="5")
        self._rel_bar_start_idx_var = tk.StringVar(value="175")
        self._rel_bar_end_idx_var = tk.StringVar(value="1175")
        self._x_window: tuple[float, float] | None = None
        self._window_var = tk.StringVar(value="Window: ALL")
        self._plot_mode_var = tk.StringVar(value="Time series")
        self._active_series: str | None = None

        # Multi-file overlay settings (Time series mode)
        self._x_align_var = tk.StringVar(value="Aligned timestamps")
        # Keep absolute paths (most-recent-first, base file first)
        self._file_paths: list[str] = []
        # Per-file shifts: path -> {x_shift_s: float, y_shift: float}
        self._file_shifts: dict[str, dict[str, float]] = {}
        # Per-file enable: path -> bool (allows toggling base/source file too)
        self._file_enabled: dict[str, bool] = {}
        # Per-file timebase/timestep override:
        # path -> {mode: 'global'|'auto'|'fixed', unit: 's'|'ms'|'us', step: float}
        self._file_timebase: dict[str, dict[str, object]] = {}
        self._selected_file_path: str | None = None
        self._x_shift_var = tk.StringVar(value="0")
        self._y_shift_var = tk.StringVar(value="0")

        # Per-file timebase edit controls (overlay UI)
        self._tb_mode_var = tk.StringVar(value="Global")
        self._tb_unit_var = tk.StringVar(value="ms")
        self._tb_step_var = tk.StringVar(value="0.01")

        btn_row = ttk.Frame(self.frame)
        btn_row.pack(fill='x', padx=5, pady=(5, 0))
        ttk.Button(btn_row, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Invert", command=self.invert_selection).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Clear", command=self.clear_selection).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Duplicate", command=self._duplicate_clicked).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Close", command=self.close).pack(side=tk.RIGHT, padx=2)
        self._signal_count_var = tk.StringVar(value="0 / 0 signals")
        ttk.Label(btn_row, textvariable=self._signal_count_var, style="Muted.TLabel").pack(side=tk.RIGHT, padx=(8, 2))

        main_box = ttk.LabelFrame(self.frame, text="Main plot")
        main_box.pack(fill='x', padx=5, pady=(5, 0))

        ylim_row = ttk.Frame(main_box)
        ylim_row.pack(fill='x', padx=5, pady=(4, 4))
        ttk.Checkbutton(
            ylim_row,
            text="Use Y limits",
            variable=self._use_ylim_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(ylim_row, text="Min:").pack(side=tk.LEFT)
        ymin_entry = ttk.Entry(ylim_row, textvariable=self._ymin_var, width=10)
        ymin_entry.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(ylim_row, text="Max:").pack(side=tk.LEFT)
        ymax_entry = ttk.Entry(ylim_row, textvariable=self._ymax_var, width=10)
        ymax_entry.pack(side=tk.LEFT, padx=(2, 0))
        ymin_entry.bind("<Return>", self._handle_change)
        ymax_entry.bind("<Return>", self._handle_change)
        ymin_entry.bind("<FocusOut>", self._handle_change)
        ymax_entry.bind("<FocusOut>", self._handle_change)

        bottom_box = ttk.LabelFrame(self.frame, text="Bottom plots")
        bottom_box.pack(fill='x', padx=5, pady=(4, 0))

        window_row = ttk.Frame(bottom_box)
        window_row.pack(fill='x', padx=5, pady=(4, 0))
        ttk.Label(window_row, textvariable=self._window_var).pack(side=tk.LEFT)
        ttk.Button(window_row, text="Clear window", command=self.clear_x_window).pack(side=tk.RIGHT)

        table_box = ttk.LabelFrame(bottom_box, text="Table")
        table_box.pack(fill='x', padx=5, pady=(4, 0))
        table_row = ttk.Frame(table_box)
        table_row.pack(fill='x', padx=5, pady=(3, 3))
        ttk.Checkbutton(
            table_row,
            text="Show table",
            variable=self._show_table_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT)

        hist_box = ttk.LabelFrame(bottom_box, text="Histogram")
        hist_box.pack(fill='x', padx=5, pady=(4, 0))
        hist_row = ttk.Frame(hist_box)
        hist_row.pack(fill='x', padx=5, pady=(3, 3))
        ttk.Checkbutton(
            hist_row,
            text="Show histogram",
            variable=self._show_hist_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT)
        ttk.Label(hist_row, text="Bins:").pack(side=tk.LEFT, padx=(10, 0))
        bins_entry = ttk.Entry(hist_row, textvariable=self._hist_bins_var, width=6)
        bins_entry.pack(side=tk.LEFT, padx=(2, 0))
        bins_entry.bind("<Return>", self._handle_change)
        bins_entry.bind("<FocusOut>", self._handle_change)

        abs_box = ttk.LabelFrame(bottom_box, text="Abs check")
        abs_box.pack(fill='x', padx=5, pady=(4, 0))
        abs_row = ttk.Frame(abs_box)
        abs_row.pack(fill='x', padx=5, pady=(3, 2))
        ttk.Checkbutton(
            abs_row,
            text="Show abs check",
            variable=self._show_abs_check_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT)

        barrier_row = ttk.Frame(abs_box)
        barrier_row.pack(fill='x', padx=5, pady=(2, 4))
        ttk.Checkbutton(
            barrier_row,
            text="Barriers",
            variable=self._barriers_enabled_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(barrier_row, text="Target:").pack(side=tk.LEFT)
        ent_target = ttk.Entry(barrier_row, textvariable=self._bar_target_var, width=7)
        ent_target.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(barrier_row, text="Limit(in):").pack(side=tk.LEFT)
        ent_in = ttk.Entry(barrier_row, textvariable=self._bar_limit_in_var, width=7)
        ent_in.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(barrier_row, text="Limit(out):").pack(side=tk.LEFT)
        ent_out = ttk.Entry(barrier_row, textvariable=self._bar_limit_out_var, width=7)
        ent_out.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(barrier_row, text="Start:").pack(side=tk.LEFT)
        ent_s = ttk.Entry(barrier_row, textvariable=self._bar_start_idx_var, width=7)
        ent_s.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(barrier_row, text="End:").pack(side=tk.LEFT)
        ent_e = ttk.Entry(barrier_row, textvariable=self._bar_end_idx_var, width=7)
        ent_e.pack(side=tk.LEFT, padx=(2, 0))

        for w in (ent_target, ent_in, ent_out, ent_s, ent_e):
            try:
                w.bind("<Return>", self._handle_change)
                w.bind("<FocusOut>", self._handle_change)
            except Exception:
                pass

        rel_box = ttk.LabelFrame(bottom_box, text="Rel change")
        rel_box.pack(fill='x', padx=5, pady=(4, 4))
        rel_row = ttk.Frame(rel_box)
        rel_row.pack(fill='x', padx=5, pady=(3, 3))
        ttk.Checkbutton(
            rel_row,
            text="Show rel change",
            variable=self._show_rel_change_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT)

        rel_barrier_row = ttk.Frame(rel_box)
        rel_barrier_row.pack(fill='x', padx=5, pady=(2, 4))
        ttk.Checkbutton(
            rel_barrier_row,
            text="Barriers",
            variable=self._rel_barriers_enabled_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(rel_barrier_row, text="Target:").pack(side=tk.LEFT)
        rel_ent_target = ttk.Entry(rel_barrier_row, textvariable=self._rel_bar_target_var, width=7)
        rel_ent_target.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(rel_barrier_row, text="Limit(in):").pack(side=tk.LEFT)
        rel_ent_in = ttk.Entry(rel_barrier_row, textvariable=self._rel_bar_limit_in_var, width=7)
        rel_ent_in.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(rel_barrier_row, text="Limit(out):").pack(side=tk.LEFT)
        rel_ent_out = ttk.Entry(rel_barrier_row, textvariable=self._rel_bar_limit_out_var, width=7)
        rel_ent_out.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(rel_barrier_row, text="Start:").pack(side=tk.LEFT)
        rel_ent_s = ttk.Entry(rel_barrier_row, textvariable=self._rel_bar_start_idx_var, width=7)
        rel_ent_s.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(rel_barrier_row, text="End:").pack(side=tk.LEFT)
        rel_ent_e = ttk.Entry(rel_barrier_row, textvariable=self._rel_bar_end_idx_var, width=7)
        rel_ent_e.pack(side=tk.LEFT, padx=(2, 0))

        for w in (rel_ent_target, rel_ent_in, rel_ent_out, rel_ent_s, rel_ent_e):
            try:
                w.bind("<Return>", self._handle_change)
                w.bind("<FocusOut>", self._handle_change)
            except Exception:
                pass

        custom_box = ttk.LabelFrame(bottom_box, text="Custom")
        custom_box.pack(fill='x', padx=5, pady=(4, 4))

        custom_row = ttk.Frame(custom_box)
        custom_row.pack(fill='x', padx=5, pady=(3, 3))
        ttk.Checkbutton(
            custom_row,
            text="Show custom",
            variable=self._show_custom_var,
            command=self._handle_change,
        ).pack(side=tk.LEFT)

        ttk.Button(custom_row, text="Apply", command=self._apply_custom_code).pack(side=tk.RIGHT)

        self._custom_text = tk.Text(custom_box, height=6, wrap="none")
        try:
            self._custom_text.insert("1.0", self._custom_code)
        except Exception:
            pass
        self._custom_text.pack(fill='both', expand=True, padx=5, pady=(0, 5))
        try:
            self._custom_text.bind("<Control-Return>", lambda _e: self._apply_custom_code())
            self._custom_text.bind("<FocusOut>", lambda _e: self._apply_custom_code())
        except Exception:
            pass

        # NOTE: Mode selection UI removed per request. Plot stays as normal Time series,
        # while extra diagnostics are shown via toggleable bottom plots.

        # Multi-file overlay controls (separate from signal selector)
        overlay_box = ttk.LabelFrame(self.frame, text="Overlay files (Time series)")
        overlay_box.pack(fill='x', padx=5, pady=(4, 0))

        overlay_row = ttk.Frame(overlay_box)
        overlay_row.pack(fill='x', padx=5, pady=(4, 0))
        ttk.Label(overlay_row, text="Overlay X:").pack(side=tk.LEFT)
        self._x_align_combo = ttk.Combobox(
            overlay_row,
            textvariable=self._x_align_var,
            state="readonly",
            values=[
                "Aligned timestamps",
                "Independent (t=0 per file)",
            ],
            width=24,
        )
        self._x_align_combo.pack(side=tk.LEFT, padx=(6, 8))
        self._x_align_combo.bind("<<ComboboxSelected>>", self._handle_change)

        ttk.Button(overlay_row, text="Add file(s)", command=self._add_files_clicked).pack(side=tk.LEFT, padx=2)
        ttk.Button(overlay_row, text="Toggle on/off", command=self._toggle_selected_file_enabled).pack(side=tk.LEFT, padx=2)
        ttk.Button(overlay_row, text="Remove", command=self._remove_selected_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(overlay_row, text="Clear", command=self._clear_extra_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(overlay_row, text="Remove all", command=self._clear_all_files).pack(side=tk.LEFT, padx=2)

        files_frame = ttk.Frame(overlay_box)
        files_frame.pack(fill='x', padx=5, pady=(2, 0))

        self._files_listbox = tk.Listbox(files_frame, selectmode=tk.SINGLE, height=3, exportselection=False)
        self._files_listbox.pack(side=tk.LEFT, fill='x', expand=True)
        self._files_listbox.bind("<<ListboxSelect>>", self._on_file_selected)
        self._files_listbox.bind("<Double-Button-1>", self._toggle_file_enabled_at_click)
        files_scroll = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=self._files_listbox.yview)
        self._files_listbox.configure(yscrollcommand=files_scroll.set)
        files_scroll.pack(side=tk.RIGHT, fill='y')

        shift_row = ttk.Frame(overlay_box)
        shift_row.pack(fill='x', padx=5, pady=(2, 6))
        ttk.Label(shift_row, text="X shift (sec):").pack(side=tk.LEFT)
        xent = ttk.Entry(shift_row, textvariable=self._x_shift_var, width=10)
        xent.pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(shift_row, text="Y shift:").pack(side=tk.LEFT)
        yent = ttk.Entry(shift_row, textvariable=self._y_shift_var, width=10)
        yent.pack(side=tk.LEFT, padx=(2, 0))
        ttk.Button(shift_row, text="Apply", command=self._apply_shifts_to_selected).pack(side=tk.LEFT, padx=8)
        xent.bind("<Return>", lambda _e: self._apply_shifts_to_selected())
        yent.bind("<Return>", lambda _e: self._apply_shifts_to_selected())
        xent.bind("<FocusOut>", lambda _e: self._apply_shifts_to_selected())
        yent.bind("<FocusOut>", lambda _e: self._apply_shifts_to_selected())

        timebase_row = ttk.Frame(overlay_box)
        timebase_row.pack(fill='x', padx=5, pady=(0, 6))
        ttk.Label(timebase_row, text="Timestep:").pack(side=tk.LEFT)
        self._tb_mode_combo = ttk.Combobox(
            timebase_row,
            textvariable=self._tb_mode_var,
            state="readonly",
            values=[
                "Global",
                "Auto",
                "Custom",
            ],
            width=8,
        )
        self._tb_mode_combo.pack(side=tk.LEFT, padx=(6, 8))
        self._tb_mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_timebase_mode_changed())

        ttk.Label(timebase_row, text="Unit:").pack(side=tk.LEFT)
        self._tb_unit_combo = ttk.Combobox(
            timebase_row,
            textvariable=self._tb_unit_var,
            state="readonly",
            values=["s", "ms", "us"],
            width=4,
        )
        self._tb_unit_combo.pack(side=tk.LEFT, padx=(6, 10))

        ttk.Label(timebase_row, text="Step:").pack(side=tk.LEFT)
        self._tb_step_entry = ttk.Entry(timebase_row, textvariable=self._tb_step_var, width=10)
        self._tb_step_entry.pack(side=tk.LEFT, padx=(6, 10))

        ttk.Button(timebase_row, text="Apply", command=self._apply_timebase_to_selected).pack(side=tk.LEFT)

        try:
            self._tb_step_entry.bind("<Return>", lambda _e: self._apply_timebase_to_selected())
            self._tb_step_entry.bind("<FocusOut>", lambda _e: self._apply_timebase_to_selected())
        except Exception:
            pass

        self._on_timebase_mode_changed()

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).pack(fill='x', padx=5, pady=(6, 0))

        # Resizable selector internals: signal list vs stats area
        self._inner_split = tk.PanedWindow(
            self.frame,
            orient=tk.VERTICAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            showhandle=True,
        )
        self._inner_split.pack(fill='both', expand=True, padx=5, pady=5)

        list_frame = ttk.LabelFrame(self._inner_split, text="Signals")
        stats_frame = ttk.Frame(self._inner_split)

        # Search/filter entry for signals
        self._search_var = tk.StringVar(value="")
        search_row = ttk.Frame(list_frame)
        search_row.pack(fill='x', padx=2, pady=(2, 0))
        ttk.Label(search_row, text="\U0001F50D").pack(side=tk.LEFT, padx=(2, 0))
        self._search_entry = ttk.Entry(search_row, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(4, 2))
        self._search_var.trace_add("write", lambda *_a: self._apply_search_filter())

        # EXTENDED enables Shift-click range selection and Ctrl-click toggling
        # Make Signals area roomier by default.
        self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=12, exportselection=False)
        for col in columns:
            self.listbox.insert(tk.END, str(col))
        self.listbox.pack(fill='both', expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        self._stats_label = ttk.Label(stats_frame, textvariable=self._stats_var, justify='left', anchor='w')
        self._stats_label.pack(fill='both', expand=True)

        try:
            # User requested a large, friendly Signals area.
            self._inner_split.add(list_frame, minsize=500)
            self._inner_split.add(stats_frame, minsize=30)
        except Exception:
            # Last-resort: if add fails, fall back to stacking without a sash
            list_frame.pack(fill='both', expand=True)
            stats_frame.pack(fill='x')

        # Default inner split: prefer Signals area unless a saved sash is restored.
        self._inner_split_restored: bool = False
        try:
            paned = self._inner_split

            def _clamp_inner_y(y: int) -> int:
                try:
                    self.frame.update_idletasks()
                except Exception:
                    pass
                try:
                    h = int(paned.winfo_height())
                except Exception:
                    h = 0
                if h <= 220:
                    return int(y)
                # Keep both panes visible: signals gets most space, stats stays readable.
                min_y = 140
                max_y = max(min_y + 20, h - 80)
                try:
                    return int(max(min_y, min(int(y), int(max_y))))
                except Exception:
                    return int(y)

            def _default_inner_split() -> None:
                if bool(getattr(self, "_inner_split_restored", False)):
                    return
                try:
                    self.frame.update_idletasks()
                except Exception:
                    pass
                try:
                    h = int(self.frame.winfo_height())
                except Exception:
                    h = 0
                if h <= 200:
                    return
                # Leave a small area for stats at the bottom.
                y = _clamp_inner_y(int(h * 0.82))
                try:
                    paned.sash_place(0, 0, y)
                except Exception:
                    pass

            self.frame.after(0, _default_inner_split)
            self.frame.after(120, _default_inner_split)
            self.frame.after(250, _default_inner_split)
        except Exception:
            pass

        self.frame.bind("<Configure>", self._on_configure)

        # Persisted UI positions
        self._plot_split_sashpos: int | None = None
        self._plot_split = None

        # Bottom area internal splitter (between bottom plots)
        self._bottom_pane = None
        self._bottom_pane_state: dict | None = None
        # When the user drags the bottom sash, keep their sizing.
        self._bottom_pane_user_modified: bool = False

    def set_columns(self, columns) -> None:
        """Replace the available Signals list contents."""
        lb = getattr(self, "listbox", None)
        if lb is None:
            return

        self._all_columns = list(columns or [])
        try:
            old_sel = []
            try:
                old_sel = [lb.get(i) for i in lb.curselection()]
            except Exception:
                old_sel = []

            lb.delete(0, tk.END)
            cols = list(columns or [])
            # Apply current search filter
            query = str(getattr(self, "_search_var", tk.StringVar()).get() or "").strip().lower()
            for c in cols:
                if query and query not in str(c).lower():
                    continue
                lb.insert(tk.END, str(c))

            if old_sel:
                want = set(str(x) for x in old_sel)
                try:
                    lb.selection_clear(0, tk.END)
                except Exception:
                    pass
                # Iterate over the *visible* listbox items (which may be filtered).
                for i in range(lb.size()):
                    try:
                        if str(lb.get(i)) in want:
                            lb.selection_set(i)
                    except Exception:
                        pass
        except Exception:
            # Keep UI resilient; a missing/misbehaving listbox should not crash loading.
            pass

    def _snapshot_bottom_pane_state(self, order: list[str] | None = None) -> None:
        """Capture current bottom pane sash positions into _bottom_pane_state."""
        paned = getattr(self, "_bottom_pane", None)
        if paned is None or not hasattr(paned, "sashpos"):
            return

        try:
            panes = list(paned.panes())
        except Exception:
            panes = []
        if len(panes) <= 1:
            return

        try:
            sashpos: list[int] = []
            for i in range(len(panes) - 1):
                try:
                    sashpos.append(int(paned.sashpos(i)))
                except Exception:
                    continue
            if self._bottom_pane_state is None or not isinstance(self._bottom_pane_state, dict):
                self._bottom_pane_state = {}
            if isinstance(order, list):
                self._bottom_pane_state["order"] = [str(x) for x in order]
            self._bottom_pane_state["sashpos"] = sashpos
            # Called from drag bindings; mark as user-modified so future rerenders
            # can respect custom sash positions.
            self._bottom_pane_user_modified = True
        except Exception:
            pass

    def apply_theme(self, palette: dict) -> None:
        # Apply to Tk widgets that don't follow ttk styling.
        if not isinstance(palette, dict):
            return
        bg = str(palette.get("bg") or "")
        panel = str(palette.get("panel") or bg or "")
        fg = str(palette.get("fg") or "")
        sel = str(palette.get("selection") or "")

        for lb in (getattr(self, "listbox", None), getattr(self, "_files_listbox", None)):
            if lb is None:
                continue
            try:
                lb.configure(
                    background=panel or bg,
                    foreground=fg,
                    selectbackground=sel,
                    selectforeground=fg,
                    highlightbackground=panel or bg,
                )
            except Exception:
                pass

    def get_inner_split_sash(self) -> dict | None:
        """Return sash coord for the selector internal split (signals vs stats)."""
        paned = getattr(self, "_inner_split", None)
        if paned is None or not hasattr(paned, "sash_coord"):
            return None
        try:
            x, y = paned.sash_coord(0)
            return {"x": int(x), "y": int(y)}
        except Exception:
            return None

    def set_inner_split_sash(self, coord: dict | None) -> None:
        paned = getattr(self, "_inner_split", None)
        if paned is None or not hasattr(paned, "sash_place"):
            return
        if not isinstance(coord, dict):
            return
        try:
            x = int(coord.get("x"))
            y = int(coord.get("y"))
        except Exception:
            return
        # Prevent default sash placement from overwriting restored layouts.
        self._inner_split_restored = True

        def _clamp_y(yv: int) -> int:
            try:
                self.frame.update_idletasks()
            except Exception:
                pass
            try:
                h = int(paned.winfo_height())
            except Exception:
                h = 0
            if h <= 220:
                return int(yv)
            min_y = 140
            max_y = max(min_y + 20, h - 80)
            try:
                return int(max(min_y, min(int(yv), int(max_y))))
            except Exception:
                return int(yv)

        def _apply():
            try:
                self.frame.update_idletasks()
            except Exception:
                pass
            try:
                paned.sash_place(0, x, _clamp_y(y))
            except Exception:
                pass

        try:
            self.frame.after(0, _apply)
        except Exception:
            _apply()

    def get_plot_split_sashpos(self) -> int | None:
        try:
            v = self._plot_split_sashpos
        except Exception:
            v = None
        if v is None:
            # If a split exists now, read it live.
            try:
                ps = getattr(self, "_plot_split", None)
                if ps is not None and hasattr(ps, "sashpos"):
                    return int(ps.sashpos(0))
            except Exception:
                pass
        return int(v) if isinstance(v, int) else v

    def set_plot_split_sashpos(self, sashpos: int | float | str | None) -> None:
        try:
            self._plot_split_sashpos = int(float(sashpos)) if sashpos is not None else None
        except Exception:
            self._plot_split_sashpos = None

    def _bind_plot_split(self, plot_split) -> None:
        """Called by plotting layer to attach the plot/bottom splitter."""
        self._plot_split = plot_split
        # Apply stored sashpos if available.
        try:
            if self._plot_split_sashpos is not None and hasattr(plot_split, "sashpos"):
                plot_split.sashpos(0, int(self._plot_split_sashpos))
        except Exception:
            pass

    def get_bottom_pane_state(self) -> dict | None:
        """Return bottom-area Panedwindow sash positions and pane order."""
        try:
            paned = self._bottom_pane
        except Exception:
            paned = None

        state: dict | None = None
        try:
            state = dict(self._bottom_pane_state) if isinstance(self._bottom_pane_state, dict) else None
        except Exception:
            state = None

        if paned is None or not hasattr(paned, "sashpos"):
            return state

        try:
            panes = list(paned.panes())
        except Exception:
            panes = []
        if len(panes) <= 1:
            return state

        try:
            sashpos: list[int] = []
            for i in range(len(panes) - 1):
                try:
                    sashpos.append(int(paned.sashpos(i)))
                except Exception:
                    continue
            base = state if isinstance(state, dict) else {}
            base = dict(base)
            base["sashpos"] = sashpos
            # Keep in-memory state in sync so a re-render can re-apply.
            try:
                if self._bottom_pane_state is None or not isinstance(self._bottom_pane_state, dict):
                    self._bottom_pane_state = {}
                # Preserve any existing order, but update sashpos.
                if isinstance(base.get("order"), list):
                    self._bottom_pane_state["order"] = [str(x) for x in base.get("order")]
                self._bottom_pane_state["sashpos"] = list(sashpos)
            except Exception:
                pass
            return base
        except Exception:
            return state

    def set_bottom_pane_state(self, state: dict | None) -> None:
        if isinstance(state, dict):
            self._bottom_pane_state = dict(state)
        else:
            self._bottom_pane_state = None

    def _bind_bottom_pane(self, bottom_pane, order: list[str]) -> None:
        """Called by plotting layer to attach the bottom plots splitter."""
        self._bottom_pane = bottom_pane

        # Record order so we only apply sashes when the same set/order is present.
        try:
            if isinstance(order, list):
                if self._bottom_pane_state is None:
                    self._bottom_pane_state = {}
                self._bottom_pane_state["order"] = [str(x) for x in order]
        except Exception:
            pass

        st = self._bottom_pane_state if isinstance(self._bottom_pane_state, dict) else None
        if st is None:
            return
        try:
            want_order = st.get("order")
            want_sashes = st.get("sashpos")
        except Exception:
            want_order = None
            want_sashes = None

        if not (isinstance(want_order, list) and isinstance(want_sashes, list)):
            return
        if [str(x) for x in want_order] != [str(x) for x in order]:
            return

        try:
            panes = list(bottom_pane.panes())
        except Exception:
            panes = []
        if len(panes) - 1 != len(want_sashes):
            return

        try:
            # Apply after geometry settles (sometimes needs more than one idle tick).
            def _apply_once() -> None:
                try:
                    for i, pos in enumerate(want_sashes):
                        bottom_pane.sashpos(i, int(pos))
                except Exception:
                    pass

            self.frame.after(0, _apply_once)
            self.frame.after(50, _apply_once)
        except Exception:
            try:
                for i, pos in enumerate(want_sashes):
                    bottom_pane.sashpos(i, int(pos))
            except Exception:
                pass

        # Update state when the user drags the sash so future rerenders keep it.
        try:
            bottom_pane.bind(
                "<ButtonRelease-1>",
                lambda _e: self._snapshot_bottom_pane_state(order),
                add="+",
            )
            bottom_pane.bind(
                "<B1-Motion>",
                lambda _e: self._snapshot_bottom_pane_state(order),
                add="+",
            )
        except Exception:
            pass

    def _add_files_clicked(self) -> None:
        if callable(self._on_add_files):
            self._on_add_files(self)

    def _normalize_path(self, p: str) -> str:
        try:
            return os.path.abspath(str(p))
        except Exception:
            return str(p)

    def _parse_float(self, s: str, default: float = 0.0) -> float:
        try:
            txt = str(s or "").strip()
            if "," in txt and "." not in txt:
                txt = txt.replace(",", ".")
            return float(txt)
        except Exception:
            return float(default)

    def set_files(self, paths: list[str] | None) -> None:
        old_enabled = dict(self._file_enabled) if isinstance(getattr(self, "_file_enabled", None), dict) else {}
        old_tb = dict(self._file_timebase) if isinstance(getattr(self, "_file_timebase", None), dict) else {}
        self._file_paths = []
        self._file_shifts = {}
        self._file_enabled = {}
        self._file_timebase = {}
        if isinstance(paths, list):
            for p in paths:
                ap = self._normalize_path(p)
                if ap and ap not in self._file_paths:
                    self._file_paths.append(ap)
                    self._file_shifts.setdefault(ap, {"x_shift_s": 0.0, "y_shift": 0.0})
                    # Preserve previous enabled state when possible.
                    try:
                        self._file_enabled[ap] = bool(old_enabled.get(ap, True))
                    except Exception:
                        self._file_enabled[ap] = True
                    # Preserve previous timebase config when possible.
                    try:
                        cfg = old_tb.get(ap)
                        if isinstance(cfg, dict):
                            self._file_timebase[ap] = dict(cfg)
                        else:
                            self._file_timebase[ap] = {"mode": "global"}
                    except Exception:
                        self._file_timebase[ap] = {"mode": "global"}
        self._refresh_files_listbox(select_index=0)
        self._handle_change()

    def add_files(self, paths: list[str] | None) -> None:
        if not isinstance(paths, list):
            return
        for p in paths:
            ap = self._normalize_path(p)
            if not ap:
                continue
            if ap in self._file_paths:
                continue
            self._file_paths.append(ap)
            self._file_shifts.setdefault(ap, {"x_shift_s": 0.0, "y_shift": 0.0})
            try:
                self._file_enabled.setdefault(ap, True)
            except Exception:
                self._file_enabled[ap] = True
            try:
                self._file_timebase.setdefault(ap, {"mode": "global"})
            except Exception:
                self._file_timebase[ap] = {"mode": "global"}
        self._refresh_files_listbox(select_index=0)
        self._handle_change()

    def get_files(self) -> list[str]:
        return list(self._file_paths)

    def get_file_enabled(self) -> dict[str, bool]:
        out: dict[str, bool] = {}
        try:
            for p in list(self._file_paths):
                ap = self._normalize_path(p)
                out[ap] = bool(self._file_enabled.get(ap, True))
        except Exception:
            pass
        return out

    def set_file_enabled(self, enabled: dict | None) -> None:
        if not isinstance(enabled, dict):
            return
        for p, v in enabled.items():
            ap = self._normalize_path(str(p))
            if ap not in self._file_paths:
                continue
            try:
                self._file_enabled[ap] = bool(v)
            except Exception:
                self._file_enabled[ap] = True
        self._refresh_files_listbox(select_index=None)

    def is_file_enabled(self, path: str) -> bool:
        ap = self._normalize_path(path)
        try:
            return bool(self._file_enabled.get(ap, True))
        except Exception:
            return True

    def get_x_alignment_mode(self) -> str:
        # returns "aligned" or "independent"
        v = str(self._x_align_var.get() or "Aligned timestamps")
        if v.lower().startswith("independent"):
            return "independent"
        return "aligned"

    def set_x_alignment_mode(self, mode: str | None) -> None:
        m = str(mode or "aligned").lower().strip()
        if m in ("independent", "relative", "t0"):
            self._x_align_var.set("Independent (t=0 per file)")
        else:
            self._x_align_var.set("Aligned timestamps")

    def get_file_shifts(self) -> dict[str, dict[str, float]]:
        # Shallow copy
        out: dict[str, dict[str, float]] = {}
        for p, cfg in self._file_shifts.items():
            try:
                out[p] = {"x_shift_s": float(cfg.get("x_shift_s", 0.0)), "y_shift": float(cfg.get("y_shift", 0.0))}
            except Exception:
                out[p] = {"x_shift_s": 0.0, "y_shift": 0.0}
        return out

    def get_file_timebase(self) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        try:
            for p in list(self._file_paths):
                ap = self._normalize_path(p)
                cfg = self._file_timebase.get(ap)
                if not isinstance(cfg, dict):
                    cfg = {"mode": "global"}
                mode = str(cfg.get("mode", "global") or "global").lower().strip()
                if mode not in ("global", "auto", "fixed"):
                    mode = "global"
                unit = str(cfg.get("unit", "ms") or "ms").lower().strip()
                if unit not in ("s", "ms", "us"):
                    unit = "ms"
                step = cfg.get("step", 0.01)
                try:
                    step_f = float(step)
                except Exception:
                    step_f = 0.01
                out[ap] = {"mode": mode, "unit": unit, "step": step_f}
        except Exception:
            pass
        return out

    def set_file_timebase(self, tb: dict | None) -> None:
        if not isinstance(tb, dict):
            return
        for p, cfg in tb.items():
            ap = self._normalize_path(str(p))
            if ap not in self._file_paths:
                continue
            if not isinstance(cfg, dict):
                continue
            mode = str(cfg.get("mode", "global") or "global").lower().strip()
            if mode not in ("global", "auto", "fixed"):
                mode = "global"
            unit = str(cfg.get("unit", "ms") or "ms").lower().strip()
            if unit not in ("s", "ms", "us"):
                unit = "ms"
            step = cfg.get("step", 0.01)
            try:
                step_f = float(step)
            except Exception:
                step_f = 0.01
            self._file_timebase[ap] = {"mode": mode, "unit": unit, "step": step_f}

        # Refresh UI fields based on current selection
        try:
            self._on_file_selected()
        except Exception:
            pass

    def set_file_shifts(self, shifts: dict | None) -> None:
        if not isinstance(shifts, dict):
            return
        for p, cfg in shifts.items():
            if not isinstance(cfg, dict):
                continue
            ap = self._normalize_path(p)
            if ap not in self._file_paths:
                continue
            try:
                xs = float(cfg.get("x_shift_s", 0.0))
            except Exception:
                xs = 0.0
            try:
                ys = float(cfg.get("y_shift", 0.0))
            except Exception:
                ys = 0.0
            self._file_shifts[ap] = {"x_shift_s": xs, "y_shift": ys}
        self._refresh_files_listbox(select_index=0)

    def _refresh_files_listbox(self, *, select_index: int | None = None) -> None:
        try:
            self._files_listbox.delete(0, tk.END)
        except Exception:
            return
        for i, p in enumerate(self._file_paths):
            base = os.path.basename(p) if isinstance(p, str) else str(p)
            prefix = "* " if i == 0 else "  "
            on = True
            try:
                on = bool(self._file_enabled.get(self._normalize_path(p), True))
            except Exception:
                on = True
            mark = "[x]" if on else "[ ]"
            self._files_listbox.insert(tk.END, f"{prefix}{mark} {base}")
        if select_index is None:
            select_index = 0 if self._file_paths else None
        if select_index is not None and self._file_paths:
            try:
                self._files_listbox.selection_clear(0, tk.END)
                self._files_listbox.selection_set(int(select_index))
                self._files_listbox.see(int(select_index))
                self._on_file_selected()
            except Exception:
                pass

    def _on_file_selected(self, _event=None) -> None:
        idxs = ()
        try:
            idxs = self._files_listbox.curselection()
        except Exception:
            idxs = ()
        if not idxs:
            self._selected_file_path = None
            return
        i = int(idxs[0])
        if i < 0 or i >= len(self._file_paths):
            self._selected_file_path = None
            return
        p = self._file_paths[i]
        self._selected_file_path = p
        cfg = self._file_shifts.get(p, {"x_shift_s": 0.0, "y_shift": 0.0})
        try:
            self._x_shift_var.set(str(cfg.get("x_shift_s", 0.0)))
            self._y_shift_var.set(str(cfg.get("y_shift", 0.0)))
        except Exception:
            pass

        # Update timebase editor for selected file.
        try:
            tbcfg = self._file_timebase.get(p)
            if not isinstance(tbcfg, dict):
                tbcfg = {"mode": "global"}
            mode = str(tbcfg.get("mode", "global") or "global").lower().strip()
            if mode == "auto":
                self._tb_mode_var.set("Auto")
            elif mode == "fixed":
                self._tb_mode_var.set("Custom")
            else:
                self._tb_mode_var.set("Global")
            unit = str(tbcfg.get("unit", "ms") or "ms").lower().strip()
            if unit not in ("s", "ms", "us"):
                unit = "ms"
            self._tb_unit_var.set(unit)
            try:
                self._tb_step_var.set(str(tbcfg.get("step", 0.01)))
            except Exception:
                self._tb_step_var.set("0.01")
            self._on_timebase_mode_changed()
        except Exception:
            pass

    def _on_timebase_mode_changed(self) -> None:
        try:
            mode = str(self._tb_mode_var.get() or "Global").strip().lower()
        except Exception:
            mode = "global"
        enable = bool(mode == "custom")
        try:
            self._tb_unit_combo.configure(state=("readonly" if enable else "disabled"))
        except Exception:
            pass
        try:
            self._tb_step_entry.configure(state=("normal" if enable else "disabled"))
        except Exception:
            pass

    def _apply_timebase_to_selected(self) -> None:
        p = self._selected_file_path
        if not p:
            return

        try:
            mode_ui = str(self._tb_mode_var.get() or "Global").strip().lower()
        except Exception:
            mode_ui = "global"

        if mode_ui == "auto":
            self._file_timebase[p] = {"mode": "auto"}
        elif mode_ui == "custom":
            unit = str(self._tb_unit_var.get() or "ms").strip().lower()
            if unit not in ("s", "ms", "us"):
                unit = "ms"
            step = self._parse_float(str(self._tb_step_var.get() or "0.01"), default=0.01)
            if step <= 0:
                step = 0.01
            self._file_timebase[p] = {"mode": "fixed", "unit": unit, "step": float(step)}
        else:
            self._file_timebase[p] = {"mode": "global"}

        self._handle_change()

    def _apply_shifts_to_selected(self) -> None:
        p = self._selected_file_path
        if not p:
            return
        try:
            xs = float(str(self._x_shift_var.get() or "0").strip())
        except Exception:
            xs = 0.0
        try:
            ys = float(str(self._y_shift_var.get() or "0").strip())
        except Exception:
            ys = 0.0
        self._file_shifts[p] = {"x_shift_s": xs, "y_shift": ys}
        self._handle_change()

    def _remove_selected_file(self) -> None:
        idxs = ()
        try:
            idxs = self._files_listbox.curselection()
        except Exception:
            idxs = ()
        if not idxs:
            return
        i = int(idxs[0])
        if i < 0 or i >= len(self._file_paths):
            return

        # Never allow removing the last remaining file.
        if len(self._file_paths) <= 1:
            return

        p = self._file_paths.pop(i)
        try:
            self._file_shifts.pop(p, None)
        except Exception:
            pass
        try:
            self._file_enabled.pop(p, None)
        except Exception:
            pass
        try:
            self._file_timebase.pop(p, None)
        except Exception:
            pass

        # Keep selection near where the user was.
        try:
            next_index = min(i, max(0, len(self._file_paths) - 1))
        except Exception:
            next_index = 0
        self._refresh_files_listbox(select_index=next_index)
        self._handle_change()

    def _clear_extra_files(self) -> None:
        if not self._file_paths:
            return
        base = self._file_paths[0]
        self._file_paths = [base]
        self._file_shifts = {base: self._file_shifts.get(base, {"x_shift_s": 0.0, "y_shift": 0.0})}
        self._file_enabled = {base: bool(self._file_enabled.get(base, True))}
        self._file_timebase = {base: self._file_timebase.get(base, {"mode": "global"})}
        self._refresh_files_listbox(select_index=0)
        self._handle_change()

    def _clear_all_files(self) -> None:
        """Remove all overlay file entries (including the base entry).

        The plotter will fall back to the currently loaded CSV when the list is empty.
        """
        self._file_paths = []
        self._file_shifts = {}
        self._file_enabled = {}
        self._file_timebase = {}
        self._selected_file_path = None

        # Also clear Signals list so the UI reflects that no source files are selected.
        try:
            self.listbox.selection_clear(0, tk.END)
        except Exception:
            pass
        try:
            self.listbox.delete(0, tk.END)
        except Exception:
            pass
        try:
            self._x_shift_var.set("0")
            self._y_shift_var.set("0")
        except Exception:
            pass
        self._refresh_files_listbox(select_index=None)
        self._handle_change()

    def _toggle_selected_file_enabled(self) -> None:
        idxs = ()
        try:
            idxs = self._files_listbox.curselection()
        except Exception:
            idxs = ()
        if not idxs:
            return
        i = int(idxs[0])
        if i < 0 or i >= len(self._file_paths):
            return
        p = self._file_paths[i]
        ap = self._normalize_path(p)
        try:
            self._file_enabled[ap] = not bool(self._file_enabled.get(ap, True))
        except Exception:
            self._file_enabled[ap] = True
        self._refresh_files_listbox(select_index=i)
        self._handle_change()

    def _toggle_file_enabled_at_click(self, event) -> None:
        try:
            i = int(self._files_listbox.nearest(event.y))
        except Exception:
            return
        if i < 0 or i >= len(self._file_paths):
            return
        try:
            self._files_listbox.selection_clear(0, tk.END)
            self._files_listbox.selection_set(i)
        except Exception:
            pass
        self._toggle_selected_file_enabled()

    def _on_configure(self, event=None):
        try:
            w = int(getattr(event, "width", 0))
        except Exception:
            w = 0
        if w > 50:
            try:
                self._stats_label.configure(wraplength=w - 20)
            except Exception:
                pass

    def _handle_change(self, _event=None):
        if callable(self._on_change):
            self._on_change()

    def close(self):
        if callable(self._on_close):
            self._on_close(self)

    def select_all(self):
        self.listbox.select_set(0, tk.END)
        self._handle_change()

    def clear_selection(self):
        self.listbox.selection_clear(0, tk.END)
        self._handle_change()

    def get_selected_columns(self, all_columns=None):
        """Return selected signal names.

        Historically this mapped listbox indices into the provided `all_columns`.
        The Signals list can now be rebuilt dynamically (e.g., from overlay files),
        so the authoritative source is the listbox contents.
        """
        try:
            indices = self.listbox.curselection()
        except Exception:
            indices = ()

        out: list[str] = []
        for i in indices:
            try:
                out.append(str(self.listbox.get(i)))
            except Exception:
                continue
        return out

    def get_ylim_config(self) -> dict:
        return {
            "enabled": bool(self._use_ylim_var.get()),
            "ymin": self._ymin_var.get(),
            "ymax": self._ymax_var.get(),
        }

    def get_display_config(self) -> dict:
        return {
            "show_table": bool(self._show_table_var.get()),
            "show_hist": bool(self._show_hist_var.get()),
            "show_abs_check": bool(self._show_abs_check_var.get()),
            "show_rel_change": bool(self._show_rel_change_var.get()),
            "show_custom": bool(self._show_custom_var.get()),
            "hist_bins": self._hist_bins_var.get(),
        }

    def get_barrier_config(self) -> dict:
        # Stored as a two-kind object so ABS and REL can be configured independently.
        return {
            "abs": {
                "enabled": bool(self._barriers_enabled_var.get()),
                "target": self._bar_target_var.get(),
                "limit_in": self._bar_limit_in_var.get(),
                "limit_out": self._bar_limit_out_var.get(),
                "start_idx": self._bar_start_idx_var.get(),
                "end_idx": self._bar_end_idx_var.get(),
            },
            "rel": {
                "enabled": bool(self._rel_barriers_enabled_var.get()),
                "target": self._rel_bar_target_var.get(),
                "limit_in": self._rel_bar_limit_in_var.get(),
                "limit_out": self._rel_bar_limit_out_var.get(),
                "start_idx": self._rel_bar_start_idx_var.get(),
                "end_idx": self._rel_bar_end_idx_var.get(),
            },
        }

    def get_plot_mode(self) -> str:
        # Mode UI removed; keep behavior as normal time series.
        return "Time series"

    def set_plot_mode(self, mode: str | None) -> None:
        # Mode UI removed; ignore persisted mode values.
        self._plot_mode_var.set("Time series")

    def set_ylim_config(self, cfg: dict | None) -> None:
        if not isinstance(cfg, dict):
            return
        self._use_ylim_var.set(bool(cfg.get("enabled", False)))
        ymin = cfg.get("ymin", "")
        ymax = cfg.get("ymax", "")
        self._ymin_var.set("" if ymin is None else str(ymin))
        self._ymax_var.set("" if ymax is None else str(ymax))

    def set_display_config(self, cfg: dict | None) -> None:
        if not isinstance(cfg, dict):
            return
        if "show_table" in cfg:
            self._show_table_var.set(bool(cfg.get("show_table")))
        if "show_hist" in cfg:
            self._show_hist_var.set(bool(cfg.get("show_hist")))
        if "show_abs_check" in cfg:
            self._show_abs_check_var.set(bool(cfg.get("show_abs_check")))
        if "show_rel_change" in cfg:
            self._show_rel_change_var.set(bool(cfg.get("show_rel_change")))
        if "show_custom" in cfg:
            self._show_custom_var.set(bool(cfg.get("show_custom")))
        if "hist_bins" in cfg:
            v = cfg.get("hist_bins", "30")
            self._hist_bins_var.set("" if v is None else str(v))

    def _apply_custom_code(self) -> None:
        try:
            if getattr(self, "_custom_text", None) is not None:
                self._custom_code = str(self._custom_text.get("1.0", "end-1c"))
        except Exception:
            pass
        self._handle_change()

    def get_custom_code(self) -> str:
        try:
            # Ensure latest edits are captured.
            if getattr(self, "_custom_text", None) is not None:
                self._custom_code = str(self._custom_text.get("1.0", "end-1c"))
        except Exception:
            pass
        return str(getattr(self, "_custom_code", "") or "")

    def set_custom_code(self, code: str | None) -> None:
        self._custom_code = str(code or "")
        try:
            t = getattr(self, "_custom_text", None)
            if t is not None:
                t.delete("1.0", "end")
                t.insert("1.0", self._custom_code)
        except Exception:
            pass

    def set_barrier_config(self, cfg: dict | None) -> None:
        if not isinstance(cfg, dict):
            return
        # Backward-compatible: older layouts stored a flat dict with enabled/target/...
        # Newer layouts store {"abs": {...}, "rel": {...}}.
        def _apply_abs(d: dict) -> None:
            try:
                if "enabled" in d:
                    self._barriers_enabled_var.set(bool(d.get("enabled")))
                if "target" in d:
                    self._bar_target_var.set("" if d.get("target") is None else str(d.get("target")))
                if "limit_in" in d:
                    self._bar_limit_in_var.set("" if d.get("limit_in") is None else str(d.get("limit_in")))
                if "limit_out" in d:
                    self._bar_limit_out_var.set("" if d.get("limit_out") is None else str(d.get("limit_out")))
                if "start_idx" in d:
                    self._bar_start_idx_var.set("" if d.get("start_idx") is None else str(d.get("start_idx")))
                if "end_idx" in d:
                    self._bar_end_idx_var.set("" if d.get("end_idx") is None else str(d.get("end_idx")))
            except Exception:
                pass

        def _apply_rel(d: dict) -> None:
            try:
                if "enabled" in d:
                    self._rel_barriers_enabled_var.set(bool(d.get("enabled")))
                if "target" in d:
                    self._rel_bar_target_var.set("" if d.get("target") is None else str(d.get("target")))
                if "limit_in" in d:
                    self._rel_bar_limit_in_var.set("" if d.get("limit_in") is None else str(d.get("limit_in")))
                if "limit_out" in d:
                    self._rel_bar_limit_out_var.set("" if d.get("limit_out") is None else str(d.get("limit_out")))
                if "start_idx" in d:
                    self._rel_bar_start_idx_var.set("" if d.get("start_idx") is None else str(d.get("start_idx")))
                if "end_idx" in d:
                    self._rel_bar_end_idx_var.set("" if d.get("end_idx") is None else str(d.get("end_idx")))
            except Exception:
                pass

        try:
            if isinstance(cfg.get("abs"), dict) or isinstance(cfg.get("rel"), dict):
                if isinstance(cfg.get("abs"), dict):
                    _apply_abs(cfg.get("abs"))
                if isinstance(cfg.get("rel"), dict):
                    _apply_rel(cfg.get("rel"))
            else:
                # Old shape: apply to both.
                _apply_abs(cfg)
                _apply_rel(cfg)
        except Exception:
            pass

    def get_hist_bins(self) -> int:
        try:
            v = int(str(self._hist_bins_var.get() or "30").strip())
            if v <= 0:
                return 30
            # Keep it sane
            return max(1, min(500, v))
        except Exception:
            return 30

    def show_table_enabled(self) -> bool:
        return bool(self._show_table_var.get())

    def show_hist_enabled(self) -> bool:
        return bool(self._show_hist_var.get())

    def show_abs_check_enabled(self) -> bool:
        return bool(self._show_abs_check_var.get())

    def show_rel_change_enabled(self) -> bool:
        return bool(self._show_rel_change_var.get())

    def show_custom_enabled(self) -> bool:
        return bool(self._show_custom_var.get())

    def set_x_window(self, xmin: float, xmax: float, *, duration_text: str | None = None) -> None:
        lo = float(min(xmin, xmax))
        hi = float(max(xmin, xmax))
        self._x_window = (lo, hi)
        if duration_text:
            self._window_var.set(f"Window: {lo:.3f} .. {hi:.3f}  (Δ {duration_text})")
        else:
            self._window_var.set(f"Window: {lo:.3f} .. {hi:.3f}")

    def clear_x_window(self) -> None:
        self._x_window = None
        self._window_var.set("Window: ALL")
        self._handle_change()

    def get_x_window(self) -> tuple[float, float] | None:
        return self._x_window

    def set_stats_text(self, text: str) -> None:
        self._stats_var.set(text or "")

    def set_selected_columns(self, selected: list[str]) -> None:
        selected_set = set(str(s) for s in selected)
        self.listbox.selection_clear(0, tk.END)
        for i in range(self.listbox.size()):
            name = self.listbox.get(i)
            if name in selected_set:
                self.listbox.selection_set(i)
        self._handle_change()

    def deselect_column(self, name: str) -> bool:
        """Remove a single column from the current selection (if present)."""
        for i in range(self.listbox.size()):
            if self.listbox.get(i) == name:
                try:
                    self.listbox.selection_clear(i)
                except Exception:
                    self.listbox.selection_clear(0, tk.END)
                self._handle_change()
                return True
        return False

    # ---- New helper methods ----

    def _on_listbox_select(self, _event=None) -> None:
        """Update signal count and forward change event."""
        self._update_signal_count()
        self._handle_change(_event)

    def _update_signal_count(self) -> None:
        """Refresh the 'N / M signals' label."""
        try:
            total = self.listbox.size()
            selected = len(self.listbox.curselection())
            self._signal_count_var.set(f"{selected} / {total} signals")
        except Exception:
            pass

    def _apply_search_filter(self) -> None:
        """Filter the Signals listbox to show only columns matching the search text."""
        query = str(self._search_var.get() or "").strip().lower()
        # Remember current selection by name
        try:
            old_sel = set(self.listbox.get(i) for i in self.listbox.curselection())
        except Exception:
            old_sel = set()

        self.listbox.delete(0, tk.END)
        for col in self._all_columns:
            if query and query not in str(col).lower():
                continue
            self.listbox.insert(tk.END, str(col))

        # Restore selection for items still visible
        if old_sel:
            for i in range(self.listbox.size()):
                if self.listbox.get(i) in old_sel:
                    self.listbox.selection_set(i)

        self._update_signal_count()

    def invert_selection(self) -> None:
        """Toggle selection state for every item in the Signals listbox."""
        try:
            current = set(self.listbox.curselection())
            self.listbox.selection_clear(0, tk.END)
            for i in range(self.listbox.size()):
                if i not in current:
                    self.listbox.selection_set(i)
        except Exception:
            pass
        self._update_signal_count()
        self._handle_change()

    def _duplicate_clicked(self) -> None:
        """Request duplication of this subplot."""
        if callable(self._on_duplicate):
            self._on_duplicate(self)

    def get_full_config(self) -> dict:
        """Return a serializable snapshot of all selector settings (for duplication)."""
        return {
            "selected_columns": self.get_selected_columns(),
            "ylim": self.get_ylim_config(),
            "display": self.get_display_config(),
            "x_window": self.get_x_window(),
            "barriers": self.get_barrier_config(),
            "plot_mode": self.get_plot_mode(),
            "files": self.get_files(),
            "x_alignment": self.get_x_alignment_mode(),
            "file_shifts": self.get_file_shifts(),
            "file_enabled": self.get_file_enabled() if hasattr(self, "get_file_enabled") else {},
            "file_timebase": self.get_file_timebase() if hasattr(self, "get_file_timebase") else {},
            "custom_code": self.get_custom_code(),
        }

    def apply_full_config(self, cfg: dict) -> None:
        """Restore selector settings from a config dict (for duplication)."""
        if not isinstance(cfg, dict):
            return
        try:
            self.set_ylim_config(cfg.get("ylim"))
        except Exception:
            pass
        try:
            self.set_display_config(cfg.get("display"))
        except Exception:
            pass
        try:
            self.set_plot_mode(cfg.get("plot_mode"))
        except Exception:
            pass
        try:
            xwin = cfg.get("x_window")
            if isinstance(xwin, (list, tuple)) and len(xwin) == 2:
                self.set_x_window(float(xwin[0]), float(xwin[1]))
        except Exception:
            pass
        try:
            self.set_barrier_config(cfg.get("barriers"))
        except Exception:
            pass
        try:
            files = cfg.get("files")
            if isinstance(files, list) and files:
                self.set_files(files)
        except Exception:
            pass
        try:
            self.set_x_alignment_mode(cfg.get("x_alignment"))
        except Exception:
            pass
        try:
            self.set_file_shifts(cfg.get("file_shifts"))
        except Exception:
            pass
        try:
            if hasattr(self, "set_file_enabled"):
                self.set_file_enabled(cfg.get("file_enabled"))
        except Exception:
            pass
        try:
            if hasattr(self, "set_file_timebase"):
                self.set_file_timebase(cfg.get("file_timebase"))
        except Exception:
            pass
        try:
            self.set_custom_code(cfg.get("custom_code"))
        except Exception:
            pass
        try:
            selected = cfg.get("selected_columns", [])
            if isinstance(selected, list):
                self.set_selected_columns([str(x) for x in selected])
        except Exception:
            pass
