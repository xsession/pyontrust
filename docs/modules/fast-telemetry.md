# Fast Telemetry (on-device app, zero USB round-trips)

The `adb shell` path costs a full process-spawn per measurement (tens of ms).
For fast measurements and events the helper APK runs a **foreground telemetry
service** that samples on-device at sensor rate, batches in memory, and streams
over one TCP connection (`adb forward`) — latency drops to ~10 ms flush
intervals with nanoTime timestamps.

## Android app (android-app/)

* `fast/FastTelemetryService.kt` — foreground service:
  * **sensors** — accelerometer / gyro / light / pressure at `SENSOR_DELAY_FASTEST`,
    each sample `[t_ns, type, x, y, z]` (values ×1e6 for integer precision)
  * **touch** — full-screen `TouchPadActivity` pushes down/move/up with
    coordinates + pressure into an in-process bus; events stream immediately
  * **audio** — 48 kHz mic energy frames `[t_ms, rms, peak]`; raw WAV recording
    to app storage (`record` command); speaker tone generation (`tone`) for
    sonar/auditory tests
  * on-device event detection: shock (accel spike > ~2.5 g) emitted as an event frame
* Start it from the PC:

      adb shell am start-foreground-service -n com.pyontrust.android/.fast.FastTelemetryService
      adb forward tcp:4780 tcp:4780

## Python client (pyontrust.phone.fastlink)

```python
from pyontrust.phone import FastLink

with FastLink(serial="ABC123") as link:          # does adb forward + connect
    link.start(streams=("sensors", "touch"))     # or + "audio"
    for s in link.iter_samples(timeout_s=0.5):   # low-latency iteration
        print(s)                                  # {t_ns, stream, x, y, z} / events

data = link.collect(duration_s=2.0)              # ring-buffer snapshot per stream
link.vibrate(300); link.tone(1000, 400)          # actuation over the same socket
ack = link.record(2000)                          # mic WAV on device; ack has path
```

## Protocol (newline-delimited JSON)

| Direction | Frame |
|---|---|
| PC → app | `{"cmd":"start","streams":[...],"rate_hz":500}` · `stop` · `vibrate{ms}` · `tone{freq,ms}` · `record{ms}` · `status` |
| app → PC | `{"type":"ack",...}` · `{"type":"batch","stream":"sensors\|touch\|audio","n":K,"samples":[[t,...],...]}` · `{"type":"event","kind":"touch_down\|touch_up\|shock","t_ns":...}` |

## Notes

* Build with the repo's usual gradle setup (no Android SDK on this host);
  install, grant RECORD_AUDIO when prompted.
* Single-client socket: one FastLink per device at a time.
* Verified without hardware: `tests/phone/test_fastlink.py` runs a fake app
  server implementing the same protocol — command framing, ack handling,
  sample flattening/scaling and event routing all asserted (9 tests).

## Sonar (speaker → mic time-of-flight)

`pyontrust.phone.PhoneSonar` turns the phone into an acoustic rangefinder:
the device plays a linear-FM chirp from its speaker while recording its own
microphone, and the PC cross-correlates the capture against a locally generated
reference. The first peak is the direct speaker→mic path (self-calibrating — it
absorbs all clock offsets); every later peak is an echo: `distance = c·Δt/2`.

```python
from pyontrust.phone import FastLink, PhoneSonar

with FastLink(serial="ABC123") as link:
    sonar = PhoneSonar(link)
    res = sonar.ping()                    # 50 ms chirp 2–8 kHz, 400 ms capture
    for pk in res.peaks:
        print(f"{pk['distance_m']:7.3f} m   amp={pk['amp']:.1f}")

# Offline analysis of a previously pulled WAV (no device needed):
res = PhoneSonar(link).ping(local_wav="sonar_123.wav")
```

* `res.peaks[0]` is the direct path (distance ≈ 0); reflections follow in arrival order.
* `threshold_db` sets how weak an echo may be relative to the direct path;
  `top_n` caps the number of reported peaks.
* The whole ping runs on-device (`record → delayed chirp → stop`), so no PC
  round-trip sits in the critical timing path:
  `{"cmd":"sonar","f0":2000,"f1":8000,"tx_ms":50,"rec_ms":400,"delay_ms":80}`.
* Verified without hardware: `tests/phone/test_sonar.py` (10 tests) — chirp endpoint
  frequencies, FFT correlation vs `np.correlate`, peak picking, WAV round-trip and a
  full offline ping recovering a synthetic reflection at 1.7 m within ±5 cm.
