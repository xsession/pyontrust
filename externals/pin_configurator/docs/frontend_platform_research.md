# Frontend Research: Platforms Similar to pin_configurator and pyontrust

## Goal

Review how tools similar to pin_configurator and pyontrust build their frontend, especially:

- frontend architecture
- layout structure
- styling direction
- UI/UX patterns
- reusable design lessons for embedded and lab-tooling software

## Local baseline in this workspace

### pin_configurator

The current pin_configurator frontend is a Flask-served single-page app with a dark engineering-style interface and hand-authored CSS and JavaScript.

Relevant local references:

- `deps/pyontrust/externals/pin_configurator/web/index.html`
- `deps/pyontrust/externals/pin_configurator/docs/frontend_mvp_refactor_plan.md`

Observed frontend traits:

- Dark theme with shared CSS variables for background, accent, success, warning, and border tokens.
- Main work area is already organized around a desktop-like shell: left peripheral list, center chip or canvas area, right config or details panel.
- Dense control styling favors engineering productivity over consumer polish.
- The newer LVGL editor surface already moves toward a true workstation layout: left sidebar, center stage or canvas, right inspector panel.
- Visual language is functional and consistent, but still mostly handcrafted and monolithic inside one HTML file.

### pyontrust

The local and public architecture around pyontrust shows a transition from mixed GUI stacks toward a unified Flask gateway with embeddable SPAs.

Relevant local references:

- `deps/pyontrust/README.md`
- `deps/pyontrust/ENTERPRISE_ARCHITECTURE.md`

Observed frontend traits:

- Today it mixes Tkinter, NiceGUI, and Flask plus vanilla JavaScript.
- The architecture plan explicitly calls this out as a problem because it fragments theme, navigation, and developer workflow.
- The target direction is a unified Flask gateway with one app shell and separate tool SPAs mounted under URL prefixes.
- The plan also standardizes a shared Catppuccin-like dark token set across tools.
- The public repo now includes a broader gateway pattern with tool-specific SPAs such as HIL, bench, FlowLab, and interface docs.

## External platforms reviewed

### STM32CubeMX

Source:

- https://www.st.com/en/development-tools/stm32cubemx.html

What stands out:

- Strong task-oriented flow: select device, configure pinout, configure clocks, configure middleware, generate code.
- Core interaction model is visual-first: pinout editor and clock tree are the centerpieces.
- Real-time constraint validation is central to the UX.
- The tool reduces risk by making conflicts visible immediately instead of after generation.

Frontend lessons:

- The center canvas should be the primary truth surface.
- Validation must be inline and immediate.
- Generated output is a consequence of configuration, not a separate detached workflow.

### TI SysConfig

Source:

- https://www.ti.com/tool/SYSCONFIG

What stands out:

- Broad configuration scope: pins, peripherals, radios, clocks, memory, RTOS, board-level and device-level views.
- Explicit emphasis on intuitive GUI, automatic conflict detection, contextual documentation, and real-time code preview.
- The tool behaves like an engineering control center rather than a simple form.

Frontend lessons:

- A mature configurator does not stop at pin muxing.
- Good embedded UX combines visual editing with live code and docs in the same workspace.
- Split views and synchronized panels matter more than decorative styling.

### MPLAB Code Configurator

Source:

- https://www.microchip.com/en-us/tools-resources/configure/mplab-code-configurator

What stands out:

- Modular architecture and content management are treated as first-class UX ideas.
- Flexible pin management is a named feature.
- Available inside IDE workflows, including VS Code integration messaging.
- Framing is practical: get drivers and configuration generated fast, reduce manual datasheet digging.

Frontend lessons:

- Users value speed-to-first-working-project more than visual novelty.
- A strong component catalog and content manager improve discoverability.
- IDE embedding is a major UX multiplier for tools like pin_configurator.

### NiceGUI foundations

Source:

- https://nicegui.io/documentation

What stands out:

- Backend-first Python model, but still browser UI underneath.
- Styling is built through Quasar, Tailwind classes, CSS, and layout primitives.
- It provides headers, drawers, tabs, splitters, cards, grids, dialogs, tables, trees, logs, charts, and editors out of the box.
- It is optimized for rapid application assembly, not for bespoke desktop-grade visual identity.

Frontend lessons:

- NiceGUI is good for fast internal tools and dashboards.
- It is less opinionated toward a custom embedded-workbench feel unless heavily themed.
- If pyontrust wants a unified product-grade UX, a shared shell and consistent tokens matter more than framework convenience.

### Public pyontrust direction

Source:

- `xsession/pyontrust` public repository materials

What stands out:

- The public repo now describes a unified Flask gateway with a shared shell and tool-specific SPAs.
- It explicitly frames dashboards as single-page apps served by the Flask gateway.
- FlowLab is described as a LabVIEW-style visual editor with a draggable palette, SVG wiring, pan and zoom canvas, and properties panel.
- The gateway structure mounts separate blueprints and static web assets for shell, HIL, CSV, pin configuration, SDR, waveforms, bench, and interface docs.

Frontend lessons:

- The product direction is converging on micro-frontends within one consistent host shell.
- Visual editors, not forms, are becoming the defining interaction pattern.
- Shared theme and navigation should be treated as platform infrastructure, not per-tool styling.

## Shared UI patterns across successful engineering tools

### 1. Persistent shell around a task canvas

The strongest recurring pattern is:

- left navigation or catalog
- center visual workspace
- right inspector or properties
- top toolbar for global actions
- bottom or side feedback area for logs, preview, or diagnostics

This is already partially visible in pin_configurator and is the right direction.

### 2. Visual-first editing, text as confirmation

The best tools let users manipulate:

- pins
- clocks
- components
- nodes
- lab assets
- test flows

Then they expose:

- generated code
- config fragments
- export artifacts
- diagnostics

Text output supports the visual workflow instead of replacing it.

### 3. Immediate validation

Embedded tools get dramatically better when they show:

- pin conflicts
- invalid clock combinations
- unavailable peripherals
- code generation blockers
- incompatible module combinations

Users trust a configurator when it fails early and visibly.

### 4. Dense but stable information hierarchy

Good engineering UX is compact, but not chaotic. Common traits:

- small but readable labels
- muted base palette
- one clear accent color
- semantic colors for warn, fail, and success
- strong borders and panel separation
- persistent headers and breadcrumbs

### 5. Workspace continuity

Mature tools preserve context through:

- saved layouts
- recent projects
- selected device state
- generated output history
- reusable profiles or presets

This matters for both pin_configurator and pyontrust because users return to the same hardware workflows repeatedly.

### 6. Integrated code preview and export

TI and similar tools explicitly surface real-time code preview or generation pathways. That pattern should be treated as core, not optional.

Best practice:

- config on the left and center
- generated artifact preview on demand
- export and apply actions always visible
- diff-like feedback where possible

## Styling direction seen across the category

### Common successful styling traits

- Dark neutral or low-glare canvas backgrounds are common for engineering-heavy interfaces.
- Accent colors are restrained and semantic, not decorative.
- Panels are boxed and spatially explicit.
- Controls look utilitarian and precise, not soft or playful.
- Tables, trees, chips, and badges are used heavily for dense information.
- Visual editors use grid backgrounds, panel shadows, and subtle depth to separate editable surfaces from surrounding chrome.

### What pin_configurator already gets right

- Cohesive dark token palette.
- Useful accent and semantic colors.
- Good panelized layout instincts.
- Center-stage bias for visual editing.
- Dense, productivity-oriented controls.

### What still looks behind leading tools

- Too much styling and layout logic is concentrated in a single static HTML surface.
- The system needs a stronger concept of app shell versus tool content.
- Advanced surfaces should share one inspector language and one toolbar language.
- The current UI feels like multiple features added into one page rather than one composed workstation.

## Architectural pattern that seems best for this tool family

Based on the local code and the public tools reviewed, the most credible architecture for this category is:

- shared shell
- tool-specific micro-frontends or feature modules
- typed backend API boundary
- persistent workspace state
- center visual editor surfaces
- reusable side panels and inspectors
- shared design tokens
- embedded code preview and diagnostics

That aligns with the local pin_configurator refactor plan, which already points toward React, TypeScript, Vite, MVP boundaries, Dockview, Radix primitives, SCSS plus CSS variables, and canvas or SVG editor surfaces.

## Practical UI recommendations for pin_configurator and pyontrust

### For pin_configurator

- Keep the dark engineering theme, but extract it into a true token system shared across all views.
- Promote the three-pane layout to the default shell for all major editors.
- Treat chip editor, clock editor, protocol editor, and LVGL editor as sibling workspaces inside one consistent frame.
- Add a consistent right inspector model: selection details, validation, generated output, and quick actions.
- Make code preview and diagnostics more persistent instead of modal or scattered.
- Reduce the perception of one giant page by separating shell, tool views, and data services.

### For pyontrust

- The strongest long-term direction is the Flask gateway plus embeddable SPAs approach already described in the architecture doc.
- NiceGUI remains useful for rapid internal modules, but it should not define the product UX unless all tools fully standardize on it.
- A unified shell matters more than the current framework choice.
- FlowLab, HIL dashboard, bench manager, and interface docs all fit the same desktop-workbench pattern: navigation, live status, center task surface, details panel, and log or artifact access.

## Most reusable UX formula for this product area

If reduced to one repeatable formula, the best frontend pattern for tools like these is:

- top bar for project, target, save, build, export, and run
- left rail for device tree, modules, peripherals, instruments, and assets
- center canvas for the thing being configured or analyzed
- right inspector for selected item properties and validation
- bottom tray for logs, generated files, events, and test output
- shared dark theme with one accent and semantic feedback colors
- instant validation and preview everywhere

## Conclusion

The comparison is consistent:

- leading embedded configurators are workflow-first, not page-first
- the center visual surface is the product
- side panels exist to support the center, not compete with it
- users want immediate validation, generated output, and persistent project context
- a shared shell plus modular editors is the strongest direction for both pin_configurator and pyontrust

pin_configurator is already moving toward the right category shape. The biggest remaining step is not inventing a new style, but turning its current dark functional UI into a real multi-tool workstation system.

## Sources

- https://www.st.com/en/development-tools/stm32cubemx.html
- https://www.ti.com/tool/SYSCONFIG
- https://www.microchip.com/en-us/tools-resources/configure/mplab-code-configurator
- https://nicegui.io/documentation
- local repository references listed above