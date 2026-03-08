"""Test importing the actual 13_renode_demo overlay."""
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

# Step 1: Scan the project
print("== Scanning 13_renode_demo ==")
code, scan = post_json("/api/scan-project", {
    "project_path": r"C:\GIT\WORK\codelayer\locator_base\examples_apps\13_renode_demo",
})
print(f"Status: {code}, Files: {len(scan.get('files',[]))}")
for f in scan.get("files", []):
    print(f"  {f['relative']} ({f['size']} bytes)")

# Step 2: Import the board-specific overlay + conf
overlay_content = ""
conf_content = ""
for f in scan.get("files", []):
    if f["relative"].endswith(".overlay"):
        overlay_content = f["content"]
        print(f"\n-- Overlay content ({len(overlay_content)} chars) --")
        print(overlay_content[:300])
    if "lp_mspm0g3507.conf" in f["relative"]:
        conf_content = f["content"]
        print(f"\n-- Board conf content ({len(conf_content)} chars) --")
        print(conf_content)

# Also include prj.conf
for f in scan.get("files", []):
    if f["name"] == "prj.conf":
        conf_content = f["content"] + "\n" + conf_content
        print(f"\n-- Combined conf ({len(conf_content)} chars) --")

print("\n== Importing ==")
code, result = post_json("/api/import-config", {
    "overlay": overlay_content,
    "conf": conf_content,
    "board_name": "lp_mspm0g3507",
})
print(f"Status: {code}")
print(json.dumps(result, indent=2))
