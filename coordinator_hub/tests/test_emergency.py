"""Emergencies: "I am dying" and other danger words -> SOS for the care manager -> Saathi's alert agent phones the
family, one contact after another, and the phone shows "Help is coming". Sarvam is simulated (a fake client that
records the calls it would place); the webhook handling, ordering, retries and safeguards are the real ones.
Run from coordinator_hub/:  python tests/test_emergency.py"""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T = tempfile.gettempdir()
for k, f in (("AEGIS_DATA_FILE", "aegis_emg_store.json"), ("AEGIS_BILLING_FILE", "aegis_emg_bill.json"), ("AEGIS_AUTH_FILE", "aegis_emg_auth.json")):
    os.environ[k] = os.path.join(T, f)
    if os.path.exists(os.environ[k]): os.remove(os.environ[k])
for k in ("SARVAM_CHECKIN_APP_ID", "SARVAM_CHECKIN_APP_VERSION", "SARVAM_ALERT_APP_ID", "SARVAM_ALERT_APP_VERSION",
          "SARVAM_CONNECTION_ID", "SARVAM_AGENT_PHONE", *[f"SARVAM_API_KEY_{i}" for i in range(2, 11)]):
    os.environ[k] = ""          # empty, not removed: removed keys would be refilled from the real .env
os.environ.update({"SARVAM_API_KEY": "fake-key", "SARVAM_ORG_ID": "org", "SARVAM_WORKSPACE_ID": "ws",
                   "AEGIS_PUBLIC_URL": "https://hub.example.test", "AEGIS_LLM": "off",
                   "AEGIS_CALL_ENGINE": "local"})   # calls stay in the app here; tests/test_phone_calls.py covers phone calls
from fastapi.testclient import TestClient
import server
from engine import emergency as E
from ai_agent.voice_agent import is_danger, is_emergency
c = TestClient(server.app)
FAILS = []
def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: FAILS.append(name)

def wait(cond, s=3.0):
    end = time.time() + s
    while time.time() < end:
        if cond(): return True
        time.sleep(0.05)
    return cond()

# ------------------------------------------------------------------ words
for t in ["I am dying", "I think I'm dying", "main mar raha hoon", "mujhe lag raha hai mar jaungi", "मैं मर रहा हूँ",
          "मुझे लगता है मैं मर रही हूँ", "dil ka daura pad raha hai", "saans nahi aa rahi", "chest pain", "I fell down"]:
    ok(f"danger: {t!r}", is_danger(t))
for t in ["I'm dying to see my grandson", "dying for a cup of chai", "bore hoke mar raha hoon", "hans hans ke mar gaye",
          "I feel fine today", "I want to talk to a person"]:
    ok(f"not a family alert: {t!r}", not is_danger(t))
ok("asking for a person still escalates to the care manager", is_emergency("I want to talk to a person"))

# ------------------------------------------------------------------ a senior with two emergency contacts
ob = c.post("/api/senior/onboard", json={"name": "Kamla Devi", "age": 74, "city": "Lucknow", "coordinator_code": "SAM-102",
                                         "language": "hi", "gender": "Female", "emergency_contact": "+91 98100 99999"}).json()
sid, D = ob["senior"]["senior_id"], {"X-Device-Key": ob["device_key"]}
pin = {x["code"]: x["pin"] for x in c.get("/api/auth/demo").json()["coordinators"]}
H = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-102", "secret": pin["SAM-102"]}).json()["token"]}
c.post(f"/api/seniors/{sid}/contacts", headers=H, json={"name": "Meera Iyer", "relation": "Daughter", "phone": "98100 12345", "is_emergency": True})
c.post(f"/api/seniors/{sid}/contacts", headers=H, json={"name": "Ravi", "relation": "Son", "phone": "+91 98100 54321", "is_emergency": True})
c.post(f"/api/seniors/{sid}/contacts", headers=H, json={"name": "Neighbour", "relation": "Friend", "phone": "98100 11111", "is_emergency": False})
order = [x["name"] or x["relation"] for x in server.store.emergency_contacts(sid)]
ok("emergency contacts in order, then the onboarding number; non-emergency contacts left out", order == ["Meera Iyer", "Ravi", "Emergency contact"])
server.store.dynamic_seniors[sid]["emergency_contact"] = "+91 98765 43210"
ok("the form's placeholder number is never rung", "Emergency contact" not in [x["relation"] for x in server.store.emergency_contacts(sid)])
server.store.dynamic_seniors[sid]["emergency_contact"] = "+91 98100 99999"

# ------------------------------------------------------------------ fakes
class FakeSarvam:
    def __init__(self): self.calls = []
    def outbound_call(self, phone, variables, language="English", webhook_url="", metadata=None):
        self.calls.append({"phone": phone, "vars": variables, "lang": language, "hook": webhook_url, "meta": metadata})
        return f"att-{len(self.calls)}"
PHONE = []
fake = FakeSarvam()
server.dispatcher.client = fake
server.dispatcher.notify_phone = lambda s, m: PHONE.append(m)
E.RETRY_AFTER_S = 0.3

# ------------------------------------------------------------------ no Sarvam number yet -> the phone dials
r = c.post("/api/senior/sos", headers=D, json={"senior_id": sid})
ok("SOS without a Sarvam number: no AI call, the phone is told to dial", r.status_code == 200 and not r.json()["family_ai_call"]
   and not fake.calls and PHONE and PHONE[-1]["ai_calling"] is False and PHONE[-1]["contact_phone"].endswith("12345"))
ev = server.store.active_sos(sid)
server.store.resolve_sos(ev["id"], "resolved", "SAM-102")

# ------------------------------------------------------------------ with the alert agent and a number
os.environ.update({"SARVAM_ALERT_APP_ID": "alert-app", "SARVAM_ALERT_APP_VERSION": "3",
                   "SARVAM_CONNECTION_ID": "conn-1", "SARVAM_AGENT_PHONE": "+911234567890"})
cid = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()["call_id"]
c.post(f"/api/calls/{cid}/start", headers=D)
t = c.post(f"/api/calls/{cid}/turn", headers=D, json={"text": "mujhe lagta hai main mar rahi hoon"}).json()
ev = server.store.active_sos(sid)
ok("'I am dying' on a call opens an SOS for the care manager", ev is not None and ev["source"] == "call" and "mar rahi" in ev["said"])
ok("the call turn reports the emergency", t["emergency"] is True)
ok("Saathi's alert agent rings the first emergency contact", wait(lambda: len(fake.calls) == 1) and fake.calls[0]["phone"] == "98100 12345")
v = fake.calls[0]["vars"]
ok("the alert says who, what they said, when, and names the care manager", v["senior_name"] == "Kamla Devi" and "mar rahi" in v["what_they_said"]
   and v["care_manager_name"] == "Rajesh Verma" and v["time_text"] and v["her_his"] == "her")
ok("alert in the senior's language, webhook carries the secret", fake.calls[0]["lang"] == "Hindi" and "k=" + server.SARVAM_HOOK_KEY in fake.calls[0]["hook"])
ok("the phone shows 'Saathi is calling Meera'", PHONE[-1]["ai_calling"] is True and PHONE[-1]["contact_name"] == "Meera Iyer")
c.post(f"/api/calls/{cid}/turn", headers=D, json={"text": "main mar rahi hoon, bachao"})
time.sleep(0.2)
ok("saying it again on the same call does not start a second round", len(fake.calls) == 1)

hook = "/api/sarvam/webhook?k=" + server.SARVAM_HOOK_KEY
def report(i, status, **extra):
    call = fake.calls[i]
    return c.post(hook, json={"attempt_id": f"att-{i + 1}", "status": status, "webhook_config": {"url": call["hook"], "metadata": call["meta"]}, **extra})
ok("webhook without the secret is refused", c.post("/api/sarvam/webhook?k=wrong", json={}).status_code == 403)
ok("an unknown attempt is ignored", c.post(hook, json={"attempt_id": "x", "status": "connected", "webhook_config": {"metadata": {"sos_id": ev["id"]}}}).json()["status"] == "ignored")
report(0, "no_answer")
ok("no answer -> the next contact is rung", wait(lambda: len(fake.calls) == 2) and fake.calls[1]["phone"] == "+91 98100 54321")
report(1, "busy")
ok("busy -> the onboarding number is rung", wait(lambda: len(fake.calls) == 3) and fake.calls[2]["phone"] == "+91 98100 99999")
report(2, "failed", failure_reason="exotel: number unreachable")
ok("nobody reached -> one more round after the wait", wait(lambda: len(fake.calls) == 4) and fake.calls[3]["meta"]["round"] == 1)
report(3, "connected", duration=41, interaction_id="20261030/abc", final_agent_variables={"acknowledged": "yes, going now"})
ev = server.store.sos_event(ev["id"])
row = next(r for r in ev["notify_log"] if r["attempt_id"] == "att-4")
ok("answered: logged as told, with what they said", ev["alert_state"] == "told" and row["status"] == "connected" and row["acknowledged"] == "yes, going now")
ok("phone numbers are masked in the log", all("12345" not in (r.get("phone") or "") for r in ev["notify_log"]))
sos = c.get("/api/coordinator/SAM-102/sos", headers=H).json()
ok("the care manager's SOS list carries what was said and the family calls", any(e["id"] == ev["id"] and e["notify_log"] and e["said"] for e in (sos if isinstance(sos, list) else sos.get("events", sos.get("sos", [])))))
time.sleep(0.4)
ok("no more calls after someone answered", len(fake.calls) == 4)
server.store.resolve_sos(ev["id"], "resolved", "SAM-102")

# ------------------------------------------------------------------ SOS button, then "pressed by mistake"
n = len(fake.calls)
r = c.post("/api/senior/sos", headers=D, json={"senior_id": sid, "latitude": 26.85, "longitude": 80.95}).json()
ok("SOS button phones the family too", r["family_ai_call"] and wait(lambda: len(fake.calls) == n + 1))
c.post("/api/senior/sos", headers=D, json={"senior_id": sid, "latitude": 26.85, "longitude": 80.95})
time.sleep(0.1)
ok("a second press (with the location) is the same SOS, no second call", len(fake.calls) == n + 1)
report(n, "no_answer"); wait(lambda: len(fake.calls) == n + 2)
c.post("/api/senior/sos/cancel", headers=D, json={"senior_id": sid})
for i in range(n + 1, len(fake.calls)):
    report(i, "no_answer")
time.sleep(0.6)
ok("after 'pressed by mistake' no further calls are placed", len(fake.calls) <= n + 3 and server.store.sos_event(r["event_id"])["status"] == "cancelled_by_senior")

# ------------------------------------------------------------------ voice notes
server.stt.transcribe = lambda wav, lang: {"text": TEXT}
TEXT = "मैं मर रहा हूँ"
n = len(fake.calls)
vr = c.post(f"/api/senior/voice-note?senior_id={sid}", headers=D, content=b"\0" * 4000).json()
ok("'मैं मर रहा हूँ' in a voice note -> SOS and a family call", vr.get("sos") and wait(lambda: len(fake.calls) == n + 1)
   and server.store.active_sos(sid)["source"] == "voice_note")
server.store.resolve_sos(server.store.active_sos(sid)["id"], "resolved", "SAM-102")
TEXT = "I am dying to see my grandson this Sunday"
n = len(fake.calls)
vr = c.post(f"/api/senior/voice-note?senior_id={sid}", headers=D, content=b"\0" * 4000).json()
time.sleep(0.2)
ok("'dying to see my grandson' is not an emergency", not vr.get("sos") and len(fake.calls) == n and server.store.active_sos(sid) is None)

# ------------------------------------------------------------------ status, no secrets
st = c.get("/api/voice/status").json()
ok("voice status says family alert calls are on and leaks nothing", st["family_alert_calls"] == "on" and "fake-key" not in str(st))

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
