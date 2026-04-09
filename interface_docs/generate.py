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
import logging
import sys
from pathlib import Path

from generators import load_yaml, resolve_types, ensure_dir
from generators.gen_c import gen_c_typedefs, gen_c_objdict, gen_c_registers
from generators.gen_python import gen_python_driver
from generators.gen_html import gen_html
from generators.gen_gui import gen_gui_jinja

logging.basicConfig(level=logging.INFO, format="  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Dispatch ─────────────────────────────────────────────────────

FORMAT_MAP = {
    "c-typedefs": "typedefs",
    "c-objdict": "objdict",
    "c-uart-protocol": "registers",
    "c-modbus-registers": "registers",
    "c-i2c-registers": "registers",
    "c-spi-devices": "registers",
    "c-tcp-protocol": "registers",
    "python": "python",
    "html": "html",
    "html-confluence": "html",
    "gui-jinja": "gui-jinja",
}


def process_target(target: dict, base_dir: Path) -> None:
    source_path = base_dir / target["source"]
    output_path = base_dir / target["output"]
    fmt = target.get("format", "")
    includes = target.get("includes", [])
    od_name = target.get("od_name", "Generated")

    data = load_yaml(source_path)
    dep_paths = [base_dir / d for d in target.get("dependencies", [])]
    types = resolve_types(dep_paths)

    kind = FORMAT_MAP.get(fmt)
    if kind is None:
        log.warning("Unknown format %r, skipping %s", fmt, output_path)
        return

    if kind == "typedefs":
        content = gen_c_typedefs(data, includes)
    elif kind == "objdict":
        content = gen_c_objdict(data, types, includes)
    elif kind == "registers":
        transport = data.get("interface", {}).get("transport", "")
        content = gen_c_registers(data, types, includes, transport)
    elif kind == "python":
        content = gen_python_driver(data, types, od_name)
    elif kind == "html":
        content = gen_html(data, types)
    elif kind == "gui-jinja":
        content = gen_gui_jinja(data, types, od_name)
    else:
        return

    ensure_dir(output_path)
    output_path.write_text(content, encoding="utf-8")
    log.info("Generated %s", output_path.relative_to(base_dir))


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
            process_target(target, base_dir)
            processed += 1
        except Exception as e:
            log.error("Failed %s: %s", source, e)

    log.info("Done — %d targets processed", processed)


if __name__ == "__main__":
    main()
