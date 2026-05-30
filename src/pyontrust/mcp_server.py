"""MCP server exposing pyontrust and pin configurator tools to local agents."""

from __future__ import annotations

import importlib
import pathlib
import sys
from typing import Any


_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PIN_CONFIGURATOR = _ROOT / "externals" / "pin_configurator"
for candidate in (_ROOT / "src", _PIN_CONFIGURATOR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
except ImportError as exc:  # pragma: no cover - import failure handled at runtime
    FastMCP = None
    _MCP_IMPORT_ERROR = exc
else:
    _MCP_IMPORT_ERROR = None


_board_schema = importlib.import_module("board_schema")
_boards = importlib.import_module("boards")
_project_bridge = importlib.import_module("project_bridge")

board_to_frontend = _board_schema.board_to_frontend
BOARDS = _boards.BOARDS
describe_generated_output = _project_bridge.describe_generated_output
export_generated_target = _project_bridge.export_generated_target
generate_from_import = _project_bridge.generate_from_import
get_board_definition = _project_bridge.get_board_definition
import_zephyr_project = _project_bridge.import_zephyr_project
scan_zephyr_project = _project_bridge.scan_zephyr_project


def _require_mcp() -> None:
    if FastMCP is None:
        raise RuntimeError(
            "The optional MCP dependency is not installed. Install it with `pip install -e .[mcp]`."
        ) from _MCP_IMPORT_ERROR


def _board_summary(board_id: str) -> dict[str, Any]:
    board = get_board_definition(board_id)
    if board is None:
        raise KeyError(f"Unknown board: {board_id}")
    payload = board_to_frontend(board)
    return {
        "id": board_id,
        "board": payload.get("board", ""),
        "soc": payload.get("soc", ""),
        "package": payload.get("package", ""),
        "pin_count": payload.get("pin_count", 0),
        "peripheral_count": len(payload.get("peripherals", [])),
        "output_targets": [target.get("kind", "") for target in payload.get("output_targets", [])],
    }


def create_server() -> Any:
    _require_mcp()
    server = FastMCP("pyontrust")

    @server.tool()
    def list_pin_configurator_boards() -> list[dict[str, Any]]:
        """List available pin configurator boards with brief metadata."""
        return [_board_summary(board_id) for board_id in sorted(BOARDS)]

    @server.tool()
    def get_pin_configurator_board(board_id: str) -> dict[str, Any]:
        """Return the full frontend board definition for a board id."""
        board = get_board_definition(board_id)
        if board is None:
            raise ValueError(f"Unknown board: {board_id}")
        return board_to_frontend(board)

    @server.tool()
    def scan_zephyr_pin_project(project_path: str) -> dict[str, Any]:
        """Scan a Zephyr app directory and return importable overlay/conf files."""
        files = scan_zephyr_project(project_path)
        return {
            "project_path": str(pathlib.Path(project_path).resolve()),
            "files": files,
        }

    @server.tool()
    def preview_zephyr_pin_import(project_path: str, board_name: str = "",
                                  overlay_paths: list[str] | None = None,
                                  conf_paths: list[str] | None = None) -> dict[str, Any]:
        """Parse Zephyr overlay/conf files and return normalized import data."""
        preview = import_zephyr_project(
            project_path,
            board_name=board_name,
            overlay_paths=overlay_paths,
            conf_paths=conf_paths,
        )
        return {
            "project_path": str(pathlib.Path(project_path).resolve()),
            "selected_overlay_paths": preview["selected_overlay_paths"],
            "selected_conf_paths": preview["selected_conf_paths"],
            "import": preview["import"],
        }

    @server.tool()
    def generate_arduino_from_zephyr_project(project_path: str, board_id: str,
                                             import_board_name: str = "",
                                             output_dir: str = "", sketch_name: str = "",
                                             overlay_paths: list[str] | None = None,
                                             conf_paths: list[str] | None = None) -> dict[str, Any]:
        """Generate Arduino-ready files from a Zephyr project and optionally export them."""
        preview = import_zephyr_project(
            project_path,
            board_name=import_board_name,
            overlay_paths=overlay_paths,
            conf_paths=conf_paths,
        )
        generated = generate_from_import(board_id, preview["import"], targets=["zephyr", "arduino", "baremetal"])
        result: dict[str, Any] = {
            "project_path": str(pathlib.Path(project_path).resolve()),
            "board_id": board_id,
            "import_board_name": import_board_name,
            "selected_overlay_paths": preview["selected_overlay_paths"],
            "selected_conf_paths": preview["selected_conf_paths"],
            "import": preview["import"],
            "generated": describe_generated_output(generated),
        }
        if output_dir:
            exported = export_generated_target(output_dir, generated.targets.get("arduino", {}), sketch_name=sketch_name)
            result["exported"] = {
                "output_dir": str(pathlib.Path(output_dir).resolve()),
                "files": exported,
            }
        return result

    @server.tool()
    def export_generated_arduino_files(output_dir: str, files: dict[str, str], sketch_name: str = "") -> dict[str, Any]:
        """Write already generated Arduino files into a sketch directory."""
        written = export_generated_target(output_dir, files, sketch_name=sketch_name)
        return {
            "output_dir": str(pathlib.Path(output_dir).resolve()),
            "files": written,
        }

    return server


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()