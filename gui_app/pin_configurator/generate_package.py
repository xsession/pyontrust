#!/usr/bin/env python3
"""
MCU Package Generator – CLI tool.

Parses an MCU manufacturer PDF (currently Texas Instruments MSPM0 family)
and generates Zephyr Pin Configurator board definition files.

Usage
-----
  # Auto-detect packages from the PDF and generate all of them:
  python generate_package.py  path/to/MSPM0G3507.pdf

  # Specify output directory:
  python generate_package.py  path/to/MSPM0G3507.pdf  -o boards/

  # Generate only a specific package (e.g. 48-pin QFP):
  python generate_package.py  path/to/MSPM0G3507.pdf  --package QFP-48

  # Override board name and DTS includes:
  python generate_package.py  path/to/MSPM0G3507.pdf  \\
      --board lp_mspm0g3507 \\
      --dts-soc '<ti/mspm0/g/mspm0g3507.dtsi>' \\
      --dts-pinctrl '<ti/mspm0g1x0x_g3x0x/mspm0g350x-pinctrl.dtsi>'

  # Dry-run: parse and show what was found without writing files:
  python generate_package.py  path/to/MSPM0G3507.pdf  --dry-run

  # Verbose logging (show PDF parsing details):
  python generate_package.py  path/to/MSPM0G3507.pdf  -v
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import textwrap

# Ensure package is importable when run directly
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pdf_parser import parse_datasheet, DatasheetInfo
from package_generator import generate_board_files, generate_board_file


def _print_summary(info: DatasheetInfo) -> None:
    """Pretty-print what was extracted from the PDF."""
    d = info.device
    print()
    print("  ┌─────────────────────────────────────────────────┐")
    print(f"  │  MCU Package Generator                           │")
    print("  └─────────────────────────────────────────────────┘")
    print()
    print(f"  SOC:       {d.soc or '(not detected)'}")
    print(f"  Vendor:    {d.vendor}")
    print(f"  Flash:     {d.flash_size_kb} KB" if d.flash_size_kb else "  Flash:     (not detected)")
    print(f"  SRAM:      {d.sram_size_kb} KB" if d.sram_size_kb else "  SRAM:      (not detected)")
    print(f"  Clock:     {d.clock_hz // 1_000_000} MHz" if d.clock_hz else "  Clock:     (not detected)")
    print()

    if info.packages:
        print(f"  Packages found ({len(info.packages)}):")
        for pkg in info.packages:
            io_count = sum(1 for p in pkg.pins if p.kind == "io")
            pwr_count = sum(1 for p in pkg.pins if p.kind in ("power", "ground"))
            spec_count = sum(1 for p in pkg.pins if p.kind == "special")
            print(f"    • {pkg.name:12s}  {pkg.pin_count:3d} pins  "
                  f"({io_count} I/O, {pwr_count} pwr/gnd, {spec_count} special)")
    else:
        print("  ⚠ No package pin-out tables found in the PDF.")
        print("    You may need to provide package data manually.")

    if info.pin_mux:
        total_funcs = sum(len(v) for v in info.pin_mux.values())
        print(f"\n  Pin-mux: {len(info.pin_mux)} pins, {total_funcs} alt-functions")

        # Show a few example pins
        sample = list(info.pin_mux.items())[:3]
        for pin_name, entries in sample:
            funcs = ", ".join(e.function_name for e in entries[:4])
            more = f" … (+{len(entries)-4})" if len(entries) > 4 else ""
            print(f"    {pin_name}: {funcs}{more}")
        if len(info.pin_mux) > 3:
            print(f"    … and {len(info.pin_mux) - 3} more pins")
    else:
        print("\n  ⚠ No PINCM / pin-mux data found in the PDF.")

    print()


def _interactive_package_select(info: DatasheetInfo) -> list[int]:
    """Let user choose which packages to generate when multiple are found."""
    print("  Select packages to generate (comma-separated, or 'all'):")
    for i, pkg in enumerate(info.packages):
        print(f"    [{i+1}] {pkg.name} ({pkg.pin_count} pins)")

    while True:
        choice = input("\n  > ").strip().lower()
        if choice in ("all", "a", "*", ""):
            return list(range(len(info.packages)))
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            if all(0 <= i < len(info.packages) for i in indices):
                return indices
        except ValueError:
            pass
        print("  Invalid selection. Enter numbers like '1,3' or 'all'.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Zephyr Pin Configurator board definitions from MCU datasheets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s  MSPM0G3507.pdf
              %(prog)s  MSPM0G3507.pdf  -o boards/  --package QFP-48
              %(prog)s  MSPM0G3507.pdf  --dry-run  -v
        """),
    )
    parser.add_argument("pdf", help="Path to the MCU manufacturer PDF datasheet")
    parser.add_argument("-o", "--output", default=None,
                        help="Output directory (default: boards/ next to this script)")
    parser.add_argument("--package", default=None,
                        help="Generate only this package (e.g. 'QFP-48'). "
                             "Default: generate all found packages.")
    parser.add_argument("--board", default=None,
                        help="Override Zephyr board name (e.g. 'lp_mspm0g3507')")
    parser.add_argument("--dts-soc", default=None,
                        help="DTS SOC include path")
    parser.add_argument("--dts-pinctrl", default=None,
                        help="DTS pinctrl include path")
    parser.add_argument("--pinctrl-header", default=None,
                        help="Pinctrl header file name")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse PDF and show results without writing files")
    parser.add_argument("--no-register", action="store_true",
                        help="Don't update boards/__init__.py")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose/debug output")

    args = parser.parse_args()

    pdf_path = pathlib.Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Parse the PDF
    print(f"\n  Parsing: {pdf_path.name} …")
    info = parse_datasheet(str(pdf_path), verbose=args.verbose)

    # Show summary
    _print_summary(info)

    if args.dry_run:
        print("  (dry-run mode — no files written)")
        return

    # Validate we have data
    if not info.packages:
        print("  Error: No package pin-out data could be extracted.", file=sys.stderr)
        print("  The PDF format might not be supported yet.", file=sys.stderr)
        print("  Try using --verbose to see parsing details.", file=sys.stderr)
        sys.exit(1)

    if not info.pin_mux:
        print("  Warning: No pin-mux data found. Generated files will have",
              file=sys.stderr)
        print("  empty alt-function lists — you'll need to fill them in manually.",
              file=sys.stderr)
        resp = input("\n  Continue anyway? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            sys.exit(0)

    # Filter to requested package
    if args.package:
        pkg_filter = args.package.upper()
        matching = [p for p in info.packages
                    if p.name.upper() == pkg_filter
                    or p.name.upper().replace("-", "") == pkg_filter.replace("-", "")]
        if not matching:
            avail = ", ".join(p.name for p in info.packages)
            print(f"  Error: Package '{args.package}' not found. Available: {avail}",
                  file=sys.stderr)
            sys.exit(1)
        info.packages = matching

    # If multiple packages and interactive, let user choose
    if len(info.packages) > 1 and sys.stdin.isatty():
        selected = _interactive_package_select(info)
        info.packages = [info.packages[i] for i in selected]

    # Determine output directory
    if args.output:
        out_dir = pathlib.Path(args.output)
    else:
        out_dir = _HERE / "boards"

    # Generate
    print(f"  Generating {len(info.packages)} board file(s) → {out_dir}/\n")
    files = generate_board_files(
        info,
        output_dir=out_dir,
        board_name=args.board,
        dts_soc_include=args.dts_soc,
        dts_pinctrl_include=args.dts_pinctrl,
        pinctrl_header=args.pinctrl_header,
        register_in_init=not args.no_register,
    )

    if files:
        print(f"\n  Done! Generated {len(files)} file(s):")
        for f in files:
            print(f"    {f}")
    else:
        print("\n  No files were generated.")

    print()


if __name__ == "__main__":
    main()
