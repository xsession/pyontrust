# Centralized Settings and Renode Plan

## Goal

Unify configuration from all editor tabs into one canonical project document, use that document plus generated artifacts to materialize a demo Zephyr application, and provide a Renode-backed test loop similar to the Swedish Embedded SDK workflow.

## Current Baseline

- Frontend tab state is still mostly owned by globals in [web/main.js](c:/GIT/addmind/deps/pyontrust/externals/pin_configurator/web/main.js).
- Aggregated Zephyr output is already merged through `generatedFragments` and `refreshGeneratedOutputs()`.
- `.zpinproj` is the closest existing cross-tab document format.
- Backend now normalizes project documents through [project_model.py](c:/GIT/addmind/deps/pyontrust/externals/pin_configurator/project_model.py).
- Backend can now export a demo Zephyr app plus Renode harness through `/api/demo-app/export`.
- A real demo app has been materialized at [demo/centralized_settings_demo](c:/GIT/addmind/deps/pyontrust/externals/pin_configurator/demo/centralized_settings_demo).

## Phase 1: Canonical Project Document

### Objective

Replace ad hoc save/load payload assembly with one normalized project schema used by save/load, demo export, test export, and future workspace automation.

### Work

- Keep [project_model.py](c:/GIT/addmind/deps/pyontrust/externals/pin_configurator/project_model.py) as the source of truth for persisted project shape.
- Move remaining tab-owned state into explicit sections under the project document.
- Add missing tab adapters for:
  - module configurator selections
  - peripheral configurator instance values
  - clock tree selections
  - interrupt configuration
  - board editor draft linkage
- Introduce a frontend `ProjectSettingsStore` in `web/ts/` to mediate reads/writes instead of writing globals directly.

### Acceptance

- Save/load round-trips preserve every tab that produces generated output.
- Generated output is reproducible from the project document without reading live UI globals.

## Phase 2: Frontend Centralization

### Objective

Make tabs consumers of a shared settings model instead of isolated state islands.

### Work

- Add `web/ts/project-settings.ts` with:
  - normalized state
  - change events
  - section-specific getters/setters
  - serialization helpers
- Convert each tab to register an adapter:
  - `collect()`
  - `restore()`
  - `generate()`
- Leave existing rendering code mostly intact in the first pass; route mutations through the store first.

### Acceptance

- Tabs can be restored from one document without hidden localStorage-only dependencies.
- Export, save, and demo generation all use the same serialized project payload.

## Phase 3: Demo Zephyr App Materialization

### Objective

Generate a portable demo app from the centralized document and collected artifacts.

### Current State

- Exporter lives behind `/api/demo-app/export`.
- Generator code lives in [demo_app_generator.py](c:/GIT/addmind/deps/pyontrust/externals/pin_configurator/demo_app_generator.py).
- Exported app contains:
  - `app.overlay`
  - `prj.conf`
  - `src/main.c`
  - `include/generated_project_summary.h`
  - `boards/<board>.resc`
  - `sample.robot`
  - `cmake/testbench.cmake`
  - preserved generated artifacts under `generated/`

### Next Work

- Add optional materialization of protocol/LVGL generated C and header files into compile-ready directories.
- Add frontend UI actions for:
  - export demo app
  - export testbench bundle
  - open generated app folder
- Add project metadata for demo profile name, output path, and chosen test strategy.

### Acceptance

- A saved project can be turned into a buildable demo app with one action.
- The exported app is self-contained and does not depend on the pin configurator source tree at build time.

## Phase 4: Renode Integration

### Objective

Attach a real simulation contract to supported boards instead of treating Renode as optional documentation only.

### Current State

- Default Renode metadata is normalized per board in [project_model.py](c:/GIT/addmind/deps/pyontrust/externals/pin_configurator/project_model.py).
- `lp_mspm0g3507` now maps to `platforms/boards/ti/lp_mspm0g3507.repl` and `sysbus.uart0`.
- Exported demo app includes `appbench`/`robotbench` assets.

### Next Work

- Add board profile registry for:
  - Renode platform path
  - console/UART path
  - boot-line expectations
  - known unsupported peripherals
- Add API validation that a requested Renode board profile exists.
- Support appbench generation for more than one board family.
- Optionally expose `boardbench`, `appbench_debugserver`, and `robotbench` launch commands in the UI.

### Acceptance

- Supported boards export a runnable `.resc` plus smoke Robot test.
- Unsupported boards fail with a clear message and a fallback compile-only workflow.

## Phase 5: VS Code-Style Test Environment

### Objective

Provide an inner-loop workflow similar to VSD/SE-SDK: build, run simulation, inspect console, and run smoke tests from one generated app.

### Work

- Add generated VS Code artifacts to exported apps:
  - `.vscode/tasks.json`
  - optional `.vscode/launch.json`
- Tasks should cover:
  - `west build`
  - `west build -t appbench`
  - `west build -t robotbench`
  - `west build -t appbench_debugserver`
- Add a smoke test profile that checks boot and one configuration summary line over UART.

### Acceptance

- A developer can open the exported app and immediately run build and simulation tasks.
- The smoke test can run unattended in CI when Renode is installed.

## Known Blocker

The exported demo app was created successfully, but the real `west build` in the current local Zephyr workspace is blocked by the workspace Python requirement:

- workspace build demanded Python `>= 3.12`
- available local interpreters are `3.10` and `3.8`

This is an environment issue, not a demo-app generation issue.

## Recommended Next Implementation Steps

1. Persist remaining generator-driving tab state in the canonical project document.
2. Add a frontend action to export the demo app directly from the UI.
3. Add compile-ready emission for protocol/LVGL generated sources where present.
4. Add generated VS Code tasks to the exported demo app.
5. Re-run the real `west build` after a Python 3.12 interpreter is available to the Zephyr workspace.