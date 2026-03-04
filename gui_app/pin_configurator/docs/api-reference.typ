// ─────────────────────────────────────────────────────────────────────────────
// Zephyr Pin Configurator — REST API Reference (standalone)
// ─────────────────────────────────────────────────────────────────────────────

#import "template.typ": *

#show: doc => enterprise-doc(
  title: "REST API Reference",
  subtitle: "Zephyr Pin Configurator",
  version: "0.1.0",
  date: datetime(year: 2026, month: 3, day: 4),
  doc,
)

= Overview

Base URL: `http://<host>:<port>` (default `http://127.0.0.1:5100`).

All endpoints return `application/json`. Errors use HTTP 4xx/5xx with:
```json
{ "error": "<human-readable message>" }
```

= Convention

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 8pt,
  [*Convention*],       [*Detail*],
  [Content-Type],       [`application/json` unless noted (multipart for uploads)],
  [Authentication],     [None (local tool — add reverse proxy authN for remote)],
  [Pagination],         [Not implemented — data sets are bounded],
  [Versioning],         [Implicit v1 — future `/api/v2/` prefix planned],
  [CORS],               [Not configured — add `flask-cors` for cross-origin],
)


= Board Endpoints

== `GET /api/boards`

List all registered board identifiers.

*Response* `200`:
```json
{ "boards": ["mspm0g3507", "stm32l476_lqfp64", …] }
```

== `GET /api/board/<name>`

Full board definition.

#param-table(
  ("name", "path", "string", "true", "Board ID from /api/boards"),
)

*Response* `200` — `BoardDef` JSON:

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 6pt,
  [*Field*], [*Type*], [*Description*],
  [`soc`], [string], [SoC identifier],
  [`board`], [string], [Board name for DTS],
  [`vendor`], [string], [Vendor slug],
  [`package`], [string], [IC package type],
  [`pin_count`], [int], [Total number of pins],
  [`pins`], [array], [Array of Pin objects with `alt_functions`],
  [`peripherals`], [array], [Array of Peripheral objects],
  [`flash_size_kb`], [int], [Flash size in KiB],
  [`sram_size_kb`], [int], [SRAM size in KiB],
  [`clock_hz`], [int], [Default system clock frequency],
)

*Error* `404`:
```json
{ "error": "Board 'xyz' not found" }
```


= Generation Endpoints

== `POST /api/generate`

Generate DTS overlay and `prj.conf` from pin assignments.

*Request body:*

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 6pt,
  [*Field*], [*Type*], [*Description*],
  [`board`], [string], [Board identifier],
  [`assignments`], [array], [Array of PinAssignment objects],
  [`peripherals`], [array], [Array of PeripheralConfig objects],
)

*PinAssignment object:*

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 6pt,
  [*Field*], [*Type*], [*Required*], [*Description*],
  [`pin_name`], [string], [yes], [Pin name ("PA10")],
  [`pincm`], [int], [yes], [PINCM register index],
  [`function_id`], [int], [yes], [Alternate function index],
  [`af_name`], [string], [yes], [AF display name ("UART0_TX")],
  [`peripheral`], [string], [yes], [Parent peripheral],
  [`signal`], [string], [yes], [Signal name ("TX")],
  [`direction`], [string], [yes], ["in" / "out" / "inout"],
  [`bias_pull_up`], [bool], [no], [Enable pull-up (default false)],
  [`bias_pull_down`], [bool], [no], [Enable pull-down],
  [`drive_open_drain`], [bool], [no], [Open-drain mode],
  [`input_enable`], [bool], [no], [Enable input buffer],
)

*Response* `200`:
```json
{
  "overlay": "&pinctrl { … };",
  "prj_conf": "CONFIG_SERIAL=y\n…"
}
```

== `POST /api/save-project`

Write generated overlay and `prj.conf` to a Zephyr project directory.

*Request body:*

#table(
  columns: (auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 6pt,
  [*Field*], [*Type*], [*Description*],
  [`project_dir`], [string], [Absolute path to Zephyr project root],
  [`board`], [string], [Board identifier (used for filename)],
  [`overlay`], [string], [DTS overlay text],
  [`prj_conf`], [string], [prj.conf text],
)

== `POST /api/project-file/save`

Save full editor state to `.zpinproj` JSON file.

*Request:*
```json
{
  "path": "/path/to/project.zpinproj",
  "state": {
    "board_id": "stm32l476_lqfp64",
    "pin_states": { … },
    "periph_states": { … },
    "generated_overlay": "…",
    "generated_conf": "…"
  }
}
```

== `POST /api/project-file/load`

Load `.zpinproj` file. Auto-appends extension if missing.

*Request:*
```json
{ "path": "/path/to/project.zpinproj" }
```

*Response:* The full state object as stored, with `"version": 1`.


= Datasheet Parsing Endpoints

== `POST /api/parse-pdf`

Upload and parse an MCU datasheet. Content-Type: `multipart/form-data`.

#table(
  columns: (auto, auto, auto, 1fr),
  stroke: 0.5pt + luma(200),
  inset: 6pt,
  [*Field*], [*Type*], [*Required*], [*Description*],
  [`file`], [file], [yes], [PDF file (max 100 MB)],
  [`verbose`], [string], [no], [`"true"` to enable debug output],
)

*Response* `200`:
```json
{
  "job_id": "abc123…",
  "status": "complete",
  "device": "STM32L476xx",
  "vendor": "stm32",
  "packages": ["LQFP64", "LQFP100", "LQFP144"],
  "pin_count": 64,
  "pin_mux_entries": 128
}
```

== `POST /api/generate-package`

Generate board Python file from parsed PDF data.

*Request:*
```json
{
  "job_id": "abc123…",
  "package": "LQFP64",
  "board": "stm32l476",
  "dts_soc": "st/stm32/stm32l476xx",
  "dts_pinctrl": "st,stm32-pinctrl"
}
```

== `GET /api/parse-jobs`

List all active PDF parse jobs.

== `GET /api/generated-packages`

List all board `.py` files in the `boards/` directory.


= MCU Identification Endpoints

== `POST /api/identify-mcu`

Identify vendor from MCU part number.

*Request:*
```json
{ "part_number": "STM32L476RGT6" }
```

*Response:*
```json
{
  "vendor": "stm32",
  "vendor_name": "STMicroelectronics",
  "family": "STM32",
  "part_number": "STM32L476RGT6",
  "datasheet_urls": ["https://…"]
}
```

== `POST /api/fetch-datasheet`

Download datasheet by part number and parse it.

*Request:*
```json
{ "part_number": "STM32L476RGT6", "url": null }
```


= Module & Kconfig Endpoints

== `GET /api/modules`

Returns all 27 Zephyr module definitions with options.

== `POST /api/generate-module-config`

Generate `prj.conf` from module selections.

*Request:*
```json
{
  "modules": {
    "bluetooth": { "CONFIG_BT": true, "CONFIG_BT_PERIPHERAL": true },
    "logging": { "CONFIG_LOG": true }
  }
}
```

*Response:*
```json
{
  "prj_conf": "CONFIG_BT=y\nCONFIG_BT_PERIPHERAL=y\nCONFIG_LOG=y\n"
}
```


= Peripheral Configuration Endpoints

== `GET /api/peripheral-templates`

Returns all peripheral configuration templates.

== `GET /api/peripheral-instances/<board>`

Board peripherals merged with matching templates.

== `POST /api/generate-peripheral-config`

Generate DTS + prj.conf from peripheral configuration.

*Request:*
```json
{
  "instances": [
    {
      "peripheral": "UART0",
      "template_id": "uart",
      "values": { "baudrate": 115200, "parity": "none" }
    }
  ],
  "board_peripherals": []
}
```


= Clock Configuration Endpoints

== `GET /api/clock-trees`

Summary list of clock trees. Response includes `id`, `name`, `max_freq_mhz`.

== `GET /api/clock-tree/<id>`

Full definition with nodes, connections, props, kconfig, peripheral clocks.

== `POST /api/clock-frequencies`

Compute frequencies from user values.

*Request:*
```json
{ "tree_id": "stm32_generic", "values": { "hse_freq": 8000000, "pll_m": 4, "pll_n": 170, "pll_r": 2 } }
```

== `POST /api/generate-clock-config`

Generate clock overlay + prj.conf + computed frequencies.


= Import & Scan Endpoints

== `POST /api/import-config`

Parse existing overlay + prj.conf into UI state.

*Request:*
```json
{
  "overlay": "&pinctrl { … };",
  "conf": "CONFIG_SERIAL=y",
  "board_name": "stm32l476_lqfp64"
}
```

== `POST /api/scan-project`

Scan directory for overlay/conf files.

*Request:*
```json
{ "project_dir": "/path/to/zephyr-app" }
```


= Driver Generation Endpoints

== `GET /api/driver-templates`

List driver scaffolding templates (sensor, gpio, custom, …).

== `POST /api/generate-driver`

Generate complete driver package.

*Request:* See `DriverSpec` schema.

*Response:* `GeneratedDriver` — `source_c`, `header_h`, `kconfig`, `cmake`,
`overlay_sample`, `prj_conf_sample`, `readme`, `test_c`.


= Sensor Parsing Endpoints

== `POST /api/parse-sensor-pdf`

Parse sensor datasheet PDF for register maps.

== `GET /api/sensor-jobs` / `GET /api/sensor-job/<id>`

List or retrieve parsed sensor data.

== `GET /api/sensor-job/<id>/header`

Generate C register header from parsed sensor.

== `POST /api/sensor-job/<id>/driver`

Generate Zephyr sensor driver from parsed data.

== `POST /api/identify-sensor`

Identify sensor vendor from part number.

*Request:*
```json
{ "part_number": "BMP280" }
```
