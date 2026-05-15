# Pin Configurator Frontend MVP Refactor Plan

## Purpose

This document defines a detailed refactor plan to evolve `pin_configurator` from the current static Flask-served JavaScript frontend into a professional-grade desktop-class engineering UI with a unified and centralized user experience for embedded engineers.

The plan is grounded in the current repository structure:

- backend API and orchestration in `server.py`
- static frontend entry in `web/index.html`
- large runtime orchestration in `web/main.js`
- specialized tab scripts such as `web/protocol-editor.js` and `web/interrupt-configurator.js`
- incremental TypeScript in `web/ts/`

The target architecture follows **Model-View-Presenter** principles and uses the requested frontend stack.

## Target Outcome

Build a frontend that feels like a serious embedded engineering workstation:

- unified navigation, layout, and project state across all tools
- desktop-grade dockable workspace for editors, outputs, logs, inspectors, and code panels
- predictable MVP boundaries for maintainability and testability
- high-performance rendering for pin/package/editor surfaces
- accessible, keyboard-driven interaction model
- consistent project save/load/export/demo/simulation workflow
- foundation for VS Code extension embedding and future standalone desktop packaging

## Recommended Stack Decisions

These recommendations stay within the requested stack while reducing ambiguity.

### Core UI Stack

- [x] Use **React + TypeScript** as the primary frontend runtime.
- [x] Use **Vite** for the new frontend workspace and development pipeline.
- [x] Keep Flask as the API host during the migration; serve the built React bundle from Flask when productionizing.

#### Core UI Stack Objectives

- [x] Establish one modern frontend runtime that can support dense engineering workflows, complex state coordination, and long-lived maintainability.
- [x] Separate frontend concerns cleanly between rendering, orchestration, state, and backend integration.
- [x] Enable fast local iteration without coupling frontend development speed to Flask template or static-file limitations.
- [x] Preserve compatibility with the current backend and VS Code extension hosting model while the migration is in progress.

#### Decision Summary

- [x] **React** is the rendering runtime because the product needs composable panels, reusable inspectors, predictable state-to-view projection, and mature ecosystem support for docking, editors, accessibility primitives, and visualization layers.
- [x] **TypeScript** is mandatory because the future product depends on strong contracts for project documents, generated artifacts, API DTOs, presenter inputs, and cross-domain coordination.
- [x] **Vite** is the development/build tool because startup time, hot reload performance, TypeScript integration, and library friendliness are materially better than continuing to grow the current hand-managed static pipeline.
- [x] **Flask remains the API server** during migration because backend endpoints, project save/load, generation, import/export, and demo/test flows already live there and should not be destabilized by the frontend rewrite.

#### React Responsibilities

- [x] Render the workspace shell, docked panels, inspectors, editors, trees, dialogs, logs, and command surfaces.
- [x] Host presentational components only; React components should receive prepared view models from presenters rather than owning backend or domain rules.
- [x] Provide composition boundaries for domain workspaces such as Pin Configurator, Clock Configurator, LVGL, Protocol Editor, Build/Sim/Test, and generated artifact review.
- [x] Support progressive migration by allowing legacy functionality to be wrapped or hosted behind feature flags while new panels are introduced.

#### TypeScript Responsibilities

- [x] Define canonical frontend-side types for `ProjectDocument`, docking layout state, diagnostics, generated fragments, build state, Renode state, and command payloads.
- [x] Enforce contracts between model, presenter, and view layers.
- [x] Prevent regressions caused by implicit object shapes currently flowing through `web/main.js` globals.
- [x] Provide explicit migration boundaries between legacy runtime objects and the new domain model.

#### Vite Responsibilities

- [x] Provide the new `frontend/` workspace with fast startup and rebuild times suitable for day-to-day UI engineering.
- [x] Build the React application as a standalone bundle that Flask can serve in production.
- [x] Support code splitting for Monaco, heavy editor surfaces, and optional workspace panels.
- [x] Support environment-driven switching between local frontend dev mode and Flask-served production mode.

#### Flask Integration Rules

- [x] Treat Flask as the authoritative backend API and orchestration surface during the migration.
- [x] Keep the initial React frontend decoupled from Flask template rendering; integration should happen at the static bundle boundary.
- [x] Add a development proxy from Vite to Flask endpoints so frontend work can proceed without duplicating backend logic.
- [x] Serve the production React build from Flask only after feature-flagged parity is proven.
- [x] Keep existing routes for project save/load, generation, import/export, demo export, and Renode/testbench orchestration stable while the frontend changes.

#### Migration Rules for the Core Stack

- [x] Do not expand the legacy `web/main.js` architecture once the React workspace exists except for compatibility shims or defect fixes.
- [x] Do not place new major features directly into static legacy pages if they belong in the future docked workspace.
- [x] Do not let React components talk to Flask using raw `fetch` from arbitrary components; all backend access should move through typed API services and presenters.
- [x] Do not mix new React-owned state with unmanaged DOM mutation on the same screen region.
- [x] Do not use Vite merely as a compile step for legacy files; it should own the new application boundary.

#### Repository Layout for the Core Stack

- [x] Create a dedicated `frontend/` root rather than continuing to grow the static `web/` directory as the primary implementation surface.
- [x] Retire `web/` from the active browser runtime once cutover is complete.
- [x] Add explicit frontend build output targeting a Flask-served static directory such as `frontend/dist/`.
- [x] Keep backend-owned static compatibility files separate from the new React source tree.

#### Development Workflow Expectations

- [x] Run React development with Vite for local UI work.
- [x] Proxy API calls to the Flask backend during development.
- [x] Keep TypeScript in strict mode from the start.
- [x] Make linting, type-checking, and component/presenter tests part of the default frontend development loop.
- [x] Preserve the ability to host the resulting frontend inside the VS Code extension after bundling.

#### Acceptance Criteria for the Core UI Stack

- [x] A new React + TypeScript + Vite workspace exists and runs independently in development.
- [x] Flask continues to provide the backend API without frontend behavioral regression.
- [x] The React app can be bundled and served by Flask in a production-like mode.
- [x] The stack supports Dockview, Monaco, virtualization, and heavy editor surfaces without architectural rework.
- [x] MVP layering remains enforceable through type boundaries, folder boundaries, and code review rules.

#### Organized Implementation

This chapter should be executed as a small platform program, not as an open-ended frontend rewrite. The point of the stack decision is to create a stable application boundary first, then move feature work into it in a controlled order.

##### Workstream 1: Frontend Workspace Bootstrap

- [x] Create a dedicated `frontend/` application root with Vite, React, and strict TypeScript.
- [x] Add the minimum platform files first: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`, and `src/styles/`.
- [x] Keep the first boot target intentionally small: render a shell page that proves the React app starts cleanly and can coexist with Flask.
- [x] Do not migrate any legacy product feature into React before the workspace boots, hot reload works, and the build output is deterministic.

##### Workstream 2: Production Integration Boundary

- [x] Define how Flask will serve the built frontend before migrating feature code.
- [x] Choose one production output contract and keep it fixed: either `frontend/dist/` copied into a Flask-served static directory or Flask configured to serve the built Vite output directly.
- [x] Add a Vite dev proxy to the existing Flask backend so the React app can call current endpoints without duplicating server logic.
- [x] Keep backend routing stable and treat the React bundle as a client replacement, not as a backend rewrite.

##### Workstream 3: Typed Platform Contracts

- [x] Create a shared frontend-side contract layer for API DTOs, project documents, generated fragments, diagnostics, build state, and Renode state.
- [x] Put these contracts under a stable path such as `frontend/src/types/` or `frontend/src/contracts/`.
- [x] Define adapters for legacy payload shapes instead of leaking raw `web/main.js` structures into new React code.
- [x] Make strict typing part of the stack rollout, not a cleanup task deferred to later phases.

##### Workstream 4: MVP Runtime Skeleton

- [x] Establish the base folder structure for model, presenter, and view responsibilities before domain migration starts.
- [x] Create a shell that already reflects the future separation: app bootstrap, providers, shared services, workspace shell, and one sample presenter-driven view.
- [x] Add a typed API client layer and a presenter example so the team has a reference implementation for all later domains.
- [x] Prevent direct backend calls from components from the first React feature onward.

##### Workstream 5: Quality and Developer Workflow

- [x] Add linting, strict type-checking, and a fast test command as part of the initial workspace setup.
- [x] Make `dev`, `build`, `typecheck`, `lint`, and `test` first-class scripts in the new frontend workspace.
- [x] Add at least one smoke test that proves the React shell renders and one contract-level test that proves API typing compiles.
- [x] Do not begin deep feature migration until these quality gates are part of the default workflow.

##### Suggested Initial Repository Shape

- [x] `frontend/src/app/` for bootstrap, providers, shell, and global composition.
- [x] `frontend/src/contracts/` for DTOs, project types, and API response shapes.
- [x] `frontend/src/services/` for backend clients and infrastructure utilities.
- [x] `frontend/src/presenters/` for app-level orchestration patterns.
- [x] `frontend/src/views/` for presentational shell components.
- [x] `frontend/src/styles/` for reset, tokens, theme variables, and SCSS entrypoints.

##### Implementation Order

1. [x] Bootstrap the standalone React + TypeScript + Vite workspace.
2. [x] Add Flask development proxy and production serving contract.
3. [x] Add strict type system, linting, and platform scripts.
4. [x] Add typed API client and contract modules.
5. [x] Add MVP shell structure with one reference presenter/view pair.
6. [x] Verify production bundle serving through Flask.
7. [x] Only then begin migrating real product domains into the new workspace.

##### First Milestone Deliverable

- [x] A developer can run the new frontend independently in development mode.
- [x] The frontend can call existing Flask APIs through the dev proxy.
- [x] The production build can be served by Flask without changing backend business logic.
- [x] The codebase already enforces strict typing and a visible MVP folder boundary.
- [x] The stack is ready for domain migration without expanding the legacy `web/` architecture further.

##### Failure Conditions to Avoid

- [x] Do not start by porting a complex tab before the workspace, proxy, and build contract are stable.
- [x] Do not let React and legacy DOM code co-own the same screen region.
- [x] Do not defer typing of project and API contracts until after multiple domains are migrated.
- [x] Do not couple the new frontend bootstrap to a large styling or docking rollout on day one.
- [x] Do not treat the stack chapter as complete until the workspace runs, builds, proxies, and serves in a production-like path.

### State Management

- [x] Use **Zustand** as the primary application store for local product state.
- [x] Reserve **Redux Toolkit** only if later needed for highly regulated action history, plugin interoperability, or external integration constraints.
- [x] Do not adopt MobX as the default path unless the team explicitly prefers implicit reactivity over explicit command flows.

### Styling System

- [x] Use **SCSS + CSS variables**.
- [x] Use CSS variables for theme tokens, spacing, density, z-index, semantic colors, and editor state colors.
- [x] Use SCSS for layout composition, panel variants, utility mixins, and token-generated scales.

### Docking / Workspace Layout

- [x] Use **Dockview** as the primary docking framework.
- [x] Keep **GoldenLayout** only as a fallback option if Dockview integration fails against critical requirements.
- [x] Avoid building a full custom docking system in the first refactor phase; only build custom splitters if the docking library proves insufficient for a specific editor surface.

### Accessible Primitives

- [x] Use **Radix primitives** for menus, dialogs, popovers, tooltips, dropdowns, tabs, and context menus.
- [x] Use **React Aria** where lower-level accessibility behavior is needed for trees, grids, command palettes, or advanced keyboard interaction models.

### Editor Surfaces

- [x] Use **SVG** for precise inspectable schematic-style surfaces where selection and semantic overlays matter.
- [x] Use **Canvas** for dense interactive package/pin/clock surfaces where node counts and redraw frequency are high.
- [x] Keep **WebGL** as an optimization path, not the initial baseline.

### Large Data Rendering

- [x] Use **TanStack Virtual** for large trees, pin lists, peripheral catalogs, sensor catalogs, logs, generated artifact lists, and validation panels.

### Code and Script Panels

- [x] Use **Monaco Editor** for overlay, `prj.conf`, generated C/H sources, Renode scripts, Robot tests, and diagnostics panels.

## MVP Architecture Rules

The new frontend must follow Model-View-Presenter rigorously.

### Model

The Model owns product state and domain rules.

- [x] Centralize project state into one typed project document compatible with the backend `project_model.py` direction.
- [x] Represent state in store slices by domain, not by screen implementation.
- [x] Keep all normalization, validation, derived selectors, and persistence adapters in model-layer modules.
- [x] Keep API DTOs separate from domain models.
- [x] Keep command history, selection state, docking state, diagnostics state, and simulation state inside typed stores or model services.

### View

The View is purely presentational.

- [x] React components render props and emit interaction intents.
- [x] Views must not call backend APIs directly.
- [x] Views must not mutate Zustand state directly except through presenter-bound actions.
- [x] Views must not contain domain rules for pinmux, clocking, protocol semantics, LVGL semantics, or export rules.

### Presenter

The Presenter coordinates state, commands, effects, and orchestration.

- [x] Implement presenters as hooks and controller modules.
- [x] Presenters map user intent to model actions and backend calls.
- [x] Presenters own async flows, optimistic updates, cancellation, debouncing, and error handling.
- [x] Presenters provide view models optimized for rendering.
- [x] Presenters bridge between Monaco, docking panels, canvas interactions, and the domain model.

### Non-Negotiable MVP Rules

- [x] No backend fetches from JSX components.
- [x] No cross-tab mutation through globals.
- [x] No business logic in docking panel registration code.
- [x] No DOM querying as the primary interaction model after migration.
- [x] No feature state hidden only in local component state if it affects project persistence or generation.

## UX Vision for Embedded Engineers

The product should feel like a hybrid of:

- IDE workspace
- board bring-up tool
- generated artifact review console
- simulator/testbench launcher

### UX Principles

- [x] One project, many coordinated tools.
- [x] Always-visible project context: board, SoC, active profile, selected core, build target, simulation target.
- [x] Inspectable outputs: every generated artifact should be traceable back to the settings that produced it.
- [x] Fast keyboard interaction for engineers who work iteratively.
- [x] Layout persistence: panel arrangement, open editors, filters, and comparisons should restore with the project.
- [x] Explicit diagnostics: conflicts, warnings, missing routes, unsupported Renode targets, and codegen risks must be visible globally.
- [x] Tool specialization without UI fragmentation.

### Primary Workspace Areas

- [x] Left navigation rail for product sections and project scopes.
- [x] Docked center workspace for editors and canvases.
- [x] Right inspector column for properties, validation, codegen preview, and selection details.
- [x] Bottom diagnostics/output zone for logs, generated files, simulation output, build output, and test results.
- [x] Global command surface for save/load/export/generate/build/simulate/test.

## Target Product Structure

### High-Level Frontend Packages

- [x] `frontend/src/app` for app shell, routing, providers, theme, and command registry.
- [x] `frontend/src/workspace` for docking layout, panel lifecycle, and layout persistence.
- [x] `frontend/src/project` for the canonical project model, persistence adapters, and save/load flows.
- [x] `frontend/src/domains/pins`
- [x] `frontend/src/domains/modules`
- [x] `frontend/src/domains/peripherals`
- [x] `frontend/src/domains/clocks`
- [x] `frontend/src/domains/protocols`
- [x] `frontend/src/domains/lvgl`
- [x] `frontend/src/domains/interrupts`
- [x] `frontend/src/domains/board-editor`
- [x] `frontend/src/domains/catalog`
- [x] `frontend/src/domains/sensors`
- [x] `frontend/src/domains/packages`
- [x] `frontend/src/domains/renode`
- [x] `frontend/src/shared/ui`
- [x] `frontend/src/shared/monaco`
- [x] `frontend/src/shared/virtualization`
- [x] `frontend/src/shared/testing`

### Store Slices

- [x] `projectStore`
- [x] `workspaceStore`
- [x] `diagnosticsStore`
- [x] `selectionStore`
- [x] `outputStore`
- [x] `buildSimulationStore`
- [x] `pinDomainStore`
- [x] `moduleDomainStore`
- [x] `peripheralDomainStore`
- [x] `clockDomainStore`
- [x] `protocolDomainStore`
- [x] `lvglDomainStore`
- [x] `interruptDomainStore`
- [x] `boardEditorStore`
- [x] `catalogStore`

### Presenter Families

- [x] command presenters
- [x] tab/domain presenters
- [x] docking/panel presenters
- [x] canvas interaction presenters
- [x] import/export presenters
- [x] build/simulation/test presenters
- [x] diagnostics presenters

## Sequential Phase Specification

This section breaks the entire plan into a strict execution sequence so the refactor can be run as a controlled program instead of a loose set of parallel ideas. Each phase should have a clear entry condition, execution focus, and exit condition before the next phase is treated as active.

### Phase Order Overview

1. [x] Phase 0: Discovery and Baseline Lock
2. [x] Phase 1: Frontend Platform Foundation
3. [x] Phase 2: Canonical Project Model and Persistence
4. [x] Phase 3: Professional Workspace Shell
5. [x] Phase 4: Design System and Interaction Language
6. [x] Phase 5: Domain-by-Domain Presenter Migration
7. [x] Phase 6: Editor Surface Modernization
8. [x] Phase 7: Large-Scale Data UX
9. [x] Phase 8: Monaco-Centered Artifact Experience
10. [x] Phase 9: Build, Renode, and Test UX
11. [x] Phase 10: Accessibility, Keyboarding, and Power-User Flow
12. [x] Phase 11: Testing and Quality Gates
13. [x] Phase 12: Incremental Cutover Strategy
14. [x] Phase 13: Packaging and Deployment

### Phase 0: Discovery and Baseline Lock

#### Why this phase exists

- [x] Establish factual understanding of the current system before platform or UI redesign begins.
- [x] Freeze baseline behavior so later changes can be judged against evidence instead of memory.

#### Entry condition

- [x] The refactor has been approved conceptually, but the current frontend, persistence, and generation flows have not yet been fully inventoried.

#### Primary outputs

- [x] current-state architecture map
- [x] endpoint-to-feature matrix
- [x] state ownership inventory
- [x] regression checklist

#### Exit condition

- [x] The team can name what exists today, what must be preserved, and what is safe to change first.

### Phase 1: Frontend Platform Foundation

#### Why this phase exists

- [x] Create the technical substrate for the new frontend without forcing early feature migration.
- [x] Establish React, TypeScript, Vite, and core tooling as stable infrastructure.

#### Entry condition

- [x] Current product behavior is sufficiently mapped to begin platform work safely.

#### Primary outputs

- [x] bootable `frontend/` workspace
- [x] Vite-to-Flask dev proxy
- [x] build, lint, typecheck, and test workflow
- [x] shell-level MVP reference structure

#### Exit condition

- [x] The repo has a stable React platform ready to host the canonical project model and later shell migration.

### Phase 2: Canonical Project Model and Persistence

#### Why this phase exists

- [x] Establish one authoritative typed project document for save/load/export/generation.
- [x] Separate project content from workspace-only UI state before more UI surfaces are migrated.

#### Entry condition

- [x] The new frontend workspace exists and can safely host model and service code.

#### Primary outputs

- [x] canonical `ProjectDocument`
- [x] normalization and serialization layer
- [x] persistence DTOs and adapters
- [x] project selectors and mutation boundaries

#### Exit condition

- [x] Future domains can rely on one stable project shape instead of inventing local persistence conventions.

### Phase 3: Professional Workspace Shell

#### Why this phase exists

- [x] Replace the page-style legacy UI with a real engineering workspace shell.
- [x] Establish the layout and navigation model that later domain panels will inhabit.

#### Entry condition

- [x] The platform and project model are stable enough that shell state and panel composition can be built on top of them.

#### Primary outputs

- [x] top command bar
- [x] left navigation rail
- [x] docked center workspace
- [x] right inspector region
- [x] bottom output zone

#### Exit condition

- [x] The new product has a usable workspace container ready to host real migrated functionality.

### Phase 4: Design System and Interaction Language

#### Why this phase exists

- [x] Ensure the workspace shell and future domain surfaces share one coherent interaction language.
- [x] Replace ad hoc visual rules with reusable tokens, primitives, and behavior patterns.

#### Entry condition

- [x] The shell exists, so visual and interaction standards can be designed against a concrete container.

#### Primary outputs

- [x] token system
- [x] reusable component primitives
- [x] inspector and dialog patterns
- [x] standardized keyboard and context-menu conventions

#### Exit condition

- [x] New screens can be built from shared primitives instead of bespoke visual decisions.

### Phase 5: Domain-by-Domain Presenter Migration

#### Why this phase exists

- [x] Move business logic out of legacy globals and imperative DOM wiring into MVP-aligned modules.
- [x] Migrate one domain at a time without reopening architectural questions on each feature.

#### Entry condition

- [x] Platform, project model, shell, and design primitives are strong enough to support disciplined migration.

#### Primary outputs

- [x] presenter modules by domain
- [x] typed command paths
- [x] retiring adapters for legacy globals

#### Exit condition

- [x] The product’s major domains are controlled through presenters and model-layer state instead of legacy orchestration.

### Phase 6: Editor Surface Modernization

#### Why this phase exists

- [x] Rebuild dense technical canvases and editors with performance and inspectability as first-class concerns.
- [x] Modernize the surfaces that are too interaction-heavy to remain legacy-first.

#### Entry condition

- [x] Domain behavior has begun moving into presenters and shared model code.

#### Primary outputs

- [x] new pin/package surface
- [x] new clock surface
- [x] React-hosted LVGL workspace surface
- [x] modernized board editor scene

#### Exit condition

- [x] The highest-value editor surfaces run on the new architecture and no longer depend on legacy DOM control patterns.

### Phase 7: Large-Scale Data UX

#### Why this phase exists

- [x] Make the product fast and navigable when lists, trees, logs, and catalogs become large.
- [x] Prevent scale-related usability regressions as more features move into the new shell.

#### Entry condition

- [x] Enough data-bearing UI has moved into the new workspace that virtualization and scalable filtering are worthwhile.

#### Primary outputs

- [x] virtualized trees and lists
- [x] scalable search/filter patterns
- [x] split-detail large-data views

#### Exit condition

- [x] Large engineering datasets remain responsive and usable under the new workspace model.

### Phase 8: Monaco-Centered Artifact Experience

#### Why this phase exists

- [x] Make generated files, overlays, scripts, and diagnostics first-class engineering artifacts inside the workspace.
- [x] Give users a serious artifact review and debugging surface.

#### Entry condition

- [x] The shell and domain model can already expose generated outputs and diagnostics coherently.

#### Primary outputs

- [x] Monaco artifact panels
- [x] diff workflows
- [x] marker/decorations pipeline
- [x] diagnostics-to-code navigation

#### Exit condition

- [x] Generated artifacts are inspectable and actionable inside the product instead of feeling bolted on.

### Phase 9: Build, Renode, and Test UX

#### Why this phase exists

- [x] Unify execution workflows so generation, build, simulation, and smoke testing happen in one coherent experience.
- [x] Connect the frontend to the repository’s Renode/demo/export direction.

#### Entry condition

- [x] The workspace can already model project data, outputs, and artifacts in a stable way.

#### Primary outputs

- [x] build/sim/test console
- [x] task and log surfaces
- [x] Renode machine selection and support messaging
- [x] demo export and test launch controls

#### Exit condition

- [x] Users can move from configuration to validation without leaving the workspace context.

### Phase 10: Accessibility, Keyboarding, and Power-User Flow

#### Why this phase exists

- [x] Ensure the system is operationally strong, not just visually improved.
- [x] Make dense engineering workflows efficient for keyboard-heavy users and accessible for broader use.

#### Entry condition

- [x] Major shell and domain interactions already exist and can now be standardized and hardened.

#### Primary outputs

- [x] keyboard navigation model
- [x] focus and selection standards
- [x] screen-reader support improvements
- [x] power-user shortcuts and bulk actions

#### Exit condition

- [x] The workspace is efficient, accessible, and consistent under real operational use.

### Phase 11: Testing and Quality Gates

#### Why this phase exists

- [x] Lock behavior while architectural migration is still happening.
- [x] Define the long-term quality bar for stores, presenters, components, and end-to-end workflows.

#### Entry condition

- [x] Enough of the new architecture exists that broad automated validation is meaningful.

#### Primary outputs

- [x] unit and integration coverage
- [x] browser flow coverage
- [x] performance budgets
- [x] quality gate matrix

#### Exit condition

- [x] The refactor is guarded by executable checks instead of manual confidence alone.

### Phase 12: Incremental Cutover Strategy

#### Why this phase exists

- [x] Retire the legacy frontend safely instead of attempting a risky big-bang replacement.
- [x] Sequence rollout and removal so parity is proven before deletion.

#### Entry condition

- [x] Major parts of the new workspace are functional enough to begin replacing legacy surfaces deliberately.

#### Primary outputs

- [x] dual-run strategy
- [x] migration order by domain
- [x] criteria for retiring legacy tabs and utilities

#### Exit condition

- [x] The old frontend can be removed in controlled slices with clear rollback and parity criteria.

### Phase 13: Packaging and Deployment

#### Why this phase exists

- [x] Make the new frontend viable across browser deployment, Flask hosting, and VS Code extension embedding.
- [x] Ensure delivery mechanics do not become the late blocker after the product architecture is ready.

#### Entry condition

- [x] The new workspace is functionally mature enough that packaging paths matter operationally.

#### Primary outputs

- [x] production build strategy
- [x] VS Code extension hosting path
- [x] deployment and source-map strategy

#### Exit condition

- [x] The refactored frontend can be built, hosted, debugged, and shipped across the required environments.

### Sequential Rules

- [x] Do not treat a phase as complete because its planning chapter exists; completion requires its exit condition and definition of done to be satisfied.
- [x] Allow overlap only where a later phase depends on a stable subset of an earlier one, not on the earlier phase being half-defined.
- [x] Use phase exit conditions as the gate for promoting new migration work, especially for shell, domain, and persistence changes.
- [x] Revisit earlier phases only to repair constraints discovered later, not to reopen already settled architecture without cause.

## Phase 0: Discovery and Baseline Lock

### Status

- [x] Phase 0 repo-side discovery artifacts are implemented.
- [x] Phase 0 browser-driven interaction evidence for complex editor surfaces is captured.
- [x] Phase 0 long-form video interaction recordings are no longer required because scripted interaction evidence and screenshots already cover the baseline review needs.

### Objectives

- map the current UI and state ownership fully
- define migration risk boundaries
- prevent regression during the refactor

### Tasks

- [x] Inventory all current frontend entrypoints under `web/`.
- [x] Inventory all tab-specific states currently living in `web/main.js` and related runtime files.
- [x] Map every backend endpoint to the owning UI surface and generated artifact.
- [x] Document current `.zpinproj` and generated fragment structures.
- [x] Document all current modal flows, import/export flows, and save/load flows.
- [x] Identify all global variables that must be removed or wrapped during migration.
- [x] Capture representative screenshots of the current product for regression comparison.
- [x] Capture browser-driven interaction evidence for complex editor surfaces.
- [x] Capture long-form interaction recordings of complex editor surfaces for regression comparison, or explicitly retire that requirement when scripted evidence is sufficient.
- [x] Identify all high-cost rendering surfaces: pin/package editor, LVGL stage, clock tree, board editor canvas.
- [x] Define non-functional goals for load time, render time, and memory use.
- [x] Freeze critical behavioral baselines with tests.

### Deliverables

- [x] current-state architecture note
- [x] endpoint-to-feature matrix
- [x] state ownership map
- [x] regression checklist

### Implemented Artifacts

- [x] `docs/phase0_current_state_architecture.md`
- [x] `docs/phase0_endpoint_feature_matrix.md`
- [x] `docs/phase0_state_ownership_map.md`
- [x] `docs/phase0_regression_checklist.md`
- [x] `docs/phase0_interaction_evidence.md`
- [x] `docs/phase0_screenshots/modules-shell.png`
- [x] `docs/phase0_screenshots/pin-configurator-shell.png`
- [x] `docs/phase0_screenshots/pin-configurator-interaction.png`
- [x] `docs/phase0_screenshots/lvgl-layout-interaction.png`
- [x] `docs/phase0_screenshots/clock-configurator-interaction.png`
- [x] `docs/phase0_screenshots/board-editor-interaction.png`
- [x] `tests/test_phase0_baseline.py`

### Definition of Done for Phase 0

- [x] The current frontend runtime, persistence flows, generation flows, and major editor surfaces are inventoried.
- [x] The team has a trustworthy state ownership map instead of relying on implicit knowledge.
- [x] Critical current behavior has a regression checklist or equivalent baseline reference.
- [x] The repo is understood well enough that Phase 1 can begin without guessing where core behavior lives.

## Phase 1: Frontend Platform Foundation

### Status

- [x] Phase 1 planning chapter is documented.
- [x] Phase 1 implementation is complete.
- [x] Phase 1 frontend workspace bootstrap is started.

### Objectives

- establish the new React frontend without breaking the current product
- prepare an incremental migration path

### Phase 1 Intent

Phase 1 is where the repo stops being a legacy static frontend with incremental scripts and becomes a two-track application: the current production UI remains operational while a new React workspace is established with clear boundaries, stable tooling, and enforceable architecture rules.

This phase is not about feature parity. It is about building the platform that every later migration step depends on.

### Tasks

- [x] Create a new `frontend/` workspace with React + TypeScript + Vite.
- [x] Configure strict TypeScript settings.
- [x] Configure SCSS pipeline and CSS variable token system.
- [x] Add Radix primitives baseline and shared wrapper components.
- [x] Add Zustand with typed slice composition.
- [x] Add TanStack Virtual.
- [x] Add Monaco integration.
- [x] Add Dockview integration.
- [x] Add linting, formatting, and import boundary rules.
- [x] Add test stack for unit, presenter, and component tests.
- [x] Add contract layer for calling existing Flask endpoints.
- [x] Add feature flags to run the legacy and new frontend in parallel during migration.

### Deliverables

- [x] bootable React shell
- [x] typed API client
- [x] shared design token system
- [x] initial docking shell

### Phase 1 Implemented Artifacts

- [x] `frontend/package.json`
- [x] `frontend/vite.config.ts`
- [x] `frontend/src/app/App.tsx`
- [x] `frontend/src/contracts/api.ts`
- [x] `frontend/src/project/projectDocument.ts`
- [x] `frontend/src/project/useProjectShellController.ts`
- [x] `frontend/src/services/pinConfiguratorApi.ts`
- [x] `frontend/src/presenters/useShellPresenter.ts`
- [x] `frontend/src/views/RenodeProfileEditor.tsx`
- [x] `frontend/src/views/ShellView.tsx`
- [x] `frontend/src/workspace/WorkspaceDock.tsx`
- [x] `frontend/src/store/featureFlagsStore.ts`
- [x] `frontend/src/styles/index.scss`
- [x] `tests/test_frontend_shell.py`

### Organized Implementation

#### Workstream 1: Repository Bootstrap

- [x] Create the `frontend/` root and keep it independent from the legacy `web/` directory.
- [x] Add the base workspace files first: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`, and `src/styles/`.
- [x] Set TypeScript to strict mode from the start rather than loosening rules for initial speed.
- [x] Define the initial script contract immediately: `dev`, `build`, `preview`, `typecheck`, `lint`, and `test`.
- [x] Keep the initial shell minimal so the first milestone proves startup, build, and isolation rather than visual completeness.

#### Workstream 2: Development and Build Pipeline

- [x] Configure Vite for local development speed, predictable production builds, and future code splitting.
- [x] Add a Flask development proxy in Vite so frontend work can call the current backend without introducing duplicate server code.
- [x] Decide how production assets will be emitted and served before migrating real domains.
- [x] Keep the production output contract stable once chosen so later phases do not churn deployment behavior.
- [x] Verify that the production bundle can be served by Flask without requiring backend route redesign.

#### Workstream 3: Base Architectural Skeleton

- [x] Create the initial application skeleton with visible package boundaries for `app`, `contracts`, `services`, `presenters`, `views`, and `styles`.
- [x] Add one reference end-to-end flow that proves the architecture: a simple shell view driven by a presenter and fed by a typed service.
- [x] Keep React components presentational from the first committed screen onward.
- [x] Establish infrastructure utilities for API transport, environment config, error handling, and feature flags.
- [x] Prevent direct component-level `fetch` usage from entering the codebase during bootstrap.

#### Workstream 4: Shared UI and Styling Foundation

- [x] Configure SCSS compilation and CSS variable entrypoints for tokens, semantic colors, spacing, density, and z-index layers.
- [x] Add a reset/base stylesheet and a token file rather than spreading ad hoc values across components.
- [x] Add Radix-based wrapper components for foundational UI primitives such as dialogs, menus, tooltips, and popovers.
- [x] Create the first shell-level layout primitives for top bar, left rail, content region, right inspector area, and bottom output strip.
- [x] Keep styling primitive and infrastructural in Phase 1; deeper visual system work belongs in the design-system phase.

#### Workstream 5: State and Service Readiness

- [x] Add Zustand as the state library, but only scaffold the store composition pattern in Phase 1.
- [x] Avoid migrating domain state into the store before the project model is defined in Phase 2.
- [x] Create typed service modules for calling current Flask endpoints, even if only a few endpoints are exercised initially.
- [x] Define placeholder contracts for project metadata, backend health/status, and feature-flag state.
- [x] Ensure service and store modules are shaped for MVP layering, not for component-local convenience.

#### Workstream 6: Heavy Dependency Integration Readiness

- [x] Add Monaco integration in a way that supports lazy loading rather than front-loading all editor cost into the shell.
- [x] Add Dockview integration at shell level with one or two example panels to prove lifecycle and layout persistence hooks.
- [x] Add TanStack Virtual baseline utilities so large list and tree rendering can be introduced without architectural churn later.
- [x] Verify that these heavy dependencies coexist cleanly with Vite build and TypeScript configuration.
- [x] Keep their first usage shallow; Phase 1 should prove integration, not full feature rollout.

#### Workstream 7: Quality Gates and Team Workflow

- [x] Add ESLint and any import-boundary rules needed to keep presenters, views, and services separated.
- [x] Add a fast test runner and one smoke test for the shell boot path.
- [x] Add at least one type-driven or service-level test that proves the frontend contract layer compiles and runs under CI.
- [x] Make lint, typecheck, and test mandatory for Phase 1 completion.
- [x] Treat build reproducibility as a platform requirement, not a later hardening task.

### Suggested Phase 1 Repository Shape

- [x] `frontend/src/app/` for bootstrap, providers, shell composition, and application entry.
- [x] `frontend/src/contracts/` for DTOs, API schemas, and frontend-side project types.
- [x] `frontend/src/services/` for backend clients, transport helpers, and environment-aware service wrappers.
- [x] `frontend/src/presenters/` for orchestration patterns and shell-level reference presenters.
- [x] `frontend/src/views/` for presentational shell components.
- [x] `frontend/src/store/` for initial Zustand setup and slice composition helpers.
- [x] `frontend/src/styles/` for SCSS entrypoints, token definitions, reset, and theme variables.
- [x] `frontend/src/shared/` for reusable UI wrappers and infrastructure utilities that are not yet domain-specific.

### Phase 1 Execution Order

1. [x] Create the standalone `frontend/` workspace and make it boot.
2. [x] Add strict TypeScript, baseline scripts, and lint/test tooling.
3. [x] Add Flask proxying and decide the production bundle-serving contract.
4. [x] Create the initial folder boundaries for app, services, contracts, presenters, views, and styles.
5. [x] Add SCSS tokens and base layout primitives.
6. [x] Add typed API client infrastructure and one shell-level presenter flow.
7. [x] Add Dockview, Monaco, and virtualization readiness integrations at minimal depth.
8. [x] Verify build, proxy, test, and Flask-served production mode before moving into Phase 2.

### First Sprint Scope for Phase 1

- [x] Deliver a running React shell in local development.
- [x] Deliver typed service access to the current Flask backend.
- [x] Deliver one presenter-driven screen or shell widget as the reference implementation.
- [x] Deliver the initial styling token layer and shell layout primitives.
- [x] Deliver one Dockview-hosted panel and one lazily integrated Monaco panel stub.

### Milestone Gates

#### Gate A: Workspace Ready

- [x] `frontend/` exists, installs cleanly, and runs in development mode.
- [x] TypeScript strict mode is enabled and passing.
- [x] Build output is reproducible.

#### Gate B: Backend Integration Ready

- [x] Vite proxies to Flask successfully.
- [x] At least one typed service call to an existing endpoint works in development.
- [x] Production build can be served through Flask without backend behavioral changes.

#### Gate C: Architecture Ready

- [x] Presenter/view/service boundaries exist in code, not just in documentation.
- [x] No direct backend access is coming from shell components.
- [x] The repo has a reference pattern future domain migrations can copy.

#### Gate D: Platform Ready for Phase 2

- [x] Dockview, Monaco, and virtualization dependencies are integrated at baseline level.
- [x] Lint, typecheck, and tests are part of the normal workflow.
- [x] The new frontend is ready to receive the canonical project model work.

### Risks to Control in Phase 1

- [x] Do not allow the new shell to grow feature logic before the platform stabilizes.
- [x] Do not mix migrated React surfaces with unmanaged legacy DOM ownership in the same region.
- [x] Do not defer service typing until after multiple endpoints are already wired up.
- [x] Do not introduce docking or Monaco in a way that forces all runtime cost into the first paint.
- [x] Do not let Phase 1 expand into Phase 3 shell ambition; the goal is readiness, not visual completion.

### Definition of Done for Phase 1

- [x] The repo contains a dedicated React + TypeScript + Vite frontend workspace.
- [x] The workspace builds, type-checks, lints, and runs tests successfully.
- [x] The workspace can talk to the existing Flask backend in development through a proxy.
- [x] Flask can serve the production build in a production-like mode.
- [x] MVP folder boundaries and typed service boundaries are present and enforced.
- [x] Baseline integrations for Dockview, Monaco, and virtualization exist without forcing immediate full feature migration.
- [x] The codebase is ready to begin canonical project-model work in Phase 2.

## Phase 2: Canonical Project Model and Persistence

### Status

- [x] Phase 2 planning chapter is documented.
- [x] Phase 2 implementation is complete.

### Objectives

- unify state across tabs
- make save/load/export deterministic

### Phase 2 Intent

Phase 2 is where the new frontend stops being only a platform shell and becomes the authoritative owner of project state shape. The goal is to define one typed project document, one normalization path, and one persistence contract that every migrated domain can rely on.

This phase must eliminate ambiguity around what constitutes the current project, what is generated output versus user-authored state, and how the frontend maps to backend persistence and export flows.

### Tasks

- [x] Define `ProjectDocument` TypeScript interfaces aligned with backend normalization.
- [x] Define DTO schemas for API responses and import/export payloads.
- [x] Create project adapters to translate old runtime structures into the new model.
- [x] Move generated artifacts into explicit typed sections instead of implicit global fragments.
- [x] Create selectors for board context, active target, diagnostics counts, and generated output availability.
- [x] Implement layout persistence for workspace state separately from project content.
- [x] Support undo/redo at the project-command level.
- [x] Add migration/version logic for persisted project files.
- [x] Add project integrity checks for missing sections and stale generated outputs.

### Deliverables

- [x] canonical typed project model
- [x] persistence adapters
- [x] typed selectors and mutation commands

### Organized Implementation

#### Workstream 1: Canonical Document Definition

- [x] Define a frontend `ProjectDocument` that mirrors the backend normalization direction in `project_model.py`.
- [x] Separate persisted project content from runtime-only UI state and workspace-only layout state.
- [x] Explicitly model all cross-domain sections that will survive save/load and demo export.
- [x] Distinguish between source-of-truth user configuration, derived state, generated fragments, and diagnostics.
- [x] Add versioning fields and migration hooks from the first stable schema revision.

#### Workstream 2: Persistence Contract and DTO Layer

- [x] Define typed request and response DTOs for save, load, generate, import, export, and demo-app flows.
- [x] Keep transport DTOs separate from internal domain types so backend changes and frontend composition can evolve independently.
- [x] Add adapters that normalize backend payloads into frontend project state.
- [x] Add serializers that emit a stable persisted shape instead of leaking live store internals.
- [x] Define how missing, legacy, or partially populated project files are normalized on load.

#### Workstream 3: Project State Boundaries

- [x] Decide exactly which current `web/main.js` globals become persisted project fields.
- [x] Separate project content from ephemeral UI selection, open tabs, filters, zoom levels, and other workspace concerns.
- [x] Define which generated artifacts are persisted directly, which are regenerated, and which are cached for convenience.
- [x] Treat docking layout persistence as a separate model from project content persistence.
- [x] Make the frontend project model the only state shape that save/load flows are allowed to consume.

#### Workstream 4: Adapters for Legacy Runtime State

- [x] Normalize persisted legacy `pin_states`, `periph_states`, `periph_core_states`, and `external_device_states` into typed canonical project sections.
- [x] Add a board-aware pin-state rehydration adapter that restores saved AF selections by `pincm` and `function_id`, with `peripheral` and `signal` fallback when board definitions drift.
- [x] Wire the React project-load flow to fetch typed board details and rehydrate saved pin selections against the live board definition.
- [x] Surface the first migrated pin-state panel in the React shell so hydrated assignments are visible outside the legacy page.
- [x] Add the first pin-state mutation command by letting the migrated panel clear saved pin assignments through the project controller.
- [x] Add row selection and a pin detail inspector so the migrated pin panel can inspect one canonical assignment at a time.
- [x] Allow the migrated pin inspector to reassign the saved alt function for a pin against the live board definition.
- [x] Add the first editable pin property field by wiring the saved `bias_pull_up` flag through the project controller and pin detail inspector.
- [x] Expand the migrated pin inspector to cover the remaining legacy boolean property flags: `bias_pull_down`, `drive_open_drain`, and `input_enable`.
- [x] Build adapters that collect data from the current legacy runtime into the new canonical project shape.
- [x] Build adapters that restore canonical project data back into legacy-compatible surfaces during the migration window.
- [x] Avoid one massive translation layer; keep adapters domain-scoped so they can be retired incrementally.
- [x] Identify every legacy structure that currently contributes to `.zpinproj` persistence or generated outputs.
- [x] Prevent direct persistence of raw legacy globals once the canonical project model exists.

#### Workstream 5: Selectors, Derivations, and Validation

- [x] Add typed selectors for board context, active target, generated-output availability, diagnostics counts, and export readiness.
- [x] Move pin-assignment row and summary derivation into model-layer selectors so the migrated panel no longer encodes those rules in JSX.
- [x] Surface the first selector-driven pin validation rule in the migrated inspector by warning on `bias_pull_up` and `bias_pull_down` conflicts.
- [x] Extend migrated pin diagnostics with a selector-driven warning when a saved pin assignment targets a disabled peripheral.
- [x] Extend migrated pin diagnostics with a selector-driven warning when the same peripheral signal is claimed on more than one pin.
- [x] Move normalization and derivation logic out of views and presenters into model-layer functions.
- [x] Add integrity checks for required project sections, schema version, stale generated artifacts, and unsupported combinations.
- [x] Define when generated fragments are considered authoritative versus stale and requiring regeneration.
- [x] Keep selector output stable and predictable so presenters can compose view models without re-encoding business rules.

#### Workstream 6: Undo/Redo and Mutation Contract

- [x] Define project mutations as explicit typed commands rather than ad hoc object edits.
- [x] Establish the boundary between persistent domain mutations and transient UI-only mutations.
- [x] Add the first undo/redo-capable mutation layer at the project-document level.
- [x] Ensure commands can be serialized or replayed if future history tooling requires it.
- [x] Avoid building domain-specific mutation shortcuts that bypass the canonical project model.

#### Workstream 7: Save/Load/Export Flow Integration

- [x] Wire the canonical project model into save and load flows first, before deep domain migration.
- [x] Ensure generated artifact export and Renode simulation export read from the same project document.
- [x] Ensure demo export and future simulation workflows read from the same project document.
- [x] Add project integrity checks before persistence and before export operations.
- [x] Make schema migration and normalization part of every load path, not a special recovery flow.
- [x] Ensure project persistence can round-trip through frontend and backend without shape drift.

#### Workstream 8: Quality Gates for the Project Model

- [x] Add tests for schema normalization, migration, adapter behavior, and selector correctness.
- [x] Add round-trip tests that validate `frontend model -> save payload -> load payload -> frontend model` stability.
- [x] Add focused tests for missing-field defaults and legacy-version migration.
- [x] Add contract tests against backend expectations where the API shape is already stable.
- [x] Treat schema clarity and testability as mandatory for Phase 2 completion.

### Suggested Phase 2 Project Shape

- [x] `frontend/src/project/types.ts` for canonical project document types.
- [x] `frontend/src/project/dto.ts` for transport-level save/load/import/export DTOs.
- [x] `frontend/src/project/normalize.ts` for defaulting, migration, and normalization logic.
- [x] `frontend/src/project/serialize.ts` for outbound persistence and export shaping.
- [x] `frontend/src/project/selectors.ts` for typed derived state.
- [x] `frontend/src/project/commands.ts` for mutation and history-safe project commands.
- [x] `frontend/src/project/adapters/` for legacy runtime and backend translation layers.
- [x] `frontend/src/project/tests/` for normalization, round-trip, and selector coverage.

### Phase 2 Execution Order

1. [x] Define the canonical `ProjectDocument` and DTO boundaries.
2. [x] Define normalization, migration, and serialization rules.
3. [x] Separate persisted project state from workspace-only UI state.
4. [x] Add selectors and project-level command boundaries.
5. [x] Build adapters from legacy runtime state into the canonical model.
6. [x] Wire save/load flows to the canonical model.
7. [x] Wire export/generation flows to the same model.
8. [x] Add round-trip, migration, and selector tests before moving deeper into domain migration.

### First Sprint Scope for Phase 2

- [x] Deliver the first canonical `ProjectDocument` type and schema version.
- [x] Deliver normalization and serialization helpers for save/load.
- [x] Deliver one legacy-to-canonical adapter path for current persisted project content.
- [x] Deliver typed selectors for board context and generated-output availability.
- [x] Deliver at least one save/load round-trip test against the new model.

### Milestone Gates

#### Gate A: Schema Ready

- [x] Canonical project types exist and cover the currently persisted product surface.
- [x] DTO boundaries are separate from internal model types.
- [x] Normalization rules are explicit and testable.

#### Gate B: Persistence Ready

- [x] Save and load flows operate through the canonical project model.
- [x] Frontend and backend can round-trip the project document without shape drift.
- [x] Legacy or partial project files can be normalized safely.

#### Gate C: Domain Integration Ready

- [x] Selectors expose stable derived state for presenters.
- [x] Project-level command boundaries exist for future undo/redo and domain updates.
- [x] Generated outputs and export flows can read from one authoritative project document.

#### Gate D: Ready for Shell and Domain Migration

- [x] The project model is stable enough that Phase 3 and later domains do not need to invent local persistence shapes.
- [x] Workspace-only layout state remains separate from project content.
- [x] Adapter strategy exists for retiring legacy globals incrementally.

### Risks to Control in Phase 2

- [x] Do not let workspace layout and project content collapse into one oversized state object.
- [x] Do not persist raw store internals or presenter-specific structures.
- [x] Do not mix generated artifacts, source configuration, and diagnostics into one ambiguous section.
- [x] Do not postpone schema migration logic until after multiple incompatible saves already exist.
- [x] Do not wire domain migrations directly to legacy globals once the canonical project model is available.

### Definition of Done for Phase 2

- [x] A canonical typed `ProjectDocument` exists and is versioned.
- [x] Save/load flows use normalization and serialization based on that model.
- [x] Frontend and backend persistence shapes are aligned through explicit DTO and adapter boundaries.
- [x] Project state is clearly separated from workspace-only UI state.
- [x] Selectors and project-level mutation boundaries exist for later domain migration.
- [x] Round-trip, migration, and selector tests cover the critical persistence paths.
- [x] The codebase is ready for deeper workspace-shell and domain migration without inventing new persistence conventions.

## Phase 3: Professional Workspace Shell

### Objectives

- replace the current page-like UI with a serious engineering workspace

### Tasks

- [x] Build top command bar with save/load/import/export/build/simulate/test actions.
- [x] Build left navigation rail for major engineering domains.
- [x] Build Dockview-based center workspace with persistent panels.
- [x] Build right inspector stack for properties, diagnostics, codegen preview, and help.
- [x] Build bottom output zone for logs, build output, generated files, and simulation output.
- [x] Add command palette.
- [x] Add searchable quick-open for boards, peripherals, sensors, outputs, and panels.
- [x] Add status bar with board, workspace profile, dirty state, generator status, and simulator status.
- [x] Add density modes suitable for laptop and external monitor workflows.
- [x] Add persisted workspace layout presets.

### Deliverables

- [x] professional app shell
- [x] docking layout persistence
- [x] command palette
- [x] status bar and workspace context

### Current Baseline for Phase 3

- [x] A real React shell already exists with a top hero/metric band, left rail, Dockview-based center workspace, and right inspector.
- [x] The center workspace can already host generated artifact, protocol, Renode, transport, and pin-assignment panels.
- [x] The shell already exposes save/load, undo/redo, generated-artifact export, and Renode bundle export actions against the canonical project model.
- [x] The shell now persists preset-scoped Dockview layouts separately from the canonical project model.
- [x] The top area is now a compact command surface with grouped project, execution, export, density, and preset controls.

#### Workstream 1: Shell Chrome and Global Command Surface

- [x] Replace the current hero-style top area with a production command bar that groups project, generation, export, build, simulate, and test actions by workflow.
- [x] Split primary actions from destructive or infrequent actions using toolbar groups, split buttons, and overflow menus.
- [x] Add always-visible workspace context chips for board, package, project dirty state, artifact authority, and simulator readiness.
- [x] Define one command registration model so buttons, menus, quick-open, and future keyboard shortcuts all invoke the same presenter actions.
- [x] Keep the shell header compact enough for laptop screens; do not let metrics or descriptive copy consume the primary action area in the long term.

#### Workstream 2: Navigation, Panel Taxonomy, and Workspace Orientation

- [x] Convert the left rail from a board-list scaffold into a true workspace navigator for domains, project assets, outputs, simulation, and diagnostics.
- [x] Define a stable panel taxonomy so users can predict where generated files, Renode artifacts, diagnostics, and execution tooling live.
- [x] Add panel presets for common workflows such as board bring-up, protocol integration, code generation review, and Renode validation.
- [x] Make panel titles, icons, and grouping rules consistent across the docked workspace.
- [x] Ensure every migrated panel can be opened through both the rail and a command-driven path.

#### Workstream 3: Bottom Output Zone and Execution Visibility

- [x] Add a bottom workspace zone for logs, build output, simulation output, test results, and environment diagnostics.
- [x] Keep output panels dock-aware and presenter-driven rather than pushing execution text into ad hoc modal dialogs or inspector-only areas.
- [x] Support clear severity states for info, warning, error, and success across execution logs.
- [x] Add filter, clear, copy, and follow-tail affordances for long-running logs.
- [x] Treat build/sim/test visibility as part of the shell, not as a later domain-specific convenience.

#### Workstream 4: Workspace Persistence and Restoration

- [x] Define a dedicated workspace-layout document separate from `ProjectDocument` so panel layout, open editors, and UI affordances can persist without polluting project content.
- [x] Persist panel arrangement, active groups, visible outputs, and inspector focus in a workspace-only model.
- [x] Decide which shell preferences are machine-local, user-local, or project-local before implementing layout save/restore.
- [x] Add at least one resilient default layout restore path for first run, corrupted layout state, and incompatible layout versions.
- [x] Do not let Dockview internals become the long-term persistence format without a thin adapter boundary.

#### Workstream 5: Command Discovery, Keyboarding, and Status Feedback

- [x] Add a command palette backed by the same typed command registry used by toolbar buttons.
- [x] Add quick-open for boards, panels, generated files, diagnostics, and recent project actions.
- [x] Introduce a real status bar for board, profile, dirty state, background activity, and simulator/build readiness.
- [x] Define shell-level keyboard shortcuts for save, load, export, search, panel switching, and command palette activation.
- [x] Keep status feedback concise and operational; move long explanations into inspectors, tooltips, or help panels.

### Suggested Phase 3 Workspace Shape

- [x] `frontend/src/workspace/shell/` for command bar, status bar, navigation rail, and output-zone composition.
- [x] `frontend/src/workspace/panels/` for panel descriptors, panel registration, and panel metadata.
- [x] `frontend/src/workspace/commands/` for command registry, command palette sources, and shortcut bindings.
- [x] `frontend/src/workspace/layout/` for workspace-only layout state, restore logic, and persistence adapters.
- [x] `frontend/src/workspace/output/` for logs, execution panels, and diagnostics aggregation.
- [x] `frontend/src/workspace/navigation/` for rail items, quick-open indexes, and domain grouping metadata.

### Phase 3 Execution Order

1. [x] Convert the top scaffold into a real command bar and workspace context strip.
2. [x] Formalize panel taxonomy and navigation so the shell is navigable without relying on implementation knowledge.
3. [x] Add the bottom output zone before deep build/sim/test migration so execution surfaces have a real home.
4. [x] Add command registry and command palette so all major shell actions share one invocation model.
5. [x] Add status bar and shell-level feedback once command and output flows exist.
6. [x] Add workspace layout persistence only after panel taxonomy and restore defaults are stable.

### Milestone Gates for Phase 3

#### Gate A: Shell Structure Ready

- [x] The workspace has a clear top command area, left navigation, center dock, right inspector, and bottom output zone.
- [x] Shell regions are purposeful rather than decorative; each one owns a stable category of workflow.
- [x] The shell can host current migrated panels without layout ambiguity.

#### Gate B: Navigation and Commands Ready

- [x] Users can reach major panels and actions through visible navigation and command-driven access.
- [x] Buttons, shortcuts, and palette actions are backed by one command registry.
- [x] The shell no longer depends on hidden or one-off action placements for core workflows.

#### Gate C: Persistence and Output Ready

- [x] Execution output has a dedicated home inside the shell.
- [x] Layout state is persisted separately from the canonical project model.
- [x] Restoring a workspace does not corrupt project content or rely on Dockview internals leaking into domain code.

#### Gate D: Ready for Phase 4 Design-System Hardening

- [x] The shell interaction model is stable enough that Phase 4 can standardize components instead of redesigning regions.
- [x] Workspace shell affordances are dense, legible, and credible for engineering use on laptop and multi-monitor setups.
- [x] Future domain migrations can plug into the shell without redefining the workspace architecture.

### UX Constraints for Phase 3

- [x] Do not let branding or marketing-style hero content dominate the shell once the command bar is introduced.
- [x] Do not scatter project actions between inspector-only buttons, dock-local controls, and hidden menus without one governing command model.
- [x] Do not persist workspace layout inside `ProjectDocument`.
- [x] Do not make logs, diagnostics, and execution output compete with inspector space meant for domain editing.
- [x] Do not introduce a command palette that bypasses presenter and command boundaries already established in Phase 2.

### Definition of Done for Phase 3

- [x] The product has a working engineering workspace shell rather than a page-style legacy layout.
- [x] Primary workspace regions exist and are usable: top command area, left navigation, docked center, right inspector, and bottom output zone.
- [x] The workspace can host migrated functionality without requiring another shell redesign.
- [x] Phase 4 design-system work can proceed against a real shell instead of a speculative one.

## Phase 4: Design System and Interaction Language

### Objectives

- create a brilliant, unified, centralized UI/UX language

### Tasks

- [x] Define semantic color tokens for success, warning, error, info, selection, focus, disabled, codegen risk, simulation, and hardware signals.
- [x] Define typography scales for panel headers, inspectors, data labels, code labels, and technical metadata.
- [x] Define spacing, control sizes, icon sizes, and panel rhythm tokens.
- [x] Define component variants for engineering data density.
- [x] Build reusable primitives for split buttons, toolbar groups, property rows, diagnostic badges, section headers, and empty states.
- [x] Build shared inspector patterns for field groups, dependency warnings, reset actions, and generated symbol previews.
- [x] Build unified dialogs for import/export/save/load/build/test actions.
- [x] Standardize keyboard shortcuts and focus movement.
- [x] Standardize context menus and selection behavior across all editors.
- [x] Define motion rules for docking, drawers, toasts, and transient overlays.

### Deliverables

- [x] design token package
- [x] reusable engineering component library
- [x] UX interaction specification

### Current Baseline for Phase 4

- [x] The frontend already has a token/base styling split with shared SCSS entrypoints.
- [x] A first set of Radix-backed primitives already exists for dialogs, dropdowns, popovers, and tooltips.
- [x] The shell already has initial layout primitives for top, left, center, right, and bottom regions.
- [x] Tokens now include a first semantic engineering layer for shell, status, focus, and output surfaces.
- [x] Shared component coverage now spans inspector rows, command bars, context menus, empty states, diagnostics, and dense technical data presentation.
- [x] Interaction rules are now documented explicitly in `docs/frontend_phase4_interaction_spec.md`.

#### Workstream 1: Semantic Token System

- [x] Split raw foundation tokens from semantic tokens so engineering meaning such as conflict, generated, simulation-ready, stale, and disabled is explicit.
- [x] Define color roles for command surfaces, inspectors, output zones, Monaco-adjacent panels, and dense data tables rather than only generic app colors.
- [x] Define typography roles for workspace chrome, panel titles, technical metadata, diagnostics, code-adjacent labels, and inspector field captions.
- [x] Define density-aware spacing and sizing tokens that support laptop, standard desktop, and multi-monitor engineering layouts.
- [x] Define elevation, border, focus, and layering tokens for docking, overlays, menus, and transient feedback.

#### Workstream 2: Engineering Component Primitive Set

- [x] Build workspace-specific primitives for command bars, toolbar groups, split buttons, status chips, inspector sections, and output headers.
- [x] Build field-row primitives for label/value alignment, inline validation, reset affordances, and dependency warnings.
- [x] Build diagnostic primitives for severity badges, summary strips, grouped warning blocks, and codegen/simulation state markers.
- [x] Build shared empty/loading/error states that match the engineering workspace rather than generic product placeholders.
- [x] Build reusable shells for docks, inspectors, lists, and output panels so future domain screens inherit layout consistency by default.

#### Workstream 3: Inspector and Panel Interaction Language

- [x] Standardize inspector anatomy: section headers, subsection rhythm, inline help, advanced settings reveal, and reset-to-derived actions.
- [x] Standardize how selections, hover targets, warnings, and generated-output previews appear across pins, protocols, Renode, and later domains.
- [x] Define one pattern for editable versus derived/generated fields so ownership is visually obvious.
- [x] Define how read-only generated artifacts, editable source inputs, and authority/staleness indicators coexist in one panel.
- [x] Prevent every domain from inventing its own inspector layout, warning placement, and field grouping logic.

#### Workstream 4: Menus, Dialogs, and Command Surfaces

- [x] Standardize modal and non-modal flows for save/load/export/build/test/simulation actions.
- [x] Define shared dialog layouts for confirmations, environment warnings, export summaries, and task-launch configuration.
- [x] Standardize context menus for dock panels, artifact editors, selection surfaces, and domain lists.
- [x] Make toolbar actions, overflow menus, command palette entries, and keyboard shortcuts feel like one system rather than parallel UIs.
- [x] Define toast/inline-status rules so transient feedback is useful without competing with persistent diagnostics.

#### Workstream 5: Motion, Focus, and Interaction Consistency

- [x] Define motion rules for docking transitions, panel activation, overlay appearance, command palette open/close, and transient status feedback.
- [x] Standardize focus-visible treatment across buttons, menus, inspectors, editors, and canvas-adjacent surfaces.
- [x] Define selection rules for rows, tree items, tab-like controls, dock panels, and inspector-linked objects.
- [x] Document keyboard movement expectations across dense panels before each domain invents its own tab/arrow behavior.
- [x] Keep animation restrained and operational: motion should clarify state changes, not decorate the shell.

### Suggested Phase 4 Package Shape

- [x] `frontend/src/styles/tokens/` for foundation and semantic token layers.
- [x] `frontend/src/styles/themes/` for density, contrast, and future theme variants.
- [x] `frontend/src/shared/ui/primitives/` for low-level accessible wrappers.
- [x] `frontend/src/shared/ui/components/` for engineering-oriented composed controls.
- [x] `frontend/src/shared/ui/inspectors/` for reusable inspector section and property-row patterns.
- [x] `frontend/src/shared/ui/feedback/` for diagnostics, toasts, badges, status chips, and empty states.
- [x] `frontend/src/shared/ui/commands/` for command bars, menus, palette surfaces, and shortcut hints.

### Phase 4 Execution Order

1. [x] Formalize foundation and semantic tokens before broad visual rewrites.
2. [x] Build the first engineering primitives around the Phase 3 shell surfaces: command bar, status chips, inspector rows, and diagnostic badges.
3. [x] Standardize inspector composition and generated-versus-editable field treatment before deep domain migration expands.
4. [x] Standardize dialog, menu, and command-surface patterns once command workflows are stable.
5. [x] Add motion and focus rules after primary component anatomy is fixed.
6. [x] Move domain screens onto shared primitives incrementally rather than doing a one-shot visual rewrite.

### Milestone Gates for Phase 4

#### Gate A: Token System Ready

- [x] Foundation and semantic tokens are distinct and documented.
- [x] Shell, inspector, diagnostic, and execution surfaces can all reference shared semantic tokens.
- [x] Density and focus behavior are controlled by shared rules rather than component-local styling guesses.

#### Gate B: Primitive Set Ready

- [x] Core engineering primitives exist for command bars, inspector rows, feedback states, and toolbar actions.
- [x] New workspace surfaces can be built from shared components instead of bespoke ad hoc markup.
- [x] Radix wrappers and composed engineering controls have a clear separation of purpose.

#### Gate C: Interaction Language Ready

- [x] Dialogs, menus, context actions, and command surfaces behave consistently.
- [x] Selection, focus, and warning presentation are standardized across multiple shell surfaces.
- [x] Inspector structure is reusable and predictable across migrated domains.

#### Gate D: Ready for Broad Domain Reuse

- [x] The shell and at least a few migrated domain panels visibly share one coherent interaction and visual language.
- [x] Future domain migration can proceed without inventing one-off UI conventions.
- [x] The design system is strong enough to support dense technical workflows under real usage pressure.

### UX Constraints for Phase 4

- [x] Do not equate a design system with a color refresh; the real goal is interaction consistency under engineering density.
- [x] Do not let generic dashboard patterns replace domain-specific technical clarity.
- [x] Do not bury warnings, authority state, or generated-versus-editable ownership behind subtle styling only.
- [x] Do not introduce multiple competing button, dialog, or inspector idioms across shell and domain panels.
- [x] Do not make visual polish dependent on dark-mode-first defaults if the product is mainly used in mixed engineering environments.

### Definition of Done for Phase 4

- [x] Shared tokens and component primitives exist for building future screens consistently.
- [x] Core interaction patterns such as inspectors, dialogs, toolbars, and context menus are standardized.
- [x] New workspace features can be built from reusable patterns instead of one-off visual and interaction decisions.
- [x] The shell and upcoming migrated domains share one coherent UI and interaction language.

## Phase 5: Domain-by-Domain Presenter Migration

### Objectives

- migrate feature logic out of `web/main.js` and tab globals into MVP modules

### Tasks

- [x] Create one presenter per migrated React-owned domain and make remaining legacy ownership explicit through a retirement plan.
- [x] Move API orchestration from legacy imperative functions into presenter actions.
- [x] Move validation into model/selectors where possible.
- [x] Move mutation logic from DOM events into command handlers.
- [x] Replace DOM query/update patterns with React rendering and controlled presenters for the migrated shell-owned domains.
- [x] Keep each migrated React-owned domain independently mountable in the docked workspace.

### Domain Tasks

- [x] Pin Configurator presenter
- [x] Module Configurator presenter
- [x] Peripheral Configurator presenter
- [x] Clock Configurator presenter
- [x] Protocol Editor presenter
- [x] LVGL Layout presenter
- [x] Interrupt Configurator presenter
- [x] Board Editor presenter
- [x] Sensor Parser presenter
- [x] Package Manager presenter
- [x] Zephyr Catalog presenter
- [x] Generated Output presenter
- [x] Build/Sim/Test presenter

### Deliverables

- [x] domain presenter layer
- [x] typed domain command APIs
- [x] removal plan for remaining legacy globals

### Definition of Done for Phase 5

- [x] Major product domains are driven by presenter-layer orchestration rather than legacy global scripts.
- [x] Domain mutation and backend coordination paths are explicit and typed.
- [x] Legacy global ownership is shrinking through planned adapters and retirement paths.
- [x] The product’s core behavior is now controllable through MVP-aligned modules.

## Phase 6: Editor Surface Modernization

### Objectives

- rebuild heavy interaction surfaces with performance and clarity in mind

### Pin / Package Surface

- [x] Rebuild package/pin map on Canvas or SVG with presenter-driven selection.
- [x] Add semantic overlays for mux conflicts, electrical constraints, and assigned peripherals.
- [x] Add hover inspectors and quick assign menus.
- [x] Add zoom, pan, fit-to-package, and filtered pin highlighting.

### Clock Tree Surface

- [x] Rebuild clock tree with SVG or Canvas.
- [x] Add live frequency propagation and invalid path highlighting.
- [x] Add lane-style visual grouping for sources, muxes, PLLs, buses, and consumers.

### LVGL Surface

- [x] Keep the existing LVGL validation and codegen work, but host it in React presenters and docked panels.
- [x] Split stage, hierarchy, style library, validation, simulation log, and props into coordinated panels.
- [x] Use Canvas/SVG for stage rendering depending on observed performance and inspectability needs.

### Board Editor Surface

- [x] Rebuild package and external-device placement with a dedicated scene/presenter model.
- [x] Add layers for package, pins, external devices, buses, and annotations.

### Deliverables

- [x] modern editor surfaces with consistent interaction model
- [x] shared scene graph/event abstractions where practical

### Definition of Done for Phase 6

- [x] High-value editor surfaces run on the new architecture with presenter-driven interaction.
- [x] Canvas/SVG scene behavior no longer depends on legacy DOM control patterns for the core experience.
- [x] The product’s most interaction-heavy tools are modernized enough to validate the new frontend direction under real usage.
- [x] Editor surfaces now fit naturally inside the workspace shell and shared design system.

## Phase 7: Large-Scale Data UX

### Objectives

- handle large engineering datasets cleanly and fast

### Tasks

- [x] Virtualize board lists, sensor results, package jobs, MCU jobs, diagnostics, search results, and large trees.
- [x] Build a shared virtualized tree/list component using TanStack Virtual.
- [x] Add fuzzy filtering and group collapsing without sacrificing keyboard access.
- [x] Add pinned rows and “recently used” sections for engineering workflows.
- [x] Add split-detail views for selected catalog items and devices.

### Deliverables

- [x] virtualized list primitives
- [x] scalable tree and log experiences

### Definition of Done for Phase 7

- [x] Large lists, trees, logs, and catalogs remain responsive under realistic engineering-scale data.
- [x] Shared virtualization and filtering primitives exist for future data-heavy panels.
- [x] Large-data usability no longer depends on naive full rendering or bespoke ad hoc list behavior.
- [x] The new workspace can scale without obvious degradation as more migrated data surfaces appear.

## Phase 8: Monaco-Centered Artifact Experience

### Objectives

- make code, overlays, scripts, and diagnostics first-class citizens

### Tasks

- [x] Create dockable Monaco panels for overlay, `prj.conf`, generated C, generated headers, Renode `.resc`, and Robot tests.
- [x] Add diff views between generated and saved artifacts.
- [x] Add synchronized navigation from diagnostics to generated code sections.
- [x] Add copy/export/save actions from Monaco panels.
- [x] Add read-only and editable modes depending on artifact ownership.
- [x] Add syntax highlighting, markers, and decorations for codegen diagnostics.

### Deliverables

- [x] professional code and script review experience
- [x] integrated diff and diagnostics flow

### Definition of Done for Phase 8

- [x] Generated artifacts and scripts are first-class, inspectable surfaces inside the workspace.
- [x] Monaco-backed review, diff, and diagnostics flows are integrated rather than bolted on.
- [x] Users can navigate from diagnostics to artifact content within the product.
- [x] Artifact inspection now feels like part of the engineering workflow instead of an afterthought.

## Phase 9: Build, Renode, and Test UX

### Objectives

- unify generation, demo export, build, simulation, and testing into one coherent workflow

### Tasks

- [x] Build a dedicated Build/Sim/Test workspace panel.
- [x] Add presenter actions for generate, export demo app, build demo app, start Renode, stop Renode, and run Robot tests.
- [x] Add support for backend-driven task history and logs.
- [x] Add live console output viewer.
- [x] Add machine profile selector for supported Renode boards.
- [x] Add clear unsupported-board messaging when no Renode profile exists.
- [x] Add generated VS Code task export for demo apps.
- [x] Add build environment diagnostics, including missing toolchain and Python mismatches.

### Deliverables

- [x] unified engineering execution console
- [x] visible build/sim/test pipeline
- [x] actionable environment diagnostics

### Definition of Done for Phase 9

- [x] Users can move from configuration to build, simulation, and smoke testing without leaving the workspace context.
- [x] Build, Renode, and test controls exist in one coherent operational surface.
- [x] Execution logs and environment diagnostics are visible enough to support real debugging and validation.
- [x] The frontend is functionally connected to the repo’s demo export and Renode test direction.

## Phase 10: Accessibility, Keyboarding, and Power-User Flow

### Objectives

- ensure the product is not just visually upgraded but operationally elite

### Tasks

- [x] Full keyboard navigation across docked panels.
- [x] Contextual shortcut reference dialog.
- [x] Focus-visible and selection-visible rules for dense technical panels.
- [x] Screen-reader labeling for dialogs, trees, editors, and command results.
- [x] High-contrast and color-safe engineering theme variants.
- [x] Bulk actions and multi-select behaviors in trees and editors.

### Deliverables

- [x] accessible engineering workspace
- [x] power-user shortcut model

### Definition of Done for Phase 10

- [x] Core workspace flows are keyboard-navigable and operationally efficient.
- [x] Focus, selection, and accessibility behavior are standardized across dense engineering panels.
- [x] The product is materially more usable for power users and more accessible for broader usage.
- [x] Interaction consistency now holds under real workflow pressure rather than only in ideal demos.

## Phase 11: Testing and Quality Gates

### Objectives

- lock behavior while allowing deep frontend change

### Tasks

- [x] Unit test store slices, selectors, and normalization.
- [x] Unit test presenters and async command flows.
- [x] Component test design-system primitives.
- [x] Component test panel shells and inspectors.
- [x] Integration test project save/load/export flows.
- [x] Integration test docking persistence.
- [x] Browser test critical engineering flows.
- [x] Keep compile-backed and Renode-backed flows in CI where environment supports them.
- [x] Add performance budgets for large trees and editor surfaces.

### Deliverables

- [x] frontend quality gate matrix
- [x] regression suite for professional workspace behavior

### Definition of Done for Phase 11

- [x] The refactor is protected by unit, integration, and workflow-level automated validation.
- [x] Quality gates exist for stores, presenters, components, and critical user flows.
- [x] Performance expectations are captured for important large-data and editor surfaces.
- [x] Confidence in the refactor depends on executable checks, not manual reassurance alone.

## Phase 12: Incremental Cutover Strategy

### Objectives

- replace the old UI without a risky big-bang rewrite
- keep dual-run rollout, rollback posture, and retirement criteria visible in the React shell

### Tasks

- [x] Start with dual-run mode: legacy frontend remains default while the new shell is feature-flagged.
- [x] Migrate one domain at a time into the new workspace.
- [x] Use adapters to read legacy state while the new project model is being adopted.
- [x] Move generated output and project save/load early, because every domain depends on them.
- [x] Migrate the workspace shell before migrating all deep editor surfaces.
- [x] Retire legacy tabs only after feature parity and test parity are proven.
- [x] Remove obsolete DOM imperative utilities as domains fully cut over.

### Delivered Artifacts

- [x] `docs/frontend_cutover_strategy.md` defines the dual-run modes, migration order, retirement criteria, and removal sequence.
- [x] `frontend/src/domains/legacy/cutoverStrategy.ts` derives rollout posture from the feature flags and retirement-plan ownership data.
- [x] `frontend/src/views/ShellView.tsx` exposes the Phase 12 cutover panel so rollout order and rollback criteria stay visible inside the workspace shell.

### Suggested Migration Order

- [x] project model and save/load
- [x] generated outputs and Monaco panels
- [x] shell and docking workspace
- [x] module/peripheral/clock simpler forms
- [x] protocol editor
- [x] LVGL workspace
- [x] pin/package canvas
- [x] board editor surface
- [x] interrupt/cross-domain diagnostics

### Definition of Done for Phase 12

- [x] The legacy frontend can be retired in controlled slices with explicit parity and rollback criteria.
- [x] Dual-run and migration sequencing rules are defined well enough to avoid a big-bang cutover.
- [x] The team knows the order in which legacy surfaces will be replaced and removed.
- [x] Final removal of old utilities and tabs is governed by proof, not optimism.

## Phase 13: Packaging and Deployment

### Objectives

- ensure the professional frontend fits every current delivery path

### Tasks

- [x] Serve React build through Flask for browser deployment.
- [x] Ensure the VS Code extension can host the new frontend bundle cleanly.
- [x] Keep west extension launch behavior intact.
- [x] Preserve headless/API-only backend workflows.
- [x] Add production build optimizations for Monaco and heavy editor surfaces.
- [x] Add source-map strategy suitable for extension debugging and production support.

### Deliverables

- [x] production-ready packaging plan
- [x] VS Code extension compatibility path

### Delivered Artifacts

- [x] `docs/frontend_packaging_plan.md` defines browser, Flask, west, headless, and VS Code extension delivery mechanics.
- [x] `frontend/vite.config.ts` now differentiates browser and extension source-map targets while preserving chunk-splitting for Monaco and other heavy editor surfaces.
- [x] `vscode-extension/scripts/prepare-package.mjs` stages a packaged runtime containing the React bundle and backend assets for VS Code hosting.
- [x] `backend_ts/src/server.ts`, `run.py`, and `scripts/west/configure.py` now route browser-facing delivery paths to `/app` without breaking API-only startup.

### Definition of Done for Phase 13

- [x] The refactored frontend can be built and served in browser/Flask deployment mode.
- [x] The VS Code extension has a clear hosting and debugging path for the new frontend bundle.
- [x] Packaging and source-map strategy are defined well enough to support shipping and maintenance.
- [x] Delivery mechanics are no longer a blocker to adopting the refactored frontend.

## Definition of Done for the Refactor

- [x] All core domains render inside the new docked React workspace.
- [x] All project-affecting state is stored in the canonical typed project model.
- [x] Views are presentational; presenters own orchestration; models own state and rules.
- [x] Generated artifacts, build, simulation, and tests are accessible from one unified UI.
- [x] Legacy `web/main.js` global orchestration is removed or reduced to a thin compatibility bridge.
- [x] Frontend UX is consistent, keyboard-friendly, accessible, and performant under large data loads.

## Immediate Next Actions

- [x] Complete the final legacy-shell retirement slices described in `docs/frontend_cutover_strategy.md` and remove the remaining compatibility bridge when rollback is no longer required.
- [x] Keep Phase 11, 12, and 13 validation commands green in CI and release packaging flows as the legacy shell is retired.
- [x] Decide whether the optional Phase 0 long-form interaction recordings are still needed; if not, retire that open checklist item explicitly.