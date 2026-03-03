# ZMQ IQ Bridge Demo

This demo connects **pyontrust SDR module** and **GNU Radio** using ZMQ.

## 1) Publish IQ from pyontrust SDR

1. Install optional ZMQ deps:

```powershell
Set-Location C:\GIT\pyontrust
python -m pip install -e sdr_module[zmq]
```

2. In the SDR UI, import and apply:

- `sdr_module/examples/graphs/zmq_publish_iq.json`

This publishes raw complex64 IQ on `tcp://*:5555`.

## 2) Consume IQ in GNU Radio

Option A: GNU Radio Companion (recommended)

- Add a **ZMQ SUB Source** block.
- Set type to `gr_complex`.
- Address: `tcp://127.0.0.1:5555`
- Connect it to a QT GUI Frequency Sink / Waterfall, or any processing chain.

Option B: If you already have a `.grc` or `.py`, run it from the `GNU Radio` tab in `pyontrust_gui` using `conda` mode.

## 3) (Reverse) Publish from GNU Radio to pyontrust SDR

- In GNU Radio, add a **ZMQ PUB Sink** (`gr_complex`) at `tcp://*:5556`.
- In SDR, import `sdr_module/examples/graphs/zmq_subscribe_iq.json` and change the address to `tcp://127.0.0.1:5556`.
