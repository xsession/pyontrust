from __future__ import annotations

from tkinter import messagebox

from lang import t


def show_help(app) -> None:
    messagebox.showinfo(t(app, "dialog.help.title"), t(app, "help.text"))


def show_about(app) -> None:
    messagebox.showinfo(t(app, "dialog.about.title"), t(app, "about.text"))
