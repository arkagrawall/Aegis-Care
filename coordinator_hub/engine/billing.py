"""Saathi subscriptions, bought by a family member for their parent.

  plan -> Razorpay order -> verified payment -> a care manager from Samarth's existing team is assigned
       -> a one-time Saathi code (SAATHI-XXXXXX) that the parent's phone redeems during setup.

Keys come from coordinator_hub/.env (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET). Only TEST keys (rzp_test_...)
are accepted for now, so no real money can move.

A payment is trusted only after its signature checks out:
    HMAC_SHA256(order_id + "|" + payment_id, key_secret) == razorpay_signature
State lives in data/billing.json (orders and subscriptions).
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any, Dict, Optional

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BILLING_FILE = os.environ.get("AEGIS_BILLING_FILE", os.path.join(DATA_DIR, "billing.json"))

PLANS = {
    "monthly": {"id": "monthly", "name_en": "Monthly", "name_hi": "मासिक", "amount": 299_00, "days": 30},
    "yearly": {"id": "yearly", "name_en": "Yearly", "name_hi": "वार्षिक", "amount": 2999_00, "days": 365},
}
RAZORPAY_API = "https://api.razorpay.com/v1"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"     # no 0/O or 1/I, easy to read out on the phone
LANGS = {"hi", "en"}


class Billing:
    def __init__(self, store, creds: Dict[str, Any], save_creds):
        self.store = store
        self.creds = creds
        self.save_creds = save_creds
        self.lock = threading.Lock()
        self.state = {"orders": {}, "subscriptions": {}}
        if os.path.exists(BILLING_FILE):
            try:
                with open(BILLING_FILE, encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception as e:
                print(f"[Billing] could not read {BILLING_FILE}: {e}")
        # an earlier version issued whole new coordinator accounts; those keep working
        for sub in self.state["subscriptions"].values():
            if sub.get("kind", "coordinator") == "coordinator":
                self.store.coordinators[sub["code"]] = {"code": sub["code"], "name": sub["name"], "city": sub["city"],
                                                        "phone": sub["phone"], "subscriber": True}

    # ------------------------------------------------------------------ keys
    @staticmethod
    def keys():
        return os.environ.get("RAZORPAY_KEY_ID", "").strip(), os.environ.get("RAZORPAY_KEY_SECRET", "").strip()

    def config(self) -> Dict[str, Any]:
        kid, sec = self.keys()
        ok = bool(kid and sec)
        test = ok and kid.startswith("rzp_test_")
        return {
            "enabled": test,
            "reason": "" if test else ("Only Razorpay TEST keys (rzp_test_...) are allowed for now." if ok else
                                       "Payments are not set up yet: add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to coordinator_hub/.env."),
            "key_id": kid if test else "",
            "test_mode": True,
            "plans": [{**p, "rupees": p["amount"] // 100} for p in PLANS.values()],
        }

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = BILLING_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, BILLING_FILE)

    # ------------------------------------------------------------------ order
    def create_order(self, plan_id: str, form: Dict[str, str]) -> Dict[str, Any]:
        cfg = self.config()
        if not cfg["enabled"]:
            return {"error": cfg["reason"]}
        plan = PLANS.get(plan_id)
        if not plan:
            return {"error": "Unknown plan"}
        clean = lambda k, n: (form.get(k) or "").strip()[:n]
        buyer = {"name": clean("name", 60), "email": clean("email", 120),
                 "phone": "".join(ch for ch in (form.get("phone") or "") if ch.isdigit() or ch == "+")[:16]}
        elder = {"name": clean("elder_name", 60), "city": clean("elder_city", 40),
                 "language": form.get("elder_language") if form.get("elder_language") in LANGS else "hi"}
        if not buyer["name"] or "@" not in buyer["email"] or sum(c.isdigit() for c in buyer["phone"]) < 10:
            return {"error": "Please enter your name, a valid email and a 10-digit phone number."}
        if not elder["name"] or not elder["city"]:
            return {"error": "Please enter your parent's name and the city they live in."}
        receipt = "SAATHI-" + secrets.token_hex(4).upper()
        body = {"amount": plan["amount"], "currency": "INR", "receipt": receipt,
                "notes": {"plan": plan_id, "buyer": buyer["name"], "for": elder["name"], "city": elder["city"]}}
        try:
            order = self._razorpay_order(body)
        except Exception as e:
            return {"error": f"Could not reach Razorpay: {e}"}
        if not order.get("id"):
            return {"error": (order.get("error") or {}).get("description") or "Razorpay did not create an order"}
        with self.lock:
            self.state["orders"][order["id"]] = {
                "order_id": order["id"], "plan": plan_id, "amount": plan["amount"], "receipt": receipt,
                "buyer": buyer, "elder": elder, "status": "created", "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save()
        return {"order_id": order["id"], "amount": plan["amount"], "currency": "INR", "key_id": cfg["key_id"],
                "plan": plan_id, "prefill": {"name": buyer["name"], "email": buyer["email"], "contact": buyer["phone"]}}

    def _razorpay_order(self, body):
        kid, sec = self.keys()
        return requests.post(f"{RAZORPAY_API}/orders", json=body, auth=(kid, sec), timeout=15).json()

    # ------------------------------------------------------------------ verify -> assign a care manager -> Saathi code
    def verify(self, order_id: str, payment_id: str, signature: str) -> Dict[str, Any]:
        _, sec = self.keys()
        order = self.state["orders"].get(order_id)
        if not order:
            return {"error": "Unknown order"}
        expected = hmac.new(sec.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not sec or not hmac.compare_digest(expected, signature or ""):
            return {"error": "Payment could not be verified"}
        with self.lock:
            if order.get("status") == "paid":               # the browser may report success twice
                return self._result(self.state["subscriptions"][order["code"]])
            plan = PLANS[order["plan"]]
            coord = self._assign(order["elder"]["city"])
            code = self._new_code()
            now = time.time()
            sub = {"kind": "activation", "code": code, "plan": order["plan"], "amount": order["amount"],
                   "order_id": order_id, "payment_id": payment_id, "buyer": order["buyer"], "elder": order["elder"],
                   "coordinator_code": coord["code"], "coordinator_name": coord["name"], "coordinator_phone": coord.get("phone", ""),
                   "started_at": time.strftime("%Y-%m-%d", time.localtime(now)),
                   "valid_until": time.strftime("%Y-%m-%d", time.localtime(now + plan["days"] * 86400)),
                   "redeemed_by": None, "redeemed_at": None}
            order.update(status="paid", payment_id=payment_id, code=code, paid_at=time.strftime("%Y-%m-%d %H:%M:%S"))
            self.state["subscriptions"][code] = sub
            self._save()
            return self._result(sub)

    def _assign(self, city: str) -> Dict[str, Any]:
        """A care manager from Samarth's existing team: one in the parent's city if there is one, otherwise
        whoever looks after the fewest people."""
        team = [c for c in self.store.coordinators.values() if not c.get("subscriber")]
        load = {c["code"]: 0 for c in team}
        for s in list(self.store.seniors_map.values()) + list(self.store.dynamic_seniors.values()):
            if s.get("coordinator_code") in load:
                load[s["coordinator_code"]] += 1
        city_l = (city or "").lower()
        local = [c for c in team if c.get("city") and (c["city"].lower() in city_l or city_l in c["city"].lower())]
        pool = local or team
        return min(pool, key=lambda c: (load[c["code"]], c["code"]))

    def _new_code(self) -> str:
        while True:
            code = "SAATHI-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            if code not in self.state["subscriptions"]:
                return code

    @staticmethod
    def _result(sub):
        return {"saathi_code": sub["code"], "plan": sub["plan"], "valid_until": sub["valid_until"],
                "buyer_name": sub["buyer"]["name"], "elder_name": sub["elder"]["name"], "elder_language": sub["elder"]["language"],
                "coordinator_name": sub["coordinator_name"], "coordinator_code": sub["coordinator_code"],
                "coordinator_phone": sub.get("coordinator_phone", "")}

    # ------------------------------------------------------------------ redeem on the parent's phone
    @staticmethod
    def is_saathi_code(code: str) -> bool:
        return (code or "").strip().upper().startswith("SAATHI-")

    def check_redeem(self, code: str) -> Dict[str, Any]:
        sub = self.state["subscriptions"].get((code or "").strip().upper())
        if not sub or sub.get("kind") != "activation":
            return {"error": "This Saathi code isn't valid. Check the code from your purchase."}
        if sub["redeemed_by"]:
            return {"error": "This Saathi code has already been used on another phone."}
        if sub["valid_until"] < time.strftime("%Y-%m-%d"):
            return {"error": "This subscription has ended. Please renew it."}
        return {"coordinator_code": sub["coordinator_code"], "subscription": sub}

    def mark_redeemed(self, code: str, senior_id: str) -> None:
        with self.lock:
            sub = self.state["subscriptions"][code.strip().upper()]
            sub["redeemed_by"], sub["redeemed_at"] = senior_id, time.strftime("%Y-%m-%d %H:%M:%S")
            self._save()

    # ------------------------------------------------------------------ old coordinator subscriptions
    def active(self, code: str) -> Optional[bool]:
        """None when the code has no coordinator subscription (Samarth's own team); otherwise whether it is paid up."""
        sub = self.state["subscriptions"].get((code or "").upper())
        if not sub or sub.get("kind", "coordinator") != "coordinator":
            return None
        return sub["valid_until"] >= time.strftime("%Y-%m-%d")
