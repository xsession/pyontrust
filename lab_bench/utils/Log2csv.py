from __future__ import annotations

import csv
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt


# -----------------------------
# Core CSV collector
# -----------------------------

@dataclass(frozen=True)
class ColumnSpec:
    key: str          # internal key (e.g. "Temp_0" or "GTMU2_0.Temp_0" depending on mode)
    header: str       # CSV header label to write


class CsvDataCollector:
    """
    Production-grade CSV collector:

    - Pre-start (schema-build): blocks/modules can register fields.
    - Start: header written once, schema locked, then only rows are appended.
    - Thread-safe and uses csv.writer for correct CSV formatting.

    Key design choice: field naming mode
      - prefix_fields_with_source=True  => columns become "source.field"
      - prefix_fields_with_source=False => columns remain "field" only (risk collisions)

    Recommended for multi-module systems: prefix_fields_with_source=True
    """
    FILE_SPLIT_OPTIONS = {"single", "source", "field", "custom_source", "custom_field"}
    SCHEMA_ORDER_OPTIONS = {"insertion", "source", "field"}
    ROTATE_OPTIONS = {"none", "off", "false", "0", "size", "time"}

    def __init__(
        self,
        base_dir: Path,
        logger: Optional[logging.Logger] = None,
        *,
        delimiter: str = ";",
        encoding: str = "utf-8",
        newline: str = "",
        prefix_fields_with_source: bool = True,
        postfix_fields_with_source: bool = False,
        include_source_column: bool = False,
        include_wall_time: bool = True,
        include_monotonic_time: bool = False,
        strict_unknown_fields: bool = False,
        strict_missing_fields: bool = False,
        flush_every_n: int = 1,
        fsync_every_n: int = 0,
        hold_last_value: bool = True,  
        schema_order = "insertion",  
        file_split = "single",   
        file_split_pattern: str = "{stem}__{group}{suffix}",
        source_groups: Optional[Dict[str, Sequence[str]]] = None,
        field_groups: Optional[Dict[str, Sequence[str]]] = None,
        unmatched_group: Optional[str] = None,
        # NEW: session folder (collect all outputs of a run into a subfolder)
        session_subdir_pattern: Optional[str] = None,  # e.g. "{stem}__{ts}"
        session_time_format: str = "%Y%m%d_%H%M%S",
        # NEW: rotation (size/time)
        rotate_mode: str = "none",              # 'none' | 'size' | 'time'
        rotate_max_bytes: int = 0,               # used when rotate_mode='size'
        rotate_every_s: float = 0.0,             # used when rotate_mode='time'
        rotate_time_format: str = "%Y%m%d_%H%M%S",
        segment_filename_pattern: str = "{stem}__{ts}__{seq:03d}{suffix}",
        rotate_folder_max_files: int = 0,         # if >0: create new folder after N segment files
        rotate_folder_pattern: str = "part_{part:03d}",
    ) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logger or logging.getLogger(__name__)

        self.delimiter = delimiter
        self.encoding = encoding
        self.newline = newline

        self.prefix_fields_with_source = prefix_fields_with_source
        self.postfix_fields_with_source = postfix_fields_with_source
        self.include_source_column = include_source_column
        self.include_wall_time = include_wall_time
        self.include_monotonic_time = include_monotonic_time

        self.strict_unknown_fields = strict_unknown_fields
        self.strict_missing_fields = strict_missing_fields

        self.flush_every_n = max(1, int(flush_every_n))
        self.fsync_every_n = max(0, int(fsync_every_n))

        # NEW
        self.hold_last_value = bool(hold_last_value)
        self.schema_order = str(schema_order or "insertion").lower()
        self._last_values: Dict[str, Any] = {}  # col_key -> last non-None value

        # NEW: optional output splitting (multiple CSV files)
        self.file_split = str(file_split or "single").lower()
        self.file_split_pattern = str(file_split_pattern or "{stem}__{group}{suffix}")
        self.source_groups = {str(k): [str(x) for x in v] for k, v in (source_groups or {}).items()}
        self.field_groups = {str(k): [str(x) for x in v] for k, v in (field_groups or {}).items()}
        self.unmatched_group = str(unmatched_group) if unmatched_group is not None else None
        self._split_children: Dict[str, "CsvDataCollector"] = {}

        # NEW: session folder
        self.session_subdir_pattern = str(session_subdir_pattern) if session_subdir_pattern else None
        self.session_time_format = str(session_time_format or "%Y%m%d_%H%M%S")
        self._session_dir: Optional[Path] = None

        # NEW: rotation
        self.rotate_mode = str(rotate_mode or "none").lower()
        self.rotate_max_bytes = max(0, int(rotate_max_bytes))
        self.rotate_every_s = float(rotate_every_s or 0.0)
        self.rotate_time_format = str(rotate_time_format or "%Y%m%d_%H%M%S")
        self.segment_filename_pattern = str(segment_filename_pattern or "{stem}__{ts}__{seq:03d}{suffix}")
        self.rotate_folder_max_files = max(0, int(rotate_folder_max_files))
        self.rotate_folder_pattern = str(rotate_folder_pattern or "part_{part:03d}")
        self._base_filename: Optional[str] = None
        self._segment_seq: int = 0
        self._segment_start_wall: float = 0.0

        # lifecycle state
        self._lock = threading.RLock()
        self._started = False
        self._schema_locked = False
        self._header_written = False

        self.file_path: Optional[Path] = None
        self._fh = None
        self._writer: Optional[csv.writer] = None
        self._rows_written = 0

        # schema storage
        self._columns: List[ColumnSpec] = []
        self._col_keys: set[str] = set()

        # computed at schema lock
        self._column_order: List[ColumnSpec] = []
        self._key_to_index: Dict[str, int] = {}

        # optional readiness bookkeeping
        self._modules_ready: Dict[str, bool] = {}

        # baseline columns
        if self.include_wall_time:
            self._add_column_internal("Timestamp", "Timestamp")
        if self.include_monotonic_time:
            self._add_column_internal("Monotonic", "Monotonic")
        if self.include_source_column:
            self._add_column_internal("Source", "Source")

    # -----------------------------
    # Schema / readiness
    # -----------------------------

    def register_module(self, module: str, ready: bool = False) -> None:
        """ Register a module for readiness tracking. """
        with self._lock:
            self._ensure_schema_mutable()
            self._modules_ready.setdefault(str(module), bool(ready))

    def mark_ready(self, module: str, ready: bool = True) -> None:
        """ Mark a registered module as ready/not ready. """
        with self._lock:
            self._ensure_schema_mutable()
            self._modules_ready[str(module)] = bool(ready)

    def is_ready(self) -> bool:
        """ Check if all registered modules are ready. """
        with self._lock:
            if not self._modules_ready:
                return True  # no readiness tracking used
            return all(self._modules_ready.values())

    def wait_until_ready(self, timeout_s: Optional[float] = None, poll_s: float = 0.05) -> bool:
        """ Wait until all registered modules are ready, or timeout."""
        t0 = time.time()
        while True:
            if self.is_ready():
                return True
            if timeout_s is not None and (time.time() - t0) >= timeout_s:
                return False
            time.sleep(poll_s)

    def register_fields(self, source: str, fields: Dict[str, Any]) -> None:
        """
        Register expected field keys prior to start to build a stable header.
        Safe to call multiple times.

        If prefix_fields_with_source=True, each field becomes "source.field".
        """
        if not isinstance(fields, dict):
            return

        with self._lock:
            self._ensure_schema_mutable()

            for k in fields.keys():
                k = str(k)
                col_key = self._make_field_key(source, k)
                # header label: use same as key by default
                self._add_column_internal(col_key, col_key)

    def register_columns(self, columns: Sequence[Tuple[str, str]]) -> None:
        """
        Register arbitrary columns (key, header) before start.
        Keys must match what you'll provide in log() if strict_unknown_fields=True.
        """
        with self._lock:
            self._ensure_schema_mutable()
            for key, header in columns:
                self._add_column_internal(str(key), str(header))

    # -----------------------------
    # Lifecycle
    # -----------------------------

    def start(self, filename: str, *, overwrite: bool = False) -> None:
        """ Start logging to the specified CSV file. """
        with self._lock:
            if self._started:
                return

            if not self.is_ready():
                pending = [m for m, r in self._modules_ready.items() if not r]
                raise RuntimeError(f"Cannot start: not ready. Pending modules: {pending}")

            self._base_filename = str(filename)
            self._segment_seq = 0
            self._segment_start_wall = time.time()
            self._session_dir = self._compute_session_dir(filename)

            self._lock_schema()

            if self._is_split_mode():
                self._start_split_children(filename, overwrite=overwrite)
                self.file_path = None
                self._fh = None
                self._writer = None
                self._header_written = True  # headers belong to child collectors
                self._last_values.clear()
                self._started = True
                self._rows_written = 0
                self.logger.info("CSV logging started (split=%s): %s", self.file_split, self._session_dir or self.base_dir)
                return

            self._open_new_segment(overwrite=overwrite)

            # NEW: reset last-value cache per file
            self._last_values.clear()

            self._started = True
            self._rows_written = 0

            self.logger.info("CSV logging started: %s", self.file_path)

    def stop(self) -> None:
        """ Stop logging and close the CSV file. """
        with self._lock:
            if self._split_children:
                for child in list(self._split_children.values()):
                    try:
                        child.stop()
                    except Exception:
                        pass
                self._split_children.clear()
            try:
                self._close_current_file()
            finally:
                self._fh = None
                self._writer = None
                self._started = False
                self.logger.info("CSV logging stopped")

    def is_started(self) -> bool:
        """ Check if logging is active. """
        with self._lock:
            return self._started

    def log(self, source: str, fields: Dict[str, Any]) -> None:
        """
        Log a measurement record.

        If hold_last_value=True:
          - missing keys or None values reuse the last known value for that column
          - columns never seen before remain empty until the first real value arrives
        """
        if not isinstance(fields, dict):
            return

        with self._lock:
            if not self._started:
                return
            if self._split_children:
                self._log_split(source, fields)
                return
            if not self._writer or not self._fh:
                return

            self._maybe_rotate()

            # Build row in final column order
            row = [""] * len(self._column_order)

            # Fill time/source base columns (always new; not held)
            if self.include_wall_time:
                row[self._key_to_index["Timestamp"]] = f"{time.time():.6f}"
            if self.include_monotonic_time:
                row[self._key_to_index["Monotonic"]] = f"{time.monotonic():.6f}"
            if self.include_source_column:
                row[self._key_to_index["Source"]] = str(source)

            # Pre-fill measurement columns with last known values
            if self.hold_last_value:
                for col in self._column_order:
                    if col.key in ("Timestamp", "Monotonic", "Source"):
                        continue
                    if col.key in self._last_values:
                        row[self._key_to_index[col.key]] = self._last_values[col.key]

            # Apply current measurements (overwrite row + update last-values)
            seen = set()
            for k, v in fields.items():
                k = str(k)
                col_key = self._make_field_key(source, k)

                idx = self._key_to_index.get(col_key)
                if idx is None:
                    if self.strict_unknown_fields:
                        raise KeyError(f"Unknown field key: {col_key!r}")
                    continue

                if v is None:
                    # keep last value if enabled; otherwise write empty
                    if not self.hold_last_value:
                        row[idx] = ""
                else:
                    row[idx] = v
                    self._last_values[col_key] = v

                seen.add(col_key)

            if self.strict_missing_fields:
                missing = []
                for c in self._column_order:
                    if c.key in ("Timestamp", "Monotonic", "Source"):
                        continue
                    idx = self._key_to_index[c.key]
                    # strict: require value either present now or previously held
                    if row[idx] == "" and c.key not in self._last_values:
                        missing.append(c.key)
                if missing:
                    raise KeyError(f"Missing fields in strict mode: {missing}")

            self._writer.writerow(row)
            self._rows_written += 1

            if (self._rows_written % self.flush_every_n) == 0:
                self._fh.flush()
            if self.fsync_every_n > 0 and (self._rows_written % self.fsync_every_n) == 0:
                os.fsync(self._fh.fileno())

    # -----------------------------
    # Session folder + rotation
    # -----------------------------

    def _compute_session_dir(self, filename: str) -> Path:
        if not self.session_subdir_pattern:
            return self.base_dir
        p = Path(filename)
        stem = p.stem
        ts = time.strftime(self.session_time_format, time.localtime())
        name = self.session_subdir_pattern.format(stem=stem, ts=ts)
        name = self._sanitize_group_name(name)
        out = self.base_dir / name
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _rotation_enabled(self) -> bool:
        mode = self.rotate_mode
        if mode in ("none", "off", "false", "0"):
            return False
        if mode == "size":
            return self.rotate_max_bytes > 0
        if mode == "time":
            return self.rotate_every_s > 0
        return False

    def _make_segment_path(self) -> Path:
        assert self._base_filename is not None
        p = Path(self._base_filename)
        stem = p.stem
        suffix = p.suffix or ".csv"
        ts = time.strftime(self.rotate_time_format, time.localtime(self._segment_start_wall))
        if self.rotate_folder_max_files > 0:
            part = self._segment_seq // self.rotate_folder_max_files
            seq_in_part = self._segment_seq % self.rotate_folder_max_files
        else:
            part = 0
            seq_in_part = self._segment_seq

        name = self.segment_filename_pattern.format(stem=stem, suffix=suffix, ts=ts, seq=seq_in_part, part=part)

        root = self._session_dir or self.base_dir
        if self.rotate_folder_max_files > 0:
            folder_name = self.rotate_folder_pattern.format(stem=stem, suffix=suffix, ts=ts, seq=seq_in_part, part=part)
            folder_name = self._sanitize_group_name(folder_name)
            root = root / folder_name
            root.mkdir(parents=True, exist_ok=True)

        return root / name

    def _close_current_file(self) -> None:
        if not self._fh:
            return
        try:
            self._fh.flush()
            if self.fsync_every_n > 0:
                os.fsync(self._fh.fileno())
        finally:
            try:
                self._fh.close()
            except Exception:
                pass

    def _open_new_segment(self, *, overwrite: bool) -> None:
        # Close any existing file
        if self._fh:
            self._close_current_file()
            self._fh = None
            self._writer = None

        if self._rotation_enabled():
            self.file_path = self._make_segment_path()
        else:
            assert self._base_filename is not None
            self.file_path = (self._session_dir or self.base_dir) / self._base_filename

        if self.file_path.exists() and not overwrite:
            raise FileExistsError(f"CSV already exists: {self.file_path}")

        self._fh = self.file_path.open("w", encoding=self.encoding, newline=self.newline)
        self._writer = csv.writer(self._fh, delimiter=self.delimiter)
        self._header_written = False
        self._write_header_once()

    def _maybe_rotate(self) -> None:
        if not self._rotation_enabled() or not self._fh:
            return

        if self.rotate_mode == "time":
            now = time.time()
            if (now - self._segment_start_wall) >= self.rotate_every_s:
                self._segment_seq += 1
                self._segment_start_wall = now
                self._open_new_segment(overwrite=True)
            return

        if self.rotate_mode == "size":
            try:
                pos = self._fh.tell()
            except Exception:
                pos = 0
            if pos >= self.rotate_max_bytes:
                self._segment_seq += 1
                self._segment_start_wall = time.time()
                self._open_new_segment(overwrite=True)
            return

    # -----------------------------
    # Split-output support
    # -----------------------------

    def _is_split_mode(self) -> bool:
        return self.file_split not in ("single", "none", "off", "false", "0")

    @staticmethod
    def _sanitize_group_name(name: str) -> str:
        """Make a safe filename fragment (Windows-safe)."""
        bad = '<>:"/\\|?*'
        out = "".join("_" if c in bad else c for c in str(name))
        out = out.strip().strip(".")
        return out or "group"

    def _split_key_parts(self, key: str) -> tuple[str, str]:
        """Return (source, field) from a column key respecting prefix/postfix mode."""
        if "." not in key:
            return "", key
        left, right = key.split(".", 1)
        if self.prefix_fields_with_source:
            return left, right
        if self.postfix_fields_with_source:
            return right, left
        return "", key

    def _make_split_filename(self, filename: str, group: str) -> str:
        p = Path(filename)
        stem = p.stem
        suffix = p.suffix or ".csv"
        group_safe = self._sanitize_group_name(group)
        return self.file_split_pattern.format(stem=stem, suffix=suffix, group=group_safe)

    def _start_split_children(self, filename: str, *, overwrite: bool) -> None:
        if self._split_children:
            return

        if self.file_split not in self.FILE_SPLIT_OPTIONS and self.file_split not in (
            "by_source",
            "by_field",
            "custom_sources",
            "custom_fields",
        ):
            raise ValueError(f"Unsupported file_split: {self.file_split!r}")

        if self.schema_order not in self.SCHEMA_ORDER_OPTIONS:
            raise ValueError(f"Unsupported schema_order: {self.schema_order!r}")

        if self.rotate_mode not in self.ROTATE_OPTIONS:
            raise ValueError(f"Unsupported rotate_mode: {self.rotate_mode!r}")

        base_keys = {"Timestamp", "Monotonic", "Source"}
        meas_cols = [c for c in self._columns if c.key not in base_keys]

        # Determine grouping rules
        if self.file_split in ("source", "by_source"):
            groups: Dict[str, List[ColumnSpec]] = {}
            for c in meas_cols:
                src, _field = self._split_key_parts(c.key)
                groups.setdefault(src or "", []).append(c)

        elif self.file_split in ("field", "by_field"):
            groups = {}
            for c in meas_cols:
                _src, field = self._split_key_parts(c.key)
                groups.setdefault(field or "", []).append(c)

        elif self.file_split in ("custom_source", "custom_sources"):
            if not self.source_groups:
                raise ValueError("file_split='custom_source' requires source_groups")
            src_to_group: Dict[str, str] = {}
            for group_name, sources in self.source_groups.items():
                for src in sources:
                    if src in src_to_group and src_to_group[src] != group_name:
                        raise ValueError(f"Source {src!r} appears in multiple source_groups")
                    src_to_group[src] = group_name
            groups = {}
            for c in meas_cols:
                src, _field = self._split_key_parts(c.key)
                g = src_to_group.get(src)
                if g is None:
                    if self.unmatched_group is not None:
                        g = self.unmatched_group
                    else:
                        continue
                groups.setdefault(g, []).append(c)

        elif self.file_split in ("custom_field", "custom_fields"):
            if not self.field_groups:
                raise ValueError("file_split='custom_field' requires field_groups")
            field_to_group: Dict[str, str] = {}
            for group_name, fields in self.field_groups.items():
                for field in fields:
                    if field in field_to_group and field_to_group[field] != group_name:
                        raise ValueError(f"Field {field!r} appears in multiple field_groups")
                    field_to_group[field] = group_name
            groups = {}
            for c in meas_cols:
                _src, field = self._split_key_parts(c.key)
                g = field_to_group.get(field)
                if g is None:
                    if self.unmatched_group is not None:
                        g = self.unmatched_group
                    else:
                        continue
                groups.setdefault(g, []).append(c)

        else:
            raise ValueError(
                "file_split must be one of: 'single', 'source', 'field', 'custom_source', 'custom_field'"
            )

        # Build and start children
        for group_name, cols in sorted(groups.items(), key=lambda kv: str(kv[0])):
            # Create a child collector with identical settings, but no splitting
            child = CsvDataCollector(
                self._session_dir or self.base_dir,
                self.logger,
                delimiter=self.delimiter,
                encoding=self.encoding,
                newline=self.newline,
                prefix_fields_with_source=self.prefix_fields_with_source,
                postfix_fields_with_source=self.postfix_fields_with_source,
                include_source_column=self.include_source_column,
                include_wall_time=self.include_wall_time,
                include_monotonic_time=self.include_monotonic_time,
                strict_unknown_fields=self.strict_unknown_fields,
                strict_missing_fields=self.strict_missing_fields,
                flush_every_n=self.flush_every_n,
                fsync_every_n=self.fsync_every_n,
                hold_last_value=self.hold_last_value,
                schema_order=self.schema_order,
                file_split="single",
                # inherit rotation
                rotate_mode=self.rotate_mode,
                rotate_max_bytes=self.rotate_max_bytes,
                rotate_every_s=self.rotate_every_s,
                rotate_time_format=self.rotate_time_format,
                segment_filename_pattern=self.segment_filename_pattern,
                rotate_folder_max_files=self.rotate_folder_max_files,
                rotate_folder_pattern=self.rotate_folder_pattern,
            )
            child.register_columns([(c.key, c.header) for c in cols])
            child.start(self._make_split_filename(filename, group_name), overwrite=overwrite)
            self._split_children[group_name] = child

        if not self._split_children:
            raise RuntimeError("Split mode produced no output files (no matching columns/groups)")

    def _log_split(self, source: str, fields: Dict[str, Any]) -> None:
        # file_split determines routing strategy
        if self.file_split in ("source", "by_source", "custom_source", "custom_sources"):
            # Determine group: either explicit grouping or plain source name
            group = source
            if self.file_split in ("custom_source", "custom_sources"):
                group = None
                for g, sources in self.source_groups.items():
                    if source in sources:
                        group = g
                        break
                if group is None:
                    group = self.unmatched_group

            if group is None:
                if self.strict_unknown_fields:
                    raise KeyError(f"Unmatched source for split logging: {source!r}")
                return

            child = self._split_children.get(group)
            if child is None:
                if self.strict_unknown_fields:
                    raise KeyError(f"No split file for group: {group!r}")
                return
            child.log(source, fields)
            return

        if self.file_split in ("field", "by_field", "custom_field", "custom_fields"):
            # Route each field to its field group file
            for field_name, value in fields.items():
                field_name = str(field_name)
                group = field_name
                if self.file_split in ("custom_field", "custom_fields"):
                    group = None
                    for g, fields_list in self.field_groups.items():
                        if field_name in fields_list:
                            group = g
                            break
                    if group is None:
                        group = self.unmatched_group

                if group is None:
                    if self.strict_unknown_fields:
                        raise KeyError(f"Unmatched field for split logging: {field_name!r}")
                    continue

                child = self._split_children.get(group)
                if child is None:
                    if self.strict_unknown_fields:
                        raise KeyError(f"No split file for group: {group!r}")
                    continue
                child.log(source, {field_name: value})
            return

        raise RuntimeError(f"Unsupported split mode: {self.file_split!r}")

    # -----------------------------
    # Charting
    # -----------------------------

    def create_chart_from_csv(
        self,
        csv_path: Path,
        output_png: Path,
        columns: Optional[List[str]] = None,
        *,
        timestamp_column: str = "Timestamp",
    ) -> None:
        """
        Read a CSV written by this collector and plot requested columns vs timestamp.

        - If columns is None: plots all numeric columns (excluding Source).
        - If user passes "A" but CSV has "S.A" (or vice versa), it tries to match intelligently.
        """
        csv_path = Path(csv_path)
        output_png = Path(output_png)

        with csv_path.open("r", encoding=self.encoding, newline="") as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            rows = list(reader)

        if not rows:
            raise ValueError("CSV file is empty")

        header = rows[0]
        if timestamp_column not in header:
            raise ValueError(f"Timestamp column {timestamp_column!r} not found in header")

        t_idx = header.index(timestamp_column)

        # Determine candidate y columns
        exclude = {timestamp_column}
        if "Source" in header:
            exclude.add("Source")

        data_cols = [c for c in header if c not in exclude]

        if columns is None:
            plot_cols = data_cols
        else:
            plot_cols = self._resolve_requested_columns(columns, data_cols)

        # Parse data
        ts: List[float] = []
        series: Dict[str, List[float]] = {c: [] for c in plot_cols}

        for r in rows[1:]:
            if len(r) <= t_idx:
                continue
            try:
                t = float(r[t_idx])
            except Exception:
                continue

            ts.append(t)

            for col in plot_cols:
                idx = header.index(col)
                val_str = r[idx] if idx < len(r) else ""
                try:
                    val = float(val_str) if val_str != "" else float("nan")
                except Exception:
                    val = float("nan")
                series[col].append(val)

        plt.figure(figsize=(10, 6))
        for name in plot_cols:
            # plot directly; matplotlib will break lines at NaNs
            plt.plot(ts, series[name], label=name)
        plt.xlabel("Timestamp (s)")
        plt.ylabel("Value")
        plt.legend()
        plt.tight_layout()
        output_png.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_png)
        plt.close()

    # -----------------------------
    # Internal helpers
    # -----------------------------

    def _make_field_key(self, source: str, field: str) -> str:
        """ Construct column key based on naming mode. """
        if self.prefix_fields_with_source:
            return f"{source}.{field}"
        elif self.postfix_fields_with_source:
            return f"{field}.{source}"
        return field

    def _add_column_internal(self, key: str, header: str) -> None:
        """ Add a column to schema if not already present. """
        if key in self._col_keys:
            return
        self._col_keys.add(key)
        self._columns.append(ColumnSpec(key=key, header=header))

    def _ensure_schema_mutable(self) -> None:
        """ Ensure schema can still be modified. """
        if self._schema_locked:
            raise RuntimeError("Schema is locked (start() already called).")

    def _lock_schema(self) -> None:
        """ Lock the schema and compute final column order. """
        if self._schema_locked:
            return

        # final order: either insertion order (default) or clustered by key parts
        if self.schema_order == "insertion":
            self._column_order = list(self._columns)
        else:
            base_keys = {"Timestamp", "Monotonic", "Source"}
            base_cols = [c for c in self._columns if c.key in base_keys]
            meas_cols = [c for c in self._columns if c.key not in base_keys]

            def split_key(key: str) -> tuple[str, str]:
                # Returns (source, field) for sorting.
                # Handles prefix mode: 'source.field'
                # Handles postfix mode: 'field.source'
                # Handles no-dot: ('', key)
                if "." not in key:
                    return "", key
                left, right = key.split(".", 1)
                if self.prefix_fields_with_source:
                    return left, right
                if self.postfix_fields_with_source:
                    return right, left
                return "", key

            if self.schema_order == "source":
                meas_cols.sort(key=lambda c: (split_key(c.key)[0], split_key(c.key)[1]))
            elif self.schema_order == "field":
                meas_cols.sort(key=lambda c: (split_key(c.key)[1], split_key(c.key)[0]))
            else:
                raise ValueError("schema_order must be one of: 'insertion', 'source', 'field'")

            # Keep base columns at the front in their original registration order
            self._column_order = base_cols + meas_cols

        self._key_to_index = {c.key: i for i, c in enumerate(self._column_order)}
        self._schema_locked = True

    def _write_header_once(self) -> None:
        if self._header_written:
            return
        assert self._writer is not None
        self._writer.writerow([c.header for c in self._column_order])
        self._header_written = True

    @staticmethod
    def _resolve_requested_columns(requested: List[str], available: List[str]) -> List[str]:
        """
        Heuristic matching:
          - exact match
          - if requested lacks prefix, match any ".requested"
          - if requested includes prefix, also try suffix-only match
        """
        avail_set = set(available)
        out: List[str] = []

        for req in requested:
            if req in avail_set:
                out.append(req)
                continue

            if "." not in req:
                matches = [a for a in available if a.endswith("." + req)]
                if len(matches) == 1:
                    out.append(matches[0])
                    continue

            if "." in req:
                suffix = req.split(".", 1)[1]
                if suffix in avail_set:
                    out.append(suffix)
                    continue

            raise ValueError(f"Requested column not found: {req!r}")

        seen = set()
        uniq = []
        for c in out:
            if c not in seen:
                uniq.append(c)
                seen.add(c)
        return uniq


# ------------------------------
# Unit tests
# ------------------------------
import unittest


class TestCsvDataCollector(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path("C:/temp_gui_reports/detector_curve_logs/test")
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def test_noop_before_start(self):
        dc = CsvDataCollector(self.test_dir)
        candidate = self.test_dir / "noop_before_start.csv"
        dc.log(source="S1", fields={"A": 1})
        self.assertFalse(candidate.exists())

    def test_header_and_rows_after_start(self):
        dc = CsvDataCollector(self.test_dir, prefix_fields_with_source=True)

        dc.register_fields("GTMU2_0_ModuleTemps", {"Temp_0": None, "Temp_1": None})
        dc.register_fields("GTMU2_1_ModuleTemps", {"Temp_0": None})

        dc.start("header_rows.csv", overwrite=True)

        for k in range(100):
            dc.log("GTMU2_0_ModuleTemps", {"Temp_0": 30.0 + 0.1 * k, "Temp_1": 31.0 + 0.05 * k})
            dc.log("GTMU2_1_ModuleTemps", {"Temp_0": 29.5 + 0.08 * k})

        dc.stop()

        csv_path = self.test_dir / "header_rows.csv"
        content = csv_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(content), 3)

        header = content[0].split(";")
        expected_cols = [
            "Timestamp",
            "GTMU2_0_ModuleTemps.Temp_0",
            "GTMU2_0_ModuleTemps.Temp_1",
            "GTMU2_1_ModuleTemps.Temp_0",
        ]
        self.assertEqual(header, expected_cols)

        # Each row has same column count as header
        self.assertEqual(len(content[1].split(";")), len(expected_cols))
        self.assertEqual(len(content[2].split(";")), len(expected_cols))

    def test_non_dict_fields_ignored(self):
        dc = CsvDataCollector(self.test_dir, prefix_fields_with_source=True)
        dc.register_fields("S2", {"A": None})
        dc.start("non_dict_fields.csv", overwrite=True)
        dc.log("S1", None)  # ignored
        for k in range(100):
            dc.log("S2", {"A": 1 + 0.2 * k})
        dc.stop()

        csv_path = self.test_dir / "non_dict_fields.csv"
        lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(lines[0], "Timestamp;S2.A")
        self.assertEqual(len(lines), 1 + 100)

        png_path = self.test_dir / "non_dict_fields.png"
        if png_path.exists():
            try:
                png_path.unlink()
            except Exception:
                pass
        dc.create_chart_from_csv(csv_path, png_path, columns=["A"])  # accepts "A" or "S2.A"
        self.assertTrue(png_path.exists())

    def test_create_chart_from_csv(self):
        dc = CsvDataCollector(self.test_dir, prefix_fields_with_source=True)
        dc.register_fields("S", {"A": None, "B": None})
        dc.start("chart_from_csv.csv", overwrite=True)
        for k in range(200):
            dc.log("S", {"A": 1.0 + 0.05 * k, "B": 2.0 + 0.03 * k})
        dc.stop()

        csv_path = self.test_dir / "chart_from_csv.csv"
        png_path = self.test_dir / "chart_from_csv.png"
        if png_path.exists():
            try:
                png_path.unlink()
            except Exception:
                pass
        dc.create_chart_from_csv(csv_path, png_path)
        self.assertTrue(png_path.exists())

    def test_split_by_source_creates_files(self):
        dc = CsvDataCollector(self.test_dir, prefix_fields_with_source=True, file_split="source")
        dc.register_fields("S1", {"A": None, "B": None})
        dc.register_fields("S2", {"A": None})
        dc.start("split_source.csv", overwrite=True)
        for k in range(10):
            dc.log("S1", {"A": k, "B": 100 + k})
            dc.log("S2", {"A": 200 + k})
        dc.stop()

        f1 = self.test_dir / "split_source__S1.csv"
        f2 = self.test_dir / "split_source__S2.csv"
        self.assertTrue(f1.exists())
        self.assertTrue(f2.exists())

        header1 = f1.read_text(encoding="utf-8").splitlines()[0].split(";")
        header2 = f2.read_text(encoding="utf-8").splitlines()[0].split(";")
        self.assertEqual(header1, ["Timestamp", "S1.A", "S1.B"])
        self.assertEqual(header2, ["Timestamp", "S2.A"])

    def test_split_by_field_creates_files(self):
        dc = CsvDataCollector(self.test_dir, prefix_fields_with_source=True, file_split="field")
        dc.register_fields("S1", {"A": None, "B": None})
        dc.register_fields("S2", {"A": None})
        dc.start("split_field.csv", overwrite=True)
        for k in range(10):
            dc.log("S1", {"A": k, "B": 100 + k})
            dc.log("S2", {"A": 200 + k})
        dc.stop()

        fa = self.test_dir / "split_field__A.csv"
        fb = self.test_dir / "split_field__B.csv"
        self.assertTrue(fa.exists())
        self.assertTrue(fb.exists())

        header_a = fa.read_text(encoding="utf-8").splitlines()[0].split(";")
        header_b = fb.read_text(encoding="utf-8").splitlines()[0].split(";")
        self.assertEqual(header_a, ["Timestamp", "S1.A", "S2.A"])
        self.assertEqual(header_b, ["Timestamp", "S1.B"])

    def test_split_outputs_can_be_collected_in_session_folder(self):
        dc = CsvDataCollector(
            self.test_dir,
            prefix_fields_with_source=True,
            file_split="source",
            session_subdir_pattern="session",
        )
        dc.register_fields("S1", {"A": None})
        dc.register_fields("S2", {"A": None})
        dc.start("split_session.csv", overwrite=True)
        dc.log("S1", {"A": 1})
        dc.log("S2", {"A": 2})
        dc.stop()

        session_dir = self.test_dir / "session"
        self.assertTrue(session_dir.exists())
        self.assertTrue((session_dir / "split_session__S1.csv").exists())
        self.assertTrue((session_dir / "split_session__S2.csv").exists())

    def test_rotate_by_size_creates_multiple_segments(self):
        dc = CsvDataCollector(
            self.test_dir,
            prefix_fields_with_source=True,
            rotate_mode="size",
            rotate_max_bytes=80,
            segment_filename_pattern="{stem}__{seq:03d}{suffix}",
        )
        dc.register_fields("S", {"A": None})
        dc.start("rotate_size.csv", overwrite=True)
        for k in range(200):
            dc.log("S", {"A": k})
        dc.stop()

        # Expect at least two segments
        f0 = self.test_dir / "rotate_size__000.csv"
        f1 = self.test_dir / "rotate_size__001.csv"
        self.assertTrue(f0.exists())
        self.assertTrue(f1.exists())

    def test_rotate_folder_rollover_after_n_files(self):
        dc = CsvDataCollector(
            self.test_dir,
            prefix_fields_with_source=True,
            rotate_mode="size",
            rotate_max_bytes=80,
            rotate_folder_max_files=3,
            rotate_folder_pattern="part_{part:03d}",
            segment_filename_pattern="{stem}__{seq:03d}{suffix}",
        )
        dc.register_fields("S", {"A": None})
        dc.start("rotate_folder.csv", overwrite=True)

        # Force enough rotations to roll over into part_001
        for k in range(500):
            dc.log("S", {"A": k})
        dc.stop()

        p0 = self.test_dir / "part_000"
        p1 = self.test_dir / "part_001"
        self.assertTrue(p0.exists())
        self.assertTrue(p1.exists())
        # At least one file in each
        self.assertTrue(any(p0.glob("rotate_folder__*.csv")))
        self.assertTrue(any(p1.glob("rotate_folder__*.csv")))


if __name__ == "__main__":
    unittest.main()
