# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2025 Pyontrust Contributors
"""
Release archive generator with SPDX BOM.

Inspired by the Swedish Embedded SDK `scripts/release` pattern.
Generates a release archive containing:
  - Compiled firmware (zephyr.elf, zephyr.bin, zephyr.hex)
  - Build config (.config)
  - SPDX Bill of Materials (via `west spdx`)
  - Version information

Usage:
    python scripts/release.py --board lp_mspm0g3507 --source apps/locator_base
    python scripts/release.py --board lp_mspm0g3507 --source . --build-dir build/
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path


def read_version(version_file: Path) -> str:
    """Read version from VERSION file."""
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


def run_cmd(cmd: list[str], cwd: str | Path = ".") -> int:
    """Run a shell command, printing output in real-time."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Generate a release archive with SPDX BOM",
    )
    parser.add_argument(
        "-b", "--board",
        required=True,
        help="Target board (e.g. lp_mspm0g3507)",
    )
    parser.add_argument(
        "-s", "--source",
        required=True,
        help="Source directory of the application",
    )
    parser.add_argument(
        "-d", "--build-dir",
        default="",
        help="Build directory (auto-generated if not specified)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="release",
        help="Output directory for the archive (default: release/)",
    )
    parser.add_argument(
        "--skip-spdx",
        action="store_true",
        help="Skip SPDX BOM generation",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip building (use existing build artifacts)",
    )
    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    pkg_dir = script_dir.parent
    version_file = pkg_dir / "VERSION"
    version = read_version(version_file)

    source_dir = Path(args.source).resolve()
    if not source_dir.is_dir():
        print(f"Error: source directory not found: {source_dir}")
        return 1

    # Build directory naming (follows SE-SDK convention)
    if args.build_dir:
        build_dir = Path(args.build_dir).resolve()
    else:
        build_dir = Path(f"build-release/{args.board}").resolve()

    build_dir.mkdir(parents=True, exist_ok=True)

    # Output directory
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Archive name: <app>-<board>-<version>.tar.gz
    app_name = source_dir.name
    archive_name = f"{app_name}-{args.board}-{version}"
    archive_path = output_dir / f"{archive_name}.tar.gz"

    print(f"\n{'='*60}")
    print(f"  Pyontrust Release Builder")
    print(f"  Version:   {version}")
    print(f"  Board:     {args.board}")
    print(f"  Source:    {source_dir}")
    print(f"  Build:     {build_dir}")
    print(f"  Archive:   {archive_path}")
    print(f"{'='*60}\n")

    # Step 1: Initialize SPDX
    if not args.skip_spdx:
        print("[1/4] Initializing SPDX...")
        rc = run_cmd(["west", "spdx", "--init", "-d", str(build_dir)])
        if rc != 0:
            print("  Warning: SPDX init failed (continuing without SPDX)")

    # Step 2: Build
    if not args.skip_build:
        print("[2/4] Building firmware...")
        rc = run_cmd([
            "west", "build",
            "-d", str(build_dir),
            "-b", args.board,
            "-s", str(source_dir),
        ])
        if rc != 0:
            print("Error: Build failed")
            return 1
    else:
        print("[2/4] Skipping build (--skip-build)")

    # Step 3: Generate SPDX
    if not args.skip_spdx:
        print("[3/4] Generating SPDX BOM...")
        rc = run_cmd(["west", "spdx", "-d", str(build_dir)])
        if rc != 0:
            print("  Warning: SPDX generation failed (continuing)")

    # Step 4: Package release
    print("[4/4] Creating release archive...")

    release_dir = build_dir / "release"
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)

    # Copy firmware artifacts
    zephyr_dir = build_dir / "zephyr"
    for pattern in ["zephyr.elf", "zephyr.bin", "zephyr.hex", "zephyr.map",
                     "zephyr.dts", "zephyr.stat"]:
        src = zephyr_dir / pattern
        if src.exists():
            shutil.copy2(src, release_dir / pattern)
            print(f"  + {pattern}")

    # Copy build config
    config_file = zephyr_dir / ".config"
    if config_file.exists():
        shutil.copy2(config_file, release_dir / ".config")
        print("  + .config")

    # Copy SPDX directory
    spdx_dir = build_dir / "spdx"
    if spdx_dir.is_dir():
        shutil.copytree(spdx_dir, release_dir / "spdx")
        print("  + spdx/")

    # Write version info
    (release_dir / "VERSION").write_text(f"{version}\n")
    (release_dir / "BUILD_INFO").write_text(
        f"version={version}\n"
        f"board={args.board}\n"
        f"source={source_dir}\n"
        f"date={datetime.now().isoformat()}\n"
    )
    print("  + VERSION, BUILD_INFO")

    # Create tar.gz archive
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(release_dir, arcname=archive_name)

    archive_size = archive_path.stat().st_size
    print(f"\n  Release archive: {archive_path}")
    print(f"  Size: {archive_size / 1024:.1f} KB")
    print(f"\n  Done!\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
