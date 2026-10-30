"""Medicine schedules, dose answers and family contacts.  Run from coordinator_hub/:  python tests/test_medicines.py"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile
os.environ["AEGIS_DATA_FILE"] = os.path.join(tempfile.gettempdir(), "aegis_test_meds.json")
if os.path.exists(os.environ["AEGIS_DATA_FILE"]): os.remove(os.environ["AEGIS_DATA_FILE"])
os.environ["SARVAM_API_KEY"] = ""   # never place real Sarvam calls from tests, whatever .env holds
os.environ.update({f"SARVAM_API_KEY_{i}": "" for i in range(2, 11)})
from fastapi.testclient import TestClient
import server
c = TestClient(server.app)
FAILS = []
def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: FAILS.append(name)

demo = c.get("/api/auth/demo").json()
pin = {x["code"]: x["pin"] for x in demo["coordinators"]}
H = lambda t: {"Authorization": "Bearer " + t}
tok = c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-101", "secret": pin["SAM-101"]}).json()["token"]
tok2 = c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-102", "secret": pin["SAM-102"]}).json()["token"]
ob = c.post("/api/senior/onboard", json={"name": "Kamla Devi", "age": 72, "coordinator_code": "SAM-101", "phone": "+91 98111 22334", "language": "hi"}).json()
sid, D = ob["senior"]["senior_id"], {"X-Device-Key": ob["device_key"]}

# --- medicines: the care manager sets them, other teams and the phone cannot
ok("add medicine without a time -> 400", c.post(f"/api/seniors/{sid}/medicines", json={"name": "Amlodipine", "times": []}, headers=H(tok)).status_code == 400)
ok("other team cannot add -> 403", c.post(f"/api/seniors/{sid}/medicines", json={"name": "X", "times": ["08:00"]}, headers=H(tok2)).status_code == 403)
ok("phone cannot add -> 403", c.post(f"/api/seniors/{sid}/medicines", json={"name": "X", "times": ["08:00"]}, headers=D).status_code == 403)
past = time.strftime("%H:%M", time.localtime(time.time() - 40 * 60))   # missed (30 min) but still today
soon = time.strftime("%H:%M", time.localtime(time.time() + 60))
m = c.post(f"/api/seniors/{sid}/medicines", json={"name": "Amlodipine", "dose_text": "5 mg, one tablet", "times": [soon, "8:0"]}, headers=H(tok)).json()["medicine"]
ok("times normalised and sorted", m["times"] == sorted([soon, "08:00"]))
# make it look added yesterday so the earlier dose today counts
server.store.medicines[sid][0]["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 86400))
server.store.medicines[sid][0]["times"] = sorted([past, soon])
mid = m["id"]

# --- the phone's view
r = c.get(f"/api/senior/medicines?senior_id={sid}", headers=D)
ok("phone reads its medicines", r.status_code == 200 and r.json()["medicines"][0]["name"] == "Amlodipine")
today = r.json()["today"]
# in the first 45 minutes after midnight "40 minutes ago" is yesterday, so these two orderings cannot be checked
EARLY = time.localtime().tm_hour == 0 and time.localtime().tm_min < 45
if EARLY: print("SKIP order checks (just after midnight)")
else: ok("today: earlier dose missed, later one due", [d["status"] for d in today] == ["missed", "due"])
ok("week has 7 days", len(r.json()["week"]) == 7)
ok("hub sends its clock", abs(r.json()["server_time"] - time.time()) < 5)
ok("phone cannot read another senior -> 403", c.get("/api/senior/medicines?senior_id=SR-1001", headers=D).status_code == 403)

ok("dose taken", c.post("/api/senior/medicines/dose", json={"senior_id": sid, "med_id": mid, "time": soon, "status": "taken"}, headers=D).status_code == 200)
ok("late answer for the missed dose", c.post("/api/senior/medicines/dose", json={"senior_id": sid, "med_id": mid, "time": past, "status": "skipped"}, headers=D).status_code == 200)
ok("unknown dose -> 404", c.post("/api/senior/medicines/dose", json={"senior_id": sid, "med_id": "nope", "time": soon, "status": "taken"}, headers=D).status_code == 404)
today = c.get(f"/api/senior/medicines?senior_id={sid}", headers=D).json()["today"]
if not EARLY: ok("today now skipped + taken", [d["status"] for d in today] == ["skipped", "taken"])

det = c.get(f"/api/senior/{sid}/details", headers=H(tok)).json()
med = det["medicines"]
ok("details carry 14 days of doses", len(med["dates"]) == 14 and len(med["medicines"][0]["days"]) == 14)
ok("adherence counts answered/missed doses", med["adherence_pct"] is not None)

ok("remove medicine", c.delete(f"/api/seniors/{sid}/medicines/{mid}", headers=H(tok)).status_code == 200)
ok("removed medicine is gone from the phone", c.get(f"/api/senior/medicines?senior_id={sid}", headers=D).json()["medicines"] == [])

# --- contacts
cl = c.get(f"/api/senior/contacts?senior_id={sid}", headers=D).json()
ok("care manager is listed with a phone", bool(cl["care_manager"]["name"]) and bool(cl["care_manager"]["phone"]))
ok("contact needs a phone -> 400", c.post(f"/api/seniors/{sid}/contacts", json={"name": "Rahul", "phone": "12"}, headers=H(tok)).status_code == 400)
ct = c.post(f"/api/seniors/{sid}/contacts", json={"name": "Rahul", "relation": "Son", "phone": "+91 98100 00001", "is_emergency": True}, headers=H(tok)).json()["contact"]
ok("contact saved", ct["name"] == "Rahul" and ct["is_emergency"])
ok("other team cannot add contacts -> 403", c.post(f"/api/seniors/{sid}/contacts", json={"name": "X", "phone": "9999999999"}, headers=H(tok2)).status_code == 403)
cl = c.get(f"/api/senior/contacts?senior_id={sid}", headers=D).json()["contacts"]
ok("phone sees the contact", [x["name"] for x in cl] == ["Rahul"])
ok("delete contact", c.delete(f"/api/seniors/{sid}/contacts/{ct['id']}", headers=H(tok)).status_code == 200)

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
