from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys


def _bootstrap_repo_src() -> None:
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[2]
    src = repo_root / "gnuradio_module" / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


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
    subprocess.check_call([str(py), "-m", "pip", "install", "-e", str(repo_root / "gnuradio_module")])


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
        _bootstrap_venv(venv_dir=venv_dir, repo_root=repo_root)
        argv = [str(__file__), "--venv", str(args.venv)]
        _reexec_in_venv(venv_dir=venv_dir, argv=argv)

    from nicegui import ui  # noqa: E402
    from pyontrust_gnuradio import GnuradioModule  # noqa: E402

    ui.page_title("Pyontrust GNU Radio")
    with ui.column().classes("w-full"):
        GnuradioModule.mount(ui.column().classes("w-full"))
    ui.run(title="Pyontrust GNU Radio", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
