"""Quick smoke test for the Pin Configurator API."""
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:5100"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"},
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

def main():
    ok = 0

    # 1. Board list
    boards = get("/api/boards")
    assert len(boards) >= 1, "No boards returned"
    print(f"[PASS] Board list: {[b['id'] for b in boards]}")
    ok += 1

    # 2. Board detail
    brd = get("/api/board/mspm0g3507")
    assert brd["soc"] == "MSPM0G3507"
    assert brd["pin_count"] == 48
    assert len(brd["pins"]) == 48
    assert len(brd["peripherals"]) >= 10
    print(f"[PASS] Board detail: {brd['soc']} {brd['package']}, "
          f"{len(brd['pins'])} pins, {len(brd['peripherals'])} peripherals")
    ok += 1

    # 3. Generate UART0 overlay
    result = post("/api/generate", {
        "board": "lp_mspm0g3507",
        "assignments": [
            {"pin_name": "PA10", "pincm": 21, "function_id": 2,
             "af_name": "UART0_TX", "peripheral": "uart0",
             "signal": "tx", "direction": "out"},
            {"pin_name": "PA11", "pincm": 22, "function_id": 2,
             "af_name": "UART0_RX", "peripheral": "uart0",
             "signal": "rx", "direction": "in"},
        ],
        "peripherals": [
            {"name": "uart0", "dts_node": "&uart0",
             "compatible": "ti,mspm0-uart", "enabled": True},
        ],
    })
    overlay = result["overlay"]
    conf = result["prj_conf"]
    assert "MSP_PINMUX" in overlay, "Missing MSP_PINMUX in overlay"
    assert "&pinctrl" in overlay, "Missing &pinctrl block"
    assert "&uart0" in overlay, "Missing &uart0 enable"
    assert "pinctrl-0" in overlay, "Missing pinctrl-0 ref"
    assert "CONFIG_SERIAL=y" in conf, "Missing SERIAL in prj.conf"
    print(f"[PASS] Generate overlay ({len(overlay)} chars)")
    print()
    print("--- Generated overlay ---")
    print(overlay)
    print("--- Generated prj.conf ---")
    print(conf)
    ok += 1

    # 4. Generate with multiple peripherals
    result2 = post("/api/generate", {
        "board": "lp_mspm0g3507",
        "assignments": [
            {"pin_name": "PA10", "pincm": 21, "function_id": 2,
             "af_name": "UART0_TX", "peripheral": "uart0",
             "signal": "tx", "direction": "out"},
            {"pin_name": "PA11", "pincm": 22, "function_id": 2,
             "af_name": "UART0_RX", "peripheral": "uart0",
             "signal": "rx", "direction": "in"},
            {"pin_name": "PA17", "pincm": 39, "function_id": 3,
             "af_name": "I2C0_SCL", "peripheral": "i2c0",
             "signal": "scl", "direction": "io"},
            {"pin_name": "PA18", "pincm": 40, "function_id": 3,
             "af_name": "I2C0_SDA", "peripheral": "i2c0",
             "signal": "sda", "direction": "io"},
        ],
        "peripherals": [
            {"name": "uart0", "dts_node": "&uart0",
             "compatible": "ti,mspm0-uart", "enabled": True},
            {"name": "i2c0", "dts_node": "&i2c0",
             "compatible": "ti,mspm0-i2c", "enabled": True},
            {"name": "gpioa", "dts_node": "&gpioa",
             "compatible": "ti,mspm0-gpio", "enabled": True},
        ],
    })
    o2 = result2["overlay"]
    c2 = result2["prj_conf"]
    assert "&i2c0" in o2, "Missing &i2c0 enable"
    assert "I2C_BITRATE_STANDARD" in o2, "Missing I2C clock"
    assert "&gpioa" in o2, "Missing &gpioa enable"
    assert "CONFIG_I2C=y" in c2, "Missing I2C in conf"
    assert "CONFIG_GPIO=y" in c2, "Missing GPIO in conf"
    print(f"[PASS] Multi-peripheral generate ({len(o2)} chars)")
    ok += 1

    print(f"\nAll {ok} tests passed!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
