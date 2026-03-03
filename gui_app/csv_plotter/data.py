"""CSV I/O layer for the CSV Plotter.

This module provides a **multi-backend** CSV reader with automatic
delimiter detection. Backends tried in order:

1. **Polars** — fastest for large files
2. **DuckDB** — SQL-based, good for filtered/column-subset reads
3. **PyArrow** — used via pandas ``engine="pyarrow"``
4. **Pandas C engine** — fallback, always available

All backends are optional; the module degrades gracefully when a backend
is not installed.

Security note:
    The DuckDB path uses ``read_csv_auto()`` with file paths properly
    escaped to prevent SQL injection.  Never interpolate untrusted user
    input into SQL strings.
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger("csv_plotter.data")

try:
    import polars as pl
except ImportError:
    pl = None  # type: ignore[assignment]

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]

try:
    import pyarrow as pa
except ImportError:
    pa = None  # type: ignore[assignment]


def sniff_csv_separator(path: str) -> str | None:
    """Best-effort delimiter detection using a small sample.

    Reads up to 64 KB of the file, uses :func:`csv.Sniffer` first and
    falls back to a simple frequency count on the first line.

    Parameters
    ----------
    path : str
        Filesystem path to the CSV file.

    Returns
    -------
    str | None
        Detected delimiter character or ``None``.
    """
    sample = ""
    try:
        with open(path, "rb") as f:
            raw = f.read(64 * 1024)
        sample = raw.decode("utf-8", errors="replace")
    except OSError:
        logger.debug("Could not read sample from %s", path, exc_info=True)
        return None

    if not sample:
        return None

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        sep = getattr(dialect, "delimiter", None)
        if sep:
            return str(sep)
    except csv.Error:
        pass

    # Fallback: pick the most frequent delimiter in the first line.
    try:
        first = sample.splitlines()[0]
        candidates = [",", ";", "\t", "|"]
        counts = {c: first.count(c) for c in candidates}
        best = max(counts, key=counts.get)  # type: ignore[arg-type]
        if counts.get(best, 0) > 0:
            return best
    except Exception:
        logger.debug("Fallback delimiter detection failed for %s", path, exc_info=True)
    return None


def read_csv_header(path: str, *, sep: str | None = None) -> tuple[list[str], str | None]:
    """Return ``(columns, sep)`` for a CSV file quickly.

    Only reads the header row (``nrows=0``).  Tries multiple backends
    for robustness: Polars → PyArrow engine → C engine → Python engine.

    Parameters
    ----------
    path : str
        Filesystem path to the CSV file.
    sep : str | None
        Explicit delimiter.  Sniffed automatically if ``None``.

    Returns
    -------
    tuple[list[str], str | None]
        Column names and detected delimiter.
    """
    if sep is None:
        try:
            sep = sniff_csv_separator(path)
        except Exception:
            sep = None

    read_kwargs = {
        "encoding": "utf-8",
        "low_memory": False,
        "memory_map": True,
    }

    if pl is not None:
        try:
            pl_kwargs = {"n_rows": 0}
            if sep:
                pl_kwargs["separator"] = sep
            df0 = pl.read_csv(path, **pl_kwargs)
            cols = [str(c) for c in df0.columns]
            return cols, sep
        except Exception:
            pass

    if sep:
        for engine in ("pyarrow", "c"):
            try:
                try:
                    df0 = pd.read_csv(path, sep=sep, engine=engine, nrows=0, encoding_errors="replace", **read_kwargs)
                except TypeError:
                    df0 = pd.read_csv(path, sep=sep, engine=engine, nrows=0, **read_kwargs)
                cols = [str(c) for c in list(df0.columns)]
                return cols, str(sep)
            except Exception:
                continue

    # Fallback: slower but robust
    try:
        try:
            df0 = pd.read_csv(path, sep=None, engine="python", nrows=0, encoding_errors="replace", **read_kwargs)
        except TypeError:
            df0 = pd.read_csv(path, sep=None, engine="python", nrows=0, **read_kwargs)
        cols = [str(c) for c in list(df0.columns)]
        return cols, sep
    except Exception:
        return [], sep


def find_newest_csv(folder: str) -> str:
    """Find the newest ``.csv`` file in *folder* (recursive).

    Parameters
    ----------
    folder : str
        Root directory to search.

    Returns
    -------
    str
        Absolute path to the most recently modified CSV.

    Raises
    ------
    FileNotFoundError
        If *folder* doesn't exist or contains no CSV files.
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    newest_path: Path | None = None
    newest_mtime = -1.0

    for root, _dirs, files in os.walk(folder_path):
        for name in files:
            if not name.lower().endswith(".csv"):
                continue
            p = Path(root) / name
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest_path = p

    if newest_path is None:
        raise FileNotFoundError("No CSV files found in the folder.")
    return str(newest_path)


def read_any_csv(
    path: str,
    *,
    sep: str | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Read a CSV file with automatic delimiter and backend selection.

    Tries Polars → DuckDB → pandas(pyarrow) → pandas(C) → pandas(python),
    returning the first successful result.

    Parameters
    ----------
    path : str
        Filesystem path to the CSV file.
    sep : str | None
        Explicit delimiter.  If ``None``, sniffed automatically.
    usecols : list[str] | None
        Subset of columns to load.
    nrows : int | None
        Maximum rows to read.

    Returns
    -------
    pd.DataFrame
        The loaded data.  May attach ``attrs["_arrow_table"]`` if a
        columnar backend was used.
    """
    if sep is None:
        try:
            sep = sniff_csv_separator(path)
        except Exception:
            sep = None

    read_kwargs = {
        "encoding": "utf-8",
        "low_memory": False,
        "memory_map": True,
        "usecols": usecols,
        "nrows": nrows,
    }

    if pl is not None:
        try:
            pl_kwargs = {"ignore_errors": True}
            if sep:
                pl_kwargs["separator"] = sep
            if usecols is not None:
                pl_kwargs["columns"] = list(usecols)
            if nrows is not None:
                pl_kwargs["n_rows"] = int(nrows)
            pl_df = pl.read_csv(path, **pl_kwargs)
            tbl = pl_df.to_arrow() if hasattr(pl_df, "to_arrow") else None
            try:
                df_pd = pl_df.to_pandas(use_pyarrow_extension_array=True)
            except Exception:
                df_pd = pl_df.to_pandas()
            if tbl is not None:
                df_pd.attrs["_arrow_table"] = tbl
            return df_pd
        except Exception:
            pass

    if duckdb is not None:
        try:
            con = duckdb.connect(database=":memory:")
            # SECURITY: Escape the file path to prevent SQL injection.
            # DuckDB's read_csv_auto takes the path as a string literal.
            safe_path = path.replace("'", "''")
            opts = []
            if sep:
                safe_sep = sep.replace("'", "''")
                opts.append(f"delim = '{safe_sep}'")
            opts_str = ", " + ", ".join(opts) if opts else ""

            if usecols is not None:
                # Column names are quoted identifiers — safe from injection.
                cols = ", ".join([f'"{c}"' for c in list(usecols)])
                sql = f"SELECT {cols} FROM read_csv_auto('{safe_path}'{opts_str})"
            else:
                sql = f"SELECT * FROM read_csv_auto('{safe_path}'{opts_str})"

            if nrows is not None:
                sql += f" LIMIT {int(nrows)}"  # int() prevents injection

            logger.debug("DuckDB query: %s", sql)
            rel = con.execute(sql)
            tbl = rel.arrow() if hasattr(rel, "arrow") else None
            df_pd = rel.df()
            if tbl is not None:
                df_pd.attrs["_arrow_table"] = tbl
            return df_pd
        except Exception:
            logger.debug("DuckDB read failed for %s, falling back", path, exc_info=True)

    # Prefer a fast engine when we have an explicit separator.
    # - pyarrow (if available) can be significantly faster on large files
    # - fall back to the default C engine
    if sep:
        for engine in ("pyarrow", "c"):
            try:
                try:
                    return pd.read_csv(path, sep=sep, engine=engine, encoding_errors="replace", **read_kwargs)
                except TypeError:
                    return pd.read_csv(path, sep=sep, engine=engine, **read_kwargs)
            except Exception:
                continue

    # Fallback: pandas auto detection (slower but robust)
    try:
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace", **read_kwargs)
        except TypeError:
            df = pd.read_csv(path, sep=None, engine="python", **read_kwargs)
    except Exception:
        df = pd.read_csv(path)

    # If delimiter detection failed, try semicolon explicitly
    if len(df.columns) == 1:
        try:
            header = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[0]
        except Exception:
            header = ""
        if ";" in header:
            try:
                try:
                    df = pd.read_csv(path, sep=";", engine="c", encoding_errors="replace", **read_kwargs)
                except TypeError:
                    df = pd.read_csv(path, sep=";", engine="c", **read_kwargs)
            except Exception:
                try:
                    df = pd.read_csv(path, sep=";", encoding="utf-8")
                except Exception:
                    pass
    return df


def read_any_csv_arrow(
    path: str,
    *,
    sep: str | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> Any:
    """Read CSV and return a :class:`pyarrow.Table` when possible.

    Falls back through Polars → DuckDB → PyArrow native.  Returns
    ``None`` if no arrow-capable backend is available.

    Parameters
    ----------
    path : str
        Filesystem path to the CSV file.
    sep : str | None
        Explicit delimiter.  If ``None``, sniffed automatically.
    usecols : list[str] | None
        Subset of columns to load.
    nrows : int | None
        Maximum rows to read.

    Returns
    -------
    pyarrow.Table | None
    """
    if sep is None:
        try:
            sep = sniff_csv_separator(path)
        except Exception:
            sep = None

    if pl is not None:
        try:
            pl_kwargs = {"ignore_errors": True}
            if sep:
                pl_kwargs["separator"] = sep
            if usecols is not None:
                pl_kwargs["columns"] = list(usecols)
            if nrows is not None:
                pl_kwargs["n_rows"] = int(nrows)
            pl_df = pl.read_csv(path, **pl_kwargs)
            return pl_df.to_arrow() if hasattr(pl_df, "to_arrow") else None
        except Exception:
            pass

    if duckdb is not None:
        try:
            con = duckdb.connect(database=":memory:")
            safe_path = path.replace("'", "''")
            opts = []
            if sep:
                safe_sep = sep.replace("'", "''")
                opts.append(f"delim = '{safe_sep}'")
            opts_str = ", " + ", ".join(opts) if opts else ""

            if usecols is not None:
                cols = ", ".join([f'"{c}"' for c in list(usecols)])
                sql = f"SELECT {cols} FROM read_csv_auto('{safe_path}'{opts_str})"
            else:
                sql = f"SELECT * FROM read_csv_auto('{safe_path}'{opts_str})"

            if nrows is not None:
                sql += f" LIMIT {int(nrows)}"

            rel = con.execute(sql)
            return rel.arrow() if hasattr(rel, "arrow") else None
        except Exception:
            logger.debug("DuckDB arrow read failed for %s", path, exc_info=True)

    if pa is not None:
        try:
            import pyarrow.csv as pacsv

            read_opts = pacsv.ReadOptions(autogenerate_column_names=False)
            parse_opts = pacsv.ParseOptions(delimiter=sep or ",")
            convert_opts = pacsv.ConvertOptions(include_columns=usecols)
            table = pacsv.read_csv(path, read_options=read_opts, parse_options=parse_opts, convert_options=convert_opts)
            if nrows is not None:
                return table.slice(0, int(nrows))
            return table
        except Exception:
            return None
    return None


def compute_timestamp_scale_for_df(df: pd.DataFrame) -> float:
    """Heuristic to detect timestamp units (seconds / ms / µs).

    Returns a multiplier that converts the dataframe's timestamp units
    to seconds.

    The function looks for the first column whose name starts with
    ``"timestamp"`` (case-insensitive) and uses the median sampling
    interval to classify:

    - ``dt ≥ 1000`` → microseconds → returns ``1e-6``
    - ``dt ≥ 50`` (or ``abs_max ≥ 1e5`` and ``dt ≥ 0.5``) → milliseconds → ``0.001``
    - otherwise → seconds → ``1.0``

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame (may be empty).

    Returns
    -------
    float
        Scale factor to convert to seconds.
    """
    scale = 1.0
    try:
        if df is None:
            return scale
        if isinstance(df, pd.DataFrame):
            ts_col = None
            try:
                for c in list(df.columns):
                    if str(c).strip().lower().startswith("timestamp"):
                        ts_col = str(c)
                        break
            except Exception:
                ts_col = None
            if not ts_col or ts_col not in df.columns:
                return scale
            x = pd.to_numeric(df[ts_col], errors="coerce").dropna()
        elif pl is not None and isinstance(df, pl.DataFrame):
            ts_col = None
            try:
                for c in list(df.columns):
                    if str(c).strip().lower().startswith("timestamp"):
                        ts_col = str(c)
                        break
            except Exception:
                ts_col = None
            if not ts_col or ts_col not in df.columns:
                return scale
            x = df[ts_col].cast(pl.Float64, strict=False).drop_nulls().to_list()
            x = pd.Series(x)
        else:
            return scale
        if len(x) < 3:
            return scale
        # Sort just in case the source isn't monotonic.
        try:
            x = x.astype(float).sort_values()
        except Exception:
            pass

        dt = x.diff().dropna()
        if len(dt) == 0:
            return scale
        try:
            dt = dt[dt > 0]
        except Exception:
            pass
        if len(dt) == 0:
            return scale

        med_dt = float(dt.median())
        try:
            abs_max = float(pd.to_numeric(x, errors="coerce").abs().max())
        except Exception:
            abs_max = 0.0

        # Microseconds (common in fast logs): dt typically >= 1_000.
        if med_dt >= 1_000:
            scale = 1e-6
        # Milliseconds: dt can be as small as 1..10, but absolute values are usually large.
        elif med_dt >= 50 or (abs_max >= 1e5 and med_dt >= 0.5):
            scale = 0.001
        else:
            scale = 1.0
    except Exception:
        scale = 1.0
    return float(scale)
