"""
Aegis Saathi - honest evaluation on the synthetic cohort's PLANTED decline cases.

Definitions (all measured, nothing hard-coded):
  decline window     [decline_start_day, event_day)   event_day = decline_start + 12 days
                     = the point where, without help, the planted decline becomes an emergency.
  alert              risk score >= 45 (ORANGE or RED).
  detected           a planted senior has >= 1 alert inside their decline window.
  lead time          event_day - first alert day inside the window (days of warning).
  alert-day precision  alert days inside a decline window / all alert days.
  false episode      a run of consecutive alert days for one senior that never touches a decline
                     window. This is what a coordinator experiences as "a false alarm".
  false alarms / coordinator-week = false episodes / (coordinators x weeks in the window).
  precision@10       of the 10 highest scores on each day, how many are in a decline window.

The ML models are cross-fitted by senior (see ml_model.py), so no senior is scored by a model that
saw them. The same days are scored three ways so the value of each layer is visible.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from .baseline_drift import latest_value
from .ml_model import FEATURES, build_features
from .nlp_extractor import extract_symptom_cues
from .nlp_eval import evaluate as evaluate_nlp

ALERT_AT = 45
FIRST_DAY, LAST_DAY = 60, 89          # 0-based day indices scored (30 days)
N_COORDINATORS = 5


def day_inputs(records: List[Dict[str, Any]], idx: int, baseline_engine, baseline: Dict[str, Any]):
    """Everything the scorer needs for day idx, from data up to and including that day."""
    cur = records[idx]
    recent = records[max(0, idx - 4): idx + 1]
    v_eval = baseline_engine.evaluate_daily_drift(cur, baseline, recent)
    v_eval["possible_fall"] = cur.get("possible_fall", False)
    v_eval["current_spo2"] = cur.get("spo2") or 98
    nlp = extract_symptom_cues(cur.get("voice_note") or "")
    last3 = records[max(0, idx - 2): idx + 1]
    missed_streak = 0
    for r in reversed(last3):
        if r.get("meds_taken") is False:
            missed_streak += 1
        else:
            break
    week = records[max(0, idx - 6): idx + 1]
    adherence = sum(1 for r in week if r.get("meds_taken", True)) / max(len(week), 1)
    med = {"consecutive_missed_doses": missed_streak, "weekly_adherence_rate": adherence}
    chk = {"status": cur.get("checkin", "good"), "emergency_sos": False}
    return v_eval, med, nlp, chk


def _episodes(days: List[int]) -> List[List[int]]:
    out: List[List[int]] = []
    for d in sorted(days):
        if out and d == out[-1][-1] + 1:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def _summarise(per_senior: Dict[str, Dict[str, Any]], seniors: List[Dict[str, Any]], scores: Dict[str, Dict[int, float]]) -> Dict[str, Any]:
    planted = [s for s in seniors if s["is_planted"]]
    detected, leads = 0, []
    tp_days = fp_days = 0
    false_eps = 0
    all_eps = 0
    for s in seniors:
        sid = s["senior_id"]
        start, event = s.get("decline_start_day"), s.get("event_day")
        alert_days = [d for d, v in scores[sid].items() if v >= ALERT_AT]
        in_window = lambda d: start is not None and start <= d < event
        for d in alert_days:
            # alerts after the event day on a planted senior are neither credit nor blame
            if start is not None and d >= event:
                continue
            if in_window(d):
                tp_days += 1
            else:
                fp_days += 1
        for ep in _episodes([d for d in alert_days if not (start is not None and d >= event)]):
            all_eps += 1
            if not any(in_window(d) for d in ep):
                false_eps += 1
        if s["is_planted"]:
            hits = [d for d in alert_days if in_window(d)]
            if hits:
                detected += 1
                leads.append(event - min(hits))
    # precision@10 per day
    p10 = []
    for day in range(FIRST_DAY, LAST_DAY + 1):
        ranked = sorted(seniors, key=lambda s: -scores[s["senior_id"]].get(day, 0))[:10]
        hit = sum(1 for s in ranked if s["is_planted"] and s["decline_start_day"] <= day < s["event_day"])
        p10.append(hit / 10.0)
    weeks = (LAST_DAY - FIRST_DAY + 1) / 7.0
    n_pl = max(len(planted), 1)
    return {
        "recall_pct": round(100 * detected / n_pl, 1),
        "detected": detected, "planted": len(planted),
        "median_lead_days": round(float(np.median(leads)), 1) if leads else 0.0,
        "mean_lead_days": round(float(np.mean(leads)), 1) if leads else 0.0,
        "alert_day_precision_pct": round(100 * tp_days / max(tp_days + fp_days, 1), 1),
        "precision_at_10_pct": round(100 * float(np.mean(p10)), 1),
        "alert_episodes": all_eps, "false_episodes": false_eps,
        "false_alarms_per_coordinator_week": round(false_eps / (N_COORDINATORS * weeks), 2),
    }


def evaluate_all(cohort: Dict[str, Any], baseline_engine, scorer, ml_model) -> Dict[str, Any]:
    seniors = cohort["seniors"]
    rules: Dict[str, Dict[int, float]] = {}
    fused: Dict[str, Dict[int, float]] = {}
    mlonly: Dict[str, Dict[int, float]] = {}
    usable = total = 0
    # 1) features for every scored day, 2) one batched ML call, 3) scoring with and without the ML signal
    meta, feats, inputs = [], [], []
    for s in seniors:
        sid, recs = s["senior_id"], s["records"]
        baseline = baseline_engine.compute_baseline(recs[:40])
        rules[sid], fused[sid], mlonly[sid] = {}, {}, {}
        for idx in range(FIRST_DAY, LAST_DAY + 1):
            v_eval, med, nlp, chk = day_inputs(recs, idx, baseline_engine, baseline)
            total += 1
            usable += 1 if v_eval.get("is_usable", True) else 0
            f = build_features(recs, idx, baseline)
            meta.append((s, idx))
            feats.append(f if f is not None else np.zeros(len(FEATURES)))
            inputs.append((v_eval, med, nlp, chk, f is not None))
    ml_results = ml_model.score_batch(np.vstack(feats), [m[0]["senior_id"] for m in meta])
    for (s, idx), (v_eval, med, nlp, chk, has_f), ml in zip(meta, inputs, ml_results):
        sid = s["senior_id"]
        if not has_f:
            ml = {"available": False, "prob": 0.0, "anomaly": 0.0, "score": 0.0, "top": []}
        rules[sid][idx] = scorer.calculate_daily_risk(s, v_eval, med, nlp, chk, None)["risk_score"]
        fused[sid][idx] = scorer.calculate_daily_risk(s, v_eval, med, nlp, chk, ml)["risk_score"]
        mlonly[sid][idx] = 100.0 * ml["score"] if ml.get("available") else 0.0

    variants = {
        "rules_only": _summarise({}, seniors, rules),
        "ml_only": _summarise({}, seniors, {k: {d: (100.0 if v >= 60 else 0.0) for d, v in dv.items()} for k, dv in mlonly.items()}),
        "combined": _summarise({}, seniors, fused),
    }
    head = variants["combined"]
    nlp = evaluate_nlp()
    return {
        "window": f"days {FIRST_DAY + 1}-{LAST_DAY + 1} of 90",
        "alert_threshold": ALERT_AT,
        "variants": variants,
        "headline": head,
        "nlp": nlp,
        "ml_training": ml_model.train_info,
        "data_quality_coverage_pct": round(100 * usable / max(total, 1), 1),
        "caveats": [
            "Measured on a simulated validation cohort (250 people, 90 days each) with 30 known decline cases across five clinical patterns. Real-world accuracy is tracked separately once a deployment has outcomes.",
            "With 30 decline cases, each case moves the catch rate by about 3 points: read the percentages as indicative, not exact.",
            "The pattern model is cross-fitted by person, so nobody is scored by a model that was trained on their own data.",
            "Symptom understanding is measured on 58 hand-written Hindi, Hinglish and English sentences kept apart from the training notes; a small set, so the score is likely optimistic.",
            "The pattern model's weight in the combined score was tuned on this same cohort, which makes the combined figures somewhat optimistic until re-measured on new data.",
        ],
        # flat keys kept for the dashboard's existing tiles
        "recall_percentage": head["recall_pct"],
        "precision_at_10": head["precision_at_10_pct"],
        "median_lead_time_days": head["median_lead_days"],
        "planted_cases_total": head["planted"],
        "planted_cases_detected": head["detected"],
        "false_alerts_per_coordinator_week": head["false_alarms_per_coordinator_week"],
        "alert_action_rate": None,   # filled from real coordinator actions by the store
    }
