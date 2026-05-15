# Phase 0 State Ownership Map

This document records where state is currently owned in the legacy frontend. The key outcome is identifying which values are project content, which are generated outputs, and which are transient UI state.

## Primary State Owner

The dominant state owner today is `web/main.js`. It holds both persistent project content and transient UI state in top-level mutable globals.

## Core Project and Shell State in `web/main.js`

### Board and pinmux context

- `boardData`
- `availableBoards`
- `pinStates`
- `periphStates`
- `periphCoreStates`
- `externalDeviceStates`
- `selectedPin`
- `highlightedPeripheral`
- `highlightedPeripheralSignal`

These variables collectively control the currently selected board, the pin assignments, enabled peripherals, and chip-surface selection state.

### Generated outputs and cross-tab artifacts

- `generatedOverlay`
- `generatedConf`
- `generatedTargets`
- `generatedFragments`

`generatedFragments` is especially important because it aggregates outputs from multiple tabs and is the current bridge between tab-local configuration and final generated artifacts.

### Shell/UI control state

- `activeTab`
- zoom state such as `chipZoom`
- shell DOM references such as `boardSelect`, `chipArea`, `periphPanel`, `outputBar`, and `outputPre`

This state is not purely presentational because tab selection and output-pane behavior influence how features are surfaced and restored.

## Domain-Specific State in `web/main.js`

### LVGL domain

- `lvglLayoutState`
- `lvglLayoutDrag`
- `lvglLayoutNextId`
- `lvglPendingImportLayout`
- `lvglPendingImportSource`

LVGL also depends on window-level helper modules: `LvglModel`, `LvglBuild`, `LvglRegistry`, and `LvglUi`.

### Board editor domain

- `boardEditorDrafts`
- `boardEditorPendingDelete`
- `boardEditorPreviewBoard`
- `boardEditorCanvasStart`
- `boardEditorCanvasDrag`
- `boardEditorWireHandleDrag`
- `boardEditorPreviewTimer`
- `boardEditorDeviceLibrary`
- `boardEditorCanvasZoom`
- `boardEditorCanvasFitMode`

This is one of the heaviest UI surfaces and has a large amount of transient editor-scene state mixed with saveable content.

### Zephyr catalog domain

- `zephyrCatalogExternalDevices`
- `zephyrCatalogBoardEditorEntries`
- `zephyrCatalogItems`
- `zephyrCatalogRoot`
- `zephyrCatalogActiveKey`
- `zephyrCatalogFilter`
- `zephyrCatalogSearch`
- `zephyrCatalogSummary`

### Package-generation domain

- `pkgJobs`
- `pkgSelectedJob`
- `pkgSelectedPkgs`

### Module-config domain

- `modModules`
- `modActiveId`
- `modEnabled`
- `modValuesMap`
- `modDefaultsMap`

### Peripheral-config domain

- `pcfgInstances`
- `pcfgActiveInst`
- `pcfgValues`
- `pcfgDefaults`
- `pcfgBoardName`
- `pcfgBoardsLoaded`
- `pcfgOutputTab`

### Clock-config domain

- `clkTrees`
- `clkCurrentTree`
- `clkSelectedNode`
- `clkValues`
- `clkFreqs`
- `clkWarnings`
- `clkOutputTab`
- `clkTreesLoaded`
- `clkViewMode`

### Import/reverse-engineering domain

- `impOverlayText`
- `impConfText`
- `impParsed`
- `impScannedFiles`

### Sensor domain

- `snsJobs`
- `snsSelectedJob`

## Sidecar Module State

### `web/protocol-editor.js`

- `PROTOCOL_EDITOR_TEMPLATES` defines protocol templates and default field schemas.
- `protocolEditorState` stores current protocol-editor content.
- `protocolEditorNextId` controls local protocol entry identity allocation.

This module is logically a domain model plus presenter helper, but it still depends on globals such as `boardData` and helper functions exposed by the legacy runtime.

### `web/interrupt-configurator.js`

- `interruptViewState` stores the current interrupt inspector selection.

This module derives state from other global stores instead of owning a clean local model. It reads from module and protocol globals such as `modModules`, `modValuesMap`, `modDefaultsMap`, and protocol entry helpers.

## Current Ownership Problems

- Project content, generated outputs, and UI-only state are mixed together.
- Many domains depend on cross-file globals instead of explicit imports and contracts.
- The window object is part of the runtime contract for LVGL and some helper behaviors.
- Some domains derive their state from several unrelated global stores, which makes migration ordering fragile.
- The lack of a typed frontend-side `ProjectDocument` means persistence rules are encoded indirectly in save/load glue instead of in one canonical model.

## Phase 2 Extraction Targets

The following state should move first into the future canonical project model or related typed stores:

- board and target context
- pin assignments and peripheral enablement
- external device selections
- generated fragment inventory
- protocol editor content
- LVGL persisted layout state
- board-editor persisted content

The following should remain workspace-only state later:

- selected tab or active panel
- zoom, hover, drag, and current selection details
- temporary search/filter text
- output-pane focus state

This separation is the main state boundary Phase 2 needs to formalize.