# Multi-Subplot CSV Viewer — User Guide

This tool lets you load a CSV, plot one or more signals, add overlay files per subplot, and analyze a selected window (Table / Histogram / Checks) with persistent layout.

## Quick start
1. **Choose CSV File** → load your main file.
2. **Add Subplot** → create additional subplots (optional).
3. In each subplot, select signals from the **Signals** list.
4. Click **Plot All**.

See infographic: `docs/infographics/workflow_basic.svg`

## Main UI concepts
- **Subplot selector (left)**: per-subplot configuration (signals, overlays, window, y-limits, bottom panels).
- **Plot area (right)**: main plot + optional bottom panels.
- **Bottom panels** (per subplot):
  - **Table**: min/max/avg/median/P2P + frequency/period estimate.
  - **Histogram**: distribution of values.
  - **Absolute range check**: compares signals against min/max barriers.
  - **Relative change**: compares change rate against barriers.

See infographic: `docs/infographics/ui_overview.svg`

## Overlay files
Each subplot can plot multiple files (base + overlays).

### Add / remove overlays
- **Add file(s)**: adds overlay CSV(s) to the subplot.
- **Toggle on/off**: disables/enables a selected overlay without removing it.
- **Remove / Clear / Remove all**: remove selected / remove extra overlays / remove all.

### Alignment and shifts
- **Overlay X** alignment:
  - **Aligned timestamps**: overlays share the same x-axis reference.
  - **Independent**: each file’s time starts at 0 (useful when starts differ).
- **X shift (sec)**: shift overlay left/right in *seconds*.
- **Y shift**: offset overlay values.

See infographic: `docs/infographics/overlay_alignment.svg`

## Analysis window (span select)
The “window” is the x-range used for Table / Histogram / Checks.

- Drag on the main plot to select a window.
- The selector shows `Window: lo .. hi (Δ duration)`.
- Click **Clear window** to analyze the full series.

See infographic: `docs/infographics/window_analysis.svg`

### Toolbar Home button
The Matplotlib **Home** (house) button resets to the **full data range** and clears any saved analysis window.

## Timebase / timestep (important)
Some CSVs have a real timestamp axis; others have a **sample counter**.

### Global timebase
Open **Settings** → **Timebase**:
- **Fixed**: use a constant timestep for “seconds per x-unit”.
  - Default: **ms** with **0.01** step.
- **Auto**: derive scaling from the file’s timestamp column.

### Per-overlay timebase
In each subplot, select an overlay file and set:
- **Timestep**: Global / Auto / Custom
- **Unit**: s / ms / us (Custom)
- **Step**: numeric (Custom)

### Sample counter behavior
If the effective timebase is **Fixed**, metrics (Freq/Period) use **uniform sample time** (`sample_index * dt`) even if a `Timestamp` column exists but behaves like a counter.

See infographic: `docs/infographics/timebase_modes.svg`

## Layout persistence
Use the **Layout** menu to save/load. The layout includes:
- subplot count and configuration
- selected signals
- overlays, shifts, enabled flags
- analysis window, y-limit config
- global and per-file timebase settings

See infographic: `docs/infographics/layout_persistence.svg`

## Tips & troubleshooting
- If plots look “squished” or metrics look wrong, check **Timebase**.
- If you want full-series analysis: press **Home** or **Clear window**.
- For large files, plotting is downsampled to keep UI responsive.
