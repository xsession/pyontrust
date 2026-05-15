from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import traceback
import uuid

from werkzeug.utils import secure_filename

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server as server_module  # noqa: E402
from pdf_parser import _detect_vendor, _extract_all_text, _stm32_find_af_tables, _stm32_find_pindef, _ti_find_packages, _ti_find_pincm  # noqa: E402
from pdf_parser import parse_datasheet  # noqa: E402
from sensor_parser import _extract_all_text as _extract_sensor_text, _find_register_detail_pages, _find_register_table_pages, parse_sensor_datasheet  # noqa: E402
from state_runtime import persist_server_state, restore_server_state  # noqa: E402
import pdfplumber  # noqa: E402


UPLOADS_DIR = ROOT / '.uploads'


def _upload_dir(kind: str) -> pathlib.Path:
    suffix = {
        'mcu-jobs': 'mcu_jobs',
        'sensor-jobs': 'sensor_jobs',
    }[kind]
    return UPLOADS_DIR / suffix

_GENERIC_PINMUX_PATTERN = re.compile(
    r'alternate\s+function|pin\s*mux|pin\s*function|signal\s*mux|'
    r'GPIO\s*Mapping|GPIO\s*alternate|'
    r'Pin\s*Name\s.*Function|Port\s*Pin\s*Function|'
    r'IO_MUX|IOMUX|PINMUX|AFR|'
    r'\bAF\d+\b|I/O\s+Multiplex|Pin\s+Multiplexing',
    re.I,
)
_GENERIC_PACKAGE_PATTERN = re.compile(
    r'pin\s*(out|diagram|assignment|description|definition)|'
    r'ball\s*map|signal\s*description|package\s*pin|'
    r'terminal\s*function|pin\s*configuration',
    re.I,
)
_SENSOR_PACKAGE_PATTERN = re.compile(
    r'package\s*(outline|information|dimensions?)|'
    r'pin\s*(configuration|assignment|description|functions?)|'
    r'mechanical\s*data|land\s*pattern|terminal\s*configuration|'
    r'outline\s*drawings?|package\s*option',
    re.I,
)


def _json_response(status: int, payload: dict) -> int:
    json.dump({'status': status, 'json': payload}, sys.stdout)
    return 0


def _handle_parse_pdf(payload: dict) -> tuple[int, dict]:
    upload_path = pathlib.Path(str(payload.get('uploadPath', '')))
    filename = str(payload.get('filename', ''))
    if not filename.lower().endswith('.pdf'):
        return 400, {'error': 'File must be a .pdf'}
    if not upload_path.exists():
        return 400, {'error': "No 'pdf' file in request"}

    safe_name = secure_filename(filename)
    job_id = uuid.uuid4().hex[:12]
    final_path = _upload_dir('mcu-jobs') / f'{job_id}_{safe_name}'
    final_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.replace(final_path)

    try:
      info = parse_datasheet(str(final_path), verbose=False)
    except Exception as exc:
      final_path.unlink(missing_ok=True)
      return 500, {'error': f'PDF parsing failed: {exc}'}

    server_module._PARSED_JOBS[job_id] = {
        'filename': safe_name,
        'upload_path': str(final_path),
        'info': info,
    }
    persist_server_state()
    return 200, {
        'job_id': job_id,
        'filename': safe_name,
        'result': server_module._datasheet_to_json(info),
    }


def _handle_parse_sensor_pdf(payload: dict) -> tuple[int, dict]:
    upload_path = pathlib.Path(str(payload.get('uploadPath', '')))
    filename = str(payload.get('filename', ''))
    if not filename.lower().endswith('.pdf'):
        return 400, {'error': 'File must be a .pdf'}
    if not upload_path.exists():
        return 400, {'error': "No 'pdf' file in request"}

    safe_name = secure_filename(filename)
    job_id = uuid.uuid4().hex[:12]
    final_path = _upload_dir('sensor-jobs') / f'{job_id}_{safe_name}'
    final_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.replace(final_path)

    try:
      info = parse_sensor_datasheet(str(final_path), verbose=False)
    except Exception as exc:
      final_path.unlink(missing_ok=True)
      return 500, {'error': f'Sensor PDF parsing failed: {exc}'}

    server_module._SENSOR_JOBS[job_id] = {
        'filename': safe_name,
        'upload_path': str(final_path),
        'info': info,
    }
    persist_server_state()
    return 200, {
        'job_id': job_id,
        'filename': safe_name,
        'result': server_module.sensor_info_to_json(info),
    }


def _handle_extract_mcu_pdf_snapshot(payload: dict) -> tuple[int, dict]:
    upload_path = pathlib.Path(str(payload.get('uploadPath', '')))
    if not upload_path.exists():
        return 400, {'error': "No 'pdf' file in request"}

    try:
        with pdfplumber.open(str(upload_path)) as pdf:
            texts = _extract_all_text(pdf)
            vendor = _detect_vendor(texts)
            pincm_tables = _ti_find_pincm(pdf, texts)
            package_rows = _ti_find_packages(pdf, texts)
            stm32_af_tables = _stm32_find_af_tables(pdf, texts)
            stm32_pindef_tables = _stm32_find_pindef(pdf, texts)
            generic_pinmux_tables: list[list[list[str]]] = []
            generic_package_pages: list[dict[str, object]] = []

            for idx, text in enumerate(texts):
                try:
                    page_tables = pdf.pages[idx].extract_tables()
                except Exception:
                    continue
                if _GENERIC_PINMUX_PATTERN.search(text):
                    generic_pinmux_tables.extend(page_tables)
                if _GENERIC_PACKAGE_PATTERN.search(text):
                    generic_package_pages.append({
                        'text': text,
                        'tables': page_tables,
                    })
    except Exception as exc:
        return 500, {'error': f'PDF extraction failed: {exc}'}

    return 200, {
        'vendor': vendor,
        'texts': texts,
        'pincm_tables': pincm_tables,
        'package_rows': package_rows,
        'stm32_af_tables': stm32_af_tables,
        'stm32_pindef_tables': stm32_pindef_tables,
        'generic_pinmux_tables': generic_pinmux_tables,
        'generic_package_pages': generic_package_pages,
    }


def _handle_extract_sensor_pdf_snapshot(payload: dict) -> tuple[int, dict]:
    upload_path = pathlib.Path(str(payload.get('uploadPath', '')))
    if not upload_path.exists():
        return 400, {'error': "No 'pdf' file in request"}

    try:
        with pdfplumber.open(str(upload_path)) as pdf:
            texts = _extract_sensor_text(pdf)
            register_pages: list[dict[str, object]] = []
            detail_pages: list[dict[str, object]] = []
            package_pages: list[dict[str, object]] = []
            for idx in _find_register_table_pages(texts):
                try:
                    page_tables = pdf.pages[idx].extract_tables()
                except Exception:
                    continue
                register_pages.append({
                    'text': texts[idx],
                    'tables': page_tables,
                })
            for idx in _find_register_detail_pages(texts):
                try:
                    page_tables = pdf.pages[idx].extract_tables()
                except Exception:
                    continue
                detail_pages.append({
                    'text': texts[idx],
                    'tables': page_tables,
                })
            for idx, text in enumerate(texts):
                if not _SENSOR_PACKAGE_PATTERN.search(text):
                    continue
                try:
                    page_tables = pdf.pages[idx].extract_tables()
                except Exception:
                    page_tables = []
                package_pages.append({
                    'text': text,
                    'tables': page_tables,
                })
    except Exception as exc:
        return 500, {'error': f'Sensor PDF extraction failed: {exc}'}

    return 200, {
        'texts': texts,
        'register_pages': register_pages,
        'detail_pages': detail_pages,
        'package_pages': package_pages,
    }


def _handle_fetch_datasheet_parse(payload: dict) -> tuple[int, dict]:
    part_number = str(payload.get('partNumber', '')).strip()
    upload_path = pathlib.Path(str(payload.get('uploadPath', '')))
    filename = str(payload.get('filename', '')).strip()
    message = str(payload.get('message', '')).strip()
    if not part_number:
        return 400, {'error': 'No part_number provided'}
    if not upload_path.exists():
        return 400, {'error': 'Downloaded datasheet file is missing'}

    try:
        info = parse_datasheet(str(upload_path), verbose=False)
    except Exception as exc:
        return 500, {'error': f'Failed: Downloaded PDF but parsing failed: {exc}'}

    job_id = uuid.uuid4().hex[:12]
    server_module._PARSED_JOBS[job_id] = {
        'filename': filename or f'{part_number}_datasheet.pdf',
        'upload_path': str(upload_path),
        'info': info,
    }
    persist_server_state()
    return 200, {
        'job_id': job_id,
        'message': message,
        'part_number': part_number,
        'result': server_module._datasheet_to_json(info),
    }


def main() -> int:
    restore_server_state()
    payload = json.load(sys.stdin)
    operation = payload.get('operation')

    try:
        if operation == 'parse-pdf':
            status, response = _handle_parse_pdf(payload)
        elif operation == 'parse-sensor-pdf':
            status, response = _handle_parse_sensor_pdf(payload)
        elif operation == 'extract-mcu-pdf-snapshot':
            status, response = _handle_extract_mcu_pdf_snapshot(payload)
        elif operation == 'extract-sensor-pdf-snapshot':
            status, response = _handle_extract_sensor_pdf_snapshot(payload)
        elif operation == 'fetch-datasheet-parse':
            status, response = _handle_fetch_datasheet_parse(payload)
        else:
            status, response = 400, {'error': f'Unknown operation: {operation}'}
    except Exception as exc:
        response = {'error': str(exc), 'traceback': traceback.format_exc()}
        status = 500

    json.dump({'status': status, 'json': response}, sys.stdout)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())