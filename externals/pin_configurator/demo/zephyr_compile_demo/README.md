# Zephyr Compile Demo

This app is a minimal Zephyr target used to validate generated pin configurator
artifacts against a real board build.

The pytest compile test copies this directory to a temporary location, writes the
generated `app.overlay` and `prj.conf`, and then runs:

```powershell
west build -p auto -b lp_mspm0g3507 -s <copied-demo-app> -d <build-dir>
```

You can also use it manually by replacing the placeholder files in this folder.