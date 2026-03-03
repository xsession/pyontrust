from __future__ import annotations

import threading
from typing import Optional

from nicegui import ui

from ..config import GnuradioConfig
from ..errors import RunnerError
from ..runner import RunSpec, build_command


class GnuradioView:
    def __init__(self, *, handle, config: GnuradioConfig) -> None:
        self._handle = handle
        self._config = config
        self._log: Optional[ui.log] = None

    def mount(self, container) -> None:
        with container:
            with ui.row().classes("w-full"):
                with ui.column().classes("w-96"):
                    ui.label("GNU Radio").classes("text-lg")

                    self._mode = ui.select(
                        options={"current": "current python", "python": "external python", "conda": "conda env"},
                        value="current",
                        label="Run mode",
                    )
                    self._python = ui.input(label="Python executable", value=self._config.default_python)
                    self._conda_env = ui.input(label="Conda env name", value=self._config.default_conda_env)
                    self._path = ui.input(label="Flowgraph (.py or .grc)", value="").classes("w-full")
                    self._args = ui.input(label="Args", value="").classes("w-full")

                    with ui.row().classes("w-full"):
                        ui.button("Run", on_click=self._run).props("color=primary")
                        ui.button("Stop", on_click=self._stop).props("outline")

                    ui.separator()
                    ui.label("In-process availability:").classes("text-sm")
                    try:
                        import gnuradio  # type: ignore

                        ui.label(f"gnuradio import OK: {getattr(gnuradio, '__version__', '(unknown)')}").classes("text-xs")
                    except Exception as exc:  # noqa: BLE001
                        ui.label(f"gnuradio import failed: {exc!r}").classes("text-xs text-gray-600")

                with ui.column().classes("grow"):
                    ui.label("Runner output").classes("text-sm")
                    self._log = ui.log(max_lines=2000).classes("w-full")

    def _stop(self) -> None:
        self._handle.stop()
        ui.notify("Stopped", type="positive")

    def _run(self) -> None:
        if self._log is None:
            return

        spec = RunSpec(
            mode=str(self._mode.value),
            python_exe=str(self._python.value or "python"),
            conda_env=str(self._conda_env.value or "gnuradio"),
            flowgraph_path=str(self._path.value or "").strip(),
            extra_args=str(self._args.value or ""),
        )

        try:
            cmd, generated = build_command(spec)
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Cannot build command: {exc}", type="negative")
            return

        self._log.push("$ " + " ".join(cmd))

        try:
            proc = start_process(cmd, generated=generated)
        except RunnerError as exc:
            ui.notify(str(exc), type="negative")
            return

        self._handle._proc = proc

        def _reader() -> None:
            assert proc is not None
            p = proc._popen  # noqa: SLF001
            if p.stdout is None:
                return
            for line in p.stdout:
                if self._log is not None:
                    self._log.push(line.rstrip("\n"))
            rc = p.poll()
            if rc is not None and self._log is not None:
                self._log.push(f"[exit] rc={rc}")

        threading.Thread(target=_reader, daemon=True).start()
