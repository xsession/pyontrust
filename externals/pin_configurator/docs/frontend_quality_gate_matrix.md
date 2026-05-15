# Frontend Quality Gate Matrix

This matrix defines the minimum executable checks required before Phase 11 can be considered complete.

## Required Gates

| Gate | Command | Scope | Budget / Pass Condition |
| --- | --- | --- | --- |
| Type safety | `npm run typecheck` | TypeScript shell, presenters, services, domains | Zero `tsc` errors |
| Lint | `npm run lint` | Source quality, hooks, unused code, unsafe patterns | Zero ESLint errors |
| Unit + integration | `npm run test:run` | Presenters, project model, shell, panels, services, app flow | All Vitest files pass |
| Browser flow | `npm run test:browser-flow` | App bootstrap, board selection, keyboard map, diagnostics review | App-level Vitest browser-flow test passes |
| Production build | `npm run build` | Vite production bundle | Build completes successfully |
| Performance budgets | `npm run check:budgets` | Built `dist/` output | `index.html` <= 5 KiB, largest JS <= 650 KiB, largest CSS <= 150 KiB |
| Full gate | `npm run quality:check` | Combined release-candidate gate | All commands above pass in sequence |

## Notes

- The browser-flow gate is intentionally app-level rather than component-level. It verifies that the loaded shell still supports a realistic review workflow after presenter and workspace changes.
- The performance budget gate is based on raw built asset sizes so it can run in any local or CI environment without requiring browser profilers.
- Budget thresholds can be overridden temporarily with `PINCFG_HTML_BUDGET`, `PINCFG_JS_BUDGET`, and `PINCFG_CSS_BUDGET`, but the defaults above are the Phase 11 baseline.