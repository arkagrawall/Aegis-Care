"""Saathi purchase flow: a family member buys for their parent -> signed payment -> a Samarth care manager is
assigned -> a one-time Saathi code -> the parent's phone redeems it during setup.
Razorpay itself is simulated (fake test keys, fake order); the signature check is the real one.
Run from coordinator_hub/:  python tests/test_billing.py"""
import hashlib, hmac, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T = tempfile.gettempdir()
for k, f in (("AEGIS_DATA_FILE", "aegis_bill_store.json"), ("AEGIS_BILLING_FILE", "aegis_bill.json"), ("AEGIS_AUTH_FILE", "aegis_bill_auth.json")):
    os.environ[k] = os.path.join(T, f)
    if os.path.exists(os.environ[k]): os.remove(os.environ[k])
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_FAKEKEY123"
os.environ["RAZORPAY_KEY_SECRET"] = "fake_secret_for_tests"
os.environ["SARVAM_API_KEY"] = ""   # never place real Sarvam calls from tests, whatever .env holds
os.environ.update({f"SARVAM_API_KEY_{i}": "" for i in range(2, 11)})
from fastapi.testclient import TestClient
import server
c = TestClient(server.app)
FAILS = []
def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: FAILS.append(name)

server.billing._razorpay_order = lambda body: {"id": "order_T" + body["receipt"][-8:], "amount": body["amount"], "status": "created"}
sign = lambda oid, pid: hmac.new(b"fake_secret_for_tests", f"{oid}|{pid}".encode(), hashlib.sha256).hexdigest()
def buy(plan="yearly", city="Lucknow", pid="pay_A"):
    o = c.post("/api/billing/order", json={"plan": plan, "name": "Meera Iyer", "email": "meera@example.com", "phone": "+91 98100 12345",
                                           "elder_name": "Kamla Devi", "elder_city": city, "elder_language": "hi"}).json()
    return o, c.post("/api/billing/verify", json={"razorpay_order_id": o["order_id"], "razorpay_payment_id": pid,
                                                   "razorpay_signature": sign(o["order_id"], pid)}).json()

home = c.get("/").text
ok("website at / looks like Samarth and has the Saathi button", "samarth" in home and "Get Saathi" in home and "/subscribe" in home)
ok("care portal at /portal", "/static/portal.js" in c.get("/portal").text)
ok("buy page at /subscribe", c.get("/subscribe").status_code == 200)
cfg = c.get("/api/billing/config").json()
ok("test mode on, secret never sent", cfg["enabled"] and "fake_secret" not in str(cfg))

ok("parent's name and city are required", c.post("/api/billing/order", json={"plan": "monthly", "name": "M", "email": "m@x.in", "phone": "9810012345", "elder_name": "", "elder_city": ""}).status_code == 400)
o, v = buy("yearly", "Lucknow")
ok("yearly order is 2999 rupees", o["amount"] == 299900)
code = v["saathi_code"]
ok("payment gives a Saathi code", code.startswith("SAATHI-") and len(code) == 13)
ok("a Samarth care manager in the parent's city is assigned (Lucknow -> SAM-102)", v["coordinator_code"] == "SAM-102" and v["coordinator_name"] == "Rajesh Verma")
ok("no new coordinator account or PIN is created", "pin" not in v and code not in server.CREDS["coordinators"])
ok("same payment twice gives the same code", c.post("/api/billing/verify", json={"razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_A",
                                                                              "razorpay_signature": sign(o["order_id"], "pay_A")}).json()["saathi_code"] == code)
ok("forged signature refused", c.post("/api/billing/verify", json={"razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_B", "razorpay_signature": "0" * 64}).status_code == 400)
_, v2 = buy("monthly", "Shimla", "pay_C")
ok("a city with no local care manager goes to the least busy one", v2["coordinator_code"] in {c_["code"] for c_ in server.store.coordinators.values()})

# the parent's phone redeems the code
ob = c.post("/api/senior/onboard", json={"name": "Kamla Devi", "age": 74, "city": "Lucknow", "coordinator_code": code.lower(), "language": "hi"})
ok("phone setup accepts the Saathi code", ob.status_code == 200 and ob.json()["senior"]["coordinator_code"] == "SAM-102")
ok("the phone is linked to the assigned care manager", "Rajesh Verma" in ob.json()["message"])
ok("the code works only once", c.post("/api/senior/onboard", json={"name": "Someone", "age": 70, "coordinator_code": code}).status_code == 400)
ok("an unknown code is refused", c.post("/api/senior/onboard", json={"name": "X", "age": 70, "coordinator_code": "SAATHI-ZZZZZZ"}).status_code == 400)
pin = {x["code"]: x["pin"] for x in c.get("/api/auth/demo").json()["coordinators"]}
tok = c.post("/api/auth/login", json={"role": "coordinator", "id": "SAM-102", "secret": pin["SAM-102"]}).json()["token"]
q = c.get("/api/coordinator/SAM-102/seniors", headers={"Authorization": "Bearer " + tok}).json()
ok("Kamla appears on Rajesh Verma's list in the portal", any(s["name"] == "Kamla Devi" for s in q["seniors"]))
ok("the senior record knows its plan", server.store.dynamic_seniors[ob.json()["senior"]["senior_id"]]["plan_valid_until"] == v["valid_until"])

server.billing.state["subscriptions"][v2["saathi_code"]]["valid_until"] = "2000-01-01"
ok("an expired code cannot be redeemed", c.post("/api/senior/onboard", json={"name": "Y", "age": 70, "coordinator_code": v2["saathi_code"]}).status_code == 400)
ok("care managers' own codes still work for setup", c.post("/api/senior/onboard", json={"name": "Z", "age": 70, "coordinator_code": "SAM-101"}).status_code == 200)
os.environ["RAZORPAY_KEY_ID"] = "rzp_live_SOMETHING"
ok("live keys are refused", not c.get("/api/billing/config").json()["enabled"])

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
