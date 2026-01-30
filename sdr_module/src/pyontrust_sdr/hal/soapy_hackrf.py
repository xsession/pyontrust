from __future__ import annotations

import time
from typing import Optional

import numpy as np

from ..errors import DeviceNotFound, DriverError, StreamOverrun
from ..models import DeviceInfo, RxConfig
from .protocol import SdrHal


class SoapyHackrfHal(SdrHal):
    """HackRF RX via SoapySDR.

    Integration choice: SoapySDR Python bindings + SoapyHackRF module.
    - Pros: portable HAL, easy future backends (RTL-SDR, Lime, USRP)
    - Cons: requires Soapy runtime install per-OS
    """

    def __init__(self) -> None:
        self._dev = None
        self._rx_stream = None
        self._cfg = RxConfig()

    def discover(self) -> list[DeviceInfo]:
        try:
            import SoapySDR  # type: ignore
        except Exception as e:
            return []

        results = []
        for item in SoapySDR.Device.enumerate({"driver": "hackrf"}):
            device_id = item.get("serial", item.get("label", "hackrf"))
            label = item.get("label", f"HackRF {device_id}")
            results.append(DeviceInfo(device_id=device_id, driver="hackrf", display_name=label, meta=dict(item)))
        return results

    def open(self, device_id: str) -> None:
        try:
            import SoapySDR  # type: ignore
            from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32  # type: ignore
        except Exception as e:
            raise DriverError(
                "SoapySDR Python bindings not available. Install optional deps: pip install 'pyontrust-sdr-module[soapy]'"
            ) from e

        # Best-effort: match by serial if provided, else let Soapy pick.
        args = {"driver": "hackrf"}
        if device_id:
            args["serial"] = device_id
        try:
            self._dev = SoapySDR.Device(args)
        except Exception as e:
            raise DeviceNotFound(f"HackRF not found (serial={device_id}).") from e

        self._dev.setSampleRate(SOAPY_SDR_RX, 0, float(self._cfg.sample_rate_hz))
        self._dev.setFrequency(SOAPY_SDR_RX, 0, float(self._cfg.center_freq_hz))
        try:
            self._dev.setGain(SOAPY_SDR_RX, 0, float(self._cfg.gain_db))
        except Exception:
            pass
        if self._cfg.bandwidth_hz is not None:
            try:
                self._dev.setBandwidth(SOAPY_SDR_RX, 0, float(self._cfg.bandwidth_hz))
            except Exception:
                pass

        self._rx_stream = self._dev.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)

    def close(self) -> None:
        try:
            self.stop_stream()
        finally:
            self._rx_stream = None
            self._dev = None

    def set_rx_config(self, cfg: RxConfig) -> None:
        self._cfg = cfg
        if not self._dev:
            return
        try:
            from SoapySDR import SOAPY_SDR_RX  # type: ignore
        except Exception:
            return
        self._dev.setSampleRate(SOAPY_SDR_RX, 0, float(cfg.sample_rate_hz))
        self._dev.setFrequency(SOAPY_SDR_RX, 0, float(cfg.center_freq_hz))
        try:
            self._dev.setGain(SOAPY_SDR_RX, 0, float(cfg.gain_db))
        except Exception:
            pass
        if cfg.bandwidth_hz is not None:
            try:
                self._dev.setBandwidth(SOAPY_SDR_RX, 0, float(cfg.bandwidth_hz))
            except Exception:
                pass

    def start_stream(self) -> None:
        if not self._dev or not self._rx_stream:
            raise DriverError("Device not opened")
        from SoapySDR import SOAPY_SDR_END_BURST  # type: ignore

        # activateStream signature differs across builds; keep minimal.
        self._dev.activateStream(self._rx_stream)

    def read_iq(self, num_samples: int, timeout_s: float) -> np.ndarray:
        if not self._dev or not self._rx_stream:
            raise DriverError("Stream not started")

        out = np.empty((num_samples,), dtype=np.complex64)
        mv = out.view(np.float32).reshape(-1)  # CF32 is interleaved floats

        start = time.time()
        got = 0
        while got < num_samples:
            remaining = num_samples - got
            buff = np.empty((remaining,), dtype=np.complex64)
            try:
                sr = self._dev.readStream(self._rx_stream, [buff], remaining, timeoutUs=int(timeout_s * 1e6))
            except Exception as e:
                raise DriverError("readStream failed") from e
            if sr.ret > 0:
                out[got : got + sr.ret] = buff[: sr.ret]
                got += sr.ret
                continue
            if sr.ret == 0:
                if time.time() - start > timeout_s:
                    break
                continue
            # negative ret indicates error
            raise StreamOverrun(f"Soapy readStream error: {sr.ret}")

        if got < num_samples:
            return out[:got]
        return out

    def stop_stream(self) -> None:
        if not self._dev or not self._rx_stream:
            return
        try:
            self._dev.deactivateStream(self._rx_stream)
        except Exception:
            pass
        try:
            self._dev.closeStream(self._rx_stream)
        except Exception:
            pass
        self._rx_stream = None
