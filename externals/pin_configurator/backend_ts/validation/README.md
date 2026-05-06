# Validation Assets

This folder contains curated cross-vendor validation inputs and generated reports.

## Contents

- `manifests/vendor_matrix.json` — explicit sensor and MCU datasheet matrix used by `npm run validate:vendor-matrix`
- `reports/vendor_matrix.latest.json` — latest generated run report

## Usage

```bash
npm run validate:vendor-matrix
npm run digest:uploads
```

The matrix runner downloads each PDF, stores the original file under `.uploads/vendor_matrix/`, posts it through the live API, and records the parse result.

The upload digester scans `.uploads/incoming/` for undigested PDFs, keeps the originals in place, and creates normal sensor or MCU parse jobs from temporary working copies.

Set `PIN_CONFIG_CLEANUP_VENDOR_JOBS=1` only when you explicitly want the matrix runner to remove the parse jobs it creates.