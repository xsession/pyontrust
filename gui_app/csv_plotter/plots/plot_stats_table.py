import tkinter as tk
from tkinter import ttk


def render_stats_table(app, bottom_area, stats_rows) -> None:
    app._ensure_table_style()

    stats_frame = ttk.Frame(bottom_area)
    stats_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))

    cols = ("Signal", "Min", "Max", "Average", "Median", "P2P", "StdDev", "RMS", "Crest", "Freq", "Period")
    tree = ttk.Treeview(
        stats_frame,
        columns=cols,
        show="headings",
        height=1,
        selectmode="extended",
        style="Stats.Treeview",
    )

    # Register so app can update row highlighting without requiring a replot.
    try:
        if app is not None and hasattr(app, "_stats_trees"):
            app._stats_trees.append(tree)
    except Exception:
        pass

    # Cross-select highlight: clicking a row toggles channel highlight everywhere.
    def _on_row_click(evt):
        # Ignore header clicks (sorting uses heading commands).
        try:
            if tree.identify_region(evt.x, evt.y) == "heading":
                return
        except Exception:
            pass
        try:
            item = tree.identify_row(evt.y)
        except Exception:
            item = ""
        if not item:
            return
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
            if app is not None and hasattr(app, "_toggle_highlight_key"):
                app._toggle_highlight_key(str(key))
        except Exception:
            pass

    try:
        tree.bind("<ButtonRelease-1>", _on_row_click, add=True)
    except Exception:
        pass

    def _parse_duration_to_ms(text: str) -> int | None:
        """Parse 'd:hh:mm:ss:ms' into total milliseconds."""
        try:
            parts = [p.strip() for p in str(text).strip().split(":")]
            if len(parts) != 5:
                return None
            d, hh, mm, ss, ms = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]))
            if d < 0 or hh < 0 or mm < 0 or ss < 0 or ms < 0:
                return None
            return (((((d * 24) + hh) * 60 + mm) * 60 + ss) * 1000) + ms
        except Exception:
            return None

    def _coerce_sort_value(value, col_name: str):
        """Return a tuple that sorts with 'n/a' last and supports numbers/durations."""
        s = ""
        try:
            s = str(value).strip()
        except Exception:
            s = ""

        if not s or s.lower() in ("n/a", "na", "nan", "none", "-", "—"):
            return (1, 0)

        if col_name == "Period":
            ms = _parse_duration_to_ms(s)
            if ms is not None:
                return (0, ms)

        # Try numeric
        try:
            # Allow common decimal comma inputs
            num = float(s.replace(",", "."))
            return (0, num)
        except Exception:
            pass

        return (0, s.lower())

    def _restripe() -> None:
        try:
            items = list(tree.get_children(""))
        except Exception:
            items = []
        for i, item in enumerate(items):
            base = "even" if (i % 2 == 0) else "odd"
            try:
                tags = list(tree.item(item, "tags") or [])
            except Exception:
                tags = []
            # Preserve hi/dim, replace even/odd
            extra = None
            for t in tags:
                if t in ("hi", "dim"):
                    extra = t
                    break
            new_tags = [base]
            if extra:
                new_tags.append(extra)
            try:
                tree.item(item, tags=tuple(new_tags))
            except Exception:
                pass

    def _sort_by(col_name: str) -> None:
        # Toggle direction for this column
        try:
            state = getattr(tree, "_csv_sort_state", None)
            if not isinstance(state, dict):
                state = {}
                tree._csv_sort_state = state
        except Exception:
            state = {}

        ascending = bool(state.get(col_name, True))
        state[col_name] = not ascending

        try:
            col_index = list(cols).index(col_name)
        except Exception:
            return

        try:
            items = list(tree.get_children(""))
        except Exception:
            items = []
        decorated = []
        for item in items:
            try:
                row = tree.item(item, "values")
            except Exception:
                row = None
            v = ""
            try:
                v = row[col_index] if row and len(row) > col_index else ""
            except Exception:
                v = ""
            decorated.append((
                _coerce_sort_value(v, col_name),
                item,
            ))

        try:
            decorated.sort(key=lambda t: t[0], reverse=not ascending)
        except Exception:
            return

        for new_index, (_k, item) in enumerate(decorated):
            try:
                tree.move(item, "", new_index)
            except Exception:
                pass
        _restripe()

    for c in cols:
        try:
            tree.heading(c, text=c, command=(lambda cc=c: _sort_by(cc)))
        except Exception:
            tree.heading(c, text=c)

    tree.column("Signal", width=200, anchor="w")
    tree.column("Min", width=72, anchor="e")
    tree.column("Max", width=72, anchor="e")
    tree.column("Average", width=72, anchor="e")
    tree.column("Median", width=72, anchor="e")
    tree.column("P2P", width=72, anchor="e")
    tree.column("StdDev", width=72, anchor="e")
    tree.column("RMS", width=72, anchor="e")
    tree.column("Crest", width=60, anchor="e")
    tree.column("Freq", width=72, anchor="e")
    tree.column("Period", width=72, anchor="e")

    try:
        pal = getattr(app, "_theme_palette", {}) if app is not None else {}
        if isinstance(pal, dict) and pal.get("bg") and pal.get("panel"):
            tree.tag_configure("even", background=str(pal.get("bg")))
            tree.tag_configure("odd", background=str(pal.get("panel")))
        else:
            tree.tag_configure("even", background="SystemWindow")
            tree.tag_configure("odd", background="SystemButtonFace")
    except Exception:
        pass

    stats_scroll = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=stats_scroll.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    stats_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Context menu: Copy to clipboard
    ctx_menu = tk.Menu(tree, tearoff=0)

    def _copy_selected_to_clipboard() -> None:
        try:
            items = tree.selection()
            if not items:
                items = tree.get_children("")
            lines = ["\t".join(cols)]
            for item in items:
                vals = tree.item(item, "values")
                lines.append("\t".join(str(v) for v in (vals or [])))
            text = "\n".join(lines)
            tree.clipboard_clear()
            tree.clipboard_append(text)
            if app is not None and hasattr(app, "status_var"):
                app.status_var.set(f"Copied {len(items)} row(s) to clipboard")
        except Exception:
            pass

    def _copy_all_to_clipboard() -> None:
        try:
            items = tree.get_children("")
            lines = ["\t".join(cols)]
            for item in items:
                vals = tree.item(item, "values")
                lines.append("\t".join(str(v) for v in (vals or [])))
            text = "\n".join(lines)
            tree.clipboard_clear()
            tree.clipboard_append(text)
            if app is not None and hasattr(app, "status_var"):
                app.status_var.set(f"Copied all {len(items)} row(s) to clipboard")
        except Exception:
            pass

    ctx_menu.add_command(label="Copy selected rows", command=_copy_selected_to_clipboard)
    ctx_menu.add_command(label="Copy all rows", command=_copy_all_to_clipboard)

    def _show_context_menu(evt):
        try:
            ctx_menu.tk_popup(evt.x_root, evt.y_root)
        finally:
            ctx_menu.grab_release()

    try:
        tree.bind("<Button-3>", _show_context_menu)
    except Exception:
        pass

    highlights = set(getattr(app, "_highlighted_channels", set()) or set()) if app is not None else set()
    nrows = 0
    try:
        nrows = int(len(stats_rows or []))
    except Exception:
        nrows = 0

    for idx, row in enumerate(stats_rows):
        base = "even" if (idx % 2 == 0) else "odd"
        sig = ""
        try:
            sig = str(row[0]) if row and len(row) else ""
        except Exception:
            sig = ""

        key = sig
        if ":" in sig:
            try:
                key = sig.split(":", 1)[1]
            except Exception:
                key = sig

        extra = "hi" if (not highlights or key in highlights) else "dim"
        tree.insert("", tk.END, values=row, tags=(base, extra))

    # Make the table request exactly the height needed for its rows.
    try:
        tree.configure(height=max(1, nrows))
    except Exception:
        pass

    # Encourage the bottom container (PanedWindow pane) to expand to fit the table.
    try:
        # Estimate pixel height: header + rows + some padding.
        style = ttk.Style(tree)
        row_h = style.lookup("Stats.Treeview", "rowheight") or style.lookup("Treeview", "rowheight")
        try:
            row_h = int(row_h)
        except Exception:
            row_h = 20
        header_h = 24
        desired = int(header_h + (row_h * max(1, nrows)) + 18)

        bottom_container = getattr(bottom_area, "master", None)
        paned = getattr(bottom_container, "master", None) if bottom_container is not None else None

        if bottom_container is not None:
            try:
                bottom_container.configure(height=desired)
            except Exception:
                pass

        if paned is not None and hasattr(paned, "paneconfigure") and bottom_container is not None:
            try:
                paned.paneconfigure(bottom_container, minsize=desired)
            except Exception:
                pass
    except Exception:
        pass
