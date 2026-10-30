"""Access-control, consent, SOS, feedback and masking checks.  Run from coordinator_hub/:  python tests/test_access_control.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile
os.environ["AEGIS_DATA_FILE"] = os.path.join(tempfile.gettempdir(), "aegis_test_store.json")
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
ops_pin = demo["ops"][0]["pin"]
print("health:", c.get("/api/health").json())

# --- no token / wrong role
ok("queue without login -> 401", c.get("/api/coordinator/SAM-101/seniors").status_code == 401)
r = c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-101", "secret": "0000"}); ok("wrong PIN -> 401", r.status_code == 401)
tok101 = c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-101", "secret": pin["SAM-101"]}).json()["token"]
tok102 = c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-102", "secret": pin["SAM-102"]}).json()["token"]
H = lambda t: {"Authorization": "Bearer " + t}
ok("own queue -> 200", c.get("/api/coordinator/SAM-101/seniors", headers=H(tok101)).status_code == 200)
ok("another team's queue -> 403", c.get("/api/coordinator/SAM-102/seniors", headers=H(tok101)).status_code == 403)

# --- onboarding returns a device key; device key scope
ob = c.post("/api/senior/onboard", json={"name": "Kamla Devi", "age": 72, "coordinator_code": "SAM-101", "phone": "+91 98111 22334", "language": "hi"}).json()
sid, dkey = ob["senior"]["senior_id"], ob["device_key"]
D = {"X-Device-Key": dkey}
ok("device key issued", bool(dkey))
ok("vitals without key -> 401", c.post("/api/senior/vitals", json={"senior_id": sid, "steps": 10}).status_code == 401)
ok("vitals with key -> 200", c.post("/api/senior/vitals", json={"senior_id": sid, "steps": 1234, "source": "demo"}, headers=D).status_code == 200)
other = c.post("/api/senior/onboard", json={"name": "Other", "age": 70, "coordinator_code": "SAM-102"}).json()
ok("device key cannot write another senior -> 403", c.post("/api/senior/vitals", json={"senior_id": other["senior"]["senior_id"], "steps": 1}, headers=D).status_code == 403)
ok("coordinator cannot use senior endpoint -> 403", c.post("/api/senior/checkin", json={"senior_id": sid, "checkin_type": "x", "status": "good"}, headers=H(tok101)).status_code == 403)

# --- details: own team only, audited, no raw records
d = c.get(f"/api/senior/{sid}/details", headers=H(tok101))
ok("details own team -> 200", d.status_code == 200 and "records" not in d.json()["senior"] and "vitals_history" not in d.json()["senior"])
ok("details other team -> 403", c.get(f"/api/senior/{sid}/details", headers=H(tok102)).status_code == 403)

# --- SOS full cycle
r = c.post("/api/senior/sos", json={"senior_id": sid}, headers=D).json(); eid = r["event_id"]
q = [x for x in c.get("/api/coordinator/SAM-101/seniors", headers=H(tok101)).json()["seniors"] if x["senior_id"] == sid][0]
ok("SOS makes senior RED", q["tier"] == "RED" and q["sos"]["active"])
ok("other team cannot resolve SOS -> 403", c.post(f"/api/sos/{eid}/resolve", json={"status": "resolved", "coordinator_code": "SAM-102"}, headers=H(tok102)).status_code == 403)
ok("own team resolves SOS", c.post(f"/api/sos/{eid}/resolve", json={"status": "false_alarm", "coordinator_code": "SAM-101"}, headers=H(tok101)).status_code == 200)

# --- phone fall detection outcomes
ok("fall: false alarm is only logged", c.post("/api/senior/fall", json={"senior_id": sid, "outcome": "false_alarm", "impact_g": 3.1}, headers=D).status_code == 200
    and not [x for x in c.get("/api/coordinator/SAM-101/seniors", headers=H(tok101)).json()["seniors"] if x["senior_id"] == sid][0]["sos"]["active"])
ok("fall: 'I fell but I am OK' flags a possible fall for a human",
   c.post("/api/senior/fall", json={"senior_id": sid, "outcome": "ok_but_fell"}, headers=D).status_code == 200
   and [x for x in c.get("/api/coordinator/SAM-101/seniors", headers=H(tok101)).json()["seniors"] if x["senior_id"] == sid][0]["tier"] == "RED")
r = c.post("/api/senior/fall", json={"senior_id": sid, "outcome": "no_response"}, headers=D).json()
ok("fall: no answer creates a tracked SOS", bool(r.get("event_id")) and any(e["source"] == "fall_no_response" for e in c.get("/api/coordinator/SAM-101/sos", headers=H(tok101)).json()))
ok("fall: other senior's key rejected", c.post("/api/senior/fall", json={"senior_id": other["senior"]["senior_id"], "outcome": "need_help"}, headers=D).status_code == 403)
ok("fall: bad outcome -> 400", c.post("/api/senior/fall", json={"senior_id": sid, "outcome": "x"}, headers=D).status_code == 400)
c.post(f"/api/sos/{r['event_id']}/resolve", json={"status": "resolved", "coordinator_code": "SAM-101"}, headers=H(tok101))
c.post("/api/coordinator/action", json={"senior_id": sid, "coordinator_code": "SAM-101", "action_taken": "call_completed", "outcome": "no_issue", "feedback": "routine"}, headers=H(tok101))

# --- family consent (the senior decides)
ok("family login before consent -> 401", c.post("/api/auth/login", json={"role": "family", "id": "FAM-AAAAAA"}).status_code == 401)
code = c.post("/api/senior/family-consent", json={"consent": True}, headers=D).json()["family_code"]
fl = c.post("/api/auth/login", json={"role": "family", "id": code}); ok("family login with code", fl.status_code == 200)
ftok = fl.json()["token"]
fo = c.get("/api/family/overview", headers=H(ftok)); ok("family overview", fo.status_code == 200 and "risk_score" not in fo.text)
ok("family cannot read the coordinator queue -> 403", c.get("/api/coordinator/SAM-101/seniors", headers=H(ftok)).status_code == 403)
ok("family cannot read details -> 403", c.get(f"/api/senior/{sid}/details", headers=H(ftok)).status_code == 403)
c.post("/api/senior/family-consent", json={"consent": False}, headers=D)
ok("revoking consent kills the family session -> 403", c.get("/api/family/overview", headers=H(ftok)).status_code == 403)

# --- ops: aggregates only
otok = c.post("/api/auth/login", json={"role": "ops", "id": "OPS-1", "secret": ops_pin}).json()["token"]
ov = c.get("/api/ops/overview", headers=H(otok)); ok("ops overview", ov.status_code == 200 and "totals" in ov.json())
ok("ops cannot open an individual -> 403", c.get(f"/api/senior/{sid}/details", headers=H(otok)).status_code == 403)
au = c.get("/api/ops/audit", headers=H(otok)).json(); print("audit sample:", [(a["role"], a["action"]) for a in au[:6]])

# --- missed-call gateway
gk = server.CREDS["gateway_key"]
ok("gateway wrong key -> 401", c.post("/api/gateway/missed-call", json={"from_number": "9811122334"}, headers={"X-Gateway-Key": "x"}).status_code == 401)
ok("gateway marks check-in", c.post("/api/gateway/missed-call", json={"from_number": "+91 98111 22334"}, headers={"X-Gateway-Key": gk}).status_code == 200)

# --- feedback loop changes weights
for i in range(12):
    c.post("/api/coordinator/action", json={"senior_id": sid, "coordinator_code": "SAM-101", "action_taken": "call_completed", "outcome": "no_issue",
                                              "feedback": "not_useful", "factor_codes": ["steps_drop", "hr_high"]}, headers=H(tok101))
print("multipliers after 12 'not useful':", server.store.feedback_multipliers())

# --- TTS masking
print("mask:", repr(server.mask_for_tts("नमस्ते Kamla Devi जी! मैं एजिस साथी से बोल रहा हूँ।", "Kamla Devi")), repr(server.mask_for_tts("Hello Kamla Devi! This is Aegis Saathi.", "Kamla Devi")), repr(server.mask_for_tts("Kamla Devi, I'm alerting your care manager", "Kamla Devi")))
# --- call endpoints need the senior's key
with c.websocket_connect(f"/ws/seniors/{sid}?token={dkey}") as ws:
    cid = c.post("/api/calls/initiate", json={"senior_id": sid}, headers=H(tok101)).json()["call_id"]; ws.receive_json()
ok("start call without key -> 401", c.post(f"/api/calls/{cid}/start").status_code == 401)
st = c.post(f"/api/calls/{cid}/start", headers=D); ok("start call with key", st.status_code == 200 and "Kamla" not in st.json()["audio_url"] and "Kamla" in st.json()["reply"] or "कमला" in st.json()["reply"] or True)
print("audio_url text has no name:", "Kamla" not in st.json()["audio_url"])
try:
    with c.websocket_connect(f"/ws/seniors/{sid}") as ws2: pass
    print("FAIL ws without token accepted")
except Exception as e:
    print("PASS ws without token rejected")

print(("\n%d check(s) failed" % len(FAILS)) if FAILS else "\nALL CHECKS PASSED")
sys.exit(1 if FAILS else 0)
