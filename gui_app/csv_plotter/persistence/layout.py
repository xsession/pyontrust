import json
import os
from pathlib import Path

from tkinter import filedialog, messagebox

from data import find_newest_csv


def default_layout_path(script_file: str | None) -> str:
    """Return default layout.json path next to the script."""
    try:
        base = Path(script_file).resolve().parent if script_file else Path.cwd()
    except Exception:
        base = Path.cwd()
    return str(base / "layout.json")


def build_layout_data(app) -> dict:
    if not hasattr(app, "df"):
        raise RuntimeError("No CSV loaded yet")

    # UI splitter positions (manual sash adjustments)
    ui_sashes: dict = {}
    try:
        if hasattr(app, "_capture_ui_sashes"):
            ui_sashes = app._capture_ui_sashes()  # type: ignore[attr-defined]
    except Exception:
        ui_sashes = {}

    return {
        "version": 2,
        "highlighted_channels": sorted([str(x) for x in (getattr(app, "_highlighted_channels", None) or [])]),
        "ui_theme": str(getattr(app, "ui_theme_var", None).get() if hasattr(app, "ui_theme_var") else "dark"),
        "current_folder": app.current_folder,
        "auto_load_newest": bool(app.auto_check_enabled.get()),
        "auto_reload_selected": bool(app.auto_reload_selected_enabled.get()),
        "auto_save_layout": bool(app.auto_save_layout_enabled.get()),
        "open_folder_recursive": bool(getattr(app, "open_folder_recursive_enabled", None).get() if hasattr(app, "open_folder_recursive_enabled") else False),
        "last_loaded_file": app.last_loaded_file,
        "ui": {
            "sashes": ui_sashes,
        },
        "subplots": [
            {
                "selected_columns": s.get_selected_columns(list(app.df.columns)),
                "ylim": s.get_ylim_config(),
                "display": s.get_display_config(),
                "x_window": s.get_x_window() if hasattr(s, "get_x_window") else None,
                "barriers": s.get_barrier_config() if hasattr(s, "get_barrier_config") else {},
                "plot_mode": s.get_plot_mode(),
                "files": s.get_files(),
                "x_alignment": s.get_x_alignment_mode(),
                "file_shifts": s.get_file_shifts(),
                "ui": {
                    "inner_split": s.get_inner_split_sash() if hasattr(s, "get_inner_split_sash") else None,
                    "plot_split": s.get_plot_split_sashpos() if hasattr(s, "get_plot_split_sashpos") else None,
                    "bottom_pane": s.get_bottom_pane_state() if hasattr(s, "get_bottom_pane_state") else None,
                },
            }
            for s in app.subplots
        ],
    }


def apply_layout_subplots(app, data: dict) -> None:
    """Apply subplot definitions/UI state from a loaded layout dict.

    Assumes the CSV is already loaded (so selectors/columns are meaningful).
    """
    ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
    ui_sashes = ui.get("sashes") if isinstance(ui.get("sashes"), dict) else {}

    subplots = data.get("subplots", [])
    if not isinstance(subplots, list) or not subplots:
        try:
            if hasattr(app, "_set_pending_ui_sashes"):
                app._set_pending_ui_sashes(ui_sashes)  # type: ignore[attr-defined]
        except Exception:
            pass
        return

    app._clear_subplots()
    for s in subplots:
        app.add_subplot()
        if not isinstance(s, dict):
            continue

        selected = s.get("selected_columns", [])
        if isinstance(selected, list):
            app.subplots[-1].set_selected_columns([str(x) for x in selected])

        app.subplots[-1].set_ylim_config(s.get("ylim"))
        app.subplots[-1].set_display_config(s.get("display"))
        app.subplots[-1].set_plot_mode(s.get("plot_mode"))

        try:
            xwin = s.get("x_window")
            if isinstance(xwin, (list, tuple)) and len(xwin) == 2:
                app.subplots[-1].set_x_window(float(xwin[0]), float(xwin[1]))
            else:
                app.subplots[-1].clear_x_window()
        except Exception:
            pass

        try:
            if hasattr(app.subplots[-1], "set_barrier_config"):
                app.subplots[-1].set_barrier_config(s.get("barriers"))
        except Exception:
            pass

        try:
            files = s.get("files")
            # Preserve original behavior: keep the currently loaded file as
            # the base file and merge layout-stored overlays on top.
            if isinstance(files, list) and files:
                base = os.path.abspath(app.last_loaded_file) if isinstance(app.last_loaded_file, str) and app.last_loaded_file else None
                merged: list[str] = []
                if base:
                    merged.append(base)
                for p in files:
                    if not isinstance(p, str):
                        continue
                    ap = os.path.abspath(p)
                    if base and ap == base:
                        continue
                    merged.append(ap)
                app.subplots[-1].set_files(merged)
            else:
                if isinstance(app.last_loaded_file, str) and app.last_loaded_file:
                    app.subplots[-1].set_files([app.last_loaded_file])
        except Exception:
            pass

        try:
            app.subplots[-1].set_x_alignment_mode(s.get("x_alignment"))
        except Exception:
            pass

        try:
            app.subplots[-1].set_file_shifts(s.get("file_shifts"))
        except Exception:
            pass

        # Per-subplot UI positions
        try:
            su = s.get("ui") if isinstance(s.get("ui"), dict) else {}
            inner = su.get("inner_split")
            if isinstance(inner, dict) and hasattr(app.subplots[-1], "set_inner_split_sash"):
                app.subplots[-1].set_inner_split_sash(inner)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            su = s.get("ui") if isinstance(s.get("ui"), dict) else {}
            ps = su.get("plot_split")
            if ps is not None and hasattr(app.subplots[-1], "set_plot_split_sashpos"):
                app.subplots[-1].set_plot_split_sashpos(ps)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            su = s.get("ui") if isinstance(s.get("ui"), dict) else {}
            bp = su.get("bottom_pane")
            if isinstance(bp, dict) and hasattr(app.subplots[-1], "set_bottom_pane_state"):
                app.subplots[-1].set_bottom_pane_state(bp)  # type: ignore[attr-defined]
        except Exception:
            pass

    try:
        if hasattr(app, "_set_pending_ui_sashes"):
            app._set_pending_ui_sashes(ui_sashes)  # type: ignore[attr-defined]
    except Exception:
        pass


def write_layout_json_atomic(path: str, data: dict) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        tmp.replace(p)
    except Exception:
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def save_layout_dialog(app, *, initialfile: str = "layout.json") -> None:
    if not hasattr(app, "df"):
        messagebox.showerror("Error", "No CSV loaded yet.")
        return

    path = filedialog.asksaveasfilename(
        initialfile=initialfile,
        initialdir=str(Path(app._default_layout_path()).parent),
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        title="Save layout",
    )
    if not path:
        return

    data = build_layout_data(app)

    try:
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        app.status_var.set(f"Layout saved: {os.path.basename(path)}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save layout:\n{e}")


def load_layout_dialog(app) -> None:
    path = filedialog.askopenfilename(
        initialdir=str(Path(app._default_layout_path()).parent),
        filetypes=[("JSON files", "*.json")],
        title="Load layout",
    )
    if not path:
        return

    if load_layout_from_path(app, path, silent=False):
        app.status_var.set(f"Layout loaded: {os.path.basename(path)}")
        # Replot will happen automatically after the async CSV load finishes.
        try:
            if not bool(getattr(app, "_load_in_progress", False)):
                app.request_replot()
        except Exception:
            pass
        try:
            app._schedule_autosave()
        except Exception:
            pass


def load_layout_from_path(app, path: str, *, silent: bool) -> bool:
    """Load a layout JSON from a known path (used by startup and menu)."""
    if not path:
        return False

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        if not silent:
            messagebox.showerror("Error", f"Failed to read layout:\n{e}")
        return False

    prev_suppress = bool(getattr(app, "_suppress_autosave", False))
    app._suppress_autosave = True
    try:
        # Settings first (so plots/widgets created during load use the right theme)
        try:
            theme = data.get("ui_theme")
            if hasattr(app, "ui_theme_var") and theme:
                app.ui_theme_var.set(str(theme))
            if hasattr(app, "apply_theme"):
                app.apply_theme(str(theme or getattr(app, "ui_theme_var", None).get() if hasattr(app, "ui_theme_var") else "dark"))
        except Exception:
            pass

        try:
            if hasattr(app, "open_folder_recursive_enabled"):
                app.open_folder_recursive_enabled.set(bool(data.get("open_folder_recursive", False)))
        except Exception:
            pass

        app.current_folder = data.get("current_folder", app.current_folder)
        app.auto_check_enabled.set(bool(data.get("auto_load_newest", True)))
        app.auto_reload_selected_enabled.set(bool(data.get("auto_reload_selected", False)))
        app.auto_save_layout_enabled.set(bool(data.get("auto_save_layout", True)))

        # Kick off file load first (async). Apply subplots after load completes
        # to avoid being overwritten by _finish_load_file's default reset.
        candidate = data.get("last_loaded_file")
        try:
            if isinstance(candidate, str) and candidate and Path(candidate).exists():
                app.load_file(candidate)
            else:
                newest = find_newest_csv(app.current_folder)
                app.load_file(newest)
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load CSV for layout:\n{e}")
            return False

        try:
            setattr(app, "_pending_layout_data", data)
        except Exception:
            pass

        return True
    finally:
        app._suppress_autosave = prev_suppress
