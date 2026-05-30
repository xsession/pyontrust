# Real Blinky Import Demo

This sample is a checked-in Zephyr-style blinky app that the purple-view Arduino importer can scan directly.

It includes:

- a board overlay with parseable UART pinctrl nodes for `lp_mspm0g3507`
- a `led0` alias for a Zephyr blinky-style main loop
- a Renode `.resc` script and Robot smoke test

Typical workflow:

```powershell
python run.py --port 4124
```

Then open the `Arduino Importer` tab and scan this directory.

If your Zephyr environment and Renode are installed, you can also build and emulate it directly:

```powershell
west build -p auto -b lp_mspm0g3507 .
west build -t appbench
west build -t run_robot
```