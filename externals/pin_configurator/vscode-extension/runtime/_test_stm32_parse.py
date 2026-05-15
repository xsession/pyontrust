"""Test the updated pdf_parser with the STM32L476RG datasheet."""
import sys
sys.path.insert(0, ".")
from pdf_parser import parse_datasheet

PDF_PATH = r"c:\Users\Riko\Downloads\stm32l476rg.pdf"

print("Parsing STM32L476RG datasheet...")
info = parse_datasheet(PDF_PATH, verbose=True)

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

print(f"\nDevice:")
print(f"  SOC: {info.device.soc}")
print(f"  Vendor: {info.device.vendor}")
print(f"  Flash: {info.device.flash_size_kb} KB")
print(f"  SRAM: {info.device.sram_size_kb} KB")
print(f"  Clock: {info.device.clock_hz} Hz ({info.device.clock_hz // 1_000_000} MHz)")

print(f"\nPackages: {len(info.packages)}")
for pkg in info.packages:
    print(f"  {pkg.name}: {pkg.pin_count} pins ({len(pkg.pins)} extracted)")
    if pkg.pins:
        print(f"    First 5: {[(p.number, p.name) for p in pkg.pins[:5]]}")

print(f"\nPin Mux: {len(info.pin_mux)} pins")
total_funcs = sum(len(v) for v in info.pin_mux.values())
print(f"  Total functions: {total_funcs}")

# Show a few sample pins
for pin_name in sorted(info.pin_mux.keys())[:5]:
    entries = info.pin_mux[pin_name]
    print(f"\n  {pin_name}: {len(entries)} functions")
    for e in entries[:6]:
        print(f"    AF{e.function_id}: {e.function_name} ({e.peripheral}.{e.signal}) [{e.direction}]")

print("\nDone!")
