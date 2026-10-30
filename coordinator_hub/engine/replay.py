"""
"Saathi saw it coming": replays one simulated decline case day by day, scored exactly as the evaluation scores it
(rules + drift + medicines + call words + the cross-fitted pattern model), so the portal can show the risk rising and
the first alert landing days before the emergency the simulation planted.
"""
from typing import Any, Dict, List

import numpy as np

from .evaluation import ALERT_AT, day_inputs
from .ml_model import FEATURES, build_features

TRAJ = {
    "frailty_drift": ("Slow frailty: walking less, sleeping badly", "धीरे-धीरे कमज़ोरी: कम चलना, ख़राब नींद"),
    "infection_respiratory": ("Chest infection building up", "छाती का संक्रमण बढ़ना"),
    "medication_failure": ("Medicines stopped working / being missed", "दवाइयाँ छूटना या असर न करना"),
    "fall_event": ("Unsteady, then a fall", "लड़खड़ाना, फिर गिरना"),
    "cognitive_withdrawal": ("Withdrawing: quieter, more confused", "चुप रहना, उलझन बढ़ना"),
}


def _score_days(store, s: Dict[str, Any], days: List[int]) -> List[Dict[str, Any]]:
    recs = s["records"]
    baseline = store.baseline_engine.compute_baseline(recs[:40])
    inputs, feats = [], []
    for idx in days:
        inputs.append(day_inputs(recs, idx, store.baseline_engine, baseline))
        f = build_features(recs, idx, baseline)
        feats.append((f if f is not None else np.zeros(len(FEATURES)), f is not None))
    mls = store.ml_model.score_batch(np.vstack([f for f, _ in feats]), [s["senior_id"]] * len(days))
    out = []
    for idx, (v_eval, med, nlp, chk), (_, has_f), ml in zip(days, inputs, feats, mls):
        if not has_f:
            ml = {"available": False, "prob": 0.0, "anomaly": 0.0, "score": 0.0, "top": []}
        r = store.scorer_engine.calculate_daily_risk(s, v_eval, med, nlp, chk, ml)
        out.append((idx, r))
    return out


def cases(store) -> List[Dict[str, Any]]:
    """Every planted decline case, with how many days early the alert came (cheap: scores only the window)."""
    rows = []
    for s in store.cohort["seniors"]:
        if not s.get("is_planted") or s.get("event_day") is None:
            continue
        ev, start = s["event_day"], s["decline_start_day"]
        scored = _score_days(store, s, list(range(start, min(ev, len(s["records"])))))
        alert = next((i for i, r in scored if r["risk_score"] >= ALERT_AT), None)
        en, hi = TRAJ.get(s.get("trajectory"), (s.get("trajectory", ""), s.get("trajectory", "")))
        rows.append({"senior_id": s["senior_id"], "name": s["name"], "age": s.get("age"), "city": s.get("city"),
                     "pattern_en": en, "pattern_hi": hi, "lead_days": (ev - alert) if alert is not None else None})
    rows.sort(key=lambda r: -(r["lead_days"] or -1))
    return rows


def replay(store, senior_id: str) -> Dict[str, Any]:
    s = next((x for x in store.cohort["seniors"] if x["senior_id"] == senior_id), None)
    if not s or not s.get("is_planted"):
        return {"error": "Not a decline case"}
    recs, ev, start = s["records"], s["event_day"], s["decline_start_day"]
    first, last = max(41, start - 10), min(len(recs) - 1, ev)
    days = []
    for idx, r in _score_days(store, s, list(range(first, last + 1))):
        rec = recs[idx]
        days.append({
            "day": idx - ev,                               # 0 = the day the emergency would have happened
            "risk": round(r["risk_score"]), "tier": r["tier"],
            "why_en": r["why_today_en"][:3], "why_hi": r["why_today_hi"][:3],
            "steps": rec.get("steps"), "sleep": rec.get("sleep_hours"), "hr": rec.get("resting_hr"),
            "spo2": rec.get("spo2"), "meds": rec.get("meds_taken", True), "said": rec.get("voice_note") or "",
        })
    alert = next((d for d in days if d["day"] >= start - ev and d["risk"] >= ALERT_AT), None)
    en, hi = TRAJ.get(s.get("trajectory"), (s.get("trajectory", ""), s.get("trajectory", "")))
    return {"senior_id": senior_id, "name": s["name"], "age": s.get("age"), "city": s.get("city"),
            "pattern_en": en, "pattern_hi": hi, "alert_at": ALERT_AT, "decline_day": start - ev,
            "alert_day": alert["day"] if alert else None, "lead_days": -alert["day"] if alert else None, "days": days,
            "note": "A simulated decline case from the validation cohort, scored day by day exactly as the evaluation scores it."}
