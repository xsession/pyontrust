# Frontend Cutover Strategy

This document is the completed Phase 12 cutover guide for retiring the legacy frontend without relying on a big-bang switch.

## Status

- Phase 12 rollout planning was implemented in the React shell and supporting cutover helpers.
- The browser-facing legacy shell has now been retired and `/` redirects to `/app`.
- The remaining value of this document is as an audit trail for the completed migration order and retirement criteria.

## Validation Evidence

1. `npm --prefix frontend run quality:check`
2. `pytest tests/test_frontend_shell.py`
3. `npm --prefix vscode-extension run build`

## Historical Runtime Modes

| Mode | Meaning | Rollback posture |
| --- | --- | --- |
| Dual-run active | React shell is primary while the legacy shell flag stays enabled. | Rollback remains available. |
| React-primary cutover | React shell remains enabled and the legacy shell flag is disabled. | Rollback requires re-enabling the legacy flag before deletion. |
| Legacy fallback | Legacy shell remains enabled while the React shell is disabled. | Parity work is paused until the React shell is restored. |

## Migration Order By Domain

1. Shell and persistence slices:
React shell, generated output, build/simulation/test review.

2. Core editors:
Pin Configurator, Protocol Editor, Peripheral Configurator, Module Configurator, Clock Configurator.

3. Supporting tools:
LVGL Layout, Interrupt Configurator, Board Editor, Sensor Parser, Package Manager, Zephyr Catalog.

## Retirement Criteria

1. All targeted domains must be owned by React presenters rather than legacy globals.
2. `npm run quality:check` must pass before any legacy slice is deleted.
3. The legacy shell flag must remain enabled through parity review so rollback is still explicit.
4. Legacy tabs and utilities should only be removed after React-primary sign-off is recorded for the affected slice.

## Removal Sequence

1. Keep dual-run active while parity review happens inside the React shell.
2. Disable the legacy shell flag after parity and rollback checks are signed off.
3. Delete legacy tabs and utilities only for slices that already have React ownership, quality-gate evidence, and rollback sign-off.

## Completion Outcome

1. React-owned domains are now the active browser experience.
2. `/` redirects to `/app`, so the React workspace is the only browser shell.
3. The remaining legacy runtime files are historical artifacts, not active cutover dependencies.