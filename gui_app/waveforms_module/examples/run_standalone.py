from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys


def _bootstrap_repo_src() -> None:
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[2]
    src = repo_root / "waveforms_module" / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _missing_deps_message(module: str, *, repo_root: pathlib.Path) -> str:
    return (
        f"Missing dependency: {module}\n\n"
        "Recommended dev run (PowerShell):\n"
        f"  Set-Location {repo_root}\n"
        "  python -m venv .venv-nicegui\n"
        "  .\\.venv-nicegui\\Scripts\\python -m pip install -U pip\n"
        "  .\\.venv-nicegui\\Scripts\\python -m pip install -r scripts\\requirements.txt\n"
        "  .\\.venv-nicegui\\Scripts\\python -m pip install -e waveforms_module\n"
        "  .\\.venv-nicegui\\Scripts\\python waveforms_module\\examples\\run_standalone.py\n"
        "\nOr run this script once with: --bootstrap\n"
    )


_bootstrap_repo_src()


def _venv_python(venv_dir: pathlib.Path) -> pathlib.Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _bootstrap_venv(*, venv_dir: pathlib.Path, repo_root: pathlib.Path) -> None:
    if sys.prefix != sys.base_prefix:
        return

    if not venv_dir.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

    py = _venv_python(venv_dir)
    if not py.exists():
        raise FileNotFoundError(str(py))

    subprocess.check_call([str(py), "-m", "pip", "install", "-U", "pip"])
    req = repo_root / "scripts" / "requirements.txt"
    if req.exists():
        subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(req)])
    subprocess.check_call([str(py), "-m", "pip", "install", "-e", str(repo_root / "waveforms_module")])


def _reexec_in_venv(*, venv_dir: pathlib.Path, argv: list[str]) -> None:
    py = _venv_python(venv_dir)
    env = dict(os.environ)
    subprocess.check_call([str(py), *argv], env=env)
    raise SystemExit(0)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--bootstrap", action="store_true", help="Create/use a venv, install deps, then run")
    p.add_argument("--venv", default=".venv-nicegui", help="Venv directory (default: .venv-nicegui)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = pathlib.Path(__file__).resolve().parents[2]

    if args.bootstrap and sys.prefix == sys.base_prefix:
        venv_arg = pathlib.Path(str(args.venv))
        venv_dir = (repo_root / venv_arg).resolve() if not venv_arg.is_absolute() else venv_arg
        try:
            _bootstrap_venv(venv_dir=venv_dir, repo_root=repo_root)
            argv = [str(__file__), "--venv", str(args.venv)]
            _reexec_in_venv(venv_dir=venv_dir, argv=argv)
        except Exception as exc:  # noqa: BLE001
            print(f"Bootstrap failed: {exc!r}", file=sys.stderr)
            print(_missing_deps_message("nicegui/pyontrust_waveforms", repo_root=repo_root), file=sys.stderr)
            raise SystemExit(1)

    try:
        from nicegui import ui
    except ModuleNotFoundError as exc:  # pragma: no cover
        if exc.name != "nicegui":
            raise
        print(_missing_deps_message("nicegui", repo_root=repo_root), file=sys.stderr)
        raise SystemExit(1)

    try:
        from pyontrust_waveforms import WaveformsConfig, WaveformsModule
        from pyontrust_waveforms.hal.simulated import SimulatedHal  # registers plugin
    except ModuleNotFoundError as exc:  # pragma: no cover
        print(_missing_deps_message(exc.name or "pyontrust_waveforms", repo_root=repo_root), file=sys.stderr)
        raise SystemExit(1)

    config = WaveformsConfig()
    with ui.column().classes("w-full") as root:
        handle = WaveformsModule.mount(root, config=config)
    ui.run(title="Waveforms Module (Standalone)")


if __name__ in {"__main__", "__mp_main__"}:
    main()
