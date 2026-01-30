import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from matplotlib.widgets import SpanSelector

from plot_histogram import render_histogram
from plot_main import build_main_plot
from plot_stats_table import render_stats_table
from plot_checks import render_abs_check, render_rel_change


def plot_all(app) -> None:
    # Clear previous plots
    for child in app.plot_area.winfo_children():
        child.destroy()
    app.plots_pane = ttk.Panedwindow(app.plot_area, orient=tk.VERTICAL)
    app.plots_pane.pack(fill=tk.BOTH, expand=True)
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

        plot_container = None
        if show_hist or show_table or show_abs or show_rel:
            # Resizable separator between the plot and bottom area (hist/table)
            plot_split = ttk.Panedwindow(pane_frame, orient=tk.VERTICAL)
            plot_split.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

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

            bottom_area = ttk.Frame(bottom_container)
            bottom_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(2, 6))
        
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
                render_histogram(app, selector, bottom_area, selected_columns)
            if show_abs:
                render_abs_check(app, selector, bottom_area, selected_columns)
            if show_rel:
                render_rel_change(app, selector, bottom_area, selected_columns)
            if show_table:
                render_stats_table(app, bottom_area, stats_rows)
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
