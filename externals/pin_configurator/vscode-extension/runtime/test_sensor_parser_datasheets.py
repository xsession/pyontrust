#!/usr/bin/env python3
"""Test sensor_parser on LM73 and BMP280 datasheets."""

import json
import sys
import logging

from sensor_parser import parse_sensor_datasheet

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DATASHEETS = [
    (".uploads/lm73.pdf",   "TI LM73 Temperature Sensor"),
    (".uploads/bmp280.pdf", "Bosch BMP280 Pressure/Temperature Sensor"),
]


def test_datasheet(pdf_path: str, label: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {label}")
    print(f"  PDF: {pdf_path}")
    print("=" * 72)

    info = parse_sensor_datasheet(pdf_path, verbose=False)

    # ── Summary ──
    s = info.summary
    print(f"\n--- Summary ---")
    print(f"  Part Number : {s.part_number}")
    print(f"  Vendor      : {s.vendor_name} ({s.vendor})")
    print(f"  Sensor Type : {s.sensor_type}")
    print(f"  Description : {s.description}")
    print(f"  WHO_AM_I reg: 0x{s.who_am_i_reg:02X}" if s.who_am_i_reg >= 0 else "  WHO_AM_I reg: (not found)")
    print(f"  WHO_AM_I val: 0x{s.who_am_i_value:02X}" if s.who_am_i_value >= 0 else "  WHO_AM_I val: (not found)")
    print(f"  Supply V    : {s.supply_voltage_min} – {s.supply_voltage_max} V")
    print(f"  Temp Range  : {s.temp_range_min} – {s.temp_range_max} °C")

    # ── Addresses ──
    a = info.address
    print(f"\n--- Communication ---")
    print(f"  Protocol    : {a.protocol}")
    print(f"  I2C Addrs   : {['0x{:02X}'.format(x) for x in a.i2c_addresses]}")
    print(f"  Addr Pin    : {a.i2c_address_pin or '(none)'}")
    print(f"  SPI Max Freq: {a.spi_max_freq_hz} Hz" if a.spi_max_freq_hz else "  SPI Max Freq: N/A")
    print(f"  SPI Mode    : {a.spi_mode}" if a.spi_mode >= 0 else "  SPI Mode    : N/A")

    # ── Register Map ──
    rm = info.register_map
    print(f"\n--- Register Map ({len(rm.registers)} registers) ---")
    for r in rm.registers:
        fields_str = f"  [{len(r.fields)} fields]" if r.fields else ""
        print(f"  0x{r.address:02X}  {r.name:<30s}  {r.access:<4s}  reset=0x{r.reset_value:02X}{fields_str}")
        if r.fields:
            for f in r.fields:
                print(f"         [{f.bits:>5s}] {f.name:<20s} {f.access:<4s}  {f.description[:50]}")

    # ── C Header Preview ──
    header = info.to_c_header()
    print(f"\n--- C Header (first 40 lines) ---")
    for line in header.split("\n")[:40]:
        print(f"  {line}")

    # ── JSON output ──
    j = info.to_json()
    print(f"\n--- JSON Summary ---")
    print(f"  register_count: {j['register_map']['register_count']}")
    print(f"  i2c_addresses : {j['address']['i2c_addresses']}")

    return info


if __name__ == "__main__":
    results = {}
    for pdf, label in DATASHEETS:
        try:
            info = test_datasheet(pdf, label)
            results[pdf] = info
        except Exception as exc:
            print(f"\n  ERROR parsing {pdf}: {exc}")
            import traceback
            traceback.print_exc()

    print("\n\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    for pdf, label in DATASHEETS:
        if pdf in results:
            info = results[pdf]
            print(f"  {label}")
            print(f"    Part: {info.summary.part_number}, Type: {info.summary.sensor_type}")
            print(f"    Regs: {len(info.register_map.registers)}, I2C: {['0x{:02X}'.format(x) for x in info.address.i2c_addresses]}")
        else:
            print(f"  {label}: FAILED")
    print()
