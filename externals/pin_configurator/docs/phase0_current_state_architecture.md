# Phase 0 Current-State Architecture

This note captures the current runtime architecture of `pin_configurator` before the frontend refactor begins. It is intended to give Phase 1 and later phases a stable baseline for what exists today and where behavior is currently controlled.

## Runtime Topology

### Backend authority

- `server.py` is the runtime entrypoint for the current product.
- It serves the static frontend from `web/` and exposes the REST API used by all current UI domains.
- It is the authoritative orchestration layer for board discovery, generation, save/load, import/export, LVGL flows, package generation, peripheral and clock config, and sensor parsing.

### Frontend authority

- `web/index.html` is the single-page shell for the current UI.
- `web/main.js` is the dominant frontend controller and state owner.
- The current frontend is not organized around explicit model/view/presenter boundaries; instead, domain logic, state mutation, DOM wiring, and backend calls are concentrated in `web/main.js`.
- Specialized helpers exist in sidecar scripts, but they still depend on globals exposed by the main runtime.

### Supporting feature modules

- `web/protocol-editor.js` owns protocol-template definitions and protocol editor normalization helpers.
- `web/interrupt-configurator.js` derives interrupt-impact views from other global stores such as module and protocol state.
- `web/lvgl-model.js`, `web/lvgl-build.js`, `web/lvgl-registry.js`, and `web/lvgl-ui.js` split LVGL behavior into submodules, but the integration contract is still global-window based.
- `project_model.py` defines the backend-side canonical project-document shape introduced during the settings-centralization work.

## Current UI Entry Surface

The app currently exposes one tabbed shell from `web/index.html` with these primary work areas:

- `modules`
- `lvgl-layout`
- `protocols`
- `interrupts`
- `peripherals`
- `clock`
- `configurator`
- `board-editor`
- `packages`
- `sensors`
- `zephyr-catalog`

The shell is still page-like rather than workspace-like:

- top header with board/project actions
- left peripheral or domain-specific navigation regions
- center editor/content region
- right-side configuration region for some tabs
- bottom output/code region

## Backend-to-Frontend Control Boundary

The current product shape is a classic Flask + static JS application:

- Flask owns routing and data generation.
- The browser fetches JSON from `/api/*` endpoints and directly mutates in-memory globals.
- DOM updates are performed imperatively from event handlers and render helpers.
- Cross-domain coordination happens through shared globals rather than typed contracts.

This is the main architectural constraint that Phase 1 and Phase 2 are intended to remove.

## Current Code Ownership by Layer

### Backend services and generators

- Board registry and frontend board payload shaping: `boards/`, `board_schema.py`
- DTS and `prj.conf` generation: `dts_generator.py`
- Overlay import and scan flows: `overlay_parser.py`
- Demo app export: `demo_app_generator.py`
- Package generation from PDFs: `package_generator.py`, `pdf_parser.py`
- Sensor parsing and code generation: `sensor_parser.py`, `driver_generator.py`
- Canonical project persistence normalization: `project_model.py`

### Frontend orchestration hot spots

- Initial board load and tab activation: `web/main.js`
- Generation and output aggregation: `web/main.js`
- Project save/load/export orchestration: `web/main.js`
- Module, peripheral, clock, package, sensor, import, and board-editor tab logic: `web/main.js`
- Protocol editing helpers: `web/protocol-editor.js`
- Interrupt analysis helpers: `web/interrupt-configurator.js`

## Current Project File Shape

The saved project file is a JSON document with `.zpinproj` extension written through `/api/project-file/save` and normalized through `project_model.py`.

The current canonical sections are:

- `version`
- `board_id`
- `pin_states`
- `periph_states`
- `periph_core_states`
- `external_device_states`
- `protocol_editor`
- `lvgl_layout`
- `generated_overlay`
- `generated_conf`
- `generated_fragments`
- `sensor_jobs`
- `sensor_selected`
- `mcu_jobs`
- `mcu_selected`
- `renode`
- `tabs`

This is the most important persistence baseline for Phase 2 because it already expresses the current cross-tab state that survives save/load.

### Generated fragment baseline

`generatedFragments` in `web/main.js` currently aggregates multi-domain outputs under these keys:

- `pin`
- `modules`
- `peripherals`
- `clock`
- `protocols`
- `lvgl`

Each fragment bucket carries some combination of overlay, `prj_conf`, generated code, headers, hooks, and integration text. This structure is the current cross-tab output inventory that the future typed project model must preserve deliberately.

## Current Save/Load and Import/Export Flow Inventory

### Save and load flows

- Save generated files into a Zephyr app directory through `/api/save-project`.
- Save full editor state into `.zpinproj` through `/api/project-file/save`.
- Load `.zpinproj` state back into the frontend through `/api/project-file/load`.
- Use `/api/path-dialog` as the native file/directory chooser for these flows.

### Import and export flows

- Import overlay and `prj.conf` content through `/api/import-config`.
- Scan an existing project tree through `/api/scan-project`.
- Import LVGL sources through `/api/lvgl/import`.
- Export LVGL layout/artifacts through `/api/lvgl/export`.
- Export a demo app and Renode test assets through `/api/demo-app/export`.

### Draft and generated-data flows

- Board editor draft save/load/delete through `/api/board-editor/*`.
- Package-generation parse and generate flows through `/api/parse-pdf`, `/api/parse-jobs`, `/api/generate-package`, and `/api/generated-packages`.
- Sensor parsing and derivative code generation through `/api/parse-sensor-pdf`, `/api/sensor-jobs`, and `/api/sensor-job/*`.

## High-Risk Migration Areas

These are the current seams most likely to create regressions during the refactor:

- Shared mutable globals in `web/main.js` used across multiple tabs.
- Window-level contracts between `main.js` and the LVGL helper scripts.
- Persistence logic that currently reconstructs project content from multiple runtime stores.
- Generated artifact aggregation through `generatedFragments` and related output panes.
- Tabs that depend on combined state from several other domains, especially `interrupts`, `protocols`, `lvgl-layout`, and `board-editor`.

## Heavy Rendering and Interaction Surfaces

These surfaces should be treated as high-cost during migration and performance validation:

- chip/package pin configurator surface
- board editor canvas and wire interaction
- LVGL stage and hierarchy tooling
- clock overview and frequency propagation views
- large Zephyr catalog lists and search/filter surfaces

## Baseline Non-Functional Goals

These are the initial refactor guardrails for later phases. They are goals, not yet measured benchmarks.

- Initial shell render should become interactive in under 2 seconds on a normal development workstation.
- Board switching should update the main UI state in under 500 ms for current supported boards.
- Tab switching and chip zoom interactions should stay visually responsive without obvious jank.
- Search/filter interactions on large lists should settle in under 150 ms after input.
- Idle memory growth during a 15-minute configuration session should remain bounded and not climb continuously.

## Phase 0 Outcome

The current system is now explicitly mapped as:

- Flask backend plus REST orchestration in `server.py`
- single-page static shell in `web/index.html`
- primary global-state and UI-control plane in `web/main.js`
- specialized helper modules that still depend on global contracts

That is the baseline architecture later phases must preserve functionally while replacing structurally.