from __future__ import annotations

import tkinter as tk

from lang import t


def build_menu(app) -> None:
    menubar = tk.Menu(app.root)

    # ── File ──
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label=t(app, "menu.file.add_new_file"), command=app.choose_file, accelerator="Ctrl+O")
    file_menu.add_command(label=t(app, "menu.file.open_folder"), command=app.open_folder_load_all, accelerator="Ctrl+Shift+O")
    file_menu.add_separator()

    # Recent files submenu (populated dynamically)
    recent_menu = tk.Menu(file_menu, tearoff=0)
    try:
        recent_menu.configure(postcommand=lambda m=recent_menu: _populate_recent_files(app, m))
    except Exception:
        pass
    file_menu.add_cascade(label=t(app, "menu.file.recent", default="Recent files"), menu=recent_menu)
    file_menu.add_separator()
    file_menu.add_command(label=t(app, "menu.file.reload", default="Reload current file"), command=lambda: _reload_current(app), accelerator="F5")
    menubar.add_cascade(label=t(app, "menu.file"), menu=file_menu)

    # ── History ──
    history_menu = tk.Menu(menubar, tearoff=0)
    try:
        history_menu.configure(postcommand=lambda m=history_menu: app._populate_history_menu(m))
    except Exception:
        pass
    menubar.add_cascade(label=t(app, "menu.history"), menu=history_menu)

    # ── View ──
    view_menu = tk.Menu(menubar, tearoff=0)
    view_menu.add_command(
        label=t(app, "menu.view.toggle_plots", default="Toggle plots pane"),
        command=lambda: _toggle_plots_pane(app),
        accelerator="Ctrl+P",
    )
    view_menu.add_command(
        label=t(app, "menu.view.add_subplot", default="Add subplot"),
        command=app.add_subplot,
        accelerator="Ctrl+N",
    )
    view_menu.add_command(
        label=t(app, "menu.view.plot_all", default="Plot all"),
        command=app.plot_all,
        accelerator="Ctrl+R",
    )
    view_menu.add_separator()
    view_menu.add_command(
        label=t(app, "menu.view.clear_highlights", default="Clear highlights"),
        command=lambda: _safe_call(app, "clear_highlights"),
    )
    view_menu.add_command(
        label=t(app, "menu.view.zoom_fit", default="Zoom to fit (all subplots)"),
        command=lambda: _zoom_fit_all(app),
        accelerator="Ctrl+0",
    )
    menubar.add_cascade(label=t(app, "menu.view", default="View"), menu=view_menu)

    # ── Settings ──
    settings_menu = tk.Menu(menubar, tearoff=0)
    settings_menu.add_command(label=t(app, "menu.settings.open"), command=app.show_settings)
    menubar.add_cascade(label=t(app, "menu.settings"), menu=settings_menu)

    # ── Layout ──
    layout_menu = tk.Menu(menubar, tearoff=0)
    layout_menu.add_command(label=t(app, "menu.layout.save"), command=app.save_layout, accelerator="Ctrl+S")
    layout_menu.add_command(label=t(app, "menu.layout.load"), command=app.load_layout, accelerator="Ctrl+L")
    layout_menu.add_separator()
    layout_menu.add_command(label=t(app, "menu.layout.clear"), command=app.clear_layout)
    menubar.add_cascade(label=t(app, "menu.layout"), menu=layout_menu)

    # ── Export ──
    export_menu = tk.Menu(menubar, tearoff=0)
    export_menu.add_command(label=t(app, "menu.export.png"), command=getattr(app, "export_plots_png", lambda: None))
    export_menu.add_command(label=t(app, "menu.export.svg"), command=getattr(app, "export_plots_svg", lambda: None))
    export_menu.add_separator()
    export_menu.add_command(
        label=t(app, "menu.export.combined_png"),
        command=getattr(app, "export_plots_combined_png", lambda: None),
    )
    export_menu.add_command(
        label=t(app, "menu.export.combined_svg"),
        command=getattr(app, "export_plots_combined_svg", lambda: None),
    )
    export_menu.add_separator()
    export_menu.add_command(
        label=t(app, "menu.export.perspective"),
        command=getattr(app, "open_perspective_view", lambda: None),
    )
    menubar.add_cascade(label=t(app, "menu.export"), menu=export_menu)

    # ── Help ──
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(
        label=t(app, "menu.help.user_guide", default="User guide"),
        command=getattr(app, "open_user_guide", lambda: None),
    )
    help_menu.add_command(
        label=t(app, "menu.help.developer_guide", default="Developer guide"),
        command=getattr(app, "open_developer_guide", lambda: None),
    )
    help_menu.add_command(
        label=t(app, "menu.help.open_docs_folder", default="Open docs folder"),
        command=getattr(app, "open_docs_folder", lambda: None),
    )
    help_menu.add_separator()
    help_menu.add_command(label=t(app, "menu.help.help"), command=app.show_help, accelerator="F1")
    help_menu.add_command(label=t(app, "menu.help.about"), command=app.show_about)
    menubar.add_cascade(label=t(app, "menu.help"), menu=help_menu)

    app.root.config(menu=menubar)

    # ── Bind keyboard accelerators ──
    try:
        app.root.bind_all("<F5>", lambda _e: _reload_current(app))
        app.root.bind_all("<F1>", lambda _e: app.show_help())
        app.root.bind_all("<Control-Key-0>", lambda _e: _zoom_fit_all(app))
    except Exception:
        pass


# ── Helper functions ──

def _safe_call(app, method_name: str) -> None:
    fn = getattr(app, method_name, None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


def _reload_current(app) -> None:
    """Force reload the currently loaded CSV."""
    try:
        path = getattr(app, "last_loaded_file", None) or getattr(app, "file_path", "")
        if isinstance(path, str) and path:
            app.load_file(path)
            app.status_var.set(f"Reloaded: {path}")
    except Exception:
        pass


def _toggle_plots_pane(app) -> None:
    """Show/hide the plots (right) pane."""
    try:
        if hasattr(app, "_set_plots_visible"):
            visible = getattr(app, "_plots_visible", True)
            app._set_plots_visible(not visible)
    except Exception:
        pass


def _zoom_fit_all(app) -> None:
    """Reset all subplots to full data range."""
    try:
        for s in list(getattr(app, "subplots", []) or []):
            try:
                s.clear_x_window()
            except Exception:
                pass
        for ax in list(getattr(app, "all_axes", []) or []):
            try:
                ax.relim()
                ax.autoscale(enable=True, axis="both")
                ax.autoscale_view()
            except Exception:
                pass
        for c in list(getattr(app, "plot_canvases", []) or []):
            try:
                c.draw_idle()
            except Exception:
                pass
        app.request_replot()
    except Exception:
        pass


def _populate_recent_files(app, menu: tk.Menu) -> None:
    """Populate the Recent Files submenu from file history."""
    try:
        menu.delete(0, tk.END)
    except Exception:
        return
    history = list(getattr(app, "file_history", []) or [])
    if not history:
        menu.add_command(label="(no recent files)", state=tk.DISABLED)
        return
    for path in history[:15]:
        try:
            import os
            label = os.path.basename(str(path))
            menu.add_command(label=label, command=lambda p=path: app.open_history_path(str(p)))
        except Exception:
            continue
    if history:
        menu.add_separator()
        menu.add_command(label="Clear recent files", command=lambda: _safe_call(app, "clear_file_history"))
