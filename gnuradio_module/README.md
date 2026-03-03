# GNU Radio Module (pyontrust)

This is an **optional**, embeddable NiceGUI module that integrates GNU Radio in a multiplatform way:

- **In-process** (if `gnuradio` is importable in the same Python interpreter)
- **External runner** (run a `.grc` or Python flowgraph using another Python executable, e.g. a Conda env)

## Dev install

```powershell
Set-Location C:\GIT\pyontrust
.\.venv-nicegui\Scripts\python -m pip install -e gnuradio_module
```

## Run standalone

```powershell
Set-Location C:\GIT\pyontrust
python gnuradio_module\examples\run_standalone.py
```
