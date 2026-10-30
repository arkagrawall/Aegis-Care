"""
Aegis Saathi - Personal Baseline & Drift Engine (rules layer)

Every senior is compared with THEIR OWN normal (robust median / std over a baseline window), never
with a population average. Output is a list of structured "factors", each with plain-language English
and Hindi text and the number of risk points it added, so the dashboard can show exactly why.

Vitals covered: steps, resting heart rate, SpO2, sleep, blood pressure, blood sugar, weight.
The language is deliberately non-diagnostic: "above personal normal", never "has hypertension".
"""

import numpy as np
from typing import Dict, List, Any, Optional

TARGET_KEYS = ["steps", "resting_hr", "spo2", "sleep_hours", "bp_sys", "bp_dia", "sugar", "weight"]


def latest_value(key: str, current_day: Dict[str, Any], recent_history: Optional[List[Dict[str, Any]]], window: int = 7):
    """Newest non-missing value of `key` in the last `window` days (BP/sugar/weight are not measured daily)."""
    v = current_day.get(key)
    if v is not None:
        return v
    for d in reversed((recent_history or [])[-window:]):
        if d.get(key) is not None:
            return d[key]
    return None


class PersonalBaselineEngine:
    def __init__(self, baseline_days: int = 14):
        self.baseline_days = baseline_days

    # ------------------------------------------------------------------ baseline
    def compute_baseline(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Robust personal normal (median, std, IQR) per metric from a window of days."""
        if not history:
            return {"has_sufficient_baseline": False, "days_available": 0, "metrics": {}}

        n_days = len(history)
        metrics_summary: Dict[str, Any] = {}
        for key in TARGET_KEYS:
            raw = [d[key] for d in history if key in d and d[key] is not None]
            if key == "steps":
                raw = [v for v in raw if v > 50]
            if key in ("resting_hr", "spo2", "sleep_hours"):
                raw = [v for v in raw if v > 0]
            if len(raw) >= 3:
                arr = np.array(raw, dtype=float)
                std = float(np.std(arr))
                q25, q75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
                metrics_summary[key] = {
                    "median": round(float(np.median(arr)), 1),
                    "std": round(std if std > 0 else 1.0, 2),
                    "iqr": round(max(q75 - q25, 1.0), 2),
                    "sample_count": len(arr),
                }
        return {"has_sufficient_baseline": n_days >= 7, "days_available": n_days, "metrics": metrics_summary}

    # ------------------------------------------------------------------ daily evaluation
    def evaluate_daily_drift(self, current_day: Dict[str, Any], baseline: Dict[str, Any],
                             recent_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        steps = current_day.get("steps") or 0
        hr = current_day.get("resting_hr") or 0
        wear_hours = current_day.get("wear_hours", 24)
        battery = current_day.get("battery", 100)
        if battery is None:
            battery = 100

        # Data quality: a watch lying on the table must not raise an alarm
        is_off_wrist = (steps < 50 and (hr == 0 or (wear_hours or 0) < 4)) or current_day.get("off_wrist", False)
        is_stale = current_day.get("data_stale", False) or battery <= 5
        if is_off_wrist or is_stale:
            msg_en = "Watch off-wrist or discharged. Alerts from watch data are paused to avoid a false alarm."
            msg_hi = "घड़ी उतरी हुई है या बंद है। झूठे अलर्ट से बचने के लिए घड़ी के आँकड़ों पर अलर्ट रोके गए हैं।"
            return {
                "data_quality_flag": "off_wrist" if is_off_wrist else "stale_battery",
                "is_usable": False, "deviation_score": 0.0,
                "contributing_factors": [msg_en],
                "factors": [{"code": "data_quality", "en": msg_en, "hi": msg_hi, "points": 0.0}],
                "z_scores": {},
            }

        if not baseline.get("has_sufficient_baseline", False):
            msg_en = "Still learning this person's normal (less than 7 days of data)."
            msg_hi = "इनका सामान्य अभी सीख रहे हैं (7 दिन से कम का डेटा)।"
            return {
                "data_quality_flag": "insufficient_baseline", "is_usable": True, "deviation_score": 5.0,
                "contributing_factors": [msg_en],
                "factors": [{"code": "learning", "en": msg_en, "hi": msg_hi, "points": 5.0}],
                "z_scores": {},
            }

        b = baseline.get("metrics", {})
        z: Dict[str, float] = {}
        factors: List[Dict[str, Any]] = []

        # Corroboration: steps / heart rate / sleep use the average of today and yesterday, so one bad
        # night or one long walk does not raise an alert. Oxygen is NOT smoothed (safety signal).
        prev = (recent_history or [])[-2] if recent_history and len(recent_history) >= 2 else None
        if recent_history and recent_history[-1] is not current_day:
            prev = recent_history[-1]
        def smooth(key, today):
            if prev is not None and not prev.get("off_wrist") and (prev.get(key) or 0) > (50 if key == "steps" else 0):
                if today:
                    return (today + prev[key]) / 2.0
            return today
        steps = smooth("steps", steps)
        hr = smooth("resting_hr", hr)

        def add(code, en, hi, pts):
            factors.append({"code": code, "en": en, "hi": hi, "points": round(float(pts), 1)})

        # ---- steps: mobility / frailty
        if "steps" in b and steps > 0:
            med = b["steps"]["median"]
            std = max(b["steps"]["std"], 300.0)
            zs = (steps - med) / std
            z["steps"] = round(zs, 2)
            if zs < -1.8:
                drop = max(min(int(round((med - steps) / med * 100)), 95), 10)
                add("steps_drop",
                    f"Steps are {drop}% below their normal ({int(round(steps)):,} vs usual {int(med):,})",
                    f"कदम सामान्य से {drop}% कम ({int(round(steps)):,} बनाम {int(med):,})",
                    min(abs(zs) * 8.0, 25.0))

        # ---- resting heart rate
        if "resting_hr" in b and hr > 35:
            med = b["resting_hr"]["median"]
            std = max(b["resting_hr"]["std"], 3.0)
            zh = (hr - med) / std
            z["resting_hr"] = round(zh, 2)
            if zh > 1.8:
                add("hr_high", f"Resting heart rate is {int(hr - med)} beats above their normal ({int(hr)} vs {int(med)})",
                    f"आराम की धड़कन सामान्य से {int(hr - med)} ज़्यादा ({int(hr)} बनाम {int(med)})", min(zh * 9.0, 30.0))
            elif zh < -2.2:
                add("hr_low", f"Resting heart rate is unusually low ({int(hr)} vs normal {int(med)})",
                    f"आराम की धड़कन असामान्य रूप से कम ({int(hr)} बनाम {int(med)})", 15.0)

        # ---- oxygen
        spo2 = current_day.get("spo2") or 0
        if "spo2" in b and spo2 > 70:
            med = b["spo2"]["median"]
            zo = (spo2 - med) / 1.5
            z["spo2"] = round(zo, 2)
            if spo2 < 92.0 or zo < -2.0:
                add("spo2_low", f"Oxygen level is low at {spo2}% (their normal is {med}%)",
                    f"ऑक्सीजन {spo2}% है, कम (इनका सामान्य {med}%)", 35.0)

        # ---- sleep
        sleep = smooth("sleep_hours", current_day.get("sleep_hours") or 0)
        if "sleep_hours" in b and sleep > 0:
            med = b["sleep_hours"]["median"]
            zsl = (sleep - med) / max(b["sleep_hours"]["std"], 1.0)
            z["sleep_hours"] = round(zsl, 2)
            if zsl < -1.8:
                add("sleep_low", f"Sleep dropped to {sleep:.1f} hours (usual {med:.1f})",
                    f"नींद घटकर {sleep:.1f} घंटे रह गई (सामान्य {med:.1f})", 12.0)

        # ---- blood pressure (not measured daily: use the newest reading from the last 7 days)
        sys_v = latest_value("bp_sys", current_day, recent_history)
        dia_v = latest_value("bp_dia", current_day, recent_history)
        if sys_v is not None and dia_v is not None:
            if sys_v >= 160 or dia_v >= 100:
                add("bp_very_high", f"Blood pressure reading is very high ({int(sys_v)}/{int(dia_v)})",
                    f"ब्लड प्रेशर रीडिंग बहुत ऊँची ({int(sys_v)}/{int(dia_v)})", 20.0)
            elif "bp_sys" in b:
                med = b["bp_sys"]["median"]
                zb = (sys_v - med) / max(b["bp_sys"]["std"], 7.0)
                z["bp_sys"] = round(zb, 2)
                if zb > 2.0:
                    add("bp_high", f"Blood pressure {int(sys_v)}/{int(dia_v)} is well above their normal (top number ~{int(med)})",
                        f"ब्लड प्रेशर {int(sys_v)}/{int(dia_v)}, इनके सामान्य (ऊपर का ~{int(med)}) से काफ़ी ज़्यादा", 12.0)
                elif sys_v < 95 and med >= 108:
                    add("bp_low", f"Blood pressure {int(sys_v)}/{int(dia_v)} is lower than their normal (~{int(med)})",
                        f"ब्लड प्रेशर {int(sys_v)}/{int(dia_v)}, इनके सामान्य (~{int(med)}) से कम", 15.0)

        # ---- blood sugar
        sugar = latest_value("sugar", current_day, recent_history)
        if sugar is not None:
            if sugar < 70:
                add("sugar_low", f"Blood sugar reading is low ({int(sugar)} mg/dL)",
                    f"शुगर रीडिंग कम ({int(sugar)} mg/dL)", 25.0)
            elif sugar >= 200:
                add("sugar_very_high", f"Blood sugar reading is very high ({int(sugar)} mg/dL)",
                    f"शुगर रीडिंग बहुत ज़्यादा ({int(sugar)} mg/dL)", 20.0)
            elif "sugar" in b:
                med = b["sugar"]["median"]
                zg = (sugar - med) / max(b["sugar"]["std"], 10.0)
                z["sugar"] = round(zg, 2)
                if zg > 2.2:
                    add("sugar_high", f"Blood sugar {int(sugar)} is well above their normal (~{int(med)})",
                        f"शुगर {int(sugar)}, इनके सामान्य (~{int(med)}) से काफ़ी ज़्यादा", 10.0)

        # ---- weight: slow unplanned loss is an early frailty / appetite signal
        weight = latest_value("weight", current_day, recent_history, window=14)
        if weight is not None and "weight" in b:
            med = b["weight"]["median"]
            change = (weight - med) / med * 100.0
            z["weight_pct"] = round(change, 1)
            if change <= -3.0:
                add("weight_loss", f"Weight is {abs(change):.1f}% below their usual ({weight} kg vs {med} kg)",
                    f"वज़न सामान्य से {abs(change):.1f}% कम ({weight} किलो बनाम {med} किलो)", min(abs(change) * 3.0, 15.0))

        # ---- sustained multi-day decline in activity
        if recent_history and len(recent_history) >= 3:
            recent = [d.get("steps", 0) or 0 for d in recent_history[-5:] if (d.get("steps", 0) or 0) > 50]
            if len(recent) >= 3 and all(recent[i] <= recent[i - 1] * 1.05 for i in range(1, len(recent))):
                if recent[-1] < b.get("steps", {}).get("median", 1000) * 0.7:
                    add("activity_decline", f"Activity has been falling steadily for {len(recent)} days",
                        f"पिछले {len(recent)} दिनों से गतिविधि लगातार घट रही है", 15.0)

        deviation = min(sum(f["points"] for f in factors), 50.0)
        return {
            "data_quality_flag": "good", "is_usable": True,
            "deviation_score": round(deviation, 1),
            "contributing_factors": [f["en"] for f in factors],
            "factors": factors,
            "z_scores": z,
        }
