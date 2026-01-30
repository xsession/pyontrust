import os
from pathlib import Path
import csv

import pandas as pd


def sniff_csv_separator(path: str) -> str | None:
    """Best-effort delimiter detection using a small sample."""
    sample = ""
    try:
        with open(path, "rb") as f:
            raw = f.read(64 * 1024)
        sample = raw.decode("utf-8", errors="replace")
    except Exception:
        sample = ""

    if not sample:
        return None

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        sep = getattr(dialect, "delimiter", None)
        return str(sep) if sep else None
    except Exception:
        pass

    # Fallback: pick the most frequent delimiter in the first line.
    try:
        first = sample.splitlines()[0]
        candidates = [",", ";", "\t", "|"]
        counts = {c: first.count(c) for c in candidates}
        best = max(counts, key=counts.get)
        if counts.get(best, 0) > 0:
            return best
    except Exception:
        pass
    return None


def read_csv_header(path: str, *, sep: str | None = None) -> tuple[list[str], str | None]:
    """Return (columns, sep) for a CSV quickly.

    Uses pandas nrows=0 so quoting is handled correctly.
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
    """Find newest .csv in folder tree (recursively)."""
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
    usecols=None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Read CSV with auto delimiter; fixes common ';' vs ',' issues.

    Args:
        sep: Optional explicit separator. If omitted, a small-sample sniff is used.
        usecols: Optional pandas read_csv usecols to load a subset of columns.
        nrows: Optional limit on rows.
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


def compute_timestamp_scale_for_df(df: pd.DataFrame) -> float:
    """Heuristic: treat Timestamp as seconds or milliseconds."""
    scale = 1.0
    try:
        if not isinstance(df, pd.DataFrame) or "Timestamp" not in df.columns:
            return scale
        x = pd.to_numeric(df["Timestamp"], errors="coerce").dropna()
        if len(x) < 3:
            return scale
        dt = x.diff().dropna()
        if len(dt) == 0:
            return scale
        med_dt = float(dt.median())
        if med_dt > 50:
            scale = 0.001
    except Exception:
        scale = 1.0
    return float(scale)
