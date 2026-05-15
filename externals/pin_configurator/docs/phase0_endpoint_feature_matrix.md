# Phase 0 Endpoint-to-Feature Matrix

This matrix records the current backend surface and the frontend feature areas that depend on it. The point is not to document every implementation detail, but to make route ownership explicit before the frontend is reorganized.

## App Shell and Board Context

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/` | `GET` | browser shell | Serve `web/index.html` and boot the current UI |
| `/api/boards` | `GET` | main shell, peripheral flows | List available boards |
| `/api/board/<name>` | `GET` | main shell | Load full board definition for the selected board |
| `/favicon.ico` | `GET` | browser | Quiet favicon route |

## Project Persistence and Output Generation

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/generate` | `POST` | configurator tab | Generate DTS overlay, `prj.conf`, and target artifacts |
| `/api/save-project` | `POST` | save-to-project action | Write generated outputs into a Zephyr project tree |
| `/api/project-file/save` | `POST` | project save flow | Save `.zpinproj`-style project document |
| `/api/project-file/load` | `POST` | project load flow | Load project document back into the UI |
| `/api/demo-app/export` | `POST` | demo export flow | Materialize demo Zephyr app plus Renode/test artifacts |
| `/api/path-dialog` | `POST` | save/load/import flows | Open native file or directory picker |

## Board Editor

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/board-editor/drafts` | `GET` | board editor tab | List saved draft boards |
| `/api/board-editor/draft/<filename>` | `GET` | board editor tab | Load a specific draft board |
| `/api/board-editor/save` | `POST` | board editor tab | Save a draft board definition |
| `/api/board-editor/delete` | `POST` | board editor tab | Delete a saved draft |

## LVGL

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/lvgl/import` | `POST` | LVGL tab | Import LVGL source/layout input |
| `/api/lvgl/export` | `POST` | LVGL tab | Export LVGL layout and generated artifacts |

## Zephyr Catalog and Modules

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/zephyr/catalog` | `GET` | Zephyr catalog tab | Discover MCUs and sensors from a Zephyr tree |
| `/api/modules` | `GET` | modules tab | Load module definitions |
| `/api/generate-module-config` | `POST` | modules tab | Generate module-related config fragments |

## Peripheral and Clock Domains

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/peripheral-templates` | `GET` | peripherals tab | List peripheral templates |
| `/api/peripheral-instances/<board_name>` | `GET` | peripherals tab | Load board-specific peripheral instances |
| `/api/generate-peripheral-config` | `POST` | peripherals tab | Generate overlay/conf for peripheral configuration |
| `/api/clock-trees` | `GET` | clock tab | List supported clock trees |
| `/api/clock-tree/<tree_id>` | `GET` | clock tab | Load a specific clock tree definition |
| `/api/clock-frequencies` | `POST` | clock tab | Calculate derived frequencies |
| `/api/generate-clock-config` | `POST` | clock tab | Generate overlay/conf for clock settings |

## Import and Project Scanning

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/import-config` | `POST` | import flow | Parse imported overlay/conf into frontend-friendly state |
| `/api/scan-project` | `POST` | import flow | Inspect a project tree for relevant config files |

## PDF, Package, and MCU Workflows

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/parse-pdf` | `POST` | packages tab | Parse MCU package datasheet PDF |
| `/api/parse-jobs` | `GET` | packages tab | Inspect current parse jobs |
| `/api/generate-package` | `POST` | packages tab | Generate board/package files from parsed data |
| `/api/generated-packages` | `GET` | packages tab | List generated board packages |
| `/api/identify-mcu` | `POST` | package/import helpers | Identify probable MCU vendor or family |
| `/api/fetch-datasheet` | `POST` | package/import helpers | Search or fetch a datasheet |

## Driver and Sensor Workflows

| Route | Methods | Current consumer | Purpose |
| --- | --- | --- | --- |
| `/api/driver-templates` | `GET` | driver generation flows | List driver templates |
| `/api/generate-driver` | `POST` | driver generation flows | Generate Zephyr driver boilerplate |
| `/api/parse-sensor-pdf` | `POST` | sensors tab | Parse a sensor datasheet |
| `/api/sensor-jobs` | `GET` | sensors tab | List sensor parsing jobs |
| `/api/sensor-job/<job_id>` | `GET` | sensors tab | Get parsed sensor-job data |
| `/api/sensor-job/<job_id>/header` | `GET` | sensors tab | Generate register header from job |
| `/api/sensor-job/<job_id>/driver` | `POST` | sensors tab | Generate complete driver from sensor job |
| `/api/identify-sensor` | `POST` | sensors tab | Identify sensor/vendor from user input |

## Migration Implications

- The new frontend must preserve these route contracts while the UI architecture changes.
- Persistence, generation, demo export, LVGL, and catalog flows already have stable backend seams and should be migrated to typed frontend services instead of being rewritten.
- Later frontend phases should treat this matrix as the contract surface that presenters and service modules must formalize.