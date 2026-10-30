"""
One path for every emergency: the SOS button, a fall, a voice note, or words like "I am dying" on a call.

raise_emergency()
  1. opens the SOS (or joins the one already open: repeats within 10 minutes never start a second round of calls)
  2. tells the phone, which shows "Help is coming" with a Call 112 button
  3. has the Sarvam "Saathi alert" agent phone the emergency contacts one by one and tell them what happened;
     the outcome of each call comes back on the webhook. No answer from anyone -> one more round after 2 minutes.
     No Sarvam number configured, or nobody reached -> the phone dials the first contact itself.

It never diagnoses and never replaces 112: the alert tells the family to call 112 if they cannot reach the senior.
"""
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from engine.sarvam_api import CONFIG, SarvamClient, language_name, public_url
except ImportError:
    from .sarvam_api import CONFIG, SarvamClient, language_name, public_url

RETRY_AFTER_S = 120
WEBHOOK_WAIT_S = 180          # no word from Sarvam about a call this long -> treat it as unanswered and move on

SOURCE_TEXT = {
    "call": "on her Saathi check-in call",
    "voice_note": "in a voice message on her Saathi app",
    "senior_hold": "by pressing the SOS button on her Saathi app",
    "fall_need_help": "after her phone detected a fall and she asked for help",
    "fall_no_response": "after her phone detected a fall and she did not respond",
    "missed_call": "by giving missed calls to the Saathi help number from her phone",
}


def _mask(phone: str) -> str:
    d = "".join(ch for ch in phone if ch.isdigit())
    return ("•" * 6 + d[-4:]) if len(d) >= 4 else ""


def _pronouns(gender: str) -> Dict[str, str]:
    female = str(gender or "").lower().startswith("f")
    return {"her": "her" if female else "his", "she": "she" if female else "he"}


class EmergencyDispatcher:
    def __init__(self, store, notify_phone: Callable[[str, Dict[str, Any]], None],
                 audit: Optional[Callable[..., None]] = None, client: Optional[SarvamClient] = None,
                 config=CONFIG, webhook_secret: str = ""):
        self.store = store
        self.notify_phone = notify_phone
        self.audit = audit or (lambda *a, **k: None)
        self.client = client or SarvamClient(config)
        self.config = config
        self.webhook_secret = webhook_secret
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ entry point
    def raise_emergency(self, senior_id: str, source: str, said: str = "", lat=None, lon=None) -> Dict[str, Any]:
        res = self.store.create_sos(senior_id, source, lat, lon, said)
        if "error" in res:
            return res
        ev = res["event"]
        with self._lock:
            if ev.get("alert_state"):                 # this emergency is already being handled
                return {"status": "ok", "event": ev, "duplicate": True}
            contacts = self.store.emergency_contacts(senior_id)
            ai = self.config.alerts_ready() and bool(contacts) and bool(public_url())
            ev["alert_state"] = "calling" if ai else ("phone_fallback" if contacts else "no_contact")
            self.store.save()
        first = contacts[0] if contacts else None
        self._tell_phone(senior_id, ev, first, ai)
        self.audit("system", "emergency", f"emergency_{source}", senior_id)
        if ai:
            threading.Thread(target=self._call, args=(ev["id"], 0, 0), daemon=True).start()
        return {"status": "ok", "event": ev, "duplicate": res.get("duplicate", False), "family_ai_call": ai}

    def cancel(self, senior_id: str) -> None:
        """The senior undid an SOS pressed by mistake: stop any calls not yet placed."""
        with self._lock:
            t = self._timers.pop(senior_id, None)
        if t:
            t.cancel()

    # ------------------------------------------------------------------ the phone
    def _tell_phone(self, senior_id: str, ev: Dict[str, Any], contact: Optional[Dict[str, Any]], ai: bool,
                    dial_now: bool = False) -> None:
        msg = {"event": "emergency", "sos_id": ev["id"], "ai_calling": ai, "dial_now": dial_now,
               "contact_name": (contact or {}).get("name") or (contact or {}).get("relation") or "",
               "contact_phone": (contact or {}).get("phone", "")}
        try:
            self.notify_phone(senior_id, msg)
        except Exception as e:
            print(f"[Emergency] phone notify failed: {e}")

    # ------------------------------------------------------------------ alert calls
    def _variables(self, ev: Dict[str, Any], contact: Dict[str, Any]) -> Dict[str, Any]:
        s = self.store._senior(ev["senior_id"]) or {}
        coord = self.store.coordinators.get(s.get("coordinator_code") or "", {})
        p = _pronouns(s.get("gender", ""))
        source = SOURCE_TEXT.get(ev.get("source", ""), "on her Saathi app")
        if p["her"] == "his":
            source = source.replace(" her ", " his ").replace(" she ", " he ")
        return {
            "senior_name": s.get("name") or ev.get("senior_name", ""),
            "her_his": p["her"], "she_he": p["she"],
            "contact_name": contact.get("name", ""),
            "relation": contact.get("relation", ""),
            "what_they_said": (ev.get("said") or "").strip() or "that she needs help now".replace("she", p["she"]),
            "how_it_came": source,
            "time_text": time.strftime("%I:%M %p", time.localtime(ev["ts"])).lstrip("0"),
            "care_manager_name": coord.get("name") or s.get("coordinator_name", ""),
            "care_manager_phone": coord.get("phone", ""),
            "location_known": "yes" if ev.get("lat") is not None else "no",
        }

    def _call(self, event_id: str, idx: int, round_no: int) -> None:
        ev = self.store.sos_event(event_id)
        if not ev or ev.get("status") != "active":
            return
        contacts = self.store.emergency_contacts(ev["senior_id"])
        if idx >= len(contacts):
            self._round_over(ev, contacts, round_no)
            return
        c = contacts[idx]
        s = self.store._senior(ev["senior_id"]) or {}
        lang = language_name(s.get("language"))
        hook = f"{public_url()}/api/sarvam/webhook?k={self.webhook_secret}"
        meta = {"sos_id": event_id, "idx": idx, "round": round_no}
        row = {"name": c.get("name") or c.get("relation") or "Emergency contact", "relation": c.get("relation", ""),
               "phone": _mask(c.get("phone", "")), "round": round_no}
        try:
            attempt = self.client.outbound_call(c["phone"], self._variables(ev, c), lang, hook, meta)
            self.store.log_sos_notify(event_id, {**row, "attempt_id": attempt, "status": "ringing"})
            print(f"[Emergency] alert call {attempt} to contact {idx + 1} for {event_id}")
            w = threading.Timer(WEBHOOK_WAIT_S, self._watchdog, args=(event_id, attempt, idx, round_no))
            w.daemon = True
            w.start()
        except Exception as e:
            no_credit = "402" in str(e) or "balance" in str(e).lower()
            self.store.log_sos_notify(event_id, {**row, "status": "failed",
                                                 "detail": "Sarvam account out of credit" if no_credit else str(e)[:120]})
            print(f"[Emergency] alert call failed: {e}")
            if no_credit:      # no call can go out until it is topped up: hand over to the phone at once, no retry wait
                ev["alert_state"] = "no_credit"
                self.store.save()
                self._tell_phone(ev["senior_id"], ev, contacts[0], ai=False, dial_now=True)
                return
            self._call(event_id, idx + 1, round_no)

    def _round_over(self, ev: Dict[str, Any], contacts: List[Dict[str, Any]], round_no: int) -> None:
        if round_no == 0 and contacts:
            t = threading.Timer(RETRY_AFTER_S, self._call, args=(ev["id"], 0, 1))
            t.daemon = True
            with self._lock:
                self._timers[ev["senior_id"]] = t
            t.start()
            return
        ev["alert_state"] = "unreached"
        self.store.save()
        self._tell_phone(ev["senior_id"], ev, contacts[0] if contacts else None, ai=False, dial_now=True)

    def _watchdog(self, event_id: str, attempt: str, idx: int, round_no: int) -> None:
        ev = self.store.sos_event(event_id)
        row = next((r for r in (ev or {}).get("notify_log", []) if r.get("attempt_id") == attempt), None)
        if row and row.get("status") == "ringing":
            self.store.log_sos_notify(event_id, {"attempt_id": attempt, "status": "no_report"})
            self._call(event_id, idx + 1, round_no)

    def on_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sarvam reports how an alert call went."""
        meta = ((payload.get("webhook_config") or {}).get("metadata") or {})
        event_id, attempt = meta.get("sos_id"), payload.get("attempt_id")
        ev = self.store.sos_event(event_id) if event_id else None
        known = ev and any(r.get("attempt_id") == attempt for r in ev.get("notify_log", []))
        if not known:
            return {"status": "ignored"}
        status = str(payload.get("status") or "failed")
        final = payload.get("final_agent_variables") or {}
        ack = str(final.get("acknowledged") or "").strip().lower()
        self.store.log_sos_notify(event_id, {"attempt_id": attempt, "status": status,
                                             "duration": payload.get("duration"), "acknowledged": ack or None,
                                             "interaction_id": payload.get("interaction_id"),
                                             "detail": (payload.get("failure_reason") or "")[:120]})
        if status == "connected":
            ev["alert_state"] = "told"
            self.store.save()
            self.audit("system", "emergency", "family_told", ev["senior_id"])
        else:
            threading.Thread(target=self._call, args=(event_id, int(meta.get("idx", 0)) + 1,
                                                      int(meta.get("round", 0))), daemon=True).start()
        return {"status": "ok"}
