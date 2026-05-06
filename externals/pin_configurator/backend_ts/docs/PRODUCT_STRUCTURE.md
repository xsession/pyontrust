# Product Structure

The TypeScript backend is organized around three concerns:

1. `src/` owns runtime behavior.
   It contains the HTTP server, parser implementations, registries, code generators, and persistence helpers.

2. `scripts/` owns executable quality gates.
   Smoke tests and regression checks live here so they can run in CI or by a developer with one command.

3. `validation/` owns curated real-world coverage.
   Manifests declare which vendor PDFs are used for broad validation and reports capture the latest run outcome.

This keeps product code, quality gates, and validation fixtures separate instead of mixing exploratory files into the runtime surface.

## Runtime Artifact Layout

- `.uploads/incoming/` stores raw user or imported PDFs that have not been normalized into a persistent parse job yet.
- `.uploads/mcu_jobs/` stores MCU datasheets that already correspond to saved parse jobs.
- `.uploads/sensor_jobs/` stores sensor datasheets that already correspond to saved parse jobs.
- `.uploads/downloads/` stores direct download results before they are promoted into a saved job.
- `.uploads/vendor_matrix/` stores curated validation inputs downloaded by the cross-vendor matrix.

This keeps source code, validation inputs, and mutable runtime artifacts separated by purpose instead of accumulating all PDFs in one flat directory.