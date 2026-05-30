# Pyontrust Driver Generator Upgrade Plan

## Goal

Expand `interface_docs` so it can cover the practical feature set currently implemented in `yaml_docs`, while keeping the `pyontrust` generator maintainable and testable.

## Status

Implemented in core `interface_docs`:

- Dispatcher refactor to a handler registry with shared job context
- Explicit target validation
- Optional `debug` side outputs
- Optional Python `generate_init` support
- Richer Python metadata generation for CANopen and the other current transport families
- Low-level format support for `mlxcheck`, `c-pdo_macro`, `xml-canether`, `vhdl-package`, `vhdl-arch`, `c-types`, `c-od`, `xml-od`, `py`, and `xml-to-yaml`
- Pyontrust-native `gui-app` and `test-sequence` scaffold formats
- GUI scaffold `build_install` support via a repo-owned `pyontrust.build_install.AppBuilder`
- Focused `tests/interface_docs/` coverage for the dispatcher, Python generator, low-level formats, and VHDL outputs
- Fixture-style scaffold output coverage for scaffold-owned generated files
- Dry-run coverage for emitted GUI scaffold build helpers across both PyInstaller and Nuitka icon-path packaging flows
- Manifest-level smoke coverage for the copied `mp.yaml` Python transport slice

## Current State

The generator started as a thin batch dispatcher with a fixed `FORMAT_MAP` and a small set of generators:

- C typedefs / object dictionaries / transport register headers
- Python driver stubs
- HTML docs
- Jinja GUI blocks

The broader `yaml_docs/source/yaml_doc.py` surface includes:

- More batch formats: `mlxcheck`, `c-pdo_macro`, `xml-canether`, `vhdl-package`, `vhdl-arch`, `c-types`, `c-od`, `xml-od`, `py`, `gui-app`, `test-sequence`, `xml-to-yaml`
- More permissive and operational job handling: auto-create output folders, optional Python `__init__.py` generation, debug side outputs
- Richer Python codegen behavior: conversion runtime hooks, field metadata, plot config support, normalized units, generated helper methods, compatibility aliases
- Higher-level app scaffolding around generated drivers
- Existing unit tests that pin this behavior in `yaml_docs/source/tests`

## Upgrade Principle

Do not copy `yaml_docs` wholesale into `pyontrust`. Instead, lift the reusable behavior into `pyontrust/interface_docs` in layers:

1. Extend the batch/job model.
2. Expand generator contexts and templates.
3. Add higher-level scaffolding generators only after the lower-level schema and runtime contracts are stable.

## Feature Gap Matrix

### Batch / orchestration gaps

- Implemented: explicit job validation.
- Implemented: support for generator-specific job fields beyond `source`, `output`, `format`, `dependencies`, `includes`, `od_name`.
- Implemented: optional `debug` outputs.
- Implemented: optional Python package init generation for generated Python outputs.
- Implemented: handler registry instead of the earlier two-step `FORMAT_MAP` to handler switch.

### Python generator gaps

- Implemented: enum-format detection from dependency YAMLs.
- Implemented: richer field metadata generation.
- Implemented: conversion metadata and runtime hook generation for the current Python generator surface.
- Partially implemented: plot/config metadata propagation where it exists in the current schemas.
- Implemented: helper methods for conversion-aware values and structured logging in the richer Python outputs.
- Not needed yet in current `interface_docs` outputs: compatibility aliases for older generated class names.

### Format support gaps

- Implemented: `mlxcheck`
- Implemented: `c-pdo_macro`
- Implemented: `xml-canether`
- Implemented: `vhdl-package`
- Implemented: `vhdl-arch`
- Implemented: `c-types`
- Implemented: `c-od`
- Implemented: `xml-od`
- Implemented: `py`
- Implemented: `gui-app`
- Implemented: `test-sequence`
- Implemented: `xml-to-yaml`

### Documentation / app gaps

- HTML/confluence remains optional and should only be expanded if `pyontrust` gets a real publishing consumer.
- The scaffold formats are now owned in-core, but they intentionally target pyontrust-native Flask and pytest/HIL surfaces rather than the original Mediso-local PWTK/mtest runtime.
- The GUI scaffold also now carries a pyontrust-native build helper instead of assuming an external `build_install` package.

## Recommended Phases

## Phase 1: Refactor the dispatcher

Target files:

- `interface_docs/generate.py`
- `interface_docs/generators/__init__.py`

Work:

- Replace `FORMAT_MAP` plus `if/elif` dispatch with a registry of format handlers.
- Introduce a `JobContext` or equivalent helper carrying `base_dir`, resolved paths, loaded source data, dependency data, resolved types, and raw job options.
- Split validation from execution so failures become deterministic and easy to test.
- Add output directory creation and a shared write helper.
- Add optional `generate_init` support for Python outputs.

Why first:

This is the minimum structural change needed before adding the rest of the yaml_docs formats without turning `generate.py` into a large monolith.

## Phase 2: Close the Python driver gap

Target files:

- `interface_docs/generators/gen_python.py`
- `interface_docs/templates/py_driver.py.j2`
- shared helper utilities in `interface_docs/generators/__init__.py`

Work:

- Port enum-format detection logic from dependency YAML parsing.
- Expand generator context to carry normalized units, conversion configuration, field metadata, and plot metadata.
- Add generation for conversion-aware helper methods and optional extra log field schemas.
- Preserve current pyontrust API names where possible; if not, add compatibility shims in generated code.
- Keep transport-specific preparation functions, but move shared metadata extraction into reusable helpers.

Exit criteria:

- Existing generated drivers still render.
- New tests cover conversion hooks, unit normalization, helper generation, and plot metadata.

## Phase 3: Add missing low-level formats

Implement first:

- `xml-canether`
- `c-pdo_macro`
- `c-types`
- `c-od`
- `xml-od`
- `py`

Approach:

- Prefer reusing or adapting existing `yaml_docs` logic where the output contracts are already proven.
- Keep format handlers isolated per file or module instead of extending one giant generator module.
- Only add formats that have a concrete pyontrust consumer or near-term user.

Why before app scaffolds:

These outputs are closer to the existing `interface_docs` responsibility and establish the schema/runtime contracts the higher-level generators depend on.

## Phase 4: Add optional high-level scaffolding generators

Candidate formats:

- `gui-app`
- `test-sequence`
- `xml-to-yaml`
- possibly `html-confluence`

Decision gate:

- If these are needed as productized pyontrust workflows, add them under `interface_docs/generators/` with their own tests and templates.
- If they are only useful for Mediso-local authoring flows, keep them outside the core generator and provide an adapter command or separate package.

Implementation note:

`gui-app` and `test-sequence` were implemented as pyontrust-native scaffolds once the local runtime targets were clear: `pyontrust.gateway.create_app` for GUI outputs and `pyontrust.hil.HILTestFixture` plus pytest for test-sequence outputs.

## Phase 5: Validation and migration

Add a dedicated test suite under `tests/interface_docs/` covering:

- dispatcher validation
- output directory creation
- Python init generation behavior
- Python generator metadata/conversion rendering
- each newly added format handler with a minimal fixture
- one end-to-end `mp.yaml` smoke run over representative transports

Add fixture-based golden tests for generated output where stability matters.

## Concrete Implementation Order

1. Introduce a handler registry and shared job context.
2. Add focused tests for current behavior before widening scope.
3. Port Python metadata and conversion features.
4. Add `generate_init`, `debug`, and dependency-derived enum/type helpers.
5. Bring in missing low-level formats.
6. Add or update batch manifests that demonstrate the expanded feature set.
7. Add golden-output fixtures for the scaffold directories if their file layouts need stronger compatibility guarantees.

## Risks

- `yaml_docs` contains Mediso-specific assumptions around `mediso_packages`, GUI runtime, and app scaffolding that do not belong in `pyontrust`.
- The pyontrust-native scaffold replacements need their own output-contract coverage so future template changes do not drift silently.
- Output compatibility can break existing generated-driver consumers if class names or helper method names change.
- Confluence publishing and some GUI behaviors appear environment-specific and should not be treated as default parity requirements.

## Scope Boundaries

Include in the upgrade:

- batch orchestration parity where it improves maintainability
- Python driver feature parity where it improves generated driver usefulness
- low-level output formats that match `interface_docs` responsibilities

Do not automatically include:

- every Mediso-local template
- publishing integrations without a pyontrust consumer
- app runtime behavior that depends on packages not owned by `pyontrust`

## Suggested Deliverables

- Refactored `interface_docs` dispatcher with pluggable handlers
- Expanded Python generator and template support for conversions, metadata, and richer helper methods
- Additional format handler modules for selected yaml_docs outputs
- New tests under `tests/interface_docs/`
- One example batch manifest documenting the expanded supported formats

## Validation Commands After Implementation

- Run focused unit tests for the new `interface_docs` suite.
- Run a smoke generation pass on `interface_docs/mp.yaml`.
- Diff regenerated artifacts against expected golden outputs.
- Run one scaffold generation smoke test per template family.

## Recommended First Milestone

Phase 1 through Phase 4 are now materially complete for the owned generator surface. Scaffold-owned file layouts and rendered contents are covered by fixture-style tests, the emitted GUI build helper is regression-tested in dry-run mode for both PyInstaller and Nuitka icon-path packaging flows, and the copied batch manifest now has a manifest-level smoke run for the Python transport slice. The next useful milestone is optional expansion of HTML/confluence only if a real consumer appears.