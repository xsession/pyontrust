# Testbench Integration

This directory contains Renode simulation testbench infrastructure for the
Pyontrust Pin Configurator, inspired by the
[Swedish Embedded SDK](https://github.com/swedishembedded/sdk) testbench
architecture.

## Architecture

```
testbench/
├── CMakeLists.txt    # Build targets: testbench, boardbench, appbench, robotbench
├── sample.robot      # RobotFramework test template
└── README.md         # This file
```

## Build Targets

| Target | Mode | Description |
|--------|------|-------------|
| `testbench` | Interactive | Run Renode console with the configured testbench |
| `testbench_xwt` | GUI | Run with Renode X Window (graphical) |
| `testbench_debugserver` | Debug | Run + start GDB server on port 3333 |
| `boardbench` | Interactive | Board-level simulation (from board .resc) |
| `appbench` | Interactive | App-specific simulation (from app boards/*.resc) |
| `appbench_debugserver` | Debug | App simulation + GDB server |
| `robotbench` | Automated | Run RobotFramework test scripts in CI |
| `run_robot` | Automated | Run sample.robot from application source |

## Usage

```bash
# Build your firmware first
west build -p -b lp_mspm0g3507 .

# Interactive simulation
west build -t testbench

# Automated tests (CI-friendly)
west build -t robotbench

# Debug with GDB
west build -t appbench_debugserver
# In another terminal:
arm-none-eabi-gdb -ex "target remote :3333" build/zephyr/zephyr.elf
```

## Integration

Add to your application `CMakeLists.txt`:

```cmake
# After find_package(Zephyr)
include(${PYONTRUST_BASE}/testbench/CMakeLists.txt)
```

Or set the `TESTBENCH` variable to point to a named testbench directory:

```cmake
set(TESTBENCH "my_testbench")
```

## Creating a Custom Testbench

1. Create a directory under `testbench/<name>/`
2. Add `testbench.resc` (Renode platform script)
3. Add `testbench.repl` (Renode platform definition)
4. Optionally add `testbench.robot` for automated tests
5. Enable via `CONFIG_TESTBENCH_<NAME>=y` in prj.conf
