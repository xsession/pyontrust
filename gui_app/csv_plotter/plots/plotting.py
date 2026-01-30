import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib.widgets import SpanSelector

from .plot_histogram import render_histogram
from .plot_main import build_main_plot
from .plot_stats_table import render_stats_table
from .plot_abs_check import render_abs_check
from .plot_rel_change import render_rel_change
from .plot_custom_code import render_custom_code


def plot_all(app) -> None:
    # Capture current subplot-height sash positions before we destroy the old UI.
    try:
        prev = getattr(app, "plots_pane", None)
        if prev is not None and hasattr(prev, "panes") and hasattr(prev, "sashpos"):
            try:
                panes = list(prev.panes())
            except Exception:
                panes = []
            coords: list[int] = []
            for i in range(max(0, len(panes) - 1)):
                try:
                    coords.append(int(prev.sashpos(i)))
                except Exception:
                    continue
            if coords:
                app._plots_pane_sashes_last = list(coords)
    except Exception:
        pass

    # Clear previous plots
    for child in app.plot_area.winfo_children():
        child.destroy()
    app.plots_pane = ttk.Panedwindow(app.plot_area, orient=tk.VERTICAL)
    app.plots_pane.pack(fill=tk.BOTH, expand=True)

    # Auto-save when user adjusts subplot-height sashes.
    # NOTE: ttk.Panedwindow doesn't reliably receive mouse events from its sash,
    # so bind at the toplevel and filter for events within plots_pane.
    try:
        if not bool(getattr(app, "_plots_pane_autosave_bound", False)):
            app._plots_pane_autosave_bound = True

            def _is_descendant(widget, ancestor) -> bool:
                try:
                    w = widget
                    while w is not None:
                        if w is ancestor:
                            return True
                        name = w.winfo_parent()
                        if not name:
                            break
                        w = w.nametowidget(name)
                except Exception:
                    return False
                return False

            def _maybe_autosave_plots_pane(_e=None) -> None:
                try:
                    pane = getattr(app, "plots_pane", None)
                    if pane is None:
                        return
                    evw = getattr(_e, "widget", None)
                    if evw is None:
                        return
                    if not _is_descendant(evw, pane):
                        return
                    # Let geometry settle so sashpos reads correctly.
                    try:
                        app.root.after(80, lambda: getattr(app, "_schedule_autosave", lambda *_a, **_k: None)())
                    except Exception:
                        getattr(app, "_schedule_autosave", lambda *_a, **_k: None)()
                except Exception:
                    pass

            app.root.bind_all("<ButtonRelease-1>", _maybe_autosave_plots_pane, add="+")
    except Exception:
        pass
    app.plot_canvases.clear()
    app._span_selectors.clear()

    # Disconnect old axes and handlers
    app.all_axes.clear()

    for i, selector in enumerate(app.subplots):
        main = build_main_plot(app, selector, i)
        fig = main.fig
        axes_for_events = main.axes_for_events
        selected_columns = main.selected_columns
        stats_rows = main.stats_rows
        do_span = main.do_span
        do_sync_xlim = main.do_sync_xlim

        # Theme the plot to match the app (Light/Dark)
        try:
            app._apply_mpl_theme(fig, axes_for_events)
        except Exception:
            pass

        # Xlim sync only for time-based single-axis modes
        if do_sync_xlim and axes_for_events:
            try:
                axes_for_events[0].callbacks.connect(
                    'xlim_changed', lambda evt, a=axes_for_events[0]: app.on_xlim_changed(a)
                )
                app.all_axes.append(axes_for_events[0])
            except Exception:
                pass

        pane_frame = ttk.Frame(app.plots_pane)
        pane_frame.pack(fill=tk.BOTH, expand=True)
        app.plots_pane.add(pane_frame, weight=1)

        show_hist = bool(selector.show_hist_enabled() and "Timestamp" in app.df.columns and selected_columns)
        show_table = bool(selector.show_table_enabled())
        show_abs = bool(getattr(selector, "show_abs_check_enabled", lambda: False)() and selected_columns)
        show_rel = bool(getattr(selector, "show_rel_change_enabled", lambda: False)() and selected_columns)
        show_custom = bool(getattr(selector, "show_custom_enabled", lambda: False)() and selected_columns)

        plot_container = None
        if show_hist or show_table or show_abs or show_rel or show_custom:
            # Resizable separator between the plot and bottom area (hist/table)
            plot_split = ttk.Panedwindow(pane_frame, orient=tk.VERTICAL)
            plot_split.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            # Auto-save when user adjusts plot/bottom sash.
            try:
                plot_split.bind("<ButtonRelease-1>", lambda _e: getattr(app, "_schedule_autosave", lambda: None)(), add="+")
            except Exception:
                pass

            # Allow layout persistence of the plot/bottom sash.
            try:
                if hasattr(selector, "_bind_plot_split"):
                    selector._bind_plot_split(plot_split)
            except Exception:
                pass

            # If no restored sash position exists, use a stable default ratio
            # (main plot gets most of the height).
            try:
                have_saved = False
                if hasattr(selector, "get_plot_split_sashpos"):
                    have_saved = selector.get_plot_split_sashpos() is not None
                if not have_saved and hasattr(plot_split, "sashpos"):
                    def _default_plot_split() -> None:
                        try:
                            h = int(pane_frame.winfo_height())
                        except Exception:
                            h = 0
                        if h > 200:
                            try:
                                plot_split.sashpos(0, int(h * 0.72))
                            except Exception:
                                pass

                    try:
                        app.root.after(0, _default_plot_split)
                        app.root.after(120, _default_plot_split)
                    except Exception:
                        _default_plot_split()
            except Exception:
                pass

            plot_container = ttk.Frame(plot_split)
            bottom_container = ttk.Frame(plot_split)
            try:
                plot_split.add(plot_container, weight=4, minsize=160)
            except Exception:
                plot_split.add(plot_container, weight=4)
            try:
                plot_split.add(bottom_container, weight=1, minsize=90)
            except Exception:
                plot_split.add(bottom_container, weight=1)

            # Bottom area: make each enabled bottom plot resizable via sashes.
            bottom_outer = ttk.Frame(bottom_container)
            bottom_outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))

            bottom_pane = ttk.Panedwindow(bottom_outer, orient=tk.VERTICAL)
            bottom_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            bottom_order: list[str] = []
            bottom_targets: dict[str, ttk.Frame] = {}

            def _add_bottom(key: str) -> None:
                f = ttk.Frame(bottom_pane)
                try:
                    bottom_pane.add(f, weight=1, minsize=50)
                except Exception:
                    bottom_pane.add(f, weight=1)
                bottom_order.append(key)
                bottom_targets[key] = f

            if show_hist:
                _add_bottom("hist")
            if show_abs:
                _add_bottom("abs")
            if show_rel:
                _add_bottom("rel")
            if show_custom:
                _add_bottom("custom")
            if show_table:
                _add_bottom("table")

            try:
                if hasattr(selector, "_bind_bottom_pane"):
                    selector._bind_bottom_pane(bottom_pane, bottom_order)
            except Exception:
                pass

            # If no restored bottom-pane sash state exists, distribute equally.
            try:
                have_saved = False
                st = getattr(selector, "_bottom_pane_state", None)
                if isinstance(st, dict):
                    try:
                        want_order = st.get("order")
                        want_sashes = st.get("sashpos")
                    except Exception:
                        want_order = None
                        want_sashes = None
                    if isinstance(want_order, list) and isinstance(want_sashes, list):
                        if [str(x) for x in want_order] == [str(x) for x in bottom_order] and len(want_sashes) == max(0, len(bottom_order) - 1):
                            # Require at least one meaningful (non-zero) sashpos to consider it restored.
                            try:
                                have_saved = any(int(v) > 0 for v in want_sashes)
                            except Exception:
                                have_saved = True

                if (not have_saved) and len(bottom_order) > 1 and hasattr(bottom_pane, "sashpos"):
                    def _default_bottom_split() -> None:
                        try:
                            h = int(bottom_outer.winfo_height())
                        except Exception:
                            h = 0
                        if h <= 120:
                            return
                        n = int(len(bottom_order))
                        for si in range(max(0, n - 1)):
                            try:
                                bottom_pane.sashpos(si, int(h * (si + 1) / n))
                            except Exception:
                                pass

                    try:
                        app.root.after(0, _default_bottom_split)
                        app.root.after(120, _default_bottom_split)
                        app.root.after(250, _default_bottom_split)
                    except Exception:
                        _default_bottom_split()
            except Exception:
                pass

            # Auto-save when the user adjusts bottom plot sashes.
            try:
                def _autosave_bottom_sashes(_e=None) -> None:
                    try:
                        # Ensure selector state is updated before saving.
                        if hasattr(selector, "get_bottom_pane_state"):
                            selector.get_bottom_pane_state()
                    except Exception:
                        pass
                    try:
                        if hasattr(app, "_schedule_autosave"):
                            app._schedule_autosave()  # type: ignore[attr-defined]
                    except Exception:
                        pass

                bottom_pane.bind("<ButtonRelease-1>", _autosave_bottom_sashes, add="+")
            except Exception:
                pass
        
        # Create canvas in the actual container it will be packed into.
        canvas_parent = plot_container if plot_container is not None else pane_frame
        canvas = FigureCanvasTkAgg(fig, master=canvas_parent)
        canvas.draw()

        # Matplotlib toolbar provides zoom/pan
        toolbar = NavigationToolbar2Tk(canvas, pane_frame)
        toolbar.update()
        toolbar.pack(side=tk.TOP, fill=tk.X)
        # Keep a reference so we can disable zoom/pan during span selection.
        try:
            canvas._csv_toolbar = toolbar
        except Exception:
            pass

        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        if plot_container is not None:
            if show_hist:
                render_histogram(app, selector, bottom_targets.get("hist"), selected_columns)
            if show_abs:
                render_abs_check(app, selector, bottom_targets.get("abs"), selected_columns)
            if show_rel:
                render_rel_change(app, selector, bottom_targets.get("rel"), selected_columns)
            if show_custom:
                render_custom_code(app, selector, bottom_targets.get("custom"), selected_columns)
            if show_table:
                render_stats_table(app, bottom_targets.get("table"), stats_rows)
        app.plot_canvases.append(canvas)

        # Click-to-highlight on lines + legend entry
        for a in (axes_for_events or []):
            canvas.mpl_connect('pick_event', lambda evt, aa=a, c=canvas: app._on_pick(evt, aa, c))
            canvas.mpl_connect('button_press_event', lambda evt, aa=a, c=canvas: app._on_button_press(evt, aa, c))

        # Drag-select a time window on the main plot
        if do_span and axes_for_events:
            try:
                main_ax = axes_for_events[0]
                span = SpanSelector(
                    main_ax,
                    lambda xmin, xmax, sel=selector: app._on_span_selected(sel, xmin, xmax),
                    direction='horizontal',
                    useblit=False,
                    interactive=True,
                    button=1,
                )
                try:
                    main_ax._csv_span = span
                except Exception:
                    pass
                app._span_selectors.append(span)
            except Exception:
                pass

    # Restore plots pane sash positions (prefer loaded layout, else last-known).
    try:
        sashes = getattr(app, "_pending_plots_pane_sashes", None)
        if not isinstance(sashes, list):
            sashes = getattr(app, "_plots_pane_sashes_last", None)

        if isinstance(sashes, list) and getattr(app, "plots_pane", None) is not None:
            def _apply_once() -> None:
                for idx, pos in enumerate(sashes):
                    try:
                        app.plots_pane.sashpos(idx, int(pos))
                    except Exception:
                        continue

            try:
                app.root.after(0, _apply_once)
                app.root.after(120, _apply_once)
                app.root.after(250, _apply_once)
            except Exception:
                _apply_once()

            try:
                app._pending_plots_pane_sashes = None
            except Exception:
                pass
    except Exception:
        pass

    # If no saved sash state exists at all, distribute subplots equally.
    try:
        if (
            not isinstance(getattr(app, "_pending_plots_pane_sashes", None), list)
            and not isinstance(getattr(app, "_plots_pane_sashes_last", None), list)
            and getattr(app, "plots_pane", None) is not None
        ):
            def _default_subplot_splits() -> None:
                try:
                    p = app.plots_pane
                    panes = list(p.panes())
                    n = int(len(panes))
                    if n <= 1:
                        return
                    h = int(p.winfo_height())
                except Exception:
                    return
                if h <= 200:
                    return
                for i in range(n - 1):
                    try:
                        p.sashpos(i, int(h * (i + 1) / n))
                    except Exception:
                        pass

            try:
                app.root.after(0, _default_subplot_splits)
                app.root.after(150, _default_subplot_splits)
            except Exception:
                _default_subplot_splits()
    except Exception:
        pass
