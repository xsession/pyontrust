from __future__ import annotations

import json
import pickle
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server as server_module  # noqa: E402


STATE_DIR = ROOT / "backend_ts" / ".bridge_state"
PARSED_JOBS_PATH = STATE_DIR / "parsed_jobs.pkl"
SENSOR_JOBS_PATH = STATE_DIR / "sensor_jobs.pkl"
PARSED_JOBS_JSON_PATH = STATE_DIR / "parsed_jobs.json"
SENSOR_JOBS_JSON_PATH = STATE_DIR / "sensor_jobs.json"


def _load_pickle(path: pathlib.Path):
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as handle:
            value = pickle.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_pickle(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(value, handle)


def _save_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


def _serialise_parsed_jobs() -> dict:
    jobs = {}
    for job_id, job in server_module._PARSED_JOBS.items():
        info = job.get("info")
        result = server_module._datasheet_to_json(info) if info is not None else None
        full_result = _datasheet_to_full_json(info) if info is not None else None
        jobs[job_id] = {
            "job_id": job_id,
            "filename": job.get("filename", ""),
            "upload_path": job.get("upload_path", ""),
            "result": result,
            "full_result": full_result,
        }
    return jobs


def _datasheet_to_full_json(info) -> dict:
    return {
        "device": {
            "soc": info.device.soc,
            "vendor": info.device.vendor,
            "flash_size_kb": info.device.flash_size_kb,
            "sram_size_kb": info.device.sram_size_kb,
            "clock_hz": info.device.clock_hz,
        },
        "packages": [
            {
                "name": pkg.name,
                "pin_count": pkg.pin_count,
                "pins": [
                    {
                        "number": pin.number,
                        "name": pin.name,
                        "port": pin.port,
                        "gpio_num": pin.gpio_num,
                        "kind": pin.kind,
                    }
                    for pin in pkg.pins
                ],
            }
            for pkg in info.packages
        ],
        "pin_mux": {
            pin_name: [
                {
                    "pin_name": entry.pin_name,
                    "pincm": entry.pincm,
                    "function_id": entry.function_id,
                    "function_name": entry.function_name,
                    "peripheral": entry.peripheral,
                    "signal": entry.signal,
                    "direction": entry.direction,
                }
                for entry in entries
            ]
            for pin_name, entries in info.pin_mux.items()
        },
    }


def _serialise_sensor_jobs() -> dict:
    jobs = {}
    for job_id, job in server_module._SENSOR_JOBS.items():
        info = job.get("info")
        result = server_module.sensor_info_to_json(info) if info is not None else None
        jobs[job_id] = {
            "job_id": job_id,
            "filename": job.get("filename", ""),
            "upload_path": job.get("upload_path", ""),
            "result": result,
        }
    return jobs


def restore_server_state() -> None:
    server_module._PARSED_JOBS.clear()
    server_module._PARSED_JOBS.update(_load_pickle(PARSED_JOBS_PATH))
    server_module._SENSOR_JOBS.clear()
    server_module._SENSOR_JOBS.update(_load_pickle(SENSOR_JOBS_PATH))


def persist_server_state() -> None:
    _save_pickle(PARSED_JOBS_PATH, server_module._PARSED_JOBS)
    _save_pickle(SENSOR_JOBS_PATH, server_module._SENSOR_JOBS)
    _save_json(PARSED_JOBS_JSON_PATH, _serialise_parsed_jobs())
    _save_json(SENSOR_JOBS_JSON_PATH, _serialise_sensor_jobs())