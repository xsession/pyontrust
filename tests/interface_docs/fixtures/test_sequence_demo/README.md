# DemoBoardSequence

Generated from `Demo Interface` using the `test-sequence` scaffold.

This scaffold embeds the generated Python driver and gives you:

- unit-style metadata tests that run without hardware
- an optional HIL smoke test using `pyontrust.hil.HILTestFixture`
- a sequence helper you can extend with device-specific checks

## Run

```bash
python -m pytest
```

To enable the HIL smoke test, set `PYONTRUST_ENABLE_HIL=1` and adjust the board/app settings in `conftest.py`.