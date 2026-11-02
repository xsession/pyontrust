# pyontrust UI/UX Review and Remediation Report

**Review date:** 2026-08-26  
**Reviewed baseline:** `pyontrust-main-fixed`  
**Remediated deliverable:** `pyontrust-main-uiux-fixed`  
**Status:** All findings in this report have been addressed in the supplied repository.

## 1. Scope

The review covered the complete user-facing surface available in the repository:

- The unified Flask gateway shell.
- Hardware Diagnostic.
- HIL Dashboard.
- Lab Bench.
- CAN Diagnostic.
- Thermal Measurement.
- CSV Plotter.
- FlowLab.
- Interface Documentation.
- Artifact management.
- Configuration management.
- The Android Jetpack Compose client.

The assessment combined:

1. Route and navigation inspection.
2. Responsive visual checks at **1440 × 900** and **390 × 844**.
3. Semantic HTML and accessible-name auditing.
4. Keyboard, focus, dialog, tab, and mobile drawer interaction checks.
5. JavaScript and Python syntax validation.
6. Static Android UI contract checks.

The browser pass used Chromium with deterministic mocked API responses because Flask and the physical gateway dependencies are not installed in the verification environment. This isolates the front-end behavior and layout from hardware availability.

## 2. Executive Summary

The baseline had two nonfunctional product destinations, contradictory shell state, a navigation bar that became unusable on narrow screens, multiple page-level responsive failures, and broad accessibility gaps. The desktop baseline contained **85 unlabeled form controls**, **95 undersized raw controls**, only **5 of 11 pages with exactly one `h1`**, and only **2 of 11 pages with a `main` landmark**. The selected mobile baseline also exposed 68 unlabeled controls and page widths up to 597 pixels in a 390-pixel viewport.

The remediated version now provides functional Artifacts and Configuration interfaces, consistent route-aware shell navigation, responsive engineering workspaces, shared accessibility behavior, explicit loading/error/empty states, offline HIL charting, and improved Android interaction semantics.

The final automated browser audit covered all **11 web routes at both desktop and mobile sizes**:

- 22/22 renders have exactly one `h1` and one `main`.
- 0 unlabeled form controls.
- 0 unnamed buttons or links.
- 0 page-level horizontal overflow cases.
- 0 browser console or page errors.
- 8/8 interaction regression checks passed.
- 7/7 static UI contract tests passed.

Three raw native checkbox glyphs remain below 32 pixels in each viewport, but each is contained by an associated label with a 34-pixel desktop and 40-pixel mobile interaction target. They are therefore not effective touch-target failures.

## 3. Findings Overview

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| UX-001 | High | Artifacts navigation opened a missing UI route | Added a complete artifact-management interface and corrected static routing |
| UX-002 | High | Configuration navigation opened raw API JSON | Added a complete JSON configuration-management interface |
| UX-003 | High | Shell selected HIL while displaying Diagnostic and lacked navigation history | Added a single route model, correct default state, hash deep links, and back/forward support |
| UX-004 | High | Mobile shell navigation was clipped and inaccessible | Replaced the fixed horizontal strip with a responsive off-canvas navigation drawer |
| UX-005 | Medium | Gateway/status failures were silently hidden | Added explicit loading, offline, timeout, success, and error feedback |
| UX-006 | High | Missing landmarks, headings, labels, and accessible names | Added shared accessibility foundations and page-specific semantic repairs |
| UX-007 | High | Weak focus visibility, dim text, and undersized targets | Added consistent focus rings, stronger secondary text, and minimum control targets |
| UX-008 | High | Tabs and dialogs were pointer-oriented and had incomplete state/focus behavior | Added ARIA state, keyboard behavior, focus trapping, focus restoration, and hidden-state synchronization |
| UX-009 | High | FlowLab side panels consumed the mobile canvas; palette use was mouse-centric | Added mobile side drawers and keyboard-operable block palette behavior |
| UX-010 | High | HIL was not robust on mobile and depended on a third-party chart CDN | Rebuilt the dashboard responsively with native canvas charts and no required remote asset |
| UX-011 | High | Thermal zone editor expanded the page beyond the viewport | Contained the dense grid in an explicit scroll region and labeled generated controls |
| UX-012 | High | CAN primary actions and connection settings were hidden in a long toolbar | Reorganized mobile controls, preserved visible capture actions, and improved saved-frame controls |
| UX-013 | High | CSV empty-state styling overlaid unrelated form content | Scoped absolute empty-state positioning to the plot canvas only |
| UX-014 | Medium | Dense pages lacked resilient mobile/table/empty-state behavior | Refactored Diagnostic, Bench, CAN, Thermal, CSV, and Interface Documentation layouts |
| UX-015 | Medium | Android status elements looked clickable but performed no action; numeric inputs lacked appropriate keyboards | Replaced fake controls with status surfaces and added numeric keyboard/inset/action sizing behavior |
| UX-016 | Medium | Malformed dates and restricted browser storage could break management workflows | Added normalization, safe date handling, guarded storage access, and DOM-safe saved-frame rendering |

## 4. Detailed Findings and Fixes

### UX-001 — Artifacts destination was nonfunctional

**Baseline evidence**

- The shell linked to `/artifacts/`.
- The expected `src/pyontrust/gateway/web/artifacts` directory did not exist in the reviewed baseline.
- Users could not browse, inspect, download, refresh, re-index, or delete run outputs from the product shell.

**User impact**

A primary management destination behaved as a dead end, making generated test outputs effectively undiscoverable through the normal UI.

**Fix**

Added a responsive master-detail artifact manager with:

- Search and result-limit controls.
- Indexed-run/report/trace/latest summary cards.
- Loading, empty, filtered-empty, and API-error states.
- Per-run metadata and file list.
- Explicit download links.
- Re-index and refresh actions with inline progress feedback.
- Destructive-action confirmation dialog.
- Mobile stacked layout.

**Changed files**

- `src/pyontrust/gateway/web/artifacts/index.html`
- `src/pyontrust/gateway/web/artifacts/app.css`
- `src/pyontrust/gateway/web/artifacts/app.js`
- `src/pyontrust/gateway/blueprints/artifacts.py`

---

### UX-002 — Configuration destination exposed raw API data

**Baseline evidence**

The shell’s Config item linked directly to `/config/api/profiles`. It displayed a JSON response rather than a product interface, offered no category model, validation, creation, deletion, or save workflow, and exposed an implementation route to end users.

**User impact**

Configuration management required external tools or manual filesystem/API manipulation. This was error-prone and inconsistent with the rest of the platform.

**Fix**

Added a configuration workspace for Profiles, Benches, and Limits with:

- Category navigation and item counts.
- Filterable file list.
- Load, create, format, validate, save, and delete workflows.
- Dirty-state indication and discard protection.
- Ctrl/Command+S support and JSON-editor Tab insertion.
- Inline parse errors and `aria-invalid` synchronization.
- Responsive list/editor stacking.
- A real `/config/` interface route while retaining the existing API endpoints.

**Changed files**

- `src/pyontrust/gateway/web/config/index.html`
- `src/pyontrust/gateway/web/config/app.css`
- `src/pyontrust/gateway/web/config/app.js`
- `src/pyontrust/gateway/blueprints/config.py`

---

### UX-003 — Contradictory shell state and no usable navigation history

**Baseline evidence**

- The iframe loaded `/diag/` by default.
- The shell JavaScript selected HIL by default.
- Tool changes did not create URL state or browser history.
- Back/forward navigation did not restore tools.
- The iframe had no descriptive title.
- The shell did not expose the active tool’s title, purpose, direct URL, or reload action.

**User impact**

The shell visually claimed one tool was active while showing another. Tool views could not be bookmarked, shared, or traversed with browser controls.

**Fix**

- Made Diagnostic the authoritative default in markup and JavaScript.
- Added hash deep links such as `#diag`, `#can`, `#artifacts`, and `#config`.
- Added `pushState`, `popstate`, and hash-change synchronization.
- Synchronized active class, `aria-current`, document title, workspace title/description, iframe title, and direct-link action.
- Added explicit reload and open-in-new-tab actions.
- Added a loading overlay with a timeout fallback.

**Changed files**

- `src/pyontrust/gateway/web/shell/index.html`
- `src/pyontrust/gateway/web/shell/shell.css`
- `src/pyontrust/gateway/web/shell/shell.js`

---

### UX-004 — Mobile shell navigation was clipped

**Baseline evidence**

At 390 pixels wide, the shell navigation container had an internal scroll width of approximately **1324 pixels**. Links after the first few tools were outside the visible viewport, while the page itself suppressed the overflow.

**User impact**

Several tools were practically unreachable on a phone-sized viewport, and the UI offered no clear indication that more navigation existed off-screen.

**Fix**

- Added a mobile menu button with `aria-controls` and `aria-expanded`.
- Converted the sidebar into an off-canvas drawer below 820 pixels.
- Added a backdrop and explicit close action.
- Added Escape-to-close and focus return to the menu button.
- Kept grouped navigation and current-page state intact at desktop size.
- Closed the drawer after a mobile navigation selection.

**Verification**

The interaction test confirms drawer opening, ARIA state, Escape closure, and focus restoration.

---

### UX-005 — Status and request failures appeared as normal idle states

**Baseline evidence**

The shell status poll returned silently on non-OK responses and swallowed network exceptions. Several tools likewise had minimal or browser-alert-only feedback.

**User impact**

A disconnected gateway could look like a healthy idle system. Users could not distinguish “nothing is happening” from “the platform is unavailable.”

**Fix**

- Added explicit `Gateway unavailable`, timeout, idle, running, stopping, and error states.
- Added request timeouts for shell status polling.
- Added reusable live-region message components.
- Added loading skeletons and clear empty/error states to Artifacts and Configuration.
- Added inline HIL validation and telemetry/status errors.
- Added structured Bench connection feedback.

---

### UX-006 — Incomplete semantic structure and accessible naming

**Baseline evidence**

Desktop audit results across 11 routes:

- 85 unlabeled form controls.
- Only 5/11 pages had exactly one `h1`.
- Only 2/11 pages had a `main` landmark.
- Several dynamic controls, canvases, modal surfaces, and tab systems lacked meaningful roles or names.

Selected mobile baseline results across six rendered routes included 68 unlabeled controls.

**User impact**

Screen-reader navigation was unreliable, form purpose was unclear, and headings/landmarks could not be used to orient within complex engineering pages.

**Fix**

Created a shared UI foundation that progressively supplies and enforces:

- Form-control accessible names.
- `main`, heading, status, canvas, SVG, dialog, and tab semantics.
- Screen-reader-only labels.
- Skip-link behavior.
- Dynamic-content handling through a `MutationObserver`.

Page-specific markup was also corrected rather than relying exclusively on runtime repair.

**Changed files**

- `src/pyontrust/gateway/web/shell/ui-foundation.css`
- `src/pyontrust/gateway/web/shell/ui-foundation.js`
- All primary web page templates.

---

### UX-007 — Weak keyboard focus, low-emphasis text, and undersized targets

**Baseline evidence**

The desktop audit detected 95 controls below the 32-pixel audit threshold. Focus treatment varied or was missing, and secondary text/borders were too subdued for dense operational screens.

**User impact**

Keyboard users could lose track of focus. Compact buttons and icon-only actions were difficult to activate, especially on touch screens. Low-emphasis labels reduced scanability.

**Fix**

- Added a consistent high-visibility `:focus-visible` ring.
- Raised shared control minimums to 34 pixels on desktop and 40 pixels on mobile.
- Increased native checkbox/radio glyph size and accent behavior.
- Strengthened dim foreground and border tokens.
- Replaced tiny icon-only saved-frame actions with named Load/Delete buttons.
- Added reduced-motion and forced-colors support.

**Final note**

The final audit reports only the three raw native checkbox glyphs as smaller than 32 pixels; their wrapping labels provide the actual 34/40-pixel interaction areas.

---

### UX-008 — Tabs and dialogs had incomplete keyboard/state behavior

**Baseline evidence**

Several tabs were styled generic elements or button-like containers without complete selected state, roving focus, panel relationships, or hidden-state synchronization. Modal overlays lacked consistent dialog semantics, focus trapping, and focus restoration.

**User impact**

Keyboard and assistive-technology users could enter invisible panels, miss the selected tab, or lose their place after closing a modal.

**Fix**

- Added shared tab semantics and Arrow/Home/End navigation support.
- Synchronized active classes, `aria-selected`, `tabIndex`, and `hidden` state.
- Added `role="dialog"`, `aria-modal`, focus trapping, Escape close, and focus return for custom modal surfaces.
- Used native `<dialog>` where appropriate in management screens.
- Ensured programmatic Thermal tab changes call the same accessible click handler as user input.

---

### UX-009 — FlowLab lost its canvas on narrow screens

**Baseline evidence**

FlowLab used permanently visible sidebars with nominal widths of 220 and 280 pixels around the canvas. A 390-pixel viewport could not accommodate both, so the primary diagram workspace was displaced/squeezed. Palette interaction was also primarily drag/mouse oriented.

**User impact**

The central task—building and inspecting a workflow—was not practically usable on smaller screens, and keyboard users had no equivalent palette activation path.

**Fix**

- Preserved the canvas as the primary full-width mobile surface.
- Added Blocks and Properties toggle buttons.
- Converted side panels to off-canvas drawers with a backdrop.
- Added Escape/backdrop closure and ARIA-expanded state.
- Added palette item roles and Enter/Space/double-click activation.
- Opened Properties automatically for selected blocks on mobile.
- Made modal/tutorial layouts responsive.

**Verification**

The interaction pass measured a mobile canvas width above 300 pixels and exercised both side drawers.

---

### UX-010 — HIL dashboard was fragile on mobile and required a remote chart library

**Baseline evidence**

- The dashboard loaded Plotly from `cdn.plot.ly` as a required runtime dependency.
- The profile input had a fixed 300-pixel width.
- Mobile control and panel layout overflowed or compressed poorly.
- Empty and unavailable states were weak.

**User impact**

The HIL view could fail in offline lab networks, restricted production environments, or when the CDN was blocked. Core controls and telemetry were less usable on narrow screens.

**Fix**

- Rebuilt the HIL page as a responsive operational dashboard.
- Replaced Plotly with a local native-canvas `TraceChart` implementation.
- Added proper profile labeling, start/stop grouping, run-state badge, inline messages, event log, history, progress, power trace, and RF trace empty states.
- Removed required third-party scripts.
- Avoided unsafe event-payload HTML insertion.

---

### UX-011 — Thermal zone editor caused page-level horizontal overflow

**Baseline evidence**

The zone row used a fixed grid of `120px + six × 60px + 30px`, which pushed the 390-pixel page to approximately **597 pixels** wide.

**User impact**

The whole page panned horizontally, causing controls, headings, and actions to drift outside the viewport.

**Fix**

- Wrapped the intentionally dense zone matrix in a named horizontal scroll region.
- Kept the body at the viewport width.
- Added accessible labels to generated zone name/position/dimension/temperature controls.
- Added named delete buttons with adequate target size.
- Made forms, stats, snapshots, and tabs responsive.
- Synchronized tab ARIA and hidden states.

**Final note**

The mobile audit correctly detects the internal 585-pixel zone grid, but it is contained within `.zone-scroll`; the page body remains 390/390 pixels.

---

### UX-012 — CAN controls were hidden in a long horizontal toolbar

**Baseline evidence**

Connection settings, capture actions, state, and filters were laid out as one unbroken toolbar. On mobile, critical Start/Stop actions could move outside the visible region. Saved-frame controls were tiny emoji/icon actions built through `innerHTML`, and browser-storage exceptions were not presented gracefully.

**User impact**

Users could configure the bus but fail to find the primary capture action. Saved frames were difficult to operate with touch or assistive technology.

**Fix**

- Reorganized the mobile toolbar into explicit connection, capture-action, status, and filter groups.
- Made Interface, Channel, Bitrate, and FD settings fit without hidden horizontal content.
- Kept Start, Stop, and Clear visible in a dedicated three-column action row.
- Added mobile-safe tab overflow.
- Added accessible tab state and status live regions.
- Guarded local-storage read/write failures.
- Replaced saved-frame `innerHTML` with DOM-safe text nodes and named Load/Delete buttons.

**Verification**

The interaction test confirms all three primary actions remain inside the 390-pixel viewport and that saved-frame actions have usable accessible names.

---

### UX-013 — CSV empty-state CSS overlaid unrelated content

**Baseline evidence**

A generic `.empty-state` class was absolutely positioned with `inset: 0`. The same class was reused outside the plotting canvas, causing mobile analysis text to overlay unrelated form fields.

**User impact**

Controls became obscured and the visual hierarchy suggested that the wrong region was empty or disabled.

**Fix**

- Made the general `.empty-state` layout flow normally.
- Scoped absolute centering to `.canvas-frame > .empty-state` only.
- Added labels and live status behavior to CSV controls.
- Preserved plot-specific centering without affecting forms or panels.

---

### UX-014 — Dense engineering pages did not adapt consistently

**Baseline evidence**

Diagnostic, Bench, CAN, Thermal, CSV, and Interface Documentation mixed fixed widths, sticky/dense tables, narrow buttons, inline styles, and inconsistent status/empty states. Interface Documentation tabs and controls overlapped on narrow screens.

**User impact**

Users had to pan or visually decode overlapping toolbars, and data tables lacked a predictable containment model.

**Fix**

- Reworked Diagnostic actions, grids, and report dialogs for narrow screens.
- Rebuilt Bench with a clear heading, status summary, semantic table, and responsive equipment controls.
- Added table-scroll containment patterns.
- Prevented Interface Documentation tabs from shrinking into each other.
- Added wrapping control groups and synchronized tab state.
- Added consistent loading, error, empty, and status feedback.

---

### UX-015 — Android status components implied nonexistent actions

**Baseline evidence**

Status information was shown through clickable `AssistChip` components with no-op click callbacks. Numeric fields did not request numeric/decimal keyboards, primary actions did not consistently use available width, and bottom content did not account for navigation-bar insets.

**User impact**

The UI falsely suggested status chips were interactive, made numeric entry slower, and reduced action reliability on compact devices.

**Fix**

- Replaced no-op chips with noninteractive `StatusBadge` surfaces.
- Added state description semantics.
- Added number and decimal keyboard types to corresponding fields.
- Made connection, measurement, and device actions full-width where appropriate.
- Added navigation-bar padding and improved control grouping.

**Changed file**

- `android-app/app/src/main/java/com/pyontrust/android/ui/PyontrustApp.kt`

---

### UX-016 — Management workflows were brittle around malformed data and restricted storage

**Baseline evidence**

Direct date conversion could throw when configuration/artifact metadata was absent or malformed. CAN saved-frame persistence assumed `localStorage` was available. Saved-frame values were rendered through interpolated HTML.

**User impact**

One bad timestamp or a restricted browser context could interrupt a whole list. User-entered CAN text could be interpreted as markup instead of data.

**Fix**

- Normalized string and object list results.
- Validated timestamps before `Date`/`Intl.DateTimeFormat` use and displayed `Unknown` when necessary.
- Guarded storage reads/writes and notified users when persistence is unavailable.
- Built saved-frame rows with `textContent` and real DOM controls.
- Added safe item-name normalization in the configuration editor.

## 5. Verification Results

### 5.1 Browser visual and structural audit

| Metric | Baseline desktop | Final desktop | Baseline mobile sample | Final mobile |
|---|---:|---:|---:|---:|
| Routes rendered | 11 | 11 | 6 | 11 |
| Routes with exactly one `h1` | 5 | 11 | 2 | 11 |
| Routes with exactly one `main` | 2 | 11 | 1 | 11 |
| Unlabeled form controls | 85 | 0 | 68 | 0 |
| Unnamed buttons/links | 0 | 0 | 0 | 0 |
| Controls below 32 px audit threshold | 95 | 3 raw checkboxes | 52 | 3 raw checkboxes |
| Page-level horizontal overflow | 0* | 0 | 2 | 0 |
| Browser errors | 1 | 0 | 0 | 0 |

\* The baseline mobile shell hid a 1324-pixel navigation strip inside a 390-pixel container; this appeared as internal clipped overflow rather than body overflow.

Final route-by-route audit result:

- Exactly one `h1` and `main` on all 22 route/viewport combinations.
- Zero unlabeled controls.
- Zero unnamed buttons/links.
- Body width equals viewport width on every page.
- Zero browser console or page errors.

### 5.2 Interaction regression checks

All 8 checks passed:

1. Shell deep links, active state, iframe title, and browser history.
2. Mobile shell drawer ARIA state, Escape close, and focus return.
3. FlowLab mobile canvas availability and Blocks/Properties drawers.
4. Thermal tab ARIA/hidden-state synchronization.
5. HIL empty-profile validation and focus placement.
6. Configuration JSON invalid-state and inline feedback.
7. Artifact empty state and re-index feedback.
8. CAN mobile primary-action visibility and named saved-frame actions.

### 5.3 Static and syntax checks

- `tests/ui_tests/test_ui_contract.py`: **7 passed**.
- Six standalone JavaScript files: syntax passed with `node --check`.
- Six inline JavaScript blocks: syntax passed with `node --check`.
- Modified Flask blueprints and UI tests: Python `compileall` passed.
- Android static UI contract: all checks passed.

The new static UI tests guard against:

- Missing primary pages.
- Missing headings or main landmarks.
- Duplicate IDs.
- Missing packaged CSS/JavaScript.
- Required remote assets.
- Loss of the shared accessibility foundation.
- Broken shell route/default-state contracts.
- Missing Config/Artifacts interfaces.
- Reintroduction of a required HIL chart CDN.

## 6. Files Added or Modified

### New files

- `UI_UX_REVIEW_AND_FIXES.md`
- `src/pyontrust/gateway/web/artifacts/index.html`
- `src/pyontrust/gateway/web/artifacts/app.css`
- `src/pyontrust/gateway/web/artifacts/app.js`
- `src/pyontrust/gateway/web/config/index.html`
- `src/pyontrust/gateway/web/config/app.css`
- `src/pyontrust/gateway/web/config/app.js`
- `src/pyontrust/gateway/web/shell/ui-foundation.css`
- `src/pyontrust/gateway/web/shell/ui-foundation.js`
- `tests/ui_tests/test_ui_contract.py`

### Modified files

- `src/pyontrust/gateway/blueprints/artifacts.py`
- `src/pyontrust/gateway/blueprints/config.py`
- `src/pyontrust/gateway/web/shell/index.html`
- `src/pyontrust/gateway/web/shell/shell.css`
- `src/pyontrust/gateway/web/shell/shell.js`
- `src/pyontrust/gateway/web/diagnostic/index.html`
- `src/pyontrust/gateway/web/hil/index.html`
- `src/pyontrust/gateway/web/bench/index.html`
- `src/pyontrust/gateway/web/can/index.html`
- `src/pyontrust/gateway/web/thermal/index.html`
- `src/pyontrust/gateway/web/csv/index.html`
- `src/pyontrust/gateway/web/csv/app.css`
- `src/pyontrust/gateway/web/flowlab/index.html`
- `src/pyontrust/gateway/web/flowlab/flowlab.css`
- `src/pyontrust/gateway/web/flowlab/flowlab.js`
- `src/pyontrust/gateway/web/ifdoc/index.html`
- `android-app/app/src/main/java/com/pyontrust/android/ui/PyontrustApp.kt`

## 7. Environment-Dependent Validation Boundaries

The following checks could not be completed in this environment and are not represented as passed:

- **Live Flask route execution:** Flask is not installed. The blueprint source compiles, the route contracts are covered statically, and the browser UIs were exercised with mocked API responses, but the full gateway was not launched.
- **Android compilation/instrumentation:** The repository has no executable Gradle wrapper, system Gradle is unavailable, and `ANDROID_HOME` is unset. The Compose source was checked statically but not assembled into an APK.
- **Physical hardware behavior:** No CAN adapter, thermal camera, Android device, HIL bench, power meter, RF instrument, or other lab device was connected.
- **Real production data volume:** Artifact/configuration behavior was verified against representative deterministic payloads, not a large production store.

These are integration and hardware validation boundaries rather than known unresolved UI defects.

## 8. Recommended CI Gate

The added UI contract test should run on every change. A production CI extension should additionally:

1. Launch the Flask gateway with a temporary data directory.
2. Run the same Chromium audit against real routes.
3. Add API-contract fixtures for Config and Artifacts.
4. Build the Android application through a checked-in Gradle wrapper.
5. Keep 1440 × 900 and 390 × 844 screenshots as reviewed visual baselines.

