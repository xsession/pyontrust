# Frontend Phase 4 Interaction Specification

## Purpose

This document defines the shared interaction language that now backs the Phase 3 workspace shell. It complements the implementation in `frontend/src/styles/tokens/`, `frontend/src/styles/themes/`, `frontend/src/shared/ui/primitives/`, `frontend/src/shared/ui/components/`, `frontend/src/shared/ui/commands/`, `frontend/src/shared/ui/inspectors/`, and `frontend/src/shared/ui/feedback/`.

## Token Layers

- Foundation tokens live in `frontend/src/styles/tokens/_foundation.scss` and hold raw color, radius, spacing, sizing, motion, and typography values.
- Semantic tokens live in `frontend/src/styles/tokens/_semantic.scss` and express engineering meaning such as success, warning, error, generated, selection, command-surface, and workspace chrome roles.
- Density rules live in `frontend/src/styles/themes/_density.scss`.
  - Default density uses `--control-height-regular` and `--panel-rhythm-regular`.
  - `:root[data-density="compact"]` is the preferred laptop engineering mode.
  - `:root[data-density="spacious"]` is reserved for multi-monitor review layouts.
- Contrast overrides live in `frontend/src/styles/themes/_contrast.scss`.
- Global focus and motion rules live in `frontend/src/styles/_base.scss`.

## Command Surfaces

### Shared anatomy

- `SplitButton` is used when one action has a dominant path but related actions must remain adjacent.
- `ToolbarGroup` is used for named clusters such as Commands, Project, History, and Export.
- `CommandSurfaceDialog` is the standard modal shell for command-heavy flows.
- `ContextMenu` is the standard overflow/context action surface for list rows and inspector-linked cards.
- `ShortcutHint` is the only shortcut badge style; shortcuts should not be rendered as freeform muted text anymore.

### Current shell rules

- The command palette remains the primary global quick-open surface.
- The workspace actions dialog is the reference layout for save, load, export, and future build/test/simulation launch flows.
- Overflow menus and context menus must expose the same action names as toolbar buttons and palette entries.
- Actions that are unavailable should stay visible but disabled, with explanation inline or in a nearby notice rather than disappearing.

### Keyboard map

The current global registry lives in `frontend/src/workspace/commands/shortcutBindings.ts`.

- `Ctrl+K`, `Ctrl+P`, `Ctrl+F`: open command palette
- `Ctrl+S`: save project
- `Ctrl+O`: load project
- `Ctrl+E`: export artifacts
- `Ctrl+Shift+E`: export Renode bundle
- `Alt+1..8`: focus dock panels

## Inspector Language

### Shared anatomy

- `InspectorSection` defines section title, summary, optional actions, and body layout.
- `PropertyGrid` and `PropertyRow` define aligned label/value presentation.
- `InspectorNotice` defines inline help, dependency warnings, reset guidance, and authority messaging.
- `GeneratedSymbolPreview` defines compact generated-output symbol previews.
- `DiagnosticBadge` and `StatusChip` define severity and state markers.
- `EmptyState` defines empty, loading, and error placeholders for dense engineering panels.

### Ownership rules

- Editable source inputs and editable generated overrides must be called out explicitly with `InspectorNotice`.
- Derived or generated outputs should stay read-only whenever structured ownership matters.
- Reset-to-derived actions should live in the same panel as the editable override they affect.
- Warnings belong inside the active inspector section, not in disconnected global copy.

### Current panel conventions

- Pin assignment conflicts appear in the selected pin detail section.
- Protocol transport and template metadata stay derived while field values remain editable.
- Renode platform readiness stays near the transport fields that determine simulation export validity.
- Generated overlay/config editors are editable overrides; generated fragments remain read-only.

## Selection, Focus, and Motion

- Focus-visible styling uses the shared focus ring from `frontend/src/styles/_base.scss`.
- List-like interactive rows use the shared selection surfaces `--surface-list-hover` and `--surface-list-selected`.
- Hover is allowed to reinforce affordance, but selection must remain visually stronger than hover.
- Motion should clarify state changes only.
  - Fast control transitions use `--motion-fast`.
  - Default dialog and overlay transitions should use `--motion-base` when added.
  - Reduced motion must collapse animation and transition duration near zero.
- No surface should require motion to communicate state.

## Feedback Rules

- Persistent diagnostics belong in the output zone or inspector warnings.
- Inline notices belong next to the field group or action they explain.
- Transient feedback should not compete with the bottom output zone; future toasts must summarize and point back to a persistent surface when the issue is actionable.
- Disabled or pending flows should remain discoverable through the shared dialog or command surfaces rather than disappearing from the shell.

## Implementation Expectation

Future shell or domain work should reuse these packages before introducing new interaction patterns:

- `frontend/src/shared/ui/primitives/`
- `frontend/src/shared/ui/components/`
- `frontend/src/shared/ui/commands/`
- `frontend/src/shared/ui/inspectors/`
- `frontend/src/shared/ui/feedback/`

If a new domain needs a new component, it should extend this interaction language rather than bypass it with domain-local button, menu, dialog, or inspector conventions.
