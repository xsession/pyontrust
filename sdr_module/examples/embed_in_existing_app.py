from nicegui import ui

from pyontrust_sdr import SdrModule


@ui.page("/")
def index() -> None:
    ui.label("Existing app")
    with ui.expansion("SDR", value=True).classes("w-full"):
        SdrModule.mount(ui.column().classes("w-full"), config=None)


def main() -> None:
    ui.run(title="Existing App + SDR")


if __name__ in {"__main__", "__mp_main__"}:
    main()
