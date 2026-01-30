import os

import tkinter as tk
from tkinter import ttk


class SubplotSelector:
    def __init__(self, parent, columns, subplot_id, *, on_change=None, on_close=None, on_add_files=None):
        self.frame = ttk.LabelFrame(parent, text=f"Subplot {subplot_id}")
        self._on_change = on_change
        self._on_close = on_close
        self._on_add_files = on_add_files

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
        self._selected_file_path: str | None = None
        self._x_shift_var = tk.StringVar(value="0")
        self._y_shift_var = tk.StringVar(value="0")

        btn_row = ttk.Frame(self.frame)
        btn_row.pack(fill='x', padx=5, pady=(5, 0))
        ttk.Button(btn_row, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Clear", command=self.clear_selection).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Close", command=self.close).pack(side=tk.RIGHT, padx=2)

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
        ttk.Button(overlay_row, text="Remove", command=self._remove_selected_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(overlay_row, text="Clear", command=self._clear_extra_files).pack(side=tk.LEFT, padx=2)

        files_frame = ttk.Frame(overlay_box)
        files_frame.pack(fill='x', padx=5, pady=(2, 0))

        self._files_listbox = tk.Listbox(files_frame, selectmode=tk.SINGLE, height=2, exportselection=False)
        self._files_listbox.pack(side=tk.LEFT, fill='x', expand=True)
        self._files_listbox.bind("<<ListboxSelect>>", self._on_file_selected)
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

        # EXTENDED enables Shift-click range selection and Ctrl-click toggling
        self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=6, exportselection=False)
        for col in columns:
            self.listbox.insert(tk.END, col)
        self.listbox.pack(fill='both', expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._handle_change)

        self._stats_label = ttk.Label(stats_frame, textvariable=self._stats_var, justify='left', anchor='w')
        self._stats_label.pack(fill='both', expand=True)

        try:
            self._inner_split.add(list_frame, minsize=140)
            self._inner_split.add(stats_frame, minsize=40)
        except Exception:
            # Last-resort: if add fails, fall back to stacking without a sash
            list_frame.pack(fill='both', expand=True)
            stats_frame.pack(fill='x')

        self.frame.bind("<Configure>", self._on_configure)

        # Persisted UI positions
        self._plot_split_sashpos: int | None = None
        self._plot_split = None

        # Bottom area internal splitter (between bottom plots)
        self._bottom_pane = None
        self._bottom_pane_state: dict | None = None

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
        def _apply():
            try:
                self.frame.update_idletasks()
            except Exception:
                pass
            try:
                paned.sash_place(0, x, y)
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

    def set_files(self, paths: list[str] | None) -> None:
        self._file_paths = []
        self._file_shifts = {}
        if isinstance(paths, list):
            for p in paths:
                ap = self._normalize_path(p)
                if ap and ap not in self._file_paths:
                    self._file_paths.append(ap)
                    self._file_shifts.setdefault(ap, {"x_shift_s": 0.0, "y_shift": 0.0})
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
        self._refresh_files_listbox(select_index=0)
        self._handle_change()

    def get_files(self) -> list[str]:
        return list(self._file_paths)

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
            self._files_listbox.insert(tk.END, f"{prefix}{base}")
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
        # Keep base file always present
        if i == 0:
            return
        if i < 0 or i >= len(self._file_paths):
            return
        p = self._file_paths.pop(i)
        try:
            self._file_shifts.pop(p, None)
        except Exception:
            pass
        self._refresh_files_listbox(select_index=0)
        self._handle_change()

    def _clear_extra_files(self) -> None:
        if not self._file_paths:
            return
        base = self._file_paths[0]
        self._file_paths = [base]
        self._file_shifts = {base: self._file_shifts.get(base, {"x_shift_s": 0.0, "y_shift": 0.0})}
        self._refresh_files_listbox(select_index=0)
        self._handle_change()

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

    def get_selected_columns(self, all_columns):
        indices = self.listbox.curselection()
        return [all_columns[i] for i in indices]

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
