"""Daily check-ins as real phone calls: Saathi (a Sarvam agent) rings the senior's own number, so a basic phone works.
Setup without the app (the family redeems the code on the website), the call, its result on the webhook, the
in-call emergency tool, and the app fallback. Sarvam is simulated by a fake client; everything else is real.
Run from coordinator_hub/:  python tests/test_phone_calls.py"""
import hashlib, hmac, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T = tempfile.gettempdir()
for k, f in (("AEGIS_DATA_FILE", "aegis_ph_store.json"), ("AEGIS_BILLING_FILE", "aegis_ph_bill.json"), ("AEGIS_AUTH_FILE", "aegis_ph_auth.json")):
    os.environ[k] = os.path.join(T, f)
    if os.path.exists(os.environ[k]): os.remove(os.environ[k])
os.environ.update({"SARVAM_API_KEY": "fake-key", "SARVAM_ORG_ID": "org", "SARVAM_WORKSPACE_ID": "ws",
                   "SARVAM_CHECKIN_APP_ID": "checkin-app", "SARVAM_CHECKIN_APP_VERSION": "2",
                   "SARVAM_ALERT_APP_ID": "alert-app", "SARVAM_ALERT_APP_VERSION": "1",
                   "SARVAM_CONNECTION_ID": "conn-1", "SARVAM_AGENT_PHONE": "+918000000000",
                   "AEGIS_PUBLIC_URL": "https://hub.example.test", "AEGIS_LLM": "off", "AEGIS_CALL_ENGINE": "",
                   "RAZORPAY_KEY_ID": "rzp_test_FAKEKEY123", "RAZORPAY_KEY_SECRET": "fake_secret_for_tests"})
os.environ.update({f"SARVAM_{k}_{i}": "" for i in range(2, 11) for k in ("API_KEY", "ORG_ID", "WORKSPACE_ID", "CHECKIN_APP_ID",
                   "CHECKIN_APP_VERSION", "ALERT_APP_ID", "ALERT_APP_VERSION", "CONNECTION_ID", "AGENT_PHONE")})   # no real extra keys
from fastapi.testclient import TestClient
import server
c = TestClient(server.app)
FAILS = []
def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: FAILS.append(name)

class FakeSarvam:
    def __init__(self): self.calls, self.spoken = [], {}
    def outbound_call(self, phone, variables, language="English", webhook_url="", metadata=None, agent="alert"):
        self.calls.append({"phone": phone, "vars": variables, "lang": language, "hook": webhook_url, "meta": metadata, "agent": agent})
        return f"att-{len(self.calls)}"
    def transcript(self, app_id, interaction_id, account=""):
        return {"messages": self.spoken.get(interaction_id, [])}
fake = FakeSarvam()
server.dispatcher.client = fake
server.dispatcher.notify_phone = lambda s, m: None
hook = "/api/sarvam/webhook?k=" + server.SARVAM_HOOK_KEY

# a family buys Saathi, then sets it up by phone on the website (no app)
server.billing._razorpay_order = lambda body: {"id": "order_T" + body["receipt"][-8:], "amount": body["amount"], "status": "created"}
o = c.post("/api/billing/order", json={"plan": "monthly", "name": "Meera Iyer", "email": "meera@example.com", "phone": "+91 98100 12345",
                                       "elder_name": "Ramesh Gupta", "elder_city": "Lucknow", "elder_language": "hi"}).json()
sig = hmac.new(b"fake_secret_for_tests", f"{o['order_id']}|pay_P".encode(), hashlib.sha256).hexdigest()
code = c.post("/api/billing/verify", json={"razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_P", "razorpay_signature": sig}).json()["saathi_code"]
ok("the website has the 'set up by phone' option", "onboard-phone" in c.get("/subscribe").text)
form = {"saathi_code": code, "name": "Ramesh Gupta", "phone": "98390 11223", "age": 78, "gender": "Male", "city": "Lucknow",
        "language": "hi", "emergency_name": "Meera Iyer", "emergency_relation": "Daughter", "emergency_phone": "+91 98100 12345", "call_time": "09:00"}
ok("a coordinator's own code cannot be used on the public form", c.post("/api/senior/onboard-phone", json={**form, "saathi_code": "SAM-101"}).status_code == 400)
ok("a number is required", c.post("/api/senior/onboard-phone", json={**form, "phone": "123"}).status_code == 400)
r = c.post("/api/senior/onboard-phone", json=form)
d = r.json()
sid = d.get("senior_id", "")
ok("setup by phone works with the Saathi code, no app and no device key", r.status_code == 200 and "device_key" not in d and d["calls_by_phone"])
ok("the code is used up", c.post("/api/senior/onboard-phone", json={**form, "phone": "98390 99999"}).status_code == 400)
ok("the same number cannot be set up twice", c.post("/api/senior/onboard-phone", json=form).status_code in (400, 409))
ok("a daily call is scheduled at the chosen time", any(e["senior_id"] == sid and e["schedule_time"] == "09:00" and e.get("recurring", True)
                                                       for e in server.store.scheduled_calls))
ok("the family member is the emergency contact", [x["name"] for x in server.store.emergency_contacts(sid)][:1] == ["Meera Iyer"])

# the care manager (or the schedule) places the check-in: Saathi rings the number
pin = {x["code"]: x["pin"] for x in c.get("/api/auth/demo").json()["coordinators"]}
H = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-102", "secret": pin["SAM-102"]}).json()["token"]}
res = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
cid = res["call_id"]
call = fake.calls[-1]
ok("the check-in agent rings the senior's own number", call["agent"] == "checkin" and call["phone"] == "98390 11223" and res["signaled"])
ok("the agent knows who it is calling (first name, care manager), in Hindi", call["vars"]["senior_first_name"] == "Ramesh"
   and call["vars"]["care_manager_name"] == "Rajesh" and call["lang"] == "Hindi")
ok("the call and senior IDs ride along for the emergency tool", call["vars"]["call_id"] == cid and call["vars"]["senior_id"] == sid)
ok("no phone number or ID goes into what the agent says about health", "98390" not in call["vars"]["health_summary"])
rec = server.store.get_call(cid)
ok("the call shows as ringing, by phone", rec["status"] == "ringing" and rec["channel"] == "phone")

def report(i, status, **extra):
    x = fake.calls[i]
    return c.post(hook, json={"attempt_id": f"att-{i + 1}", "status": status, "webhook_config": {"url": x["hook"], "metadata": x["meta"]}, **extra})

fake.spoken["20261030/a1"] = [{"role": "assistant", "content": "नमस्ते रमेश जी, मैं साथी बोल रही हूँ। आज कैसा लग रहा है?"},
                              {"role": "user", "content": "थोड़ा चक्कर आ रहा है, और रात को नींद नहीं आई"},
                              {"role": "assistant", "content": "ओह, आपके केयर मैनेजर आज आपसे बात करेंगे।"}]
report(len(fake.calls) - 1, "connected", duration=95, interaction_id="20261030/a1",
       interaction_transcript=[{"role": "user", "en_text": "feeling a little dizzy"}])
rec = server.store.get_call(cid)
ok("answered call is saved with the words as spoken (Hindi)", rec["status"] == "completed" and any("चक्कर" in t["text"] for t in rec["transcript"]))
ok("the NLP picks up dizziness and poor sleep from the senior's words", {"dizziness", "poor_sleep"} <= set(rec.get("symptoms_reported") or rec.get("symptoms", [])))
n = len(fake.calls)
report(n - 1, "connected", duration=95, interaction_id="20261030/a1")
ok("a repeated webhook is ignored", server.store.get_call(cid)["status"] == "completed" and len(fake.calls) == n)

# unanswered: marked missed, so the schedule's retry rings again later
cid2 = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()["call_id"]
report(len(fake.calls) - 1, "no_answer")
ok("an unanswered call is marked missed", server.store.get_call(cid2)["status"] == "missed")

# danger said DURING the call: the agent's tool raises it at once
cid3 = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()["call_id"]
tool = "/api/sarvam/tools/emergency?k="
body = {"call_id": cid3, "senior_id": sid, "said": "main mar raha hoon"}
ok("tool without the secret is refused", c.post(tool + "wrong", json=body).status_code == 403)
ok("tool with another senior's call is refused", c.post(tool + server.SARVAM_HOOK_KEY, json={**body, "senior_id": "SR-X"}).status_code == 404)
before = len(fake.calls)
r = c.post(tool + server.SARVAM_HOOK_KEY, json=body)
ev = server.store.active_sos(sid)
ok("the emergency tool opens an SOS with what was said", r.status_code == 200 and ev and ev["source"] == "call" and "mar raha" in ev["said"])
time.sleep(0.3)
ok("and the family alert agent rings the emergency contact", len(fake.calls) == before + 1 and fake.calls[-1]["agent"] == "alert"
   and fake.calls[-1]["phone"] == "+91 98100 12345")
c.post(tool + server.SARVAM_HOOK_KEY, json=body)
time.sleep(0.2)
ok("calling the tool twice does not ring the family twice", len(fake.calls) == before + 1)
server.store.resolve_sos(ev["id"], "resolved", "SAM-102")

# backup: danger words found in the transcript afterwards, when the tool did not fire
cid4 = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()["call_id"]
fake.spoken["20261030/a4"] = [{"role": "user", "content": "seene mein dard ho raha hai"}]
n = len(fake.calls)
report(n - 1, "connected", duration=30, interaction_id="20261030/a4")
time.sleep(0.3)
ok("chest pain in the transcript still raises the SOS and the family call", server.store.active_sos(sid) is not None and len(fake.calls) == n + 1)

# English said on a Hindi call comes back in Devanagari ("आई एम डाइंग"), and Sarvam's English rendering is checked too
def danger_after_call(spoken, en_text):
    server.store.resolve_sos(server.store.active_sos(sid)["id"], "resolved", "SAM-102")
    c.post("/api/calls/initiate", headers=H, json={"senior_id": sid})
    iid = f"20261030/d{len(fake.calls)}"
    fake.spoken[iid] = [{"role": "user", "content": spoken}]
    n = len(fake.calls)
    report(n - 1, "connected", duration=20, interaction_id=iid, interaction_transcript=[{"role": "user", "en_text": en_text}])
    time.sleep(0.3)
    return server.store.active_sos(sid) is not None and len(fake.calls) == n + 1 and fake.calls[-1]["agent"] == "alert"
ok("'I am dying' written in Devanagari rings the family", danger_after_call("आई एम डाइंग।", ""))
ok("danger only visible in Sarvam's English rendering still rings the family", danger_after_call("माइक्रोफोन।", "I am dying."))

# Sarvam account out of credit: the check-in says so plainly, and an emergency is handed over at once (no 2-minute wait)
real_call = fake.outbound_call
def broke(*a, **k): raise RuntimeError('sarvam outbound 402: {"error":{"message":"(402) Insufficient Balance"}}')
fake.outbound_call = broke
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("no credit: the care manager is told the Sarvam account needs a top-up", "out of credit" in r["message"] and not r["signaled"])
server.store.resolve_sos(server.store.active_sos(sid)["id"], "resolved", "SAM-102")
server.dispatcher.raise_emergency(sid, "call", "I am dying")
ev = server.store.active_sos(sid)
ok("no credit: the SOS says so and the family alert is handed over at once", ev["alert_state"] == "no_credit"
   and ev["notify_log"][-1]["detail"] == "Sarvam account out of credit")
server.store.resolve_sos(ev["id"], "resolved", "SAM-102")

# no credit, but the Saathi app is open: the check-in moves into the app (no phone charges)
APP = []
async def app_send(s, m): APP.append(m); return True
real_online, real_send = server.ws_manager.is_online, server.ws_manager.send_to_senior
server.ws_manager.is_online = lambda s: True
server.ws_manager.send_to_senior = app_send
server.store.dynamic_seniors[sid]["call_mode"] = "phone"     # even a phone marked basic: the app is the only way left
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("no credit + app online: the call rings inside the app instead", r["signaled"] and r["channel"] == "app" and APP
   and APP[-1].get("call_id") == r["call_id"] and "inside the app" in r["note"])
ok("and it is not recorded as missed", server.store.get_call(r["call_id"])["status"] in ("ringing", "queued"))
server.ws_manager.is_online = lambda s: False
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("no credit + basic phone + no app: missed, and it says why", not r["signaled"] and "out of credit" in r["message"]
   and server.store.get_call(r["call_id"])["status"] == "missed")
fake.outbound_call = real_call

# the care manager's toggle: smartphone (in app when online) or basic phone (always a normal call)
toggle = f"/api/coordinator/seniors/{sid}/call-mode"
H1 = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-101", "secret": pin["SAM-101"]}).json()["token"]}
ok("another team cannot change how Saathi calls", c.post(toggle, headers=H1, json={"call_mode": "app"}).status_code == 403)
ok("only 'phone' or 'app'", c.post(toggle, headers=H, json={"call_mode": "pigeon"}).status_code == 400)
ok("the care manager marks a smartphone", c.post(toggle, headers=H, json={"call_mode": "app"}).json()["call_mode"] == "app")
ok("the senior page shows the setting", c.get(f"/api/senior/{sid}/details", headers=H).json()["senior"]["call_mode"] == "app")
server.ws_manager.is_online = lambda s: True
n, a = len(fake.calls), len(APP)
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("smartphone + app online: Saathi calls inside the app, no Sarvam phone call", len(fake.calls) == n and len(APP) == a + 1 and r["channel"] == "app")
server.ws_manager.is_online = lambda s: False
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("smartphone but the app is offline: Saathi rings the number", len(fake.calls) == n + 1 and fake.calls[-1]["agent"] == "checkin" and r["channel"] == "phone")
c.post(toggle, headers=H, json={"call_mode": "phone"})
server.ws_manager.is_online = lambda s: True
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("basic phone: a normal call even when an app is online", len(fake.calls) == n + 2 and r["channel"] == "phone")
server.ws_manager.is_online, server.ws_manager.send_to_senior = real_online, real_send

# several Sarvam keys: a random one per call; an account out of credit hands over to the next
from engine import sarvam_api as SA
os.environ.update({"SARVAM_API_KEY_2": "fake-key-2", "SARVAM_ORG_ID_2": "org-2", "SARVAM_CONNECTION_ID_2": "conn-2",
                   "SARVAM_AGENT_PHONE_2": "+918000000002"})
SA.POOL._empty.clear()
ok("both keys are in the pool", [a.name for a in SA.POOL.accounts()] == ["1", "2"])
ok("the second key uses its own org and shares the rest", SA.POOL.get("2").org_id == "org-2" and SA.POOL.get("2").checkin_app == "checkin-app")
class Resp:
    def __init__(self, code, body): self.status_code, self._b, self.text = code, body, str(body)
    def json(self): return self._b
    def raise_for_status(self): pass
SENT = []
def fake_post(url, json=None, headers=None, timeout=None):
    SENT.append((headers["X-API-Key"], url))
    return Resp(402, {"error": "(402) Insufficient Balance"}) if headers["X-API-Key"] == "fake-key" else Resp(200, {"attempt_id": "att-k2"})
real_post = SA.requests.post
SA.requests.post = fake_post
picked = set()
for _ in range(12):
    SA.POOL._empty.clear()
    picked.add(SA.POOL.order()[0].name)
ok("keys are picked at random", picked == {"1", "2"})
SA.POOL._empty.clear()
meta = {}
for _ in range(6):
    SENT.clear(); meta = {}
    att = SA.SarvamClient().outbound_call("98390 11223", {}, "Hindi", "https://h/x", meta, agent="checkin")
ok("an empty key is skipped for the one with credit", att == "att-k2" and meta["acct"] == "2" and "/orgs/org-2/" in SENT[-1][1])
ok("once known to be empty, that key is tried last", [k for k, _ in SENT] == ["fake-key-2"] and SA.POOL.has_credit())
SA.requests.post = lambda *a, **k: Resp(402, {"error": "(402) Insufficient Balance"})
try:
    SA.SarvamClient().outbound_call("98390 11223", {}, "Hindi"); err = ""
except Exception as e:
    err = str(e)
ok("every key empty: the 402 comes back and in-app Sarvam calls stand down", "402" in err and not SA.POOL.has_credit()
   and not SA.CONFIG.calls_ready())
ok("voice status counts the keys and those with credit", c.get("/api/voice/status").json()["keys"] == 2
   and c.get("/api/voice/status").json()["keys_with_credit"] == 0)
# a second account with no phone number of its own: in-app calls only, never the first account's number
os.environ.update({"SARVAM_CONNECTION_ID_2": "", "SARVAM_AGENT_PHONE_2": ""})
SA.POOL._empty.clear(); SENT.clear()
SA.requests.post = fake_post
ok("an account without its own number does not borrow the first account's", not SA.POOL.get("2").has_phone()
   and SA.POOL.get("1").has_phone())
try:
    SA.SarvamClient().outbound_call("98390 11223", {}, "Hindi", agent="checkin"); err = ""
except Exception as e:
    err = str(e)
ok("so phone calls never go through it (the 402 from account 1 still moves the call into the app)",
   "402" in err and [k for k, _ in SENT] == ["fake-key"] and SA.POOL.has_credit() and SA.CONFIG.calls_ready())
SA.requests.post = real_post
SA.POOL._empty.clear()
os.environ.update({"SARVAM_API_KEY_2": "", "SARVAM_ORG_ID_2": ""})

# a family voice message on a phone call: Saathi passes it on in words; marked played once the call connects
c.post(toggle, headers=H, json={"call_mode": "phone"})
server.store.dynamic_seniors[sid].setdefault("family_messages", []).append(
    {"id": "VM-TEST", "from": "Meera", "relation": "daughter", "ts": time.time(), "seconds": 3, "text": "papa main sunday aaungi", "played_at": None})
c.post(f"/api/coordinator/seniors/{sid}/language", headers=H, json={"language": "ta"})
cidm = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()["call_id"]
ok("the phone call carries the family message for the agent to read out", "Meera (daughter)" in fake.calls[-1]["vars"]["memory_note"]
   and "sunday" in fake.calls[-1]["vars"]["memory_note"])
ok("and is placed in the senior's language (Tamil)", fake.calls[-1]["lang"] == "Tamil")
report(len(fake.calls) - 1, "connected", duration=40, interaction_id="20261030/vm")
vm = server.store.dynamic_seniors[sid]["family_messages"][-1]
ok("once connected, the message counts as delivered", vm["played_how"] == "read_on_phone_call" and vm["call_id"] == cidm)
c.post(f"/api/coordinator/seniors/{sid}/language", headers=H, json={"language": "hi"})

# missed-call SOS from a basic phone: two missed calls within 2 minutes, or one to the SOS number
gw = {"x-gateway-key": server.CREDS["gateway_key"]}
active = server.store.active_sos(sid)
if active: server.store.resolve_sos(active["id"], "resolved", "SAM-102")
n = len(fake.calls)
r1 = c.post("/api/gateway/missed-call", headers=gw, json={"from_number": "+91 98390 11223"}).json()
ok("one missed call is the usual 'I am fine'", r1["status"] == "ok" and server.store.active_sos(sid) is None)
r2 = c.post("/api/gateway/missed-call", headers=gw, json={"from_number": "98390 11223"}).json()
time.sleep(0.3)
ev = server.store.active_sos(sid)
ok("a second missed call within 2 minutes raises the SOS and rings the family", r2["status"] == "sos" and ev and ev["source"] == "missed_call"
   and len(fake.calls) == n + 1 and fake.calls[-1]["agent"] == "alert")
server.store.resolve_sos(ev["id"], "resolved", "SAM-102")
r3 = c.post("/api/gateway/missed-call", headers=gw, json={"from_number": "98390 11223", "kind": "sos"}).json()
ok("a missed call to the SOS number raises it at once", r3["status"] == "sos" and server.store.active_sos(sid)["source"] == "missed_call")
server.store.resolve_sos(server.store.active_sos(sid)["id"], "resolved", "SAM-102")
ok("the gateway needs its key", c.post("/api/gateway/missed-call", json={"from_number": "98390 11223"}).status_code == 401)

# without Sarvam phone calls, the app still rings as before
os.environ["AEGIS_CALL_ENGINE"] = "app"
n = len(fake.calls)
r = c.post("/api/calls/initiate", headers=H, json={"senior_id": sid}).json()
ok("with phone calls switched off, the call goes to the app instead", len(fake.calls) == n and r["status"] == "success")
os.environ["AEGIS_CALL_ENGINE"] = ""
ok("voice status says calls go by phone", c.get("/api/voice/status").json()["calls"] == "phone")

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
