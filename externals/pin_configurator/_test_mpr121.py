"""Quick MPR121 test script."""
import sys, time
sys.path.insert(0, r"c:\GIT\pyontrust\gui_app\pin_configurator")

from sensor_parser import parse_sensor_datasheet, sensor_info_to_json, identify_sensor

# Quick identify test
print("Identify MPR121:", identify_sensor("MPR121"))

# Full parse
t0 = time.time()
info = parse_sensor_datasheet(r"c:\Users\Riko\Downloads\MPR121.pdf")
j = sensor_info_to_json(info)
dt = time.time() - t0

print(f"\nParse time: {dt:.1f}s")
print(f"Part: {j['summary']['part_number']}")
print(f"Vendor: {j['summary']['vendor_name']}")
print(f"Type: {j['summary']['sensor_type']}")
print(f"Description: {j['summary']['description'][:120]}..." if j['summary']['description'] else "Description: (none)")
print(f"Regs: {len(j['register_map']['registers'])}")
print(f"Protocol: {j['address']['protocol']}")
print(f"I2C addrs: {j['address']['i2c_addresses']}")
print(f"Addr pin: {j['address']['i2c_address_pin']}")

print("\nFirst 10 registers:")
for r in j['register_map']['registers'][:10]:
    addr = r['address']
    name = r['name']
    access = r['access']
    nf = len(r.get('fields', []))
    if isinstance(addr, int):
        print(f"  0x{addr:02X}  {name:30s}  [{access:3s}]  fields={nf}")
    else:
        print(f"  {str(addr):6s}  {name:30s}  [{access:3s}]  fields={nf}")
