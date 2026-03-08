"""Stub instrument drivers with entry-point factories.

These stubs lazy-import their optional dependencies inside open().
The actual driver logic is preserved from the original codebase;
only the factory function is new for the entry-point system.
"""

from __future__ import annotations

from typing import Any


# --- AD3 Cluster ---
def _create_ad3_cluster(config: dict[str, Any]) -> Any:
    from pyontrust_packages.power_test_framework.instruments.ad3_cluster import (
        Ad3ClusterPowerMeter,
        Ad3DeviceConfig,
    )

    devices = [Ad3DeviceConfig.from_dict(d) for d in config.get("devices", [])]
    return Ad3ClusterPowerMeter(
        devices=devices,
        buffer_size=int(config.get("buffer_size", 8192)),
        trigger_source=config.get("trigger_source", "none"),
    )


# --- PPK2 ---
def _create_ppk2(config: dict[str, Any]) -> Any:
    from pyontrust_packages.power_test_framework.instruments.ppk2 import Ppk2PowerMeter

    return Ppk2PowerMeter(
        serial_port=config.get("serial_port", config.get("port", "auto")),
        sample_rate_hz=float(config.get("sample_rate_hz", 100_000)),
        mode=config.get("mode", "ampere"),
        source_voltage_mv=int(config.get("source_voltage_mv", 3300)),
    )


# --- SK120 PSU ---
def _create_sk120(config: dict[str, Any]) -> Any:
    from pyontrust_packages.power_test_framework.instruments.sk120_psu import Sk120PowerSupply

    return Sk120PowerSupply(
        port=config.get("port", ""),
        baud=int(config.get("baud", 9600)),
        voltage_v=float(config.get("voltage_v", 3.3)),
        current_limit_a=float(config.get("current_limit_a", 0.5)),
        channel=int(config.get("channel", 1)),
        output_on=bool(config.get("output_on", True)),
    )


# --- J-Link ---
def _create_jlink(config: dict[str, Any]) -> Any:
    from pyontrust_packages.power_test_framework.instruments.jlink_ctrl import JLinkController

    return JLinkController(
        device=config.get("device", ""),
        interface=config.get("interface", "swd"),
        speed_khz=int(config.get("speed_khz", 4000)),
        serial=config.get("serial", "auto"),
        jlink_path=config.get("jlink_path", "auto"),
    )


# --- HackRF ---
def _create_hackrf(config: dict[str, Any]) -> Any:
    from pyontrust_packages.power_test_framework.instruments.hackrf_instrument import HackRfInstrument

    return HackRfInstrument(
        freq_hz=int(config.get("freq_hz", 2_402_000_000)),
        sample_rate_hz=int(config.get("sample_rate_hz", 10_000_000)),
        lna_gain_db=int(config.get("lna_gain_db", 16)),
        vga_gain_db=int(config.get("vga_gain_db", 20)),
        amp_enable=bool(config.get("amp_enable", False)),
        device_serial=config.get("device_serial", "auto"),
    )


# --- Webcam ---
def _create_webcam(config: dict[str, Any]) -> Any:
    from pyontrust_packages.power_test_framework.instruments.webcam_instrument import WebcamInstrument

    return WebcamInstrument(
        input_device=config.get("input_device", ""),
        ffmpeg_path=config.get("ffmpeg_path", "ffmpeg"),
        framerate=int(config.get("framerate", 30)),
        video_size=config.get("video_size", "1280x720"),
    )


# --- PCAN ---
def _create_pcan(config: dict[str, Any]) -> Any:
    # Placeholder — PCAN as instrument (vs recorder) is rare
    raise NotImplementedError("PCAN instrument not yet available; use pcan_can recorder instead.")


# --- SoapySDR ---
def _create_soapy(config: dict[str, Any]) -> Any:
    # Placeholder for SoapySDR integration
    raise NotImplementedError("SoapySDR instrument — use sdr_module HAL directly.")


# --- CSV Replay ---
def _create_csv_replay(config: dict[str, Any]) -> Any:
    from pyontrust.instruments.csv_power_meter import CsvFilePowerMeter

    return CsvFilePowerMeter(
        csv_path=config["csv_path"],
        t_col=config.get("t_col", "t_s"),
        i_col=config.get("i_col", "current_a"),
        v_col=config.get("v_col", "voltage_v"),
    )


# --- nRF52840 Dongle ---
def _create_nrf52840_dongle(config: dict[str, Any]) -> Any:
    from pyontrust_packages.drivers.nrf52840_dongle import Nrf52840Dongle

    return Nrf52840Dongle(
        port=config.get("port"),
        baudrate=int(config.get("baudrate", 115200)),
    )
