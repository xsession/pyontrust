"""Interface documentation code generator.

Reads a batch manifest (mp.yaml) and generates C headers, Python
driver stubs, Jinja2 GUI widget blocks, and HTML documentation from
YAML interface descriptions.

Usage:
    python interface_docs/generate.py interface_docs/mp.yaml
    python interface_docs/generate.py interface_docs/mp.yaml --only uart
    python interface_docs/generate.py interface_docs/mp.yaml --format html
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
from typing import Callable
import sys
from pathlib import Path

from generators import detect_hex_enum_types, load_yaml, resolve_types, ensure_dir
from generators.gen_c import gen_c_typedefs, gen_c_objdict, gen_c_registers
from generators.gen_advanced import (
    gen_c_od,
    gen_c_pdo_macro,
    gen_c_types,
    gen_py_alias,
    gen_xml_canether,
    gen_xml_od,
    gen_xml_to_yaml,
)
from generators.gen_mlxcheck import gen_mlx_report
from generators.gen_python import gen_python_driver
from generators.gen_scaffold import gen_gui_app_scaffold, gen_test_sequence_scaffold
from generators.gen_vhdl import gen_vhdl_arch, gen_vhdl_package
from generators.gen_html import gen_html
from generators.gen_gui import gen_gui_jinja

logging.basicConfig(level=logging.INFO, format="  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Dispatch ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class JobContext:
    target: dict
    base_dir: Path
    source_path: Path
    output_path: Path
    format_name: str
    includes: list[str]
    od_name: str
    data: dict
    dep_paths: list[Path]
    types: dict
    enum_formats: list[str]


@dataclass(frozen=True)
class HandlerResult:
    content: str | None = None
    handled_output: bool = False


Handler = Callable[[JobContext], HandlerResult]


def _build_job_context(target: dict, base_dir: Path) -> JobContext:
    source_path = base_dir / target["source"]
    output_path = base_dir / target["output"]
    dep_paths = [base_dir / dep for dep in target.get("dependencies", [])]
    return JobContext(
        target=target,
        base_dir=base_dir,
        source_path=source_path,
        output_path=output_path,
        format_name=target.get("format", ""),
        includes=target.get("includes", []),
        od_name=target.get("od_name", "Generated"),
        data=load_yaml(source_path),
        dep_paths=dep_paths,
        types=resolve_types(dep_paths),
        enum_formats=detect_hex_enum_types([source_path, *dep_paths]),
    )


def _handle_c_typedefs(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_c_typedefs(context.data, context.includes))


def _handle_c_objdict(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_c_objdict(context.data, context.types, context.includes))


def _handle_c_registers(context: JobContext) -> HandlerResult:
    transport = context.data.get("interface", {}).get("transport", "")
    return HandlerResult(content=gen_c_registers(context.data, context.types, context.includes, transport))


def _handle_python(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_python_driver(
        context.data,
        context.types,
        context.od_name,
        enum_formats=context.enum_formats,
    ))


def _handle_html(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_html(context.data, context.types))


def _handle_gui_jinja(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_gui_jinja(context.data, context.types, context.od_name))


def _handle_mlxcheck(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_mlx_report(
        context.data,
        min_mlx=context.target.get("minMLX"),
        max_mlx=context.target.get("maxMLX"),
    ))


def _handle_xml_canether(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_xml_canether(context.data, context.types, context.od_name))


def _handle_c_types(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_c_types(context.target, context.base_dir))


def _handle_c_od(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_c_od(context.target, context.base_dir))


def _handle_xml_od(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_xml_od(context.target, context.base_dir))


def _handle_py_alias(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_py_alias(context.target, context.base_dir))


def _handle_xml_to_yaml(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_xml_to_yaml(context.target, context.base_dir))


def _handle_c_pdo_macro(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_c_pdo_macro(context.target, context.base_dir))


def _handle_vhdl_package(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_vhdl_package(context.target, context.base_dir))


def _handle_vhdl_arch(context: JobContext) -> HandlerResult:
    return HandlerResult(content=gen_vhdl_arch(context.target, context.base_dir))


def _handle_gui_app(context: JobContext) -> HandlerResult:
    gen_gui_app_scaffold(context)
    return HandlerResult(handled_output=True)


def _handle_test_sequence(context: JobContext) -> HandlerResult:
    gen_test_sequence_scaffold(context)
    return HandlerResult(handled_output=True)


FORMAT_HANDLERS: dict[str, Handler] = {
    "c-typedefs": _handle_c_typedefs,
    "c-objdict": _handle_c_objdict,
    "c-uart-protocol": _handle_c_registers,
    "c-modbus-registers": _handle_c_registers,
    "c-i2c-registers": _handle_c_registers,
    "c-spi-devices": _handle_c_registers,
    "c-tcp-protocol": _handle_c_registers,
    "python": _handle_python,
    "py": _handle_py_alias,
    "html": _handle_html,
    "html-confluence": _handle_html,
    "gui-jinja": _handle_gui_jinja,
    "mlxcheck": _handle_mlxcheck,
    "xml-canether": _handle_xml_canether,
    "c-types": _handle_c_types,
    "c-od": _handle_c_od,
    "xml-od": _handle_xml_od,
    "xml-to-yaml": _handle_xml_to_yaml,
    "c-pdo_macro": _handle_c_pdo_macro,
    "vhdl-package": _handle_vhdl_package,
    "vhdl-arch": _handle_vhdl_arch,
    "gui-app": _handle_gui_app,
    "test-sequence": _handle_test_sequence,
}


def _write_python_package_init(context: JobContext) -> None:
    if context.format_name != "python":
        return
    if not context.target.get("generate_init", False):
        return

    init_path = context.output_path.parent / "__init__.py"
    if init_path.exists():
        log.info("Package init already exists %s; keeping it unchanged", init_path)
        return

    init_path.write_text(f"from .{context.output_path.stem} import *\n", encoding="utf-8")


def _write_debug_output(context: JobContext) -> None:
    debug_relpath = context.target.get("debug")
    if not debug_relpath:
        return

    debug_path = context.base_dir / debug_relpath
    ensure_dir(debug_path)
    payload = {
        "source": str(context.source_path),
        "output": str(context.output_path),
        "format": context.format_name,
        "includes": context.includes,
        "od_name": context.od_name,
        "dependencies": [str(path) for path in context.dep_paths],
        "enum_formats": context.enum_formats,
    }
    debug_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def validate_target(target: dict, base_dir: Path) -> None:
    for key in ("source", "output", "format"):
        if key not in target:
            raise ValueError(f"Missing required target key: {key}")

    source_path = base_dir / target["source"]
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    dependencies = target.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("Target 'dependencies' must be a list")
    for dependency in dependencies:
        dependency_path = base_dir / dependency
        if not dependency_path.exists():
            raise FileNotFoundError(f"Dependency file not found: {dependency_path}")

    includes = target.get("includes", [])
    if not isinstance(includes, list):
        raise ValueError("Target 'includes' must be a list")

    format_name = target.get("format", "")
    if format_name not in FORMAT_HANDLERS:
        raise ValueError(f"Unsupported format: {format_name}")


def process_target(target: dict, base_dir: Path) -> None:
    context = _build_job_context(target, base_dir)
    handler = FORMAT_HANDLERS.get(context.format_name)
    if handler is None:
        log.warning("Unknown format %r, skipping %s", context.format_name, context.output_path)
        return

    result = handler(context)
    if not result.handled_output:
        if result.content is None:
            raise ValueError(f"Handler for {context.format_name} did not return content")
        ensure_dir(context.output_path)
        context.output_path.write_text(result.content, encoding="utf-8")
    _write_python_package_init(context)
    _write_debug_output(context)
    log.info("Generated %s", context.output_path.relative_to(base_dir))


# ── Main ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Interface documentation code generator")
    parser.add_argument("batch_file", help="Path to mp.yaml batch manifest")
    parser.add_argument("--only", help="Only process targets whose source contains this substring")
    parser.add_argument("--format", help="Only process targets with this format")
    args = parser.parse_args()

    batch_path = Path(args.batch_file)
    base_dir = batch_path.parent

    targets = load_yaml(batch_path)
    if not isinstance(targets, list):
        log.error("Batch file must be a YAML list of targets")
        sys.exit(1)

    processed = 0
    for target in targets:
        source = target.get("source", "")
        fmt = target.get("format", "")

        if args.only and args.only not in source:
            continue
        if args.format and args.format != fmt:
            continue

        try:
            validate_target(target, base_dir)
            process_target(target, base_dir)
            processed += 1
        except Exception as e:
            log.error("Failed %s: %s", source, e)

    log.info("Done — %d targets processed", processed)


if __name__ == "__main__":
    main()
