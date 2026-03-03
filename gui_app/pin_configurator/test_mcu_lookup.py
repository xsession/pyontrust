"""Test identify-mcu for various part numbers."""
import json, urllib.request

BASE = "http://127.0.0.1:5100"

parts = [
    "STM32L476", "STM32L476RG", "STM32F401RE", "STM32H750",
    "MSPM0G3507", "MSP430F5529",
    "nRF52840", "nRF5340",
    "ESP32S3", "ESP32C3",
    "LPC1768", "MIMXRT1060",
    "CY8CKIT", "XMC4500", "PSOC6",
    "RA4M1",
    "UNKNOWN_CHIP_123",
]

for pn in parts:
    try:
        req = urllib.request.Request(
            f"{BASE}/api/identify-mcu",
            data=json.dumps({"part_number": pn}).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        d = json.loads(resp.read())
        vendor = d.get("vendor_name") or "-"
        family = d.get("family") or "-"
        urls = len(d.get("datasheet_urls", []))
        existing = d.get("existing_board") or ""
        known = d["known"]
        print(f"  {pn:18s} known={known!s:5s}  vendor={vendor:26s} family={family:12s} urls={urls}  existing={existing}")
    except Exception as e:
        print(f"  {pn:18s} ERROR: {e}")
