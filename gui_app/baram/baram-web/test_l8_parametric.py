"""
L8 Parametric Study — Comprehensive API Test Suite
Tests all endpoints for parametric studies, input/output variables,
design points, compare definitions, and legacy variants.
Aligned with actual server routes and dataclass field names.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from server import app

client = app.test_client()

def j(resp):
    return resp.get_json(silent=True) or {}

passed = 0
failed = 0

def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}  {detail}")


print("\n" + "=" * 70)
print("  L8 PARAMETRIC STUDY — API TEST SUITE")
print("=" * 70)

# ── 1. List (empty initially) ───────────────────────────────────
print("\n── List Studies (empty) ───")
r = client.get("/api/floefd/parametric")
d = j(r)
initial_count = len(d) if isinstance(d, list) else 0
check("GET list 200", r.status_code == 200)

# ── 2. Create studies ───────────────────────────────────────────
print("\n── Create Studies ───")
r1 = client.post("/api/floefd/parametric", json={"name": "What-If A", "study_type": "what_if"})
d1 = j(r1)
check("create what_if 200", r1.status_code == 200)
check("has id", "id" in d1)
sid = d1.get("id", "")
check("study_type = what_if", d1.get("study_type") == "what_if")

r2 = client.post("/api/floefd/parametric", json={"name": "Goal Opt B", "study_type": "goal_optimization"})
d2 = j(r2)
check("create goal_opt 200", r2.status_code == 200)
sid2 = d2.get("id", "")
check("study_type = goal_optimization", d2.get("study_type") == "goal_optimization")

# ── 3. List studies ─────────────────────────────────────────────
print("\n── List Studies ───")
r = client.get("/api/floefd/parametric")
d = j(r)
check("GET list 200", r.status_code == 200)
check("2 more studies", len(d) == initial_count + 2)

# ── 4. Get single study ────────────────────────────────────────
print("\n── Get / Update / Delete Study ───")
r = client.get(f"/api/floefd/parametric/{sid}")
d = j(r)
check("GET single 200", r.status_code == 200)
check("name match", d.get("name") == "What-If A")
check("study_type match", d.get("study_type") == "what_if")

# ── 5. Update study ────────────────────────────────────────────
r = client.put(f"/api/floefd/parametric/{sid}", json={
    "name": "What-If A (updated)",
    "run_on_network": True,
    "excel_output": True,
    "compare_active_scene": True,
})
d = j(r)
check("PUT update 200", r.status_code == 200)
check("name updated", d.get("name") == "What-If A (updated)")
check("run_on_network True", d.get("run_on_network") == True)

# ── 6. Input Variables ─────────────────────────────────────────
print("\n── Input Variables ───")
r = client.post(f"/api/floefd/parametric/{sid}/input-variables", json={
    "name": "inlet_velocity",
    "source": "simulation",
    "category": "boundary_conditions",
    "property_name": "velocity",
    "variation_type": "discrete_values",
    "discrete_values": [1, 3, 5, 7, 10],
    "unit": "m/s",
    "current_value": 5,
})
d = j(r)
check("add IV 200", r.status_code == 200)
check("IV has id", "id" in d)
iv_id = d.get("id", "")
check("IV name", d.get("name") == "inlet_velocity")
check("IV discrete_values", d.get("discrete_values") == [1, 3, 5, 7, 10])
check("IV variation_type", d.get("variation_type") == "discrete_values")
check("IV computed_values", d.get("computed_values") == [1, 3, 5, 7, 10])

# add a second input variable (range_with_number)
r = client.post(f"/api/floefd/parametric/{sid}/input-variables", json={
    "name": "fan_power",
    "source": "simulation",
    "category": "features",
    "variation_type": "range_with_number",
    "range_min": 10,
    "range_max": 50,
    "range_number": 3,
    "unit": "W",
    "current_value": 30,
})
d = j(r)
check("add IV (range) 200", r.status_code == 200)
iv2_id = d.get("id", "")
check("IV2 computed_values", d.get("computed_values") == [10, 30, 50])

# verify study has 2 input vars
r = client.get(f"/api/floefd/parametric/{sid}")
d = j(r)
check("study has 2 IVs", len(d.get("input_variables", [])) == 2)

# remove second input variable
r = client.delete(f"/api/floefd/parametric/{sid}/input-variables/{iv2_id}")
d = j(r)
check("remove IV 200", r.status_code == 200)
check("remove IV success", d.get("success") == True)

# verify 1 left
r = client.get(f"/api/floefd/parametric/{sid}")
d = j(r)
check("study has 1 IV", len(d.get("input_variables", [])) == 1)

# ── 7. Output Variables ────────────────────────────────────────
print("\n── Output Variables ───")
r = client.post(f"/api/floefd/parametric/{sid}/output-variables", json={
    "name": "Max Temperature",
    "goal_id": "gg_max_temp_1",
    "use_for_optimization": True,
    "target_value": 350,
    "tolerance": 5,
})
d = j(r)
check("add OV 200", r.status_code == 200)
check("OV name", d.get("name") == "Max Temperature")
ov_id = d.get("id", "")

r = client.post(f"/api/floefd/parametric/{sid}/output-variables", json={
    "name": "Pressure Drop",
    "goal_id": "sg_pressure_drop_1",
})
d = j(r)
check("add OV2 200", r.status_code == 200)
ov2_id = d.get("id", "")

r = client.delete(f"/api/floefd/parametric/{sid}/output-variables/{ov2_id}")
d = j(r)
check("remove OV 200", r.status_code == 200)

# verify 1 OV
r = client.get(f"/api/floefd/parametric/{sid}")
d = j(r)
check("study has 1 OV", len(d.get("output_variables", [])) == 1)

# ── 8. Generate Design Points ──────────────────────────────────
print("\n── Generate Design Points ───")
r = client.post(f"/api/floefd/parametric/{sid}/generate-design-points", json={})
d = j(r)
check("generate DPs 200", r.status_code == 200)
check("is list", isinstance(d, list))
check("5 DPs (from 5 discrete values)", len(d) == 5, f"got {len(d)}")
if len(d) > 0:
    dp0 = d[0]
    check("first DP has status", "status" in dp0)
    check("first DP has input_values", len(dp0.get("input_values", {})) > 0)
    dp0_id = dp0.get("id", "")
else:
    dp0_id = ""
    check("first DP exists", False, "no DPs generated")

# ── 9. Run single design point ─────────────────────────────────
print("\n── Run Design Points ───")
if dp0_id:
    r = client.post(f"/api/floefd/parametric/{sid}/run/{dp0_id}", json={})
    d = j(r)
    check("run single DP 200", r.status_code == 200)
    check("DP has status", "status" in d)
    check("DP has output_results", isinstance(d.get("output_results"), dict))
else:
    check("run single DP (skipped)", False, "no dp0_id")

# ── 10. Run all design points ──────────────────────────────────
print("\n── Run All DPs ───")
r = client.post(f"/api/floefd/parametric/{sid}/run", json={})
d = j(r)
check("run-all 200", r.status_code == 200)
check("returns study dict", "design_points" in d)

# ── 11. Compare Definitions ────────────────────────────────────
print("\n── Compare Definitions ───")
r = client.post("/api/floefd/compare", json={
    "name": "Scene Compare",
    "compare_active_scene": True,
})
d = j(r)
check("create compare 200", r.status_code == 200)
check("compare has id", "id" in d)
cmp_id = d.get("id", "")
check("compare name", d.get("name") == "Scene Compare")

r = client.post("/api/floefd/compare", json={
    "name": "Goal Compare",
    "compare_goal_plots": ["Max Temperature"],
})
d = j(r)
check("create compare2 200", r.status_code == 200)
cmp2_id = d.get("id", "")

# list compare
r = client.get("/api/floefd/compare")
d = j(r)
check("list compares 200", r.status_code == 200)
check("at least 2 compares", len(d) >= 2)

# update compare
r = client.put(f"/api/floefd/compare/{cmp_id}", json={"side_by_side": False})
d = j(r)
check("update compare 200", r.status_code == 200)
check("side_by_side False", d.get("side_by_side") == False)

# delete compare
r = client.delete(f"/api/floefd/compare/{cmp2_id}")
d = j(r)
check("delete compare 200", r.status_code == 200)
check("delete compare success", d.get("success") == True)

# ── 12. Legacy Variant Support ─────────────────────────────────
print("\n── Legacy Variant Support ───")
r = client.post(f"/api/floefd/parametric/{sid}/variant", json={
    "name": "Legacy V1",
    "parameters": {"inlet_velocity": 99},
})
d = j(r)
check("add variant 200", r.status_code == 200)
check("variant name", d.get("name") == "Legacy V1")
variant_id = d.get("id", "")

r = client.post(f"/api/floefd/parametric/{sid}/clone", json={
    "variant_id": variant_id,
    "name": "Clone V1",
})
d = j(r)
check("clone variant 200", r.status_code == 200)
check("clone name", d.get("name") == "Clone V1")

# ── 13. Delete study ───────────────────────────────────────────
print("\n── Delete Study ───")
r = client.delete(f"/api/floefd/parametric/{sid2}")
d = j(r)
check("delete study 200", r.status_code == 200)
check("delete study success", d.get("success") == True)

r = client.get("/api/floefd/parametric")
d = j(r)
check("one fewer study", len(d) == initial_count + 1)

# ── 14. Error cases ────────────────────────────────────────────
print("\n── Error Cases ───")
r = client.get("/api/floefd/parametric/nonexistent-id")
check("get missing study 404", r.status_code == 404)

r = client.delete("/api/floefd/parametric/nonexistent-id")
check("delete missing study 404", r.status_code == 404)

r = client.post(f"/api/floefd/parametric/{sid}/input-variables", json={})
check("add IV no name still 200", r.status_code == 200)

r = client.delete(f"/api/floefd/parametric/{sid}/input-variables/fake-id")
check("delete missing IV 404", r.status_code == 404)

r = client.delete(f"/api/floefd/parametric/{sid}/output-variables/fake-id")
check("delete missing OV 404", r.status_code == 404)


# ── REPORT ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"  RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    print("  🎉 ALL TESTS PASSED!")
    sys.exit(0)
