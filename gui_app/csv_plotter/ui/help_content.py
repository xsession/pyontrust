from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from lang import t


def show_help(app) -> None:
    """Show a scrollable, searchable help dialog instead of a plain messagebox."""
    # Single-instance guard
    existing = getattr(app, "_help_dialog", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
    except Exception:
        pass

    dlg = tk.Toplevel(app.root)
    app._help_dialog = dlg
    dlg.title(t(app, "dialog.help.title"))
    dlg.geometry("720x560")
    try:
        dlg.transient(app.root)
    except Exception:
        pass

    # Search bar
    search_frame = ttk.Frame(dlg, padding=(8, 6, 8, 2))
    search_frame.pack(fill="x")
    ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 6))
    search_var = tk.StringVar(value="")
    search_entry = ttk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side=tk.LEFT, fill="x", expand=True)

    # Scrollable text area
    text_frame = ttk.Frame(dlg, padding=(8, 4, 8, 8))
    text_frame.pack(fill="both", expand=True)
    text_widget = tk.Text(text_frame, wrap="word", font=("Consolas", 10), state="disabled", relief="flat")
    text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=text_scroll.set)
    text_scroll.pack(side=tk.RIGHT, fill="y")
    text_widget.pack(side=tk.LEFT, fill="both", expand=True)

    # Apply theme
    try:
        pal = getattr(app, "_theme_palette", {})
        if isinstance(pal, dict) and pal.get("bg"):
            text_widget.configure(
                background=str(pal.get("bg")),
                foreground=str(pal.get("fg", "white")),
                insertbackground=str(pal.get("fg", "white")),
            )
    except Exception:
        pass

    help_text = t(app, "help.text")
    text_widget.tag_configure("highlight", background="#FFFF00", foreground="#000000")

    def _populate(filter_text: str = "") -> None:
        text_widget.configure(state="normal")
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", help_text)
        # Highlight matches
        if filter_text.strip():
            query = filter_text.strip().lower()
            start = "1.0"
            while True:
                pos = text_widget.search(query, start, nocase=True, stopindex="end")
                if not pos:
                    break
                end_pos = f"{pos}+{len(query)}c"
                text_widget.tag_add("highlight", pos, end_pos)
                start = end_pos
        text_widget.configure(state="disabled")

    _populate()

    def _on_search(*_args) -> None:
        _populate(search_var.get())

    search_var.trace_add("write", _on_search)

    # Close button
    btn_frame = ttk.Frame(dlg, padding=(8, 0, 8, 8))
    btn_frame.pack(fill="x")
    ttk.Button(btn_frame, text="Close", command=dlg.destroy).pack(side=tk.RIGHT)

    search_entry.focus_set()


def show_about(app) -> None:
    """Show a richer About dialog with version info."""
    try:
        version = getattr(app, "__version__", None)
        if version is None:
            import csv_plotter
            version = getattr(csv_plotter, "__version__", "0.0.1")
    except Exception:
        version = "0.0.1"

    about_text = t(app, "about.text")
    about_text += f"\nVersion: {version}"
    messagebox.showinfo(t(app, "dialog.about.title"), about_text)
