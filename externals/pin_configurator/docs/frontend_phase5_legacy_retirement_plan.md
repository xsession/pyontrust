# Frontend Phase 5 Legacy Domain Retirement Plan

This document tracks the domains that still depend on `web/main.js` global ownership and the presenter boundary expected to replace them.

## Migrated Domains

- Pin Configurator: owned by React presenter modules and canonical project-document commands.
- Module Configurator: owned by typed module-definition presenters and module config generation actions.
- Peripheral Configurator: owned by React presenter modules and canonical peripheral/device command handlers.
- Clock Configurator: owned by typed clock-tree presenters, derived frequency computation, and generated clock artifact actions.
- Protocol Editor: owned by React presenter modules and canonical project-document commands.
- LVGL Layout: owned by typed LVGL import/export services plus canonical layout presenter state.
- Interrupt Configurator: owned by typed presenter composition over protocol, module, and clock workflows.
- Board Editor: owned by typed board-editor draft presenters and dock-hosted JSON editing flows.
- Sensor Parser: owned by React presenter modules for persisted job inspection and catalog-to-job handoff.
- Package Manager: owned by React presenter modules for persisted MCU job inspection and catalog imports.
- Zephyr Catalog: owned by a typed API service plus React presenter-owned loading, filtering, selection, and workflow actions.
- Generated Output: owned by React presenter modules, artifact exports, and canonical generated-output state.
- Build/Sim/Test: owned by React presenter modules that derive output and readiness state from the canonical project document.

## Remaining Legacy Domains

No remaining React-shell domains are still tracked as `legacy-global` in the presenter retirement registry.

## Migration Order

Completed in this order:

1. Module Configurator
2. Clock Configurator
3. LVGL Layout
4. Board Editor
5. Interrupt Configurator

## Exit Criteria

- No product-critical domain depends on ad hoc reads or writes to `window` globals from `web/main.js`.
- Each migrated domain exposes typed presenter commands and a mountable React-facing contract.
- Remaining legacy ownership is visible in code review through explicit adapter or registry entries instead of hidden global coupling.