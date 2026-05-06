# Pin Configurator TS Backend

This directory contains the productized TypeScript backend for the pin configurator.

## Layout

- `src/` — application source and parser implementations
- `scripts/` — executable validation and smoke-test entry points
- `docs/` — backend-facing product documentation
- `validation/manifests/` — curated vendor test matrices
- `validation/reports/` — generated validation reports

## Core Commands

```bash
npm run build
npm run organize:runtime
npm run digest:uploads
npm run check:native-sensors
npm run check:native-mcus
npm run smoke:api-sensor
npm run smoke:api-mcu
npm run check:all-native
npm run validate:vendor-matrix
```

## Quality Gates

- `check:native-sensors` locks sensor sample parity.
- `check:native-mcus` locks MCU sample parity.
- `smoke:api-sensor` verifies the sensor upload flow and saved job endpoints.
- `smoke:api-mcu` verifies MCU upload and package generation with cleanup.
- `organize:runtime` migrates legacy flat `.uploads/` artifacts into the structured runtime folders.
- `digest:uploads` scans `.uploads/incoming/`, keeps the original PDFs, and creates normal parse jobs for undigested files.
- `validate:vendor-matrix` downloads and tests the broad cross-vendor matrix while retaining the downloaded PDFs under `.uploads/vendor_matrix/`.