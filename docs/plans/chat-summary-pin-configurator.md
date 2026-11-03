# Chat Summary: Pin Configurator Package Manager & STM32 Parser Fixes

**Date:** May 31, 2026  
**Repository:** `pyontrust`  
**Area:** `externals/pin_configurator`  
**Runtime:** Flask app on `http://127.0.0.1:4124`

---

## Objective

Stabilize the live Pin Configurator workflow after the user reported that Package Manager:

1. Mixed MCU and sensor data
2. Missed STM32 package and pin-mux information
3. Later failed to parse uploads reliably in the live browser flow

---

## Phase 1: Restore MCU-Only Package Manager Behavior

### Problem

Package Manager had drifted into a mixed MCU/sensor workflow:

- Sensor jobs appeared in Package Manager
- Sensor generation paths were reachable from the MCU package endpoint
- Cached stale jobs could continue showing even after server state changed

### Files Updated

| File | Change |
|------|--------|
| `externals/pin_configurator/web/package-manager-live.js` | Forced Package Manager job handling back to MCU-only |
| `externals/pin_configurator/web/main.js` | Mirrored MCU-only Package Manager behavior |
| `externals/pin_configurator/web/index.html` | Restored MCU-only wording in upload and empty-state copy |
| `externals/pin_configurator/server.py` | Removed sensor fallback branch from `/api/generate-package` |

### Key Fixes

- Package Manager now treats all Package Manager jobs as MCU jobs
- Sensor job loading was removed from the Package Manager path
- Package Manager cache sync now prefers current server jobs over stale local storage
- `/api/generate-package` now rejects non-MCU job IDs with a clear MCU-only error

### Validation

- Live Package Manager no longer showed sensor badges or mixed sensor entries
- Sensor job generation through the Package Manager endpoint was rejected correctly
- Stale missing jobs stopped reappearing in the Package Manager sidebar

---

## Phase 2: Fix STM32 Mixed Alphanumeric Alternate Function Parsing

### Problem

STM32 board generation contained malformed alternate-function entries such as:

```python
_AF(5, "I2S4_SD", "i2", "", "io")
```

The root cause was that STM32-style peripheral names with interleaved letters and digits were being truncated during parsing.

### Files Updated

| File | Change |
|------|--------|
| `externals/pin_configurator/pdf_parser.py` | Broadened peripheral-prefix parsing for mixed alphanumeric STM32 names |
| `externals/pin_configurator/tests/test_pdf_parser.py` | Added regression coverage for STM32 mixed alphanumeric prefixes |

### Parser Fix

Updated `_RE_FUNC_SPLIT` from:

```python
([A-Za-z]+\d*)(?:_(.+))?
```

to:

```python
([A-Za-z][A-Za-z0-9]*)(?:_(.+))?
```

### New Regression Coverage

Added focused test cases for:

- `I2S4_CK -> ("i2s4", "ck")`
- `I2S3EXT_SD -> ("i2s3ext", "sd")`
- `USART2_CTS -> ("usart2", "cts")`
- `USB_FS_SOF -> ("usb", "fs_sof")`

### Validation

- Focused parser tests passed: `5 passed, 16 deselected`
- Reparsing the real STM32F411 datasheet produced correct live pin-mux entries
- Freshly generated STM32 board files now emit correct entries such as:

```python
_AF(5, "I2S4_SD", "i2s4", "sd", "io")
```

---

## Phase 3: Live Runtime Mismatch and Server Restart

### Problem

The code on disk had the parser fix, but the live 4124 server initially still returned old malformed STM32 parse results.

### Resolution

- Confirmed the local module import path was correct
- Identified the mismatch as a stale live process image rather than wrong source files
- Restarted the Flask app from the active workspace checkout
- Reparsed the STM32F411 PDF against the restarted live server

### Validation

- The fresh live parse job returned correct STM32 peripheral/signal pairs
- The generated `stm32f411_lqfp64.py` file on disk matched the corrected artifact output

---

## Phase 4: Diagnose Parse Upload Failures

### Problem

Later uploads started failing in the browser with:

- `Upload failed: Unexpected token '<'`
- HTTP 500 responses from `/api/parse-pdf`

The live Flask traceback showed:

```text
OSError: [Errno 28] No space left on device
```

### Investigation

- Checked free space on the `C:` drive and found it effectively exhausted
- Measured likely workspace storage contributors
- Confirmed the repo itself was not the primary problem
- Identified stale upload cache files under `externals/pin_configurator/.uploads` as the safest immediate cleanup target

### Cleanup Performed

- Removed duplicate cached upload PDFs while preserving the newest copy of each filename
- Removed root-level cached upload PDFs under `.uploads`
- Recovered enough free space for live upload parsing to resume

### Validation

- A parse request that previously caused a 500 now returned a normal JSON validation error instead
- A successful browser-driven upload of `mcu_st_stm32f411re.pdf` completed end-to-end
- The live parse job list showed the new MCU parse job alongside the earlier STM32F411 job

---

## Final State

### Confirmed Working

- Package Manager is MCU-only again
- Sensor Parser remains separate from Package Manager behavior
- STM32 mixed alphanumeric alternate-function parsing is fixed
- Fresh STM32F411 board generation emits corrected `i2s4` / `sd` style entries
- Live browser upload parsing works again after disk cleanup

### Observed Remaining Risk

- The machine remained very low on free disk space after cleanup
- Additional cleanup or larger disk recovery may be needed to avoid repeated upload failures

---

## Key Files Touched During the Session

- `externals/pin_configurator/web/package-manager-live.js`
- `externals/pin_configurator/web/main.js`
- `externals/pin_configurator/web/index.html`
- `externals/pin_configurator/server.py`
- `externals/pin_configurator/pdf_parser.py`
- `externals/pin_configurator/tests/test_pdf_parser.py`
- `externals/pin_configurator/boards/stm32f411_lqfp64.py`

---

## Validation Summary

### Executable Validation

- Focused parser regression tests passed
- Live `/api/parse-pdf` reparsing succeeded for STM32F411
- Live `/api/generate-package` produced corrected STM32 board artifacts
- Browser upload flow succeeded again after disk cleanup

### User-Visible Outcomes

- Package Manager stopped mixing MCU and sensor content
- Parsed STM32F411 jobs now expose correct package sets and alternate functions
- Upload failures caused by disk exhaustion were resolved sufficiently for normal parsing to resume

---

## Suggested Follow-Up

- Clear additional nonessential cache or generated data on the machine to prevent future `No space left on device` failures
- If more STM32 families are in scope, run the same regression sweep across additional generated STM32 board files