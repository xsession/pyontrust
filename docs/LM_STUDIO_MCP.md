# LM Studio MCP Setup

This repository now includes a local stdio MCP server for pyontrust and the purple-view pin configurator.

## Install

From the repository root:

```powershell
python -m pip install -e .[mcp]
```

If you also use the pin configurator UI locally, keep its existing dependencies installed as well.

## Run The MCP Server Manually

Either command works from the repo root:

```powershell
python mcp_server.py
```

```powershell
pyontrust-mcp
```

The server uses stdio transport, which is the safest default for LM Studio and agent-style MCP clients.

## Tools Exposed

- `list_pin_configurator_boards`
- `get_pin_configurator_board`
- `scan_zephyr_pin_project`
- `preview_zephyr_pin_import`
- `generate_arduino_from_zephyr_project`
- `export_generated_arduino_files`

The key end-to-end tool is `generate_arduino_from_zephyr_project`. It scans a Zephyr app, parses its overlay and `prj.conf`, maps the result back onto the selected pin-configurator board definition, generates Zephyr, Arduino, and bare-metal outputs, and can optionally export the Arduino sketch folder in one call.

Use `import_board_name` when the Zephyr project board target differs from the pin-configurator `board_id` you want to generate against.

## LM Studio Configuration

In LM Studio, add a custom MCP server that launches the command below from the repository root:

```powershell
python mcp_server.py
```

If your LM Studio build accepts JSON-based MCP definitions, the common shape is:

```json
{
  "mcpServers": {
    "pyontrust": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "C:/GIT/addmind/deps/pyontrust"
    }
  }
}
```

Use the repository root as `cwd` so the server can resolve the pin configurator modules under `externals/pin_configurator`.

## Hermes Agent Wiring

If your Hermes agent runtime can consume MCP servers, point it at the same stdio command:

```powershell
python mcp_server.py
```

The useful first workflow for Hermes is:

1. `scan_zephyr_pin_project`
2. `preview_zephyr_pin_import`
3. `generate_arduino_from_zephyr_project`

For direct export, pass both `output_dir` and `sketch_name` to `generate_arduino_from_zephyr_project`.

## Example MCP Call

Example arguments for converting a Zephyr app into an Arduino sketch folder:

```json
{
  "project_path": "C:/GIT/WORK/codelayer/locator_base/apps/locator_base",
  "board_id": "lp_mspm0g3507",
  "import_board_name": "nrf9160dk_nrf9160_ns",
  "output_dir": "C:/GIT/WORK/arduino/locator_base_bridge",
  "sketch_name": "locator_base_bridge"
}
```

## Notes

- The MCP server does not need the Flask UI running.
- The server resolves board metadata directly from the pin configurator registry.
- Arduino export writes the primary `.ino` file using the requested sketch name or the output folder name.