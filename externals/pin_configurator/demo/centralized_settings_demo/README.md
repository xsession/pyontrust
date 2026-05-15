# Pin Configurator Demo App

This app was materialized from a normalized Pin Configurator project document.

It contains:
- generated Zephyr overlay and `prj.conf`
- a small firmware entrypoint that prints the collected configuration summary
- a Renode appbench script in `boards/lp_mspm0g3507.resc`
- a RobotFramework smoke test in `sample.robot`
- preserved generated source artifacts under `generated/`

## Build

```powershell
west build -p auto -b lp_mspm0g3507 .
```

## Renode

```powershell
west build -t appbench
west build -t robotbench
```
