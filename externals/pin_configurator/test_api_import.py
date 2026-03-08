"""Quick API integration test for import & MCU lookup endpoints."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json
import urllib.request

BASE = "http://127.0.0.1:5100"

def post_json(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}


def test_boards():
    print("-- GET /api/boards --")
    req = urllib.request.Request(BASE + "/api/boards")
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode())
    print(f"  Status: {resp.status}, Boards: {[b['board'] for b in data]}")
    return resp.status == 200


def test_import_config_conf_only():
    print("\n-- POST /api/import-config (conf only) --")
    code, data = post_json("/api/import-config", {
        "conf": "CONFIG_SERIAL=y\nCONFIG_GPIO=y\nCONFIG_CONSOLE=y\n",
        "board_name": "lp_mspm0g3507",
    })
    print(f"  Status: {code}")
    print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
    if code == 200:
        print(f"  Kconfig count: {len(data.get('kconfig', []))}")
        for k in data.get("kconfig", []):
            print(f"    {k}")
    else:
        print(f"  Error: {data}")
    return code == 200


def test_import_config_overlay():
    print("\n-- POST /api/import-config (overlay + conf) --")
    overlay = """
&pinctrl {
    uart0_default: uart0_default {
        group1 {
            pinmux = <PINCM1_PF_UART0_TX>;
        };
        group2 {
            pinmux = <PINCM2_PF_UART0_RX>;
            input-enable;
        };
    };
};

&uart0 {
    status = "okay";
    pinctrl-0 = <&uart0_default>;
    pinctrl-names = "default";
    current-speed = <115200>;
};
"""
    conf = "CONFIG_SERIAL=y\nCONFIG_CONSOLE=y\nCONFIG_UART_CONSOLE=y\nCONFIG_GPIO=y\n"

    code, data = post_json("/api/import-config", {
        "overlay": overlay,
        "conf": conf,
        "board_name": "lp_mspm0g3507",
    })
    print(f"  Status: {code}")
    if code == 200:
        pins = data.get("pins", [])
        periphs = data.get("peripherals", [])
        kconfigs = data.get("kconfig", [])
        warnings = data.get("warnings", [])
        print(f"  Pins: {len(pins)}")
        for p in pins:
            print(f"    {p}")
        print(f"  Peripherals: {len(periphs)}")
        for p in periphs:
            print(f"    {p}")
        print(f"  Kconfig: {len(kconfigs)}")
        print(f"  Warnings: {len(warnings)}")
        for w in warnings:
            print(f"    ! {w}")
    else:
        print(f"  Error: {data}")
    return code == 200


def test_scan_project():
    print("\n-- POST /api/scan-project --")
    code, data = post_json("/api/scan-project", {
        "project_path": r"C:\GIT\WORK\codelayer\locator_base\examples_apps\13_renode_demo",
    })
    print(f"  Status: {code}")
    if code == 200:
        files = data.get("files", [])
        print(f"  Found {len(files)} file(s):")
        for f in files:
            print(f"    {f['relative']} ({f['type']}, {f['size']} bytes)")
    else:
        print(f"  Error: {data}")
    return code == 200


def test_identify_mcu():
    print("\n-- POST /api/identify-mcu --")
    results = []
    for pn in ["MSPM0G3507", "STM32F401RE", "NRF52840", "UNKNOWN_CHIP_123"]:
        code, data = post_json("/api/identify-mcu", {"part_number": pn})
        if code == 200:
            known = data.get("known", False)
            vendor = data.get("vendor_name", "?")
            urls = len(data.get("datasheet_urls", []))
            existing = data.get("existing_board", "")
            print(f"  {pn}: known={known}, vendor={vendor}, urls={urls}, existing={existing}")
            results.append(True)
        else:
            print(f"  {pn}: error {code} - {data}")
            results.append(False)
    return all(results)


if __name__ == "__main__":
    results = []
    results.append(("boards", test_boards()))
    results.append(("import_conf", test_import_config_conf_only()))
    results.append(("import_overlay", test_import_config_overlay()))
    results.append(("scan_project", test_scan_project()))
    results.append(("identify_mcu", test_identify_mcu()))

    print("\n======================================")
    for name, ok in results:
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name}")
    print("======================================")
