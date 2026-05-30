from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal


Backend = Literal["pyinstaller", "nuitka"]


class AppBuilder:
    """Small executable-builder wrapper for generated pyontrust apps.

    The interface intentionally matches the existing build_install-style usage in
    reference generator templates: callers configure an app, optionally attach
    dependency directories, then call ``build_installer()``.
    """

    def __init__(
        self,
        app_name: str = "YourAppName",
        app_path: str | os.PathLike[str] | None = None,
        main_script: str | os.PathLike[str] = "main.py",
        debug_info: bool = True,
        hide_console: bool = True,
        dist_folder: str | os.PathLike[str] = "dist",
        build_folder: str | os.PathLike[str] = "build",
        backend: Backend | None = None,
        icon_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self.app_name = app_name
        self.app_path = Path(app_path).resolve() if app_path is not None else None
        self.main_script = Path(main_script)
        self.debug_info = debug_info
        self.hide_console = hide_console
        self.dist_folder = Path(dist_folder)
        self.build_folder = Path(build_folder)
        self.icon_path = Path(icon_path).resolve() if icon_path is not None else None
        self.backend = self._normalize_backend(backend or os.environ.get("BUILD_BACKEND") or "pyinstaller")
        self.dry_run = _env_flag("PYONTRUST_BUILD_DRY_RUN")

        self.dependency_dirs: list[tuple[str, str]] = []
        self.pyinstaller_hidden_imports: list[str] = []
        self.nuitka_cmd: list[str] = []
        self.pyinstaller_cmd: list[str] = []

    @staticmethod
    def _normalize_backend(value: str) -> Backend:
        normalized = str(value).strip().lower()
        if normalized not in {"pyinstaller", "nuitka"}:
            raise ValueError(f"Unsupported backend: {value}")
        return normalized  # type: ignore[return-value]

    def _main_script_path(self) -> Path:
        if self.main_script.is_absolute():
            return self.main_script
        if self.app_path is not None:
            return (self.app_path / self.main_script).resolve()
        return self.main_script.resolve()

    def _dist_path(self) -> Path:
        return self._resolve_dir(self.dist_folder)

    def _build_path(self) -> Path:
        return self._resolve_dir(self.build_folder)

    def _resolve_dir(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        base_dir = self.app_path or self._main_script_path().parent
        return (base_dir / path).resolve()

    def get_version(self) -> str:
        """Read ``__version__`` from the entry script without importing it."""
        script_path = self._main_script_path()
        if not script_path.exists():
            return "unknown"

        tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value
        return "unknown"

    def _data_sep(self) -> str:
        return ";" if os.name == "nt" else ":"

    def _iter_existing_dependency_dirs(self) -> list[tuple[Path, str]]:
        entries: list[tuple[Path, str]] = []
        for source, destination in self.dependency_dirs:
            source_path = Path(source).resolve()
            if source_path.exists():
                entries.append((source_path, destination))
        return entries

    def generate_pyinstaller_command(self) -> list[str]:
        script_path = self._main_script_path()
        dist_path = self._dist_path()
        build_path = self._build_path()

        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            self.app_name,
            "--distpath",
            str(dist_path),
            "--workpath",
            str(build_path),
            "--specpath",
            str(build_path),
        ]
        if self.hide_console:
            command.append("--noconsole")
        if self.icon_path is not None:
            command.extend(["--icon", str(self.icon_path)])
        for hidden_import in self.pyinstaller_hidden_imports:
            command.extend(["--hidden-import", hidden_import])
        for source_path, destination in self._iter_existing_dependency_dirs():
            command.extend(["--add-data", f"{source_path}{self._data_sep()}{destination}"])

        command.append(str(script_path))
        self.pyinstaller_cmd = command
        return command

    def generate_nuitka_command(self) -> list[str]:
        script_path = self._main_script_path()
        dist_path = self._dist_path()
        build_path = self._build_path()

        command = [
            sys.executable,
            "-m",
            "nuitka",
            "--assume-yes-for-downloads",
            "--onefile",
            "--remove-output",
            f"--output-dir={dist_path}",
            f"--output-filename={self.app_name}.exe",
        ]
        if self.hide_console:
            command.append("--windows-console-mode=disable")
        if self.icon_path is not None:
            command.append(f"--windows-icon-from-ico={self.icon_path}")
        if self.debug_info:
            report_path = build_path / f"{self.app_name}.xml"
            command.append(f"--report={report_path}")
        for source_path, destination in self._iter_existing_dependency_dirs():
            command.append(f"--include-data-dir={source_path}={destination}")

        command.append(str(script_path))
        self.nuitka_cmd = command
        return command

    def run_command(self, command: list[str]) -> bool:
        if self.dry_run:
            print(json.dumps({"backend": self.backend, "command": command}))
            return True
        result = subprocess.run(command, check=False)
        return result.returncode == 0

    def build_installer(self) -> bool:
        version = self.get_version()
        if version == "unknown":
            raise ValueError(f"Could not determine __version__ from {self._main_script_path()}")

        self._dist_path().mkdir(parents=True, exist_ok=True)
        self._build_path().mkdir(parents=True, exist_ok=True)

        if self.backend == "pyinstaller":
            return self.run_command(self.generate_pyinstaller_command())
        return self.run_command(self.generate_nuitka_command())


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}