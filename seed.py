"""
WasteIQ Test Data Seeder
Usage: python seed.py [API_URL]
Default API: http://localhost:8000
Example: python seed.py https://wasteiq-rho.vercel.app
"""
import sys
import json
import urllib.request
import urllib.error

API_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

# ── helpers ──────────────────────────────────────────────────────────────────

def post(path, body, token=None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  ERROR {e.code} on {path}: {e.read().decode()}")
        return None

def post_form(path, body):
    import urllib.parse
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        f"{API_URL}{path}", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  ERROR {e.code} on {path}: {e.read().decode()}")
        return None

def ok(label, result):
    if result:
        print(f"  [OK] {label}")
    return result

# ── 1. Register test account ──────────────────────────────────────────────────

print(f"\nSeeding WasteIQ at {API_URL}\n")
print("1. Creating test account...")

reg = post("/auth/register", {
    "email": "demo@wasteiq.com",
    "password": "Demo1234!",
    "full_name": "Demo User",
    "company_name": "BuildRight Construction"
})

if not reg:
    print("  Account may already exist — trying login...")
    reg = post_form("/auth/login", {"username": "demo@wasteiq.com", "password": "Demo1234!"})

if not reg:
    print("  Could not authenticate. Check API URL and try again.")
    sys.exit(1)

token = reg["access_token"]
ok("Logged in as demo@wasteiq.com (company: BuildRight Construction)", token)

# ── 2. Create crew profiles ───────────────────────────────────────────────────

print("\n2. Creating crew profiles...")

crew_a = post("/projects/crews/", {"name": "Alpha Crew", "size": 12, "avg_experience_years": 8}, token)
ok("Alpha Crew — 12 workers, 8 yrs avg experience", crew_a)

crew_b = post("/projects/crews/", {"name": "Beta Crew", "size": 6, "avg_experience_years": 2}, token)
ok("Beta Crew — 6 workers, 2 yrs avg experience (junior)", crew_b)

crew_c = post("/projects/crews/", {"name": "Senior Squad", "size": 8, "avg_experience_years": 15}, token)
ok("Senior Squad — 8 workers, 15 yrs avg experience", crew_c)

# ── 3. Project 1 — Residential House ─────────────────────────────────────────

print("\n3. Creating Project 1: Residential House (Chennai)...")

p1 = post("/projects/", {
    "name": "Greenfield Villa — Block A",
    "type": "residential",
    "location": "Chennai, India",
    "area_sqm": 320,
    "start_date": "2026-04-01T00:00:00",
    "phases": [
        {"phase_name": "foundation", "planned_start": "2026-04-01T00:00:00", "planned_end": "2026-04-30T00:00:00"},
        {"phase_name": "framing",    "planned_start": "2026-05-01T00:00:00", "planned_end": "2026-06-15T00:00:00"},
        {"phase_name": "finishing",  "planned_start": "2026-06-16T00:00:00", "planned_end": "2026-08-01T00:00:00"},
    ],
    "materials": [
        {
            "material_type": "concrete",
            "estimated_quantity": 85,
            "unit": "m3",
            "unit_price": 120,
            "phase_name": "foundation",
            "crew_profile_id": crew_a["id"] if crew_a else None
        },
        {
            "material_type": "steel_rebar",
            "estimated_quantity": 4200,
            "unit": "kg",
            "unit_price": 0.85,
            "phase_name": "foundation",
            "crew_profile_id": crew_a["id"] if crew_a else None
        },
        {
            "material_type": "lumber",
            "estimated_quantity": 180,
            "unit": "m3",
            "unit_price": 650,
            "phase_name": "framing",
            "crew_profile_id": crew_b["id"] if crew_b else None
        },
        {
            "material_type": "drywall",
            "estimated_quantity": 420,
            "unit": "sheets",
            "unit_price": 18,
            "phase_name": "finishing",
            "crew_profile_id": crew_b["id"] if crew_b else None
        },
        {
            "material_type": "tiles",
            "estimated_quantity": 680,
            "unit": "sqm",
            "unit_price": 35,
            "phase_name": "finishing",
            "crew_profile_id": crew_c["id"] if crew_c else None
        },
    ]
}, token)
ok(f"Project created (id: {p1['id'][:8]}...)", p1)

# Generate predictions
pred1 = post("/predictions/generate", {"project_id": p1["id"]}, token)
ok(f"Predictions generated ({len(pred1)} materials)", pred1)

# Record actuals for foundation phase (project is partially complete)
if p1 and p1["materials"]:
    mat_map = {m["material_type"]: m["id"] for m in p1["materials"]}
    print("  Recording actuals for foundation phase...")

    post("/actuals/", {
        "material_line_item_id": mat_map["concrete"],
        "actual_waste_qty": 7.2,
        "notes": "Formwork spill + over-pour on column footings"
    }, token)
    ok("Concrete actual: 7.2 m3 wasted", True)

    post("/actuals/", {
        "material_line_item_id": mat_map["steel_rebar"],
        "actual_waste_qty": 310,
        "notes": "Off-cuts from column ties"
    }, token)
    ok("Steel rebar actual: 310 kg wasted", True)

# ── 4. Project 2 — Commercial Office ─────────────────────────────────────────

print("\n4. Creating Project 2: Commercial Office (Mumbai)...")

p2 = post("/projects/", {
    "name": "TechPark Tower — Floor 3-8 Fitout",
    "type": "commercial",
    "location": "Mumbai, India",
    "area_sqm": 2800,
    "start_date": "2026-03-15T00:00:00",
    "phases": [
        {"phase_name": "mep",        "planned_start": "2026-03-15T00:00:00", "planned_end": "2026-05-01T00:00:00"},
        {"phase_name": "finishing",  "planned_start": "2026-05-01T00:00:00", "planned_end": "2026-07-15T00:00:00"},
    ],
    "materials": [
        {
            "material_type": "pipe",
            "estimated_quantity": 1800,
            "unit": "m",
            "unit_price": 12,
            "phase_name": "mep",
            "crew_profile_id": crew_c["id"] if crew_c else None
        },
        {
            "material_type": "drywall",
            "estimated_quantity": 1200,
            "unit": "sheets",
            "unit_price": 18,
            "phase_name": "finishing",
            "crew_profile_id": crew_b["id"] if crew_b else None
        },
        {
            "material_type": "tiles",
            "estimated_quantity": 2100,
            "unit": "sqm",
            "unit_price": 42,
            "phase_name": "finishing",
            "crew_profile_id": crew_b["id"] if crew_b else None
        },
        {
            "material_type": "glass",
            "estimated_quantity": 380,
            "unit": "sqm",
            "unit_price": 180,
            "phase_name": "finishing",
            "crew_profile_id": crew_c["id"] if crew_c else None
        },
        {
            "material_type": "insulation",
            "estimated_quantity": 950,
            "unit": "sqm",
            "unit_price": 22,
            "phase_name": "mep",
            "crew_profile_id": crew_a["id"] if crew_a else None
        },
    ]
}, token)
ok(f"Project created (id: {p2['id'][:8]}...)", p2)

pred2 = post("/predictions/generate", {"project_id": p2["id"]}, token)
ok(f"Predictions generated ({len(pred2)} materials)", pred2)

# ── 5. Project 3 — Infrastructure ────────────────────────────────────────────

print("\n5. Creating Project 3: Road Infrastructure (Delhi)...")

p3 = post("/projects/", {
    "name": "NH-48 Service Road — Section 4B",
    "type": "infrastructure",
    "location": "Delhi, India",
    "area_sqm": 12000,
    "start_date": "2026-02-01T00:00:00",
    "phases": [
        {"phase_name": "foundation", "planned_start": "2026-02-01T00:00:00", "planned_end": "2026-03-15T00:00:00"},
        {"phase_name": "framing",    "planned_start": "2026-03-15T00:00:00", "planned_end": "2026-05-01T00:00:00"},
    ],
    "materials": [
        {
            "material_type": "concrete",
            "estimated_quantity": 1850,
            "unit": "m3",
            "unit_price": 110,
            "phase_name": "foundation",
            "crew_profile_id": crew_a["id"] if crew_a else None
        },
        {
            "material_type": "steel_rebar",
            "estimated_quantity": 28000,
            "unit": "kg",
            "unit_price": 0.82,
            "phase_name": "foundation",
            "crew_profile_id": crew_a["id"] if crew_a else None
        },
        {
            "material_type": "brick",
            "estimated_quantity": 45000,
            "unit": "pcs",
            "unit_price": 0.45,
            "phase_name": "framing",
            "crew_profile_id": crew_c["id"] if crew_c else None
        },
    ]
}, token)
ok(f"Project created (id: {p3['id'][:8]}...)", p3)

pred3 = post("/predictions/generate", {"project_id": p3["id"]}, token)
ok(f"Predictions generated ({len(pred3)} materials)", pred3)

# Record full actuals for infrastructure project (completed)
if p3 and p3["materials"]:
    mat_map3 = {m["material_type"]: m["id"] for m in p3["materials"]}
    print("  Recording actuals (project completed)...")

    post("/actuals/", {"material_line_item_id": mat_map3["concrete"],   "actual_waste_qty": 98,   "notes": "Weather delay caused partial set waste"}, token)
    post("/actuals/", {"material_line_item_id": mat_map3["steel_rebar"],"actual_waste_qty": 1540, "notes": "Off-cuts from pier reinforcement"}, token)
    post("/actuals/", {"material_line_item_id": mat_map3["brick"],      "actual_waste_qty": 2100, "notes": "Breakage during delivery + cutting"}, token)
    ok("All actuals recorded", True)

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"""
Done! Test data created successfully.

Login credentials:
  Email:    demo@wasteiq.com
  Password: Demo1234!

Projects seeded:
  1. Greenfield Villa (Residential, Chennai) — predictions + 2 actuals
  2. TechPark Tower (Commercial, Mumbai)     — predictions only
  3. NH-48 Service Road (Infrastructure, Delhi) — predictions + 3 actuals

Open the app and log in to explore the predictions dashboard.
""")
