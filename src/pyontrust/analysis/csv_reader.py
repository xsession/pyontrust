"""CSV I/O layer — multi-backend reader with automatic delimiter detection.

Re-exports the proven read pipeline from the CSV Plotter data module into the
unified ``pyontrust.analysis`` namespace.  All backends are optional — the
module degrades gracefully:

1. **Polars** — fastest for large files
2. **DuckDB** — SQL-based, good for filtered/column-subset reads
3. **PyArrow** — columnar via pandas ``engine="pyarrow"``
4. **Pandas C engine** — fallback, always available
"""
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("pyontrust.analysis.csv_reader")

# ── Optional fast backends ──────────────────────────────────────────────
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


# ── Delimiter detection ─────────────────────────────────────────────────

def sniff_csv_separator(path: str) -> str | None:
    """Best-effort delimiter detection using a small sample (≤64 KB).

    Uses :func:`csv.Sniffer` first, then falls back to a simple
    frequency count on the first line.
    """
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


# ── Header-only read ────────────────────────────────────────────────────

def read_csv_header(
    path: str, *, sep: str | None = None
) -> tuple[list[str], str | None]:
    """Return ``(columns, sep)`` by reading only the header row.

    Tries Polars → pandas(pyarrow) → pandas(C) → pandas(python).
    """
    if sep is None:
        try:
            sep = sniff_csv_separator(path)
        except Exception:
            sep = None

    _kw: dict[str, Any] = {
        "encoding": "utf-8",
        "low_memory": False,
        "memory_map": True,
    }

    if pl is not None:
        try:
            pl_kw: dict[str, Any] = {"n_rows": 0}
            if sep:
                pl_kw["separator"] = sep
            df0 = pl.read_csv(path, **pl_kw)
            return [str(c) for c in df0.columns], sep
        except Exception:
            pass

    if sep:
        for engine in ("pyarrow", "c"):
            try:
                try:
                    df0 = pd.read_csv(
                        path, sep=sep, engine=engine, nrows=0,
                        encoding_errors="replace", **_kw,
                    )
                except TypeError:
                    df0 = pd.read_csv(
                        path, sep=sep, engine=engine, nrows=0, **_kw,
                    )
                return [str(c) for c in df0.columns], str(sep)
            except Exception:
                continue

    try:
        try:
            df0 = pd.read_csv(
                path, sep=None, engine="python", nrows=0,
                encoding_errors="replace", **_kw,
            )
        except TypeError:
            df0 = pd.read_csv(path, sep=None, engine="python", nrows=0, **_kw)
        return [str(c) for c in df0.columns], sep
    except Exception:
        return [], sep


# ── Full read (pandas DataFrame) ────────────────────────────────────────

def read_any_csv(
    path: str,
    *,
    sep: str | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Read CSV with automatic delimiter and backend selection.

    Returns a :class:`pandas.DataFrame`.  When a columnar backend
    succeeds the arrow table is attached as ``df.attrs["_arrow_table"]``.
    """
    if sep is None:
        try:
            sep = sniff_csv_separator(path)
        except Exception:
            sep = None

    _kw: dict[str, Any] = {
        "encoding": "utf-8",
        "low_memory": False,
        "memory_map": True,
        "usecols": usecols,
        "nrows": nrows,
    }

    # 1) Polars
    if pl is not None:
        try:
            pl_kw: dict[str, Any] = {"ignore_errors": True}
            if sep:
                pl_kw["separator"] = sep
            if usecols is not None:
                pl_kw["columns"] = list(usecols)
            if nrows is not None:
                pl_kw["n_rows"] = int(nrows)
            pl_df = pl.read_csv(path, **pl_kw)
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

    # 2) DuckDB
    if duckdb is not None:
        try:
            con = duckdb.connect(database=":memory:")
            safe_path = path.replace("'", "''")
            opts: list[str] = []
            if sep:
                opts.append(f"delim = '{sep.replace(chr(39), chr(39)+chr(39))}'")
            opts_str = ", " + ", ".join(opts) if opts else ""

            if usecols is not None:
                cols = ", ".join(f'"{c}"' for c in usecols)
                sql = f"SELECT {cols} FROM read_csv_auto('{safe_path}'{opts_str})"
            else:
                sql = f"SELECT * FROM read_csv_auto('{safe_path}'{opts_str})"
            if nrows is not None:
                sql += f" LIMIT {int(nrows)}"

            rel = con.execute(sql)
            tbl = rel.arrow() if hasattr(rel, "arrow") else None
            df_pd = rel.df()
            if tbl is not None:
                df_pd.attrs["_arrow_table"] = tbl
            return df_pd
        except Exception:
            logger.debug("DuckDB read failed for %s", path, exc_info=True)

    # 3) pandas with explicit separator
    if sep:
        for engine in ("pyarrow", "c"):
            try:
                try:
                    return pd.read_csv(
                        path, sep=sep, engine=engine,
                        encoding_errors="replace", **_kw,
                    )
                except TypeError:
                    return pd.read_csv(path, sep=sep, engine=engine, **_kw)
            except Exception:
                continue

    # 4) pandas auto-detection
    try:
        try:
            df = pd.read_csv(
                path, sep=None, engine="python",
                encoding_errors="replace", **_kw,
            )
        except TypeError:
            df = pd.read_csv(path, sep=None, engine="python", **_kw)
    except Exception:
        df = pd.read_csv(path)

    # 5) Last-resort semicolon check
    if len(df.columns) == 1:
        try:
            header = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[0]
        except Exception:
            header = ""
        if ";" in header:
            try:
                try:
                    df = pd.read_csv(
                        path, sep=";", engine="c",
                        encoding_errors="replace", **_kw,
                    )
                except TypeError:
                    df = pd.read_csv(path, sep=";", encoding="utf-8")
            except Exception:
                pass
    return df


# ── Arrow-native read ───────────────────────────────────────────────────

def read_any_csv_arrow(
    path: str,
    *,
    sep: str | None = None,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> Any:
    """Read CSV and return a :class:`pyarrow.Table` when possible.

    Falls back Polars → DuckDB → PyArrow native.  Returns ``None`` if
    no arrow-capable backend is available.
    """
    if sep is None:
        try:
            sep = sniff_csv_separator(path)
        except Exception:
            sep = None

    if pl is not None:
        try:
            pl_kw: dict[str, Any] = {"ignore_errors": True}
            if sep:
                pl_kw["separator"] = sep
            if usecols is not None:
                pl_kw["columns"] = list(usecols)
            if nrows is not None:
                pl_kw["n_rows"] = int(nrows)
            pl_df = pl.read_csv(path, **pl_kw)
            return pl_df.to_arrow() if hasattr(pl_df, "to_arrow") else None
        except Exception:
            pass

    if duckdb is not None:
        try:
            con = duckdb.connect(database=":memory:")
            safe_path = path.replace("'", "''")
            opts: list[str] = []
            if sep:
                opts.append(f"delim = '{sep.replace(chr(39), chr(39)+chr(39))}'")
            opts_str = ", " + ", ".join(opts) if opts else ""
            if usecols is not None:
                cols = ", ".join(f'"{c}"' for c in usecols)
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
            table = pacsv.read_csv(
                path,
                read_options=read_opts,
                parse_options=parse_opts,
                convert_options=convert_opts,
            )
            if nrows is not None:
                return table.slice(0, int(nrows))
            return table
        except Exception:
            return None
    return None


# ── Newest-file finder ──────────────────────────────────────────────────

def find_newest_csv(folder: str) -> str:
    """Return the path of the most recently modified ``.csv`` in *folder*."""
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


# ── Timestamp-scale heuristic ───────────────────────────────────────────

def compute_timestamp_scale(df: pd.DataFrame) -> float:
    """Detect timestamp units (s / ms / µs) and return a → seconds multiplier.

    Looks for the first column whose name starts with ``"timestamp"``
    (case-insensitive) and uses the median sampling interval.
    """
    scale = 1.0
    try:
        if df is None:
            return scale
        ts_col: str | None = None
        for c in list(df.columns):
            if str(c).strip().lower().startswith("timestamp"):
                ts_col = str(c)
                break
        if not ts_col or ts_col not in df.columns:
            return scale

        x = pd.to_numeric(df[ts_col], errors="coerce").dropna()
        if len(x) < 3:
            return scale

        x = x.astype(float).sort_values()
        dt = x.diff().dropna()
        dt = dt[dt > 0]
        if len(dt) == 0:
            return scale

        med_dt = float(dt.median())
        abs_max = float(x.abs().max())

        if med_dt >= 1_000:
            scale = 1e-6
        elif med_dt >= 50 or (abs_max >= 1e5 and med_dt >= 0.5):
            scale = 0.001
    except Exception:
        scale = 1.0
    return float(scale)
