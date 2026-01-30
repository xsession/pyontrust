from __future__ import annotations

import tkinter as tk

from lang import t


def build_menu(app) -> None:
    menubar = tk.Menu(app.root)

    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label=t(app, "menu.file.add_new_file"), command=app.choose_file)
    file_menu.add_command(label=t(app, "menu.file.open_folder"), command=app.open_folder_load_all)
    menubar.add_cascade(label=t(app, "menu.file"), menu=file_menu)

    history_menu = tk.Menu(menubar, tearoff=0)
    try:
        history_menu.configure(postcommand=lambda m=history_menu: app._populate_history_menu(m))
    except Exception:
        pass
    menubar.add_cascade(label=t(app, "menu.history"), menu=history_menu)

    settings_menu = tk.Menu(menubar, tearoff=0)
    settings_menu.add_command(label=t(app, "menu.settings.open"), command=app.show_settings)
    menubar.add_cascade(label=t(app, "menu.settings"), menu=settings_menu)

    layout_menu = tk.Menu(menubar, tearoff=0)
    layout_menu.add_command(label=t(app, "menu.layout.save"), command=app.save_layout)
    layout_menu.add_command(label=t(app, "menu.layout.load"), command=app.load_layout)
    layout_menu.add_separator()
    layout_menu.add_command(label=t(app, "menu.layout.clear"), command=app.clear_layout)
    menubar.add_cascade(label=t(app, "menu.layout"), menu=layout_menu)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label=t(app, "menu.help.help"), command=app.show_help)
    help_menu.add_command(label=t(app, "menu.help.about"), command=app.show_about)
    menubar.add_cascade(label=t(app, "menu.help"), menu=help_menu)

    app.root.config(menu=menubar)
