"""Plot-data extraction helpers (NO Tkinter dependency).

This package contains pure-Python modules that extract plot-ready data
structures (dicts/lists suitable for JSON serialisation) from pandas
DataFrames.  Each module mirrors one of the original ``plots/*.py``
Tkinter renderers but returns JSON-friendly data instead of embedding
matplotlib figures into Tk widgets.
"""
