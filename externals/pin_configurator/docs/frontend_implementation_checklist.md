# Pin Configurator Frontend Implementation Checklist

## Goal

Convert the product design spec and platform research into an execution checklist for the React frontend workspace and the remaining legacy cutover work.

## Phase 1: Shell clarity

- [x] Replace the weak context strip with an explicit workflow map in the React shell.
- [x] Keep command, navigation, workspace, inspector, and output zones visually distinct.
- [x] Ensure every major layout preset communicates its intended workflow clearly.
- [x] Add empty-state copy that explains the next useful action, not just missing data.
- [x] Remove or rewrite any remaining hero-style or marketing-style copy in shell surfaces.

## Phase 2: Navigation and focus

- [x] Audit left-rail destinations against the real engineering workflows.
- [x] Ensure the most-used dock panels have stable keyboard shortcuts.
- [x] Add quick-focus actions for the highest-value generated artifacts.
- [x] Make active output channel selection visible in both the rail and the bottom strip.
- [x] Persist last active dock panel and output channel across reloads.

## Phase 3: Inspector system

- [x] Standardize inspector sections across pins, clocks, protocols, LVGL, and Renode.
- [x] Keep persistence state, artifact ownership, and blocking notices at the top of the inspector stack.
- [x] Use one common pattern for editable values versus generated or derived values.
- [x] Add summary counts for warnings, unresolved selections, and generated groups where useful.
- [x] Remove one-off inspector phrasing that does not match the shared shell language.

## Phase 4: Validation and readiness

- [x] Surface pin conflicts inline and in a summarized readiness view.
- [x] Surface clock validation inline and in a summarized readiness view.
- [x] Add artifact readiness summaries for overlay, config, fragments, headers, source, RESC, and Robot.
- [x] Route validation failures into diagnostics output consistently.
- [x] Ensure readiness states are reflected in status bar items and output channel badges.

## Phase 5: Artifact review

- [x] Keep generated overlay and config immediately accessible from both inspector and dock.
- [x] Add clearer distinction between editable project assets and generated outputs.
- [x] Show when generated outputs are stale relative to the current project state.
- [x] Add quick diffs or change summaries where feasible for regenerated artifacts.
- [x] Ensure export actions explain what bundle or files will be produced.

## Phase 6: Domain panels

### Pin assignments

- [x] Keep the scene, unresolved issues, and selected-pin details synchronized.
- [x] Improve scanability of alternate-function choices.
- [x] Add stronger visual cues for ownership, conflicts, and incomplete assignments.

### Clock configurator

- [x] Keep tree context visible while editing node properties.
- [x] Expose derived frequencies and warnings without forcing users to switch surfaces.

### Protocol editor

- [x] Tie protocol-entry edits more directly to generated C and header review.
- [x] Expose protocol readiness before export.

### LVGL layout

- [x] Keep hierarchy, stage, props, and style library synchronized.
- [x] Preserve simulation log visibility near the editing flow.

### Renode profile

- [x] Make simulation bundle readiness explicit in the shell.
- [x] Keep machine selection, RESC, and Robot review in one coherent loop.

## Phase 7: Visual system

- [x] Audit token usage so shell surfaces consistently use the workspace token set.
- [x] Normalize border radii, panel elevation, and spacing rhythm across shell components.
- [x] Reduce visual noise from inconsistent secondary backgrounds.
- [x] Verify compact and regular density modes stay readable across all major panels.
- [x] Review mobile and narrow-width behavior so shell zones collapse predictably.

## Phase 8: Legacy cutover alignment

- [x] Keep the React shell as the canonical model for workstation behavior.
- [x] Avoid adding new major UX patterns to the legacy `web/index.html` path.
- [x] Track which workflows still require legacy-only support.
- [x] Port remaining shell-critical patterns only once they are stable in React.
- [x] Define the cutover threshold where the legacy shell stops receiving feature work.

## Phase 9: Quality gates

- [x] Add shell-level tests for navigation, workflow map, inspector actions, and output routing.
- [x] Add tests for layout preset persistence and density persistence.
- [x] Add tests that generated-artifact focus actions reach the expected dock panels.
- [x] Add tests that diagnostics and readiness badges update for representative state changes.
- [x] Include one browser-flow test that exercises save, focus, export, and output review in sequence.

## Current progress snapshot

- Research document created.
- Product design spec created.
- Implementation checklist created.
- Phase 1 shell clarity is complete: workflow map, layout preset signaling, task-focused shell copy, and next-step empty states are all in place.
- React shell workflow map added and validated through `ShellView.test.tsx`.
- Phase 2 navigation and focus is complete: the rail now prioritizes preset-anchor workflow destinations, exposes route metadata directly, and panel shortcuts resolve by definition instead of array order.
- Phase 3 inspector system is complete: pins, clocks, protocols, LVGL, and Renode now share top-of-panel readiness summaries, anchored blocker notices, explicit editable-versus-derived sections, and summary counts for warnings, unresolved work, and generated outputs.
- Workspace shell preferences now persist and rehydrate active dock focus and active output channel selections.
- Layout presets now communicate their focus panel and output route explicitly in both the left rail and quick-open surface.
- The right inspector now uses shared inspector sections for project state, artifact review, review routes, pin assignments, Renode, and protocol work.
- The output zone now surfaces active-channel state plus artifact authority, readiness, and integrity blockers in a dedicated summary band.
- Status bar items and output channel badges now derive from readiness, artifact authority, and integrity state instead of static counts.
- Focused tests now cover readiness-aware status-bar derivation, build/sim/test badge semantics, and shell rendering of the updated model.
