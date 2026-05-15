# Phase 0 Regression Checklist

This checklist defines what must continue to work while the frontend is being refactored. It combines executable baseline checks with manual comparison points.

## Executable Baseline Locks

Use these tests as the minimum automated baseline before changing shell structure or state ownership:

- `pytest tests/test_phase0_baseline.py`
- `pytest tests/test_api.py -k "project_file|demo_app_export|path_dialog|board_editor"`
- `pytest tests/test_lvgl_frontend_contract.py`

These checks lock the current shell contract, critical route registration, persistence round-trip behavior, demo export surface, and LVGL frontend contract.

## Manual Shell Regression Pass

- App loads from `/` without JS boot failure.
- Board selector is populated.
- Major tabs remain visible and switchable.
- The chip/package view renders after selecting a board.
- Output panes still show generated artifacts.

## Manual Project Workflow Regression Pass

- Generate overlay and `prj.conf` from a simple board assignment.
- Save generated output into a project tree.
- Save a project document to disk.
- Load the saved project back into the UI.
- Confirm protocol editor content survives project save/load.
- Confirm generated fragments remain visible after load.

## Manual Domain Regression Pass

- Board editor draft list, save, load, and delete still work.
- LVGL import/export still works for at least one representative source.
- Module configuration still generates config fragments.
- Peripheral configuration still generates overlay/config output.
- Clock configuration still calculates frequencies and generates output.
- Import-config and project scan flows still parse representative inputs.
- Package PDF parsing still produces a job and package generation result.
- Sensor PDF parsing still produces a job and derivative outputs.

## Manual Build and Demo Regression Pass

- Demo app export still creates a buildable app directory.
- Generated Renode and Robot artifacts are still present in the exported demo.
- Environment diagnostics remain understandable when build prerequisites are missing.

## Evidence Stored in Repo During Phase 0

- current-state architecture note
- endpoint-to-feature matrix
- state ownership map
- executable shell and route baseline test
- representative baseline screenshots under `docs/phase0_screenshots/`
- complex-surface interaction evidence under `docs/phase0_interaction_evidence.md`

## Remaining Manual Evidence

The current toolchain in this repo can lock API and shell contracts automatically, but richer visual comparison still needs manual execution during the early refactor:

- optional video recordings for complex editor surfaces
- side-by-side UX comparisons during shell cutover

Those manual checks should be attached to Phase 3 and Phase 6 reviews if they are not captured earlier.