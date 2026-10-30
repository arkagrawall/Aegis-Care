"""
Aegis Saathi - Coordinator & Senior Persistence Store
Handles coordinator codes, dynamic senior onboarding, real-time sync, and feedback records.
"""

import atexit
import functools
import json
import os
import threading
import time
import uuid
from typing import Dict, List, Any, Optional
from .cohort_generator import COORDINATORS, generate_cohort, evaluate_cohort_performance
from .baseline_drift import PersonalBaselineEngine
from .hybrid_scorer import HybridRiskScorer
from .nlp_extractor import extract_symptom_cues
from .ml_model import MLRiskModel, build_features
from .evaluation import evaluate_all

# Everything the apps create (seniors, check-ins, calls...) is saved here so a server restart
# no longer wipes it. The synthetic 250-senior cohort is regenerated deterministically (seed 42).
DATA_FILE = os.environ.get(
    "AEGIS_DATA_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "store.json"),
)


def _persisted(fn):
    """Saves the store (debounced) after any method that changes data."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        result = fn(self, *args, **kwargs)
        self.save()
        return result
    return wrapper


class CoordinatorStore:
    def __init__(self):
        self.coordinators = {c["code"]: c for c in COORDINATORS}
        self.baseline_engine = PersonalBaselineEngine()
        self.scorer_engine = HybridRiskScorer()
        
        # Load synthetic 250 cohort
        print("Generating synthetic 250-senior × 90-day cohort...")
        self.cohort = generate_cohort(250, 90)
        self.seniors_map: Dict[str, Dict[str, Any]] = {s["senior_id"]: s for s in self.cohort["seniors"]}
        
        # ML layer (anomaly detector + explainable supervised model), cross-fitted by senior
        self.ml_model = MLRiskModel()
        self.ml_model.fit(self.cohort["seniors"], self.baseline_engine)

        # Honest evaluation on the planted decline cases (measured, not hard-coded)
        self.eval_metrics = evaluate_all(self.cohort, self.baseline_engine, self.scorer_engine, self.ml_model)
        h = self.eval_metrics["headline"]
        print(f"[Eval] recall {h['recall_pct']}% | alert-day precision {h['alert_day_precision_pct']}% | "
              f"median lead {h['median_lead_days']} d | false alarms/coordinator-week {h['false_alarms_per_coordinator_week']}")

        # Dynamic seniors onboarded via mobile app
        self.dynamic_seniors: Dict[str, Dict[str, Any]] = {}
        # Coordinator feedback & action logs
        self.action_logs: List[Dict[str, Any]] = []
        # AI Voice Calling & Scheduled Check-ins
        self.call_records: List[Dict[str, Any]] = []
        self.scheduled_calls: List[Dict[str, Any]] = []
        self.sos_events: List[Dict[str, Any]] = []
        self.audit_log: List[Dict[str, Any]] = []
        self.fall_events: List[Dict[str, Any]] = []
        self.feedback_stats: Dict[str, Dict[str, int]] = {}
        # Medicine schedules, dose answers and family contacts, per senior (set by the care manager)
        self.medicines: Dict[str, List[Dict[str, Any]]] = {}
        self.dose_log: List[Dict[str, Any]] = []
        self.contacts: Dict[str, List[Dict[str, Any]]] = {}
        self._ops_cache = (0.0, None)

        self._save_lock = threading.Lock()
        self._last_save = 0.0
        self._timer: Optional[threading.Timer] = None
        self._load_state()
        atexit.register(self._write_now)
        self.apply_feedback_to_scorer()

    # -------------------------------------------------------------
    # Persistence (JSON snapshot, atomic write)
    # -------------------------------------------------------------
    def _load_state(self) -> None:
        if not os.path.exists(DATA_FILE):
            print(f"[Store] No saved data yet ({DATA_FILE}); starting fresh")
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # corrupt file: keep it for inspection, start clean
            print(f"[Store] Could not read {DATA_FILE}: {e}")
            try:
                os.replace(DATA_FILE, DATA_FILE + ".corrupt")
            except OSError:
                pass
            return

        self.dynamic_seniors = data.get("dynamic_seniors", {})
        self.call_records = data.get("call_records", [])
        self.action_logs = data.get("action_logs", [])
        self.scheduled_calls = data.get("scheduled_calls", [])
        self.sos_events = data.get("sos_events", [])
        self.audit_log = data.get("audit_log", [])
        self.fall_events = data.get("fall_events", [])
        self.feedback_stats = data.get("feedback_stats", {})
        self.medicines = data.get("medicines", {})
        self.dose_log = data.get("dose_log", [])
        self.contacts = data.get("contacts", {})
        for sid, status in data.get("cohort_status", {}).items():
            if sid in self.seniors_map:
                self.seniors_map[sid]["current_status"] = status

        # A call that was ringing/connected when the server stopped can never finish
        interrupted = 0
        for c in self.call_records:
            if c.get("status") in ("ringing", "connected", "queued"):
                c["status"] = "missed"
                c["end_time"] = c.get("end_time") or time.strftime("%Y-%m-%d %H:%M:%S")
                c["summary"] = c.get("summary") or "Call interrupted (server restarted)."
                interrupted += 1
        print(f"[Store] Restored {len(self.dynamic_seniors)} app seniors, {len(self.call_records)} calls, "
              f"{len(self.action_logs)} actions ({interrupted} interrupted calls closed)")

    def save(self, force: bool = False) -> None:
        """Debounced: bursts of updates (watch syncs every few seconds) become one write per second."""
        now = time.time()
        if force or now - self._last_save >= 1.0:
            self._write_now()
        elif self._timer is None:
            self._timer = threading.Timer(1.0, self._write_now)
            self._timer.daemon = True
            self._timer.start()

    def _write_now(self) -> None:
        with self._save_lock:
            self._timer = None
            self._last_save = time.time()
            snapshot = {
                "dynamic_seniors": self.dynamic_seniors,
                "call_records": self.call_records,
                "action_logs": self.action_logs,
                "scheduled_calls": self.scheduled_calls,
                "sos_events": self.sos_events,
                "audit_log": self.audit_log[-2000:],
                "fall_events": self.fall_events[-2000:],
                "feedback_stats": self.feedback_stats,
                "medicines": self.medicines,
                "dose_log": self.dose_log[-20000:],
                "contacts": self.contacts,
                "cohort_status": {
                    sid: s["current_status"] for sid, s in self.seniors_map.items() if "current_status" in s
                },
            }
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            tmp = DATA_FILE + ".tmp"
            for attempt in range(3):  # another thread may mutate a dict while we serialise it
                try:
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(snapshot, f, ensure_ascii=False, default=str)
                    os.replace(tmp, DATA_FILE)
                    return
                except RuntimeError:
                    time.sleep(0.05)
                except OSError as e:
                    print(f"[Store] Save failed: {e}")
                    return

    # -------------------------------------------------------------
    # SOS events: tracked until a coordinator closes them
    # -------------------------------------------------------------
    @_persisted
    def report_fall(self, senior_id: str, outcome: str, impact_g: float = 0.0) -> Dict[str, Any]:
        """
        Outcome of the on-phone "Did you fall?" screen (phone-sensor fall detection):
          false_alarm   the senior said they are fine: logged for the detector's precision, nothing else happens
          ok_but_fell   they fell but are OK: flagged as a possible fall for a human to verify (not an emergency)
          need_help     they asked for help        -> tracked SOS
          no_response   no answer for 30 s         -> tracked SOS
        """
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}
        if outcome not in ("false_alarm", "ok_but_fell", "need_help", "no_response"):
            return {"error": "Invalid outcome"}
        self.fall_events.append({"ts": time.time(), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "senior_id": senior_id,
                                 "coordinator_code": senior.get("coordinator_code"), "outcome": outcome,
                                 "impact_g": round(float(impact_g or 0.0), 2)})
        result: Dict[str, Any] = {"status": "ok", "outcome": outcome}
        if outcome == "ok_but_fell":
            cur = self._ensure_current_status(senior)
            cur["possible_fall"] = True
            self.record_checkin(senior_id, "fall_report", "weak", "I had a fall but I am OK")
        elif outcome in ("need_help", "no_response"):
            sos = self.create_sos(senior_id, "fall_" + outcome)
            result["event_id"] = sos.get("event", {}).get("id")
        return result

    def fall_summary(self) -> Dict[str, Any]:
        counts = {"false_alarm": 0, "ok_but_fell": 0, "need_help": 0, "no_response": 0}
        for e in self.fall_events:
            counts[e["outcome"]] = counts.get(e["outcome"], 0) + 1
        total = len(self.fall_events)
        return {"triggers": total, **counts,
                "false_trigger_pct": round(100 * counts["false_alarm"] / total, 1) if total else None}

    def active_sos(self, senior_id: str) -> Optional[Dict[str, Any]]:
        for e in reversed(self.sos_events):
            if e["senior_id"] == senior_id and e["status"] == "active":
                return e
        return None

    def _sos_summary(self, senior_id: str) -> Dict[str, Any]:
        e = self.active_sos(senior_id)
        return {"active": bool(e), "event_id": e["id"] if e else None, "since": e["time"] if e else None}

    @_persisted
    def create_sos(self, senior_id: str, source: str = "senior_hold", lat=None, lon=None, said: str = "") -> Dict[str, Any]:
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}
        existing = self.active_sos(senior_id)
        if existing and time.time() - existing["ts"] < 600:      # repeat presses within 10 min = same event
            if lat is not None and lon is not None:               # the phone sends its location as soon as it has a fix
                existing["lat"], existing["lon"] = lat, lon
            if said and not existing.get("said"):
                existing["said"] = said[:300]
            return {"status": "ok", "event": existing, "duplicate": True}
        ev = {
            "id": f"SOS-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}",
            "senior_id": senior_id, "senior_name": senior["name"],
            "coordinator_code": senior.get("coordinator_code"),
            "ts": time.time(), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active", "source": source, "lat": lat, "lon": lon,
            "resolved_by": None, "resolved_at": None, "note": "",
            "said": (said or "")[:300], "notify_log": [],
        }
        self.sos_events.append(ev)
        self.record_checkin(senior_id, "emergency_sos", "bad", "EMERGENCY SOS: panic button held by senior")
        return {"status": "ok", "event": ev, "duplicate": False}

    def sos_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        return next((x for x in self.sos_events if x["id"] == event_id), None)

    @_persisted
    def log_sos_notify(self, event_id: str, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """One line per alert call to the family: who, when, and how it went (updated by attempt_id)."""
        e = self.sos_event(event_id)
        if not e:
            return None
        log = e.setdefault("notify_log", [])
        row = next((r for r in log if entry.get("attempt_id") and r.get("attempt_id") == entry["attempt_id"]), None)
        if row is None:
            row = {"time": time.strftime("%H:%M:%S")}
            log.append(row)
        row.update(entry)
        return row

    def emergency_contacts(self, senior_id: str) -> List[Dict[str, Any]]:
        """Who to ring in an emergency, in order: saved contacts marked for emergencies, then the onboarding number."""
        out, seen = [], set()
        saved = [c for c in self.contacts.get(senior_id, []) if c.get("is_emergency")]
        s = self._senior(senior_id) or {}
        onboarding = {"id": "emergency", "name": "", "relation": "Emergency contact",
                      "phone": str(s.get("emergency_contact") or "").strip(), "is_emergency": True}
        for c in saved + [onboarding]:
            digits = "".join(ch for ch in c.get("phone", "") if ch.isdigit())[-10:]
            # 98765 43210 is the form's placeholder, a stranger's number: never ring it
            if len(digits) >= 10 and digits not in seen and digits != "9876543210":
                seen.add(digits)
                out.append(c)
        return out

    @_persisted
    def cancel_sos(self, senior_id: str) -> Dict[str, Any]:
        """The senior pressed by mistake and cancelled within 2 minutes."""
        e = self.active_sos(senior_id)
        if not e or time.time() - e["ts"] > 120:
            return {"error": "No recent SOS to cancel"}
        e["status"] = "cancelled_by_senior"
        e["resolved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return {"status": "ok", "event": e}

    @_persisted
    def resolve_sos(self, event_id: str, status: str, by: str, note: str = "") -> Dict[str, Any]:
        e = next((x for x in self.sos_events if x["id"] == event_id), None)
        if not e:
            return {"error": "SOS event not found"}
        if status not in ("confirmed", "false_alarm", "resolved"):
            return {"error": "Invalid status"}
        e["status"], e["resolved_by"], e["note"] = status, by, note
        e["resolved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return {"status": "ok", "event": e}

    def list_sos(self, coord_code: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        out = [e for e in self.sos_events if (not coord_code or e.get("coordinator_code") == coord_code.upper())
               and (not active_only or e["status"] == "active")]
        return sorted(out, key=lambda e: e["ts"], reverse=True)

    # -------------------------------------------------------------
    # Audit, consent, family
    # -------------------------------------------------------------
    @_persisted
    def audit(self, role: str, sub: str, action: str, target: str = "") -> None:
        self.audit_log.append({"ts": time.time(), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "role": role, "who": sub, "action": action, "target": target})

    @_persisted
    def set_family_consent(self, senior_id: str, consent: bool) -> Dict[str, Any]:
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}
        senior["family_sharing_consent"] = bool(consent)
        if consent:
            if not senior.get("family_code"):
                senior["family_code"] = "FAM-" + uuid.uuid4().hex[:6].upper()
        else:
            senior["family_code"] = None      # revoking consent also revokes every family login
        self.audit_log.append({"ts": time.time(), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "role": "senior",
                               "who": senior_id, "action": "family_consent_" + ("granted" if consent else "revoked"),
                               "target": senior_id})
        return {"status": "ok", "consent": bool(consent), "family_code": senior.get("family_code")}

    def find_by_family_code(self, code: str) -> Optional[Dict[str, Any]]:
        code = (code or "").strip().upper()
        for s in list(self.dynamic_seniors.values()) + list(self.seniors_map.values()):
            if s.get("family_code") and s["family_code"] == code and s.get("family_sharing_consent"):
                return s
        return None

    def find_by_phone(self, number: str) -> Optional[Dict[str, Any]]:
        digits = "".join(ch for ch in (number or "") if ch.isdigit())[-10:]
        if len(digits) < 10:
            return None
        for s in self.dynamic_seniors.values():
            if "".join(ch for ch in s.get("phone", "") if ch.isdigit())[-10:] == digits:
                return s
        return None

    def family_overview(self, senior_id: str) -> Dict[str, Any]:
        """Weekly wellbeing view for family: plain language, no scores, no clinical detail."""
        summary = self.get_family_summary(senior_id)
        if "error" in summary:
            return summary
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        cur = self._ensure_current_status(senior)
        hist = (senior.get("vitals_history") or senior.get("records", [])[:80])[-7:]
        mood = {"good": "Doing well", "weak": "A little tired", "bad": "Not feeling well", "missed": "No check-in yet"}
        summary.update({
            "today_mood": mood.get(cur.get("last_checkin") or cur.get("checkin", "good"), "Doing well"),
            "last_checkin_time": cur.get("last_checkin_time"),
            "steps_7d": [d.get("steps", 0) or 0 for d in hist],
            "meds_7d": [1 if d.get("meds_taken", True) else 0 for d in hist],
            "serious_alert": self._sos_summary(senior_id)["active"],
        })
        # when the care manager has set medicines, the week comes from the real dose answers
        dd = self.dose_days(senior_id, 7)
        if dd["medicines"]:
            week = []
            for i in range(7):
                st = [c["status"] for m in dd["medicines"] for c in m["days"][i]["doses"] if c["status"] in ("taken", "skipped", "missed")]
                week.append(None if not st else 1 if all(x == "taken" for x in st) else 0)
            summary["meds_7d"] = week
            if dd["adherence_pct"] is not None:
                summary["adherence_rate"] = f"{dd['adherence_pct']}%"
        # check-in calls this week: only the day and how they sounded, never what was said
        since = time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 86400))
        summary["calls_7d"] = [{"date": str(c.get("start_time"))[:10], "mood": c.get("mood"), "done": c.get("status") == "completed"}
                               for c in self.call_records if c.get("senior_id") == senior_id and str(c.get("start_time"))[:10] >= since]
        coord = self.coordinators.get(senior.get("coordinator_code"), {})
        summary["coordinator_phone"] = coord.get("phone", "")
        return summary

    # -------------------------------------------------------------
    # Feedback loop and missed check-ins
    # -------------------------------------------------------------
    def feedback_multipliers(self) -> Dict[str, float]:
        """'Not useful' ratings turn a reason down, 'useful' turns it up (bounded 0.6x - 1.25x)."""
        out = {}
        for code, row in self.feedback_stats.items():
            u, n = row.get("useful", 0), row.get("not_useful", 0)
            out[code] = round(max(0.6, min(1.25, 1.0 + 0.5 * (u - n) / (u + n + 6))), 3)
        return out

    def apply_feedback_to_scorer(self) -> None:
        self.scorer_engine.multipliers = self.feedback_multipliers()

    @_persisted
    def sweep_missed_checkins(self, cutoff: str = "10:30") -> int:
        """After the cutoff, app seniors who have not checked in today are marked 'missed' (once per day)."""
        if time.strftime("%H:%M") < cutoff:
            return 0
        today = time.strftime("%Y-%m-%d")
        n = 0
        for s in self.dynamic_seniors.values():
            cur = self._ensure_current_status(s)
            if cur.get("last_checkin_date") != today and cur.get("missed_marked_date") != today:
                cur["missed_marked_date"] = today
                cur["last_checkin"] = "missed"
                cur["last_checkin_type"] = "no_response"
                n += 1
        return n

    # -------------------------------------------------------------
    # Operations view (aggregates only - no individual records)
    # -------------------------------------------------------------
    def _all_scored(self) -> List[Dict[str, Any]]:
        ts, cached = self._ops_cache
        if cached is not None and time.time() - ts < 20:
            return cached
        rows: List[Dict[str, Any]] = []
        for code in self.coordinators:
            for r in self.get_coordinator_seniors(code):
                rows.append({"coordinator": code, "city": r["city"], "tier": r["tier"], "score": r["risk_score"],
                             "sos": r["sos"]["active"], "is_dynamic": r["is_dynamic"]})
        self._ops_cache = (time.time(), rows)
        return rows

    def _trend_14d(self) -> Dict[str, Any]:
        """Per day for the last 14 days: emergencies, falls, completed calls and follow-ups logged."""
        days = [time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400 * i)) for i in range(13, -1, -1)]
        def count(items, key):
            n = {d: 0 for d in days}
            for x in items:
                d = str(x.get(key) or "")[:10]
                if d in n:
                    n[d] += 1
            return [n[d] for d in days]
        return {"days": days,
                "sos": count(self.sos_events, "time"),
                "falls": count(self.fall_events, "time"),
                "calls": count([c for c in self.call_records if c.get("status") == "completed"], "start_time"),
                "followups": count(self.action_logs, "timestamp")}

    def ops_overview(self) -> Dict[str, Any]:
        rows = self._all_scored()
        tiers = {"RED": 0, "ORANGE": 0, "YELLOW": 0, "GREEN": 0}
        by_coord: Dict[str, Dict[str, int]] = {}
        by_city: Dict[str, Dict[str, int]] = {}
        for r in rows:
            tiers[r["tier"]] += 1
            for table, key in ((by_coord, r["coordinator"]), (by_city, r["city"])):
                t = table.setdefault(key, {"RED": 0, "ORANGE": 0, "YELLOW": 0, "GREEN": 0, "total": 0})
                t[r["tier"]] += 1
                t["total"] += 1
        coord_names = {c["code"]: c["name"] for c in self.coordinators.values()}

        sos = self.sos_events
        resolved = [e for e in sos if e.get("resolved_at") and e["status"] in ("confirmed", "false_alarm", "resolved")]
        def mins(e):
            try:
                a = time.mktime(time.strptime(e["time"], "%Y-%m-%d %H:%M:%S"))
                b = time.mktime(time.strptime(e["resolved_at"], "%Y-%m-%d %H:%M:%S"))
                return max(0.0, (b - a) / 60.0)
            except Exception:
                return 0.0
        sos_summary = {
            "total": len(sos), "active": sum(1 for e in sos if e["status"] == "active"),
            "confirmed": sum(1 for e in sos if e["status"] == "confirmed"),
            "false_alarm": sum(1 for e in sos if e["status"] == "false_alarm"),
            "cancelled_by_senior": sum(1 for e in sos if e["status"] == "cancelled_by_senior"),
            "avg_response_minutes": round(sum(mins(e) for e in resolved) / len(resolved), 1) if resolved else None,
        }

        outcomes: Dict[str, int] = {}
        feedback: Dict[str, int] = {}
        for a in self.action_logs:
            outcomes[a.get("outcome") or "unknown"] = outcomes.get(a.get("outcome") or "unknown", 0) + 1
            feedback[a.get("feedback") or "none"] = feedback.get(a.get("feedback") or "none", 0) + 1
        needing = tiers["RED"] + tiers["ORANGE"]
        acted = len({a.get("senior_id") for a in self.action_logs})
        calls: Dict[str, int] = {}
        for c in self.call_records:
            calls[c.get("status", "unknown")] = calls.get(c.get("status", "unknown"), 0) + 1
        rated = sum(r.get("useful", 0) + r.get("not_useful", 0) for r in self.feedback_stats.values())

        return {
            "totals": {"seniors": len(rows), **tiers, "needing_attention": needing},
            "by_coordinator": [{"code": k, "name": coord_names.get(k, k), **v} for k, v in sorted(by_coord.items())],
            "by_city": [{"city": k, **v} for k, v in sorted(by_city.items(), key=lambda kv: -kv[1]["total"])],
            "sos": sos_summary,
            "falls": self.fall_summary(),
            "actions": {"total": len(self.action_logs), "outcomes": outcomes, "feedback": feedback,
                        "alert_action_rate_pct": round(100 * acted / needing, 1) if needing else None},
            "calls": {"total": len(self.call_records), "by_status": calls,
                      "escalated": sum(1 for c in self.call_records if c.get("escalation_flag"))},
            "learning": {"ratings": rated, "reason_multipliers": self.feedback_multipliers()},
            "trend_14d": self._trend_14d(),
            "moods": {m: sum(1 for c in self.call_records if c.get("mood") == m) for m in ("good", "okay", "low", "distressed")},
            "sos_recent": [{k: e.get(k) for k in ("id", "senior_id", "senior_name", "time", "status", "lat", "lon", "coordinator_code")}
                           for e in sorted(self.sos_events, key=lambda e: -e["ts"]) if time.time() - e["ts"] < 7 * 86400][:30],
            "model": {"headline": self.eval_metrics["headline"], "variants": self.eval_metrics["variants"],
                      "window": self.eval_metrics["window"], "nlp": {k: self.eval_metrics["nlp"][k] for k in
                                                                       ("examples", "micro_precision", "micro_recall", "micro_f1")},
                      "caveats": self.eval_metrics["caveats"]},
        }

    def get_coordinator(self, code: str) -> Optional[Dict[str, Any]]:
        return self.coordinators.get(code.upper())

    def list_coordinators(self) -> List[Dict[str, Any]]:
        result = []
        for code, c in self.coordinators.items():
            count = sum(1 for s in self.seniors_map.values() if s.get("coordinator_code") == code)
            count += sum(1 for s in self.dynamic_seniors.values() if s.get("coordinator_code") == code)
            res = dict(c)
            res["senior_count"] = count
            result.append(res)
        return result

    @_persisted
    def register_senior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Onboards a new senior from the Android App using Coordinator Code.
        Strictly validates coordinator code and generates collision-free ID.
        """
        coord_code = data.get("coordinator_code", "").upper().strip()
        if coord_code not in self.coordinators:
            return {"error": f"Invalid coordinator code '{coord_code}'. Please verify with your care manager."}

        senior_id = f"SR-APP-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
        senior_record = {
            "senior_id": senior_id,
            "name": data.get("name", "Senior Citizen"),
            "age": data.get("age", 70),
            "gender": data.get("gender", "Female"),
            "city": data.get("city", "Delhi NCR"),
            "emergency_contact": data.get("emergency_contact", "+91 98765 43210"),
            "language": data.get("language", "hi"),
            "coordinator_code": coord_code,
            "coordinator_name": self.coordinators[coord_code]["name"],
            "watch_mac": data.get("watch_mac", "DA:F1:70:01:23:45"),
            "watch_model": data.get("watch_model", "Da Fit / Moyoung Band"),
            "battery": data.get("battery", 92),
            "phone": data.get("phone", ""),
            "consent_care_team": bool(data.get("consent", True)),
            "consent_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "family_sharing_consent": False,
            "family_code": None,
            "is_dynamic": True,
            "is_planted": False,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "vitals_history": [],
            "current_status": {
                "steps": data.get("initial_steps", 1420),
                "resting_hr": data.get("initial_hr", 72),
                "live_hr": data.get("initial_hr", 72),
                "spo2": data.get("initial_spo2", 98.0),
                "sleep_hours": 7.2,
                "wear_hours": 20,
                "battery": data.get("battery", 92),
                "meds_taken": True,
                "last_checkin": "good",
                "voice_note": None,
                "possible_fall": False,
                "last_sync_time": time.strftime("%I:%M %p")
            }
        }

        # Seed 14 initial normal days so baseline is established immediately
        base_steps = senior_record["current_status"]["steps"]
        base_hr = senior_record["current_status"]["resting_hr"]
        for d in range(14):
            senior_record["vitals_history"].append({
                "day": d + 1,
                "steps": int(base_steps * (0.9 + (d % 3)*0.1)),
                "resting_hr": base_hr + (d % 4) - 2,
                "spo2": 98.0,
                "sleep_hours": 7.0 + (d % 2)*0.4,
                "wear_hours": 22,
                "battery": 80,
                "off_wrist": False,
                "meds_taken": True,
                "checkin": "good"
            })

        self.dynamic_seniors[senior_id] = senior_record
        print(f"Registered Senior {senior_id} ({senior_record['name']}) under {coord_code}")
        return senior_record

    def _ensure_current_status(self, senior: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures both cohort and dynamic seniors have a live mutable current_status dict."""
        if "current_status" not in senior:
            if senior.get("records"):
                senior["current_status"] = dict(senior["records"][79])
            else:
                senior["current_status"] = {}
        return senior["current_status"]

    @_persisted
    def update_senior_vitals(self, senior_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates live vitals from the watch/mobile app without overwriting resting_hr with active walk HR.
        Also appends to vitals_history so baseline naturally adapts.
        """
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}

        cur = self._ensure_current_status(senior)
        if data.get("steps") is not None:
            cur["steps"] = data["steps"]

        if data.get("heart_rate") is not None:
            cur["live_hr"] = data["heart_rate"]
            # Only update resting_hr if senior is at rest (e.g. steps < 50) or explicit resting_hr provided
            if data.get("resting_hr") is not None:
                cur["resting_hr"] = data["resting_hr"]
            elif cur.get("steps", 0) < 50:
                cur["resting_hr"] = data["heart_rate"]

        if data.get("spo2") is not None:
            cur["spo2"] = data["spo2"]
        if data.get("battery") is not None:
            cur["battery"] = data["battery"]
        if data.get("sleep_hours") is not None:
            cur["sleep_hours"] = data["sleep_hours"]
        if data.get("bp_sys") is not None and data.get("bp_dia") is not None:
            cur["bp_sys"], cur["bp_dia"] = data["bp_sys"], data["bp_dia"]
        if data.get("sugar") is not None:
            cur["sugar"] = data["sugar"]
        if data.get("weight") is not None:
            cur["weight"] = data["weight"]
        cur["data_source"] = data.get("source") or "watch"   # watch | demo | manual
        cur["last_sync_ts"] = time.time()

        cur["last_sync_time"] = time.strftime("%I:%M %p")
        senior["current_status"] = cur

        # Append/update vitals_history for dynamic senior so baseline evolves
        if senior.get("is_dynamic"):
            vh = senior.setdefault("vitals_history", [])
            today = time.strftime("%Y-%m-%d")
            entry = {
                "day": len(vh) + 1,
                "date": today,
                "steps": cur.get("steps", 0),
                "resting_hr": cur.get("resting_hr", 72),
                "spo2": cur.get("spo2", 98.0),
                "sleep_hours": cur.get("sleep_hours", 7.0),
                "wear_hours": 22,
                "battery": cur.get("battery", 90),
                "off_wrist": False,
                "meds_taken": cur.get("meds_taken", True),
                "checkin": cur.get("last_checkin", "good"),
                "bp_sys": cur.get("bp_sys"), "bp_dia": cur.get("bp_dia"),
                "sugar": cur.get("sugar"), "weight": cur.get("weight"),
            }
            if vh and vh[-1].get("date") == today:
                entry["day"] = vh[-1].get("day", len(vh))
                vh[-1] = entry          # same calendar day: update in place
            else:
                vh.append(entry)

        return {"status": "ok", "current": cur}

    @_persisted
    def record_checkin(self, senior_id: str, checkin_type: str, status: str, voice_text: str = None, emergency_sos: bool = False) -> Dict[str, Any]:
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}

        cur = self._ensure_current_status(senior)
        cur["last_checkin"] = status
        cur["last_checkin_type"] = checkin_type  # 'one_tap', 'missed_call', 'voice'

        # If senior explicitly reported feeling 'good' / 'theek', clear previous transient symptoms
        if status == "good" and not voice_text:
            cur["voice_note"] = None
            cur["possible_fall"] = False
        elif voice_text:
            cur["voice_note"] = voice_text
            cur["voice_note_time"] = time.time()

        cur["last_checkin_time"] = time.strftime("%I:%M %p")
        cur["last_checkin_date"] = time.strftime("%Y-%m-%d")
        senior["current_status"] = cur
        return {"status": "ok", "checkin": cur}

    @_persisted
    def record_medication(self, senior_id: str, action: str, med_name: str = None) -> Dict[str, Any]:
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}

        cur = self._ensure_current_status(senior)
        # action: 'taken', 'skipped', 'later'
        cur["last_med_action"] = action
        cur["last_med_time"] = time.strftime("%I:%M %p")

        if action == "taken":
            cur["meds_taken"] = True
            cur["consecutive_missed_doses"] = 0
        elif action == "later":
            # Deferred reminder: does NOT increment consecutive missed doses
            pass
        elif action == "skipped":
            cur["meds_taken"] = False
            cur["consecutive_missed_doses"] = cur.get("consecutive_missed_doses", 0) + 1

        senior["current_status"] = cur
        return {"status": "ok", "med_status": cur}

    # -------------------------------------------------------------
    # Medicine schedules and doses
    # -------------------------------------------------------------
    MISSED_AFTER_MIN = 30   # a dose with no answer this long after its time counts as missed

    @staticmethod
    def _hhmm(v: str) -> Optional[str]:
        try:
            hh, mm = [int(x) for x in str(v).strip().split(":")[:2]]
            assert 0 <= hh < 24 and 0 <= mm < 60
            return f"{hh:02d}:{mm:02d}"
        except Exception:
            return None

    def _senior(self, senior_id: str) -> Optional[Dict[str, Any]]:
        return self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)

    def list_medicines(self, senior_id: str) -> List[Dict[str, Any]]:
        return [m for m in self.medicines.get(senior_id, []) if m.get("active", True)]

    @_persisted
    def save_medicine(self, senior_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Adds a medicine, or updates it when data has an existing id. Only what the care manager types is stored:
        a name, the dose as written on the prescription, and the times of day."""
        if not self._senior(senior_id):
            return {"error": "Senior not found"}
        name = str(data.get("name") or "").strip()[:60]
        if not name:
            return {"error": "Medicine name is required"}
        times = sorted({t for t in (self._hhmm(x) for x in (data.get("times") or [])) if t})
        if not times:
            return {"error": "Add at least one time, like 08:00"}
        meds = self.medicines.setdefault(senior_id, [])
        med = next((m for m in meds if m["id"] == data.get("id")), None)
        if med is None:
            med = {"id": "MED-" + uuid.uuid4().hex[:8], "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "active": True}
            meds.append(med)
        med.update({"name": name, "dose_text": str(data.get("dose_text") or "").strip()[:80], "times": times,
                    "with_food": bool(data.get("with_food", False))})
        return {"status": "ok", "medicine": med}

    @_persisted
    def delete_medicine(self, senior_id: str, med_id: str) -> Dict[str, Any]:
        med = next((m for m in self.medicines.get(senior_id, []) if m["id"] == med_id), None)
        if not med:
            return {"error": "Medicine not found"}
        med["active"] = False                      # kept so the dose history still has a name
        return {"status": "ok"}

    @_persisted
    def record_dose(self, senior_id: str, med_id: str, dose_time: str, status: str, date: Optional[str] = None) -> Dict[str, Any]:
        """The senior's answer on the dose reminder: taken / skipped / later (later is only a snooze)."""
        if status not in ("taken", "skipped", "later"):
            return {"error": "Invalid status"}
        med = next((m for m in self.medicines.get(senior_id, []) if m["id"] == med_id), None)
        hhmm = self._hhmm(dose_time)
        if not med or not hhmm:
            return {"error": "Medicine or time not found"}
        day = date or time.strftime("%Y-%m-%d")
        if status != "later":
            self.dose_log = [d for d in self.dose_log if not (d["senior_id"] == senior_id and d["med_id"] == med_id
                                                             and d["date"] == day and d["time"] == hhmm)]
            self.dose_log.append({"senior_id": senior_id, "med_id": med_id, "date": day, "time": hhmm, "status": status,
                                  "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        self.record_medication(senior_id, status, med["name"])
        return {"status": "ok"}

    def dose_days(self, senior_id: str, days: int = 14) -> Dict[str, Any]:
        """For each active medicine and each of the last `days` days: every dose as taken / skipped / missed /
        due (not yet, today). Missed = no answer 30 minutes after its time."""
        meds = self.list_medicines(senior_id)
        log = {(d["med_id"], d["date"], d["time"]): d["status"] for d in self.dose_log if d["senior_id"] == senior_id}
        now = time.time()
        dates = [time.strftime("%Y-%m-%d", time.localtime(now - 86400 * i)) for i in range(days - 1, -1, -1)]
        out = []
        for m in meds:
            created = str(m.get("created_at", ""))[:16]
            rows = []
            for day in dates:
                cells = []
                for t in m["times"]:
                    st = log.get((m["id"], day, t))
                    if not st:
                        if f"{day} {t}" < created:     # added after this dose time
                            st = "none"
                        else:
                            due = time.mktime(time.strptime(f"{day} {t}", "%Y-%m-%d %H:%M")) + self.MISSED_AFTER_MIN * 60
                            st = "missed" if now > due else "due"
                    cells.append({"time": t, "status": st})
                rows.append({"date": day, "doses": cells})
            out.append({**{k: m[k] for k in ("id", "name", "dose_text", "times", "with_food")}, "days": rows})
        counted = [c["status"] for m in out for r in m["days"] for c in r["doses"] if c["status"] in ("taken", "skipped", "missed")]
        recent = [c["status"] for m in out for r in m["days"][-2:] for c in r["doses"] if c["status"] in ("taken", "skipped", "missed")]
        return {"dates": dates, "medicines": out,
                "adherence_pct": round(100 * counted.count("taken") / len(counted)) if counted else None,
                "missed_in_a_row": len(recent) >= 2 and all(x != "taken" for x in recent[-2:])}

    def today_doses(self, senior_id: str) -> List[Dict[str, Any]]:
        """Today's doses in time order, for the phone."""
        d = self.dose_days(senior_id, 1)
        rows = [{"med_id": m["id"], "name": m["name"], "dose_text": m["dose_text"], "with_food": m["with_food"],
                 "time": c["time"], "status": c["status"]} for m in d["medicines"] for c in m["days"][0]["doses"]]
        return sorted(rows, key=lambda r: r["time"])

    # -------------------------------------------------------------
    # Family and friends the senior can call with one tap
    # -------------------------------------------------------------
    def list_contacts(self, senior_id: str) -> List[Dict[str, Any]]:
        saved = list(self.contacts.get(senior_id, []))
        if saved:
            return saved
        s = self._senior(senior_id) or {}
        ec = str(s.get("emergency_contact") or "").strip()
        return [{"id": "emergency", "name": "", "relation": "Emergency contact", "phone": ec, "is_emergency": True}] if ec else []

    @_persisted
    def save_contact(self, senior_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._senior(senior_id):
            return {"error": "Senior not found"}
        name = str(data.get("name") or "").strip()[:40]
        phone = "".join(ch for ch in str(data.get("phone") or "") if ch.isdigit() or ch in "+ ").strip()[:20]
        if not name or sum(ch.isdigit() for ch in phone) < 6:
            return {"error": "Name and a phone number are required"}
        lst = self.contacts.setdefault(senior_id, [])
        c = next((x for x in lst if x["id"] == data.get("id")), None)
        if c is None:
            c = {"id": "CT-" + uuid.uuid4().hex[:8]}
            lst.append(c)
        c.update({"name": name, "relation": str(data.get("relation") or "").strip()[:30], "phone": phone,
                  "is_emergency": bool(data.get("is_emergency", False))})
        return {"status": "ok", "contact": c}

    @_persisted
    def delete_contact(self, senior_id: str, contact_id: str) -> Dict[str, Any]:
        lst = self.contacts.get(senior_id, [])
        if not any(c["id"] == contact_id for c in lst):
            return {"error": "Contact not found"}
        self.contacts[senior_id] = [c for c in lst if c["id"] != contact_id]
        return {"status": "ok"}

    def _ml_signal(self, senior: Dict[str, Any], records: List[Dict[str, Any]], cur: Dict[str, Any], baseline: Dict[str, Any]):
        """ML signal for today. Cohort seniors are scored by the cross-fit model that never saw them."""
        try:
            if not self.ml_model.ready:
                return None
            if not senior.get("is_dynamic") and senior.get("records") and len(senior["records"]) > 79:
                recs = list(senior["records"][:80])
                idx = 79
                sid = senior["senior_id"]
            elif len(records) >= 15:
                recs = list(records)
                idx = len(recs) - 1
                sid = None
            else:
                return None
            last = dict(recs[idx])
            if cur:
                last["checkin"] = cur.get("last_checkin") or last.get("checkin", "good")
                last["voice_note"] = cur.get("voice_note", last.get("voice_note"))
                last["meds_taken"] = cur.get("meds_taken", last.get("meds_taken", True))
                last["possible_fall"] = cur.get("possible_fall", last.get("possible_fall", False))
                for k in ("steps", "resting_hr", "spo2", "sleep_hours", "bp_sys", "bp_dia", "sugar", "weight"):
                    if cur.get(k) is not None:
                        last[k] = cur[k]
            recs[idx] = last
            return self.ml_model.score(build_features(recs, idx, baseline), sid)
        except Exception as e:  # the ML layer must never take the queue down
            print(f"[ML] skipped: {e}")
            return None

    def get_coordinator_seniors(self, coord_code: str) -> List[Dict[str, Any]]:
        """
        Returns ranked list of seniors for a specific coordinator with explainable scores.
        Uniformly scores live updates on both cohort and dynamic seniors.
        """
        coord_code = coord_code.upper()
        all_seniors = []
        for s in list(self.dynamic_seniors.values()) + list(self.seniors_map.values()):
            if s.get("coordinator_code") == coord_code:
                all_seniors.append(s)

        scored_seniors = []
        for s in all_seniors:
            # Extract live status & records
            if "current_status" in s:
                cur = s["current_status"]
                records = s.get("vitals_history") or s.get("records", [])[:80]
            elif s.get("is_dynamic"):
                records = s.get("vitals_history", [])
                cur = s.get("current_status", {})
            else:
                records = s.get("records", [])[:80]
                cur = records[79] if len(records) > 79 else (records[-1] if records else {})

            baseline = self.baseline_engine.compute_baseline(records[:40] if not s.get('is_dynamic') else records[:30])
            v_eval = self.baseline_engine.evaluate_daily_drift(cur, baseline, records[-5:])
            v_eval["possible_fall"] = cur.get("possible_fall", False)
            v_eval["current_spo2"] = cur.get("spo2", 98.0) or 98.0

            voice = cur.get("voice_note") or ""
            nlp_res = extract_symptom_cues(voice)

            # Medication data computation
            last_act = cur.get("last_med_action")
            if last_act == "later":
                consecutive_missed = 0
                weekly_adh = 0.90
            elif cur.get("meds_taken") is False:
                consecutive_missed = cur.get("consecutive_missed_doses", 1)
                weekly_adh = 0.60
            else:
                consecutive_missed = 0
                weekly_adh = 0.95

            med_data = {
                "consecutive_missed_doses": consecutive_missed,
                "weekly_adherence_rate": weekly_adh
            }
            chk_status = {
                "status": cur.get("last_checkin") or cur.get("checkin", "good"),
                "emergency_sos": self.active_sos(s["senior_id"]) is not None
            }

            ml_data = self._ml_signal(s, records, cur, baseline)
            eval_res = self.scorer_engine.calculate_daily_risk(s, v_eval, med_data, nlp_res, chk_status, ml_data)

            scored_seniors.append({
                "senior_id": s["senior_id"],
                "name": s["name"],
                "age": s["age"],
                "city": s["city"],
                "is_dynamic": s.get("is_dynamic", False),
                "is_planted": s.get("is_planted", False),
                "trajectory": s.get("trajectory", "stable"),
                "risk_score": eval_res["risk_score"],
                "tier": eval_res["tier"],
                "urgency": eval_res["urgency"],
                "confidence": eval_res["confidence"],
                "why_today_en": eval_res["why_today_en"],
                "why_today_hi": eval_res["why_today_hi"],
                "recommended_action_en": eval_res["recommended_action_en"],
                "recommended_action_hi": eval_res["recommended_action_hi"],
                "action_type": eval_res["action_type"],
                "current_vitals": {
                    "steps": cur.get("steps") if cur.get("steps") is not None else 0,
                    "resting_hr": cur.get("resting_hr") if cur.get("resting_hr") is not None else 0,
                    "live_hr": cur.get("live_hr") if cur.get("live_hr") is not None else cur.get("resting_hr", 0),
                    "spo2": cur.get("spo2") if cur.get("spo2") is not None else 98.0,
                    "sleep_hours": cur.get("sleep_hours") if cur.get("sleep_hours") is not None else 7.0,
                    "battery": cur.get("battery") if cur.get("battery") is not None else 85,
                    "last_sync": cur.get("last_sync_time", "Recently"),
                    "last_sync_ts": cur.get("last_sync_ts"),
                    "sync_age_s": (int(time.time() - cur["last_sync_ts"]) if cur.get("last_sync_ts") else None),
                    "source": cur.get("data_source") or ("synthetic" if not s.get("is_dynamic") else "none"),
                    "bp": (f"{int(cur['bp_sys'])}/{int(cur['bp_dia'])}" if cur.get("bp_sys") else None),
                    "sugar": cur.get("sugar"),
                    "weight": cur.get("weight"),
                },
                "sos": self._sos_summary(s["senior_id"]),
                "factors": eval_res["factors"],
                "ml": eval_res["ml"],
                "family_sharing": bool(s.get("family_sharing_consent")),
                "breakdown": eval_res["breakdown"]
            })

        # Sort by urgency: RED > ORANGE > YELLOW > GREEN, then by risk score descending
        tier_weights = {"RED": 4, "ORANGE": 3, "YELLOW": 2, "GREEN": 1}
        scored_seniors.sort(key=lambda x: (tier_weights.get(x["tier"], 0), x["risk_score"]), reverse=True)
        return scored_seniors

    @_persisted
    def record_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Records coordinator feedback and clears transient alert symptom flags upon resolution.
        """
        senior_id = action_data.get("senior_id")
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if senior and "current_status" in senior:
            # Symptoms cleared upon coordinator follow-up
            senior["current_status"]["voice_note"] = None
            senior["current_status"]["possible_fall"] = False

        log_entry = {
            "id": len(self.action_logs) + 1,
            "senior_id": senior_id,
            "coordinator_code": action_data.get("coordinator_code"),
            "action_taken": action_data.get("action_taken"),
            "outcome": action_data.get("outcome"),
            "feedback": action_data.get("feedback"),
            "notes": action_data.get("notes", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.action_logs.append(log_entry)
        if action_data.get("feedback") in ("useful", "not_useful"):
            for code in set(action_data.get("factor_codes") or []):
                row = self.feedback_stats.setdefault(code, {"useful": 0, "not_useful": 0})
                row[action_data["feedback"]] += 1
            self.apply_feedback_to_scorer()
        return {"status": "ok", "log": log_entry}

    def get_family_summary(self, senior_id: str) -> Dict[str, Any]:
        """
        Generates a warm, plain-language weekly summary for family members based on actual 7-day data.
        """
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}

        name = senior["name"]
        cur = self._ensure_current_status(senior)
        meds_ok = cur.get("meds_taken", True)

        history = senior.get("vitals_history") or senior.get("records", [])
        recent_7 = history[-7:] if len(history) >= 7 else history
        if recent_7:
            valid_steps = [d.get("steps", 0) for d in recent_7 if d.get("steps") is not None]
            avg_steps = int(sum(valid_steps) / max(len(valid_steps), 1))
            meds_count = sum(1 for d in recent_7 if d.get("meds_taken", True))
            adherence_rate = f"{int((meds_count / len(recent_7)) * 100)}%"
        else:
            avg_steps = cur.get("steps", 2500)
            adherence_rate = "95%" if meds_ok else "70%"

        summary_en = (
            f"{name} had an active week averaging around {avg_steps} daily steps. "
            f"Medications were taken consistently and daily check-ins were on time. "
            f"Overall wellbeing appears stable with no major concerns."
        ) if meds_ok else (
            f"{name} had a slightly slower week with some missed morning doses. "
            f"Care Coordinator {senior['coordinator_name']} is currently following up."
        )

        summary_hi = (
            f"{name} ji ka pichhla hafta theek raha, unhone lagbhag {avg_steps} kadam rozana chale aur dawayein niyamit li. "
            f"Care Coordinator unke niyamit sampark mein hain."
        ) if meds_ok else (
            f"{name} ji ka pichhla hafta thoda sust raha aur subah ki kuch dawayein chhoot gayi. "
            f"Care Coordinator {senior['coordinator_name']} unki dekhbhal kar rahe hain."
        )

        consent = senior.get("family_sharing_consent", True)

        return {
            "senior_id": senior_id,
            "name": name,
            "city": senior["city"],
            "consent_status": "Active (Senior Consented for Family Sharing)" if consent else "Pending Consent",
            "week_period": "Past 7 Days",
            "summary_en": summary_en,
            "summary_hi": summary_hi,
            "adherence_rate": adherence_rate,
            "avg_daily_steps": avg_steps,
            "coordinator_contact": senior["coordinator_name"]
        }

    # -------------------------------------------------------------
    # AI Voice Call Management
    # -------------------------------------------------------------
    @_persisted
    def initiate_call(self, senior_id: str, caller_type: str = "ai_health_check") -> Dict[str, Any]:
        """
        Creates an active call session record for a senior with a collision-free UUID.
        """
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}

        call_id = f"CALL-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
        call_record = {
            "call_id": call_id,
            "senior_id": senior_id,
            "senior_name": senior["name"],
            "coordinator_code": senior["coordinator_code"],
            "caller_name": "एजिस साथी AI स्वास्थ्य सहायक",
            "caller_type": caller_type,
            "status": "ringing",  # ringing, connected, completed, declined, missed, queued
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": None,
            "duration_seconds": 0,
            "transcript": [],
            "symptoms_reported": [],
            "meds_status": None,
            "escalation_flag": False
        }
        self.call_records.append(call_record)
        return {"status": "ok", "call": call_record}

    @_persisted
    def record_call_outcome(self, call_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes finished call: saves transcript, extracts NLP cues from SENIOR'S utterances only,
        updates meds and triage status.
        """
        record = next((c for c in self.call_records if c["call_id"] == call_id), None)
        senior_id = data.get("senior_id")
        if not record and senior_id:
            # Create on the fly if not initiated earlier
            senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
            record = {
                "call_id": call_id or f"CALL-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}",
                "senior_id": senior_id,
                "senior_name": senior["name"] if senior else "Senior",
                "coordinator_code": senior["coordinator_code"] if senior else "SAM-101",
                "caller_name": "एजिस साथी AI स्वास्थ्य सहायक",
                "caller_type": "ai_health_check",
                "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.call_records.append(record)

        if not record:
            return {"error": "Call record not found"}

        status = data.get("status", "completed")  # completed, declined, missed
        record["status"] = status
        record["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        record["duration_seconds"] = data.get("duration_seconds", 45)
        record["transcript"] = data.get("transcript", [])
        record["summary"] = data.get("summary", "")

        # Extract only senior's utterances for clinical NLP (AI's own questions are ignored)
        if isinstance(record["transcript"], list):
            senior_lines = [
                t.get("text", "") for t in record["transcript"]
                if isinstance(t, dict) and t.get("speaker", "").lower() in ["senior", "patient", "user"]
            ]
            if not senior_lines:
                # If no speaker field specified, exclude any line explicitly marked as 'ai'/'assistant'
                senior_lines = [
                    t.get("text", "") if isinstance(t, dict) else str(t)
                    for t in record["transcript"]
                    if not (isinstance(t, dict) and t.get("speaker", "").lower() in ["ai", "assistant", "system"])
                ]
            transcript_text = " ".join(senior_lines)
        else:
            transcript_text = str(record["transcript"])
        
        # NLP cue extraction from senior's words only
        extracted_cues = extract_symptom_cues(transcript_text)
        extracted_cues = extract_symptom_cues(transcript_text)
        detected_symptoms = extracted_cues.get("categories", [])
        record["symptoms_reported"] = detected_symptoms

        meds_taken = data.get("meds_taken")
        if meds_taken is not None:
            record["meds_status"] = "taken" if meds_taken else "skipped"
            self.record_medication(record["senior_id"], "taken" if meds_taken else "skipped")

        # Determine senior status for checkin record
        if status in ["missed", "not_answered"]:
            checkin_status = "weak"
            record["summary"] = record.get("summary") or "Call was not answered after 30 seconds of ringing."
        elif status == "declined":
            checkin_status = "weak"
            record["summary"] = record.get("summary") or "Senior declined call from lock screen."
        elif "chest_pain" in detected_symptoms or "fall" in detected_symptoms or "dizziness" in detected_symptoms or data.get("emergency"):
            checkin_status = "bad"
            record["escalation_flag"] = True
        elif detected_symptoms or (meds_taken is False):
            checkin_status = "weak"
        else:
            checkin_status = "good"

        # Auto-update senior checkin in store
        self.record_checkin(
            senior_id=record["senior_id"],
            checkin_type="ai_voice_call",
            status=checkin_status,
            voice_text=record["summary"] if status != "completed" else transcript_text[:200]
        )

        return {"status": "ok", "call": record}

    @_persisted
    def schedule_call(self, senior_id: str, schedule_time: str, recurring: bool = True) -> Dict[str, Any]:
        """
        Schedules a daily recurring or one-time AI check-in call at HH:MM (hub's local time). The hub's scheduler
        places it at that time (see due_schedules); a time already past today starts tomorrow.
        """
        senior = self.dynamic_seniors.get(senior_id) or self.seniors_map.get(senior_id)
        if not senior:
            return {"error": "Senior not found"}
        try:
            hh, mm = [int(x) for x in str(schedule_time).strip().split(":")[:2]]
            assert 0 <= hh < 24 and 0 <= mm < 60
        except Exception:
            return {"error": "Time must look like 09:30"}
        hhmm = f"{hh:02d}:{mm:02d}"
        if any(e for e in self.scheduled_calls if e.get("senior_id") == senior_id and e.get("status") == "active"
               and e.get("schedule_time") == hhmm):
            return {"error": "A call is already scheduled at that time"}
        entry = {
            "schedule_id": f"SCH-{uuid.uuid4().hex[:8].upper()}",
            "senior_id": senior_id,
            "senior_name": senior["name"],
            "schedule_time": hhmm,
            "recurring": recurring,
            "status": "active",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            # a time that has already passed today first fires tomorrow
            "last_fired": time.strftime("%Y-%m-%d") if hhmm <= time.strftime("%H:%M") else "",
            "last_call_id": None,
            "retries": 0,
        }
        self.scheduled_calls.append(entry)
        return {"status": "ok", "schedule": entry}

    def list_schedules(self, senior_id: str) -> List[Dict[str, Any]]:
        return sorted([e for e in self.scheduled_calls if e.get("senior_id") == senior_id and e.get("status") == "active"],
                      key=lambda e: e.get("schedule_time", ""))

    @_persisted
    def cancel_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        e = next((x for x in self.scheduled_calls if x.get("schedule_id") == schedule_id), None)
        if e:
            e["status"] = "cancelled"
        return e

    @_persisted
    def due_schedules(self) -> List[Dict[str, Any]]:
        """Schedules whose time has come today and that have not fired yet today; marks them fired."""
        today, now = time.strftime("%Y-%m-%d"), time.strftime("%H:%M")
        due = []
        for e in self.scheduled_calls:
            if e.get("status") != "active" or e.get("last_fired") == today:
                continue
            if e.get("schedule_time", "99:99") <= now:
                e["last_fired"] = today
                e["fired_at"] = time.time()
                e["retries"] = 0
                if not e.get("recurring", True):
                    e["status"] = "done"
                due.append(e)
        return due

    @_persisted
    def schedules_to_retry(self, after_s: int = 600) -> List[Dict[str, Any]]:
        """A scheduled call that went unanswered (missed, or the phone was offline) is tried once more after 10 min.
        A declined call is respected and not repeated."""
        out = []
        for e in self.scheduled_calls:
            if e.get("retries", 0) >= 1 or not e.get("last_call_id") or time.time() - e.get("fired_at", 0) < after_s:
                continue
            rec = self.get_call(e["last_call_id"])
            if rec and rec.get("status") in ("missed", "queued"):
                e["retries"] = 1
                e["fired_at"] = time.time()
                out.append(e)
        return out

    @_persisted
    def note_schedule_call(self, schedule_id: str, call_id: Optional[str]) -> None:
        e = next((x for x in self.scheduled_calls if x.get("schedule_id") == schedule_id), None)
        if e:
            e["last_call_id"] = call_id

    def pending_calls(self, senior_id: str, max_age_s: int = 600) -> List[Dict[str, Any]]:
        """Calls placed while the phone was offline (queued) in the last 10 minutes: ring them when it reconnects."""
        out = []
        for c in self.call_records:
            if c.get("senior_id") != senior_id or c.get("status") != "queued":
                continue
            try:
                age = time.time() - time.mktime(time.strptime(c["start_time"], "%Y-%m-%d %H:%M:%S"))
            except Exception:
                continue
            if age <= max_age_s:
                out.append(c)
        return out

    def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        return next((c for c in self.call_records if c["call_id"] == call_id), None)

    @_persisted
    def attach_call_notes(self, call_id: str, notes: Dict[str, Any], flags: List[Dict[str, str]]) -> None:
        """The language model's notes for a finished call: summary, mood, concerns, the encouragement given and a
        memory note for the next call. Flags raised during the call are kept; an urgent one escalates the call."""
        rec = self.get_call(call_id)
        if not rec:
            return
        notes = notes or {}
        from ai_agent.llm_agent import no_dashes
        for k in ("summary_en", "summary_hi", "encouragement", "memory_note"):
            if isinstance(notes.get(k), str):
                notes[k] = no_dashes(notes[k])
        notes["concerns"] = [no_dashes(str(c)) for c in (notes.get("concerns") or [])]
        for k in ("summary_en", "summary_hi"):
            if notes.get(k):
                rec["ai_" + k] = str(notes[k])[:800]
        if notes.get("mood") in ("good", "okay", "low", "distressed"):
            rec["mood"] = notes["mood"]
        rec["concerns"] = [str(c)[:160] for c in (notes.get("concerns") or [])][:6]
        rec["encouragement"] = str(notes.get("encouragement") or "")[:240]
        rec["memory_note"] = str(notes.get("memory_note") or "")[:240]
        if notes.get("meds_taken") is not None and not rec.get("meds_status"):
            rec["meds_status"] = "taken" if notes["meds_taken"] else "skipped"
        rec["flags"] = flags or []
        if any(f.get("urgency") == "urgent" for f in rec["flags"]) or rec.get("mood") == "distressed":
            rec["escalation_flag"] = True

    @_persisted
    def set_call_status(self, call_id: str, status: str) -> None:
        """Moves a still-open call (ringing/queued) to a new live status, e.g. 'connected'."""
        rec = self.get_call(call_id)
        if rec and rec.get("status") in ("ringing", "queued", "connected"):
            rec["status"] = status

    def get_call_history(self, senior_id: str) -> List[Dict[str, Any]]:
        """
        Returns all AI call records for a senior sorted recent first.
        """
        records = [c for c in self.call_records if c["senior_id"] == senior_id]
        records.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        return records
