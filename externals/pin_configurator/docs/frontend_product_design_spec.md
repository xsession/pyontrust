# Pin Configurator Frontend Product Design Spec

## Purpose

This document turns the platform research and the existing frontend refactor plans into a concrete product design target for the Pin Configurator workspace.

It is intentionally product-facing rather than framework-facing. The question it answers is not which library to use, but what the frontend should feel like when the engineering workspace is complete.

## Product position

Pin Configurator should behave like an embedded engineering workstation, not a form-heavy utility page.

The product needs to support four continuous loops:

- choose the target board and workspace scope
- configure pins, modules, clocks, protocols, and simulation assets
- inspect generated artifacts and validation feedback
- verify readiness through build, simulation, and test outputs

The frontend should keep those loops visible at the same time instead of making the user jump between disconnected pages.

## UX principles

### 1. Canvas-first, not form-first

The visual editor or primary domain surface is the product center. Peripheral lists, inspectors, and generated outputs exist to support that center.

### 2. Persistent shell

The shell must remain stable while the active editor changes. Navigation, command surfaces, inspector structure, and output routing should stay consistent across pins, clocks, LVGL, protocols, and Renode.

### 3. Immediate validation

Configuration problems must appear inline and as close as possible to the originating action. The frontend should surface conflicts, incomplete configuration, and generation blockers before export time.

### 4. Artifact transparency

The user must always be able to answer three questions quickly:

- what is editable
- what is generated
- what will be exported

### 5. Workspace continuity

The shell should preserve layout, density, recent actions, active outputs, and active panels so repeat visits feel like resuming work rather than reopening a wizard.

## Target layout model

The default shell is a workstation-style four-zone layout.

### Top bar

Purpose:

- project identity
- command palette access
- save, load, export, build, simulate, and test actions
- layout preset and density selection
- quick status summary

Requirements:

- no marketing hero copy
- actions grouped by workflow purpose
- keyboard-first access for primary commands

### Left rail

Purpose:

- workspace navigation
- board switching
- layout preset switching
- output channel routing
- quick project signals

Requirements:

- support one-click movement between major tool surfaces
- keep inventory and routing decisions out of the main dock
- remain compact enough to avoid stealing focus from the main workspace

### Center workspace

Purpose:

- docked primary editors and artifact viewers
- focus the active engineering task

Requirements:

- center region must default to the currently active engineering flow
- generated editors and simulation assets must live beside, not outside, the active task
- panel focus changes should be fast and reversible

### Right inspector

Purpose:

- project persistence state
- artifact ownership and review
- selection-aware details
- workflow-specific notices and calls to action

Requirements:

- one consistent inspector language across domains
- use stacked sections rather than bespoke per-panel sidebars when possible
- clearly separate editable values from derived read-only outputs

### Bottom strip

Purpose:

- execution outputs
- diagnostics
- readiness status
- build, simulation, and test review

Requirements:

- output routing is always explicit
- user can switch channels without losing shell context
- logs and readiness should read like workflow state, not raw console noise only

## Shell information hierarchy

The frontend should communicate in this order:

1. where the user is
2. what target or project is active
3. what the active workflow step is
4. what needs attention now
5. what artifacts or outputs are available

This order matters more than any visual style choice.

## Interaction model

### Primary interaction families

- direct visual manipulation for pins, layouts, and topology-like surfaces
- structured forms for precise property entry
- dock switching for work-mode changes
- command palette for fast navigation and repeat actions
- bottom-strip review for verification and diagnostics

### Fast-path actions

The fastest operations should always be available without hunting:

- select board
- save project
- load project
- export artifacts
- export Renode bundle
- focus generated overlay
- focus generated config
- focus simulation assets
- run build output review
- run simulation output review
- run test output review

### Keyboard requirements

- command palette must remain the global accelerator
- dock focus shortcuts should map to the most important panels
- status and outputs should be navigable without pointer-only affordances

## Visual design direction

### Overall tone

The product should look precise, deliberate, and durable. It should resemble a professional workstation more than a landing page.

### Surfaces

- chrome surfaces should feel stable and slightly elevated
- working panels should have clear boundaries
- active surfaces should be highlighted with restrained emphasis
- background treatment should support depth without adding distraction

### Color system

- one primary accent color
- semantic colors for success, warning, and error
- muted support tones for metadata and structure
- avoid using color as the only indicator of state

### Typography

- strong, compact headings
- highly legible body copy
- monospace only where artifacts or code need it
- labels should read as information scent, not decoration

## Domain-specific expectations

### Pin assignment surfaces

- conflict visibility is mandatory
- selected pin context must be mirrored in the inspector
- alternative functions and ownership must be scan-friendly

### Clock configuration

- tree relationships should remain visible while editing leaf values
- derived frequencies and warnings must update immediately

### Protocol editor

- protocol entries should feel compositional, not like spreadsheet rows only
- generated header and source outputs must be easy to inspect beside edits

### LVGL layout

- hierarchy, stage, and property model must stay synchronized
- simulation log should remain attached to the workspace, not detached from it

### Renode profile and tests

- simulation assets should feel like first-class project outputs
- RESC and Robot review should sit naturally beside generated overlay and config review

## Validation model

Validation should exist in four layers:

- inline field or selection validation
- panel-level readiness and issue summaries
- inspector notices for ownership and blocking conditions
- bottom-strip readiness through output and diagnostics channels

## Non-goals

- Do not make the product look like a generic SaaS dashboard.
- Do not hide core engineering data behind excessive modal flows.
- Do not make code generation feel separate from configuration.
- Do not introduce per-tool shell behavior that breaks workspace consistency.

## Acceptance criteria

The frontend is aligned with this design spec when:

- the user can identify the active board, active workflow stage, and active output channel at a glance
- navigation, dock focus, inspector review, and output review feel like one shell rather than separate tools
- generated artifacts are visibly distinguished from editable project state
- major engineering flows follow the same shell grammar
- validation appears before export and remains visible after changes
