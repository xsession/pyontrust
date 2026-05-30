from __future__ import annotations

import io
import importlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd


SUPPORTED_SIGNAL_EXTENSIONS = (
    ".csv",
    ".txt",
    ".tsv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".feather",
    ".xlsx",
    ".h5",
    ".hdf",
    ".hdf5",
    ".npz",
    ".mat",
    ".tdms",
    ".root",
)


def ensure_optional_dependency(
    import_name: str,
    package_name: str,
    *,
    package_spec: str | None = None,
    purpose: str | None = None,
):
    try:
        return importlib.import_module(import_name)
    except Exception as exc:
        requested = package_spec or package_name
        reason = f" for {purpose}" if purpose else ""
        raise RuntimeError(f"Missing optional dependency '{requested}'{reason}.") from exc


def supported_signal_suffixes() -> tuple[str, ...]:
    return SUPPORTED_SIGNAL_EXTENSIONS


def read_signal_file(path: str) -> pd.DataFrame:
    from pyontrust.analysis.csv_reader import read_any_csv, sniff_csv_separator

    input_path, root_object = split_root_object_spec(path)
    file_path = Path(input_path)
    suffix = file_path.suffix.lower()

    if suffix in {".csv", ".txt", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else None
        if sep is None:
            try:
                sep = sniff_csv_separator(str(file_path))
            except Exception:
                sep = None
        frame = read_any_csv(str(file_path), sep=sep)
    elif suffix == ".json":
        try:
            frame = pd.read_json(str(file_path))
        except ValueError:
            frame = pd.json_normalize(json.loads(file_path.read_text(encoding="utf-8")))
    elif suffix in {".jsonl", ".ndjson"}:
        frame = pd.read_json(str(file_path), lines=True)
    elif suffix == ".parquet":
        ensure_optional_dependency("pyarrow", "pyarrow", package_spec="pyarrow>=12.0", purpose="Parquet import")
        frame = pd.read_parquet(str(file_path))
    elif suffix == ".feather":
        ensure_optional_dependency("pyarrow", "pyarrow", package_spec="pyarrow>=12.0", purpose="Feather import")
        frame = pd.read_feather(str(file_path))
    elif suffix == ".xlsx":
        ensure_optional_dependency("openpyxl", "openpyxl", package_spec="openpyxl>=3.1", purpose="Excel import")
        frame = pd.read_excel(str(file_path))
    elif suffix in {".h5", ".hdf", ".hdf5"}:
        ensure_optional_dependency("tables", "tables", package_spec="tables>=3.8", purpose="HDF5 import")
        frame = pd.read_hdf(str(file_path))
    elif suffix == ".npz":
        with np.load(str(file_path), allow_pickle=True) as data:
            frame = pd.DataFrame({str(key): data[key] for key in data.files})
    elif suffix == ".mat":
        scipy_io = ensure_optional_dependency("scipy.io", "scipy", package_spec="scipy>=1.10", purpose="MATLAB MAT import")
        raw = scipy_io.loadmat(str(file_path))
        columns: dict[str, np.ndarray] = {}
        for key, value in raw.items():
            if str(key).startswith("__"):
                continue
            array = np.asarray(value)
            if array.ndim == 2 and 1 in array.shape:
                array = array.reshape(-1)
            if array.ndim == 1:
                columns[str(key)] = array
        frame = pd.DataFrame(columns)
    elif suffix == ".tdms":
        nptdms = ensure_optional_dependency("nptdms", "nptdms", package_spec="nptdms>=1.10", purpose="TDMS import")
        tdms_file = nptdms.TdmsFile.read(str(file_path))
        columns = {}
        for group in tdms_file.groups():
            for channel in group.channels():
                columns[f"{group.name}/{channel.name}"] = channel[:]
        frame = pd.DataFrame(columns)
    elif suffix == ".root":
        uproot = ensure_optional_dependency("uproot", "uproot", package_spec="uproot>=5.0", purpose="ROOT import")
        with uproot.open(str(file_path)) as root_file:
            object_name = root_object
            if not object_name:
                keys = [str(key).split(";")[0] for key in root_file.keys()]
                object_name = next((key for key in keys if key), None)
            if not object_name:
                raise ValueError("ROOT file does not contain a readable tree or object.")
            arrays = root_file[object_name].arrays(library="np")
        frame = pd.DataFrame({str(key): value for key, value in arrays.items()})
        frame.attrs["root_file_path"] = str(file_path)
        frame.attrs["root_object_path"] = str(object_name)
    else:
        raise ValueError(f"Unsupported input format: {suffix or file_path.name}")

    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(frame)
    return frame


def find_newest_signal_file(folder: str) -> str:
    folder_path = Path(folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    newest_path: Path | None = None
    newest_mtime = -1.0

    for root, _dirs, files in os.walk(folder_path):
        for name in files:
            candidate = Path(root) / name
            if candidate.suffix.lower() not in SUPPORTED_SIGNAL_EXTENSIONS:
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest_path = candidate
                newest_mtime = mtime

    if newest_path is None:
        raise FileNotFoundError("No supported signal files found in the folder.")
    return str(newest_path)


def split_root_object_spec(path: str) -> tuple[str, str | None]:
    text = str(path or "")
    if "::" not in text:
        return text, None
    base, obj = text.split("::", 1)
    obj = str(obj or "").strip() or None
    return base, obj


def cli_base_path(path: str) -> Path:
    base_path, _root_object = split_root_object_spec(str(path))
    return Path(str(base_path))


def is_supported_signal_path(path: str) -> bool:
    try:
        return cli_base_path(path).suffix.lower() in supported_signal_suffixes()
    except Exception:
        return False


def sanitize_cli_name(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "").strip())
    value = value.strip("._-")
    return value or "signal"


def default_cli_output_stem(source_path: str, df: pd.DataFrame | None = None) -> str:
    try:
        attrs = df.attrs if isinstance(df, pd.DataFrame) else {}
    except Exception:
        attrs = {}

    root_file_path = attrs.get("root_file_path") if isinstance(attrs, dict) else None
    root_object_path = attrs.get("root_object_path") if isinstance(attrs, dict) else None

    if isinstance(root_file_path, str) and root_file_path:
        stem = Path(root_file_path).stem
        if isinstance(root_object_path, str) and root_object_path:
            return sanitize_cli_name(f"{stem}_{Path(root_object_path).name}")

    try:
        base_path = cli_base_path(source_path)
        return sanitize_cli_name(base_path.stem)
    except Exception:
        return "signal"


def build_export_payload(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {str(col): df[col].to_numpy() for col in df.columns}


def save_matlab_export(out_path: str | Path, payload: dict[str, np.ndarray]) -> None:
    scipy_io = ensure_optional_dependency(
        "scipy.io",
        "scipy",
        package_spec="scipy>=1.10",
        purpose="MATLAB MAT export",
    )
    scipy_io.savemat(str(out_path), payload)


def save_tdms_export(out_path: str | Path, payload: dict[str, np.ndarray]) -> None:
    nptdms = ensure_optional_dependency(
        "nptdms",
        "nptdms",
        package_spec="nptdms>=1.10",
        purpose="TDMS export",
    )
    ChannelObject = nptdms.ChannelObject
    GroupObject = nptdms.GroupObject
    RootObject = nptdms.RootObject
    TdmsWriter = nptdms.TdmsWriter

    groups: dict[str, list[object]] = {}
    for key, values in payload.items():
        group_name = "Signals"
        channel_name = str(key)
        if "/" in channel_name:
            raw_group, raw_channel = channel_name.split("/", 1)
            group_name = str(raw_group or "Signals")
            channel_name = str(raw_channel or channel_name)
        groups.setdefault(group_name, []).append(ChannelObject(group_name, channel_name, np.asarray(values)))

    objects: list[object] = [RootObject(properties={"writer": "pyontrust.csv_plotter"})]
    for group_name in sorted(groups):
        objects.append(GroupObject(group_name))
        objects.extend(groups[group_name])

    with TdmsWriter(str(out_path)) as writer:
        writer.write_segment(objects)


def write_dataframe_export(df: pd.DataFrame, out_path: str | Path, fmt: str) -> None:
    fmt_norm = str(fmt or "").strip().lower()
    out_path_str = str(out_path)

    if fmt_norm == "csv":
        df.to_csv(out_path_str, index=False)
        return
    if fmt_norm == "txt":
        df.to_csv(out_path_str, index=False, sep="\t")
        return
    if fmt_norm == "json":
        df.to_json(out_path_str, orient="records", indent=2)
        return
    if fmt_norm in {"jsonl", "ndjson"}:
        df.to_json(out_path_str, orient="records", lines=True)
        return
    if fmt_norm == "parquet":
        ensure_optional_dependency("pyarrow", "pyarrow", package_spec="pyarrow>=12.0", purpose="Parquet export")
        df.to_parquet(out_path_str, index=False)
        return
    if fmt_norm == "feather":
        ensure_optional_dependency("pyarrow", "pyarrow", package_spec="pyarrow>=12.0", purpose="Feather export")
        df.reset_index(drop=True).to_feather(out_path_str)
        return
    if fmt_norm == "xlsx":
        ensure_optional_dependency("openpyxl", "openpyxl", package_spec="openpyxl>=3.1", purpose="Excel export")
        df.to_excel(out_path_str, index=False)
        return
    if fmt_norm in {"h5", "hdf", "hdf5"}:
        ensure_optional_dependency("tables", "tables", package_spec="tables>=3.8", purpose="HDF5 export")
        df.to_hdf(out_path_str, key="signals", mode="w")
        return
    if fmt_norm == "npz":
        np.savez(out_path_str, **build_export_payload(df))
        return
    if fmt_norm == "mat":
        save_matlab_export(out_path_str, build_export_payload(df))
        return
    if fmt_norm == "tdms":
        save_tdms_export(out_path_str, build_export_payload(df))
        return
    raise ValueError(f"Unsupported export format: {fmt}")


def export_dataframe_bytes(df: pd.DataFrame, fmt: str) -> bytes:
    fmt_norm = str(fmt or "").strip().lower()

    if fmt_norm == "csv":
        return df.to_csv(index=False).encode("utf-8")
    if fmt_norm == "txt":
        return df.to_csv(index=False, sep="\t").encode("utf-8")
    if fmt_norm == "json":
        return df.to_json(orient="records", indent=2).encode("utf-8")
    if fmt_norm in {"jsonl", "ndjson"}:
        return df.to_json(orient="records", lines=True).encode("utf-8")
    if fmt_norm == "parquet":
        ensure_optional_dependency("pyarrow", "pyarrow", package_spec="pyarrow>=12.0", purpose="Parquet export")
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        return buffer.getvalue()
    if fmt_norm == "feather":
        ensure_optional_dependency("pyarrow", "pyarrow", package_spec="pyarrow>=12.0", purpose="Feather export")
        buffer = io.BytesIO()
        df.reset_index(drop=True).to_feather(buffer)
        return buffer.getvalue()
    if fmt_norm == "xlsx":
        ensure_optional_dependency("openpyxl", "openpyxl", package_spec="openpyxl>=3.1", purpose="Excel export")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()
    if fmt_norm == "npz":
        buffer = io.BytesIO()
        np.savez(buffer, **build_export_payload(df))
        return buffer.getvalue()
    if fmt_norm == "mat":
        scipy_io = ensure_optional_dependency(
            "scipy.io",
            "scipy",
            package_spec="scipy>=1.10",
            purpose="MATLAB MAT export",
        )
        buffer = io.BytesIO()
        scipy_io.savemat(buffer, build_export_payload(df))
        return buffer.getvalue()
    raise NotImplementedError(f"Export format requires filesystem-backed export: {fmt}")


def format_window_bound_for_filename(value: object) -> str:
    try:
        text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    except Exception:
        text = str(value)
    return sanitize_cli_name(text)