# Pyontrust Android USB App

Native Kotlin Android prototype for running, editing, and monitoring measurement sessions against USB-connected hardware.

## Current capabilities

- Discover USB host devices attached to the Android phone or tablet
- Request USB permission and open a bulk IN/OUT interface
- Edit a persistent measurement profile on-device
- Apply profile settings using a templated command string
- Start and stop a measurement run
- Poll device status once per second and show live responses in a log panel

## Important assumption

This first version uses a generic bulk-endpoint transport. It works best when the hardware exposes a simple USB bulk protocol and accepts line-oriented text commands such as:

```text
SET RATE=1000;DURATION=10;CHANNEL=A0
MEASURE:START
MEASURE:STATUS?
MEASURE:STOP
```

If the target hardware uses CDC ACM, HID, vendor control transfers, or a binary framing protocol, extend `PyontrustUsbRepository` to match that transport.

## Suggested next steps

1. Replace the default commands with the real pyontrust hardware command set.
2. Add framing/parsing for structured measurement samples.
3. Export captured runs to JSON or CSV for the existing Python-side analysis pipeline.
