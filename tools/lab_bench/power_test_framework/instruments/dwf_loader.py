from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Optional


def _repo_root() -> Path:
    # instruments/ -> power_test_framework/ -> pyontrust_packages/ -> repo root
    return Path(__file__).resolve().parents[3]


def candidate_dwf_library_paths(
    *,
    platform: str | None = None,
    env: dict[str, str] | None = None,
    repo_root: Path | None = None,
) -> Iterable[Path]:
    """Yield plausible DWF library locations.

    Order matters: earlier paths are preferred.
    """

    platform = sys.platform if platform is None else platform
    env = os.environ if env is None else env
    repo_root = _repo_root() if repo_root is None else repo_root

    env_hint = env.get("DWF_LIB_PATH")
    if env_hint:
        yield Path(env_hint)

    if platform.startswith("win"):
        # Typical install locations.
        program_files = [
            env.get("ProgramFiles"),
            env.get("ProgramFiles(x86)"),
        ]
        for base in [p for p in program_files if p]:
            base_path = Path(base)
            for rel in [
                Path("Digilent") / "WaveFormsSDK" / "lib" / "x64" / "dwf.dll",
                Path("Digilent") / "WaveFormsSDK" / "lib" / "x86" / "dwf.dll",
                Path("Digilent") / "WaveForms" / "dwf.dll",
                Path("Digilent") / "WaveForms" / "dwf.dll",
            ]:
                yield base_path / rel

        # Fallback: rely on PATH search (ctypes will find it if available).
        # We return a sentinel-like relative name for callers that want to try it.
        yield Path("dwf.dll")
        return

    # Linux: prefer vendored SDK in this repo if present.
    vendored = repo_root / "externals" / "WaveformSDK_linux" / "usr" / "lib"
    yield vendored / "libdwf.so"
    yield vendored / "libdwf.so.3"

    # Typical system installs.
    yield Path("/usr/lib/libdwf.so")
    yield Path("/usr/local/lib/libdwf.so")

    # Fallback: rely on loader paths.
    yield Path("libdwf.so")


def find_dwf_library(
    *,
    platform: str | None = None,
    env: dict[str, str] | None = None,
    repo_root: Path | None = None,
) -> Optional[Path]:
    for p in candidate_dwf_library_paths(platform=platform, env=env, repo_root=repo_root):
        # For relative fallbacks like "dwf.dll" / "libdwf.so", we can't validate existence.
        if not p.is_absolute():
            return p
        if p.exists():
            return p
    return None


def load_dwf():
    """Load and return the DWF shared library (ctypes CDLL/WinDLL object).

    Raises a RuntimeError with a helpful message if it cannot be loaded.
    """

    import ctypes

    lib = find_dwf_library()
    if lib is None:
        raise RuntimeError(
            "DWF library not found. Set DWF_LIB_PATH to dwf.dll/libdwf.so, or install Digilent WaveForms."  # noqa: E501
        )

    try:
        if sys.platform.startswith("win"):
            # Ensure dependency resolution for absolute paths (Python 3.8+).
            if lib.is_absolute() and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(lib.parent))
            # WinDLL uses stdcall; Digilent examples often use cdll.dwf; WinDLL is safer.
            return ctypes.WinDLL(str(lib))

        # Linux: if using vendored SDK, prepend its folder so dependencies can resolve.
        if lib.is_absolute():
            lib_dir = str(lib.parent)
            cur = os.environ.get("LD_LIBRARY_PATH", "")
            if cur:
                if lib_dir not in cur.split(":"):
                    os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{cur}"
            else:
                os.environ["LD_LIBRARY_PATH"] = lib_dir

        return ctypes.CDLL(str(lib))
    except OSError as exc:
        raise RuntimeError(f"Failed to load DWF library from '{lib}': {exc}") from exc
