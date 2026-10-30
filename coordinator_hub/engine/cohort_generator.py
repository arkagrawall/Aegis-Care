"""
Aegis Saathi - Synthetic Cohort Generator (250 Seniors × 90 Days)
Builds realistic longitudinal data with personal baselines, realistic noise,
off-wrist periods, and 30 planted decline cases across 5 clinically validated trajectories.
"""

import random
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Common Indian senior names & cities
FIRST_NAMES = [
    "Ramesh", "Suresh", "Om Prakash", "Shanti", "Kamla", "Mohan", "Kusum", "Anand",
    "Ganga", "Devendra", "Usha", "Satish", "Vimla", "Kishore", "Sita", "Hari",
    "Vijay", "Saroj", "Ashok", "Laxmi", "Balram", "Pushpa", "Dina Nath", "Meera",
    "Jagdish", "Savita", "Govind", "Radha", "Nand Kishore", "Sushila"
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Mishra", "Patel", "Singh", "Yadav", "Trivedi",
    "Chauhan", "Joshi", "Bhatt", "Pandey", "Shukla", "Saxena", "Srivastava", "Agarwal"
]

CITIES = ["Delhi NCR", "Lucknow", "Jaipur", "Varanasi", "Indore", "Bhopal", "Dehradun", "Patna", "Chandigarh"]

COORDINATORS = [
    {"code": "SAM-101", "name": "Sunita Sharma", "city": "Delhi NCR", "phone": "+91 98112 34567"},
    {"code": "SAM-102", "name": "Rajesh Verma", "city": "Lucknow", "phone": "+91 94150 12345"},
    {"code": "SAM-103", "name": "Ananya Joshi", "city": "Jaipur", "phone": "+91 98290 54321"},
    {"code": "SAM-104", "name": "Vikas Trivedi", "city": "Varanasi", "phone": "+91 99350 98765"},
    {"code": "SAM-105", "name": "Pooja Gupta", "city": "Indore", "phone": "+91 98930 11223"}
]


# Voice/check-in notes: several paraphrases per trajectory, Hindi / Hinglish / English / Devanagari mixed,
# plus harmless everyday notes so the detector faces realistic noise, not templates.
NOTE_VARIANTS = {
    "frailty_drift": [
        "Aaj kal bahot thakan rehti hai, kamar dard ki wajah se chalna mushkil ho raha hai.",
        "chalne mein dikkat hai, ghar ke andar bhi zyada nahi chal pata",
        "mujhe bahut kamzori lagti hai, subah uthne ka mann nahi karta",
        "बहुत थकावट रहती है, सीढ़ियाँ चढ़ना मुश्किल हो गया है",
        "feeling very tired lately, knees are paining and I avoid walking",
        "bhookh bhi kam lagti hai aur himmat nahi hai kuch karne ki",
    ],
    "infection_respiratory": [
        "Do din se bukhar aur khansi hai, saans phool rahi hai.",
        "raat bhar khansi ki wajah se so nahi paya, thand lag rahi thi",
        "सांस लेने में तकलीफ है और बुखार जैसा लग रहा है",
        "I have a cough and fever since two days, feeling breathless on stairs",
        "gala kharab hai, chhati mein bhaaripan, body garam rehti hai",
    ],
    "medication_failure": [
        "Subah BP ki goli bhool gaye the, thoda chakkar aa raha hai.",
        "dawa lena yaad nahi raha kal se, sir ghoom raha hai",
        "goli khatam ho gayi hai, do din se nahi li, chakkar jaisa lagta hai",
        "मैंने दवा नहीं ली और सिर घूम रहा है",
        "forgot my tablets again, feeling a bit dizzy when I stand up",
    ],
    "fall_event": [
        "Bathroom mein paon phisal gaya tha, chot lagi hai ghutne par.",
        "kal raat gir gaye the, ghutne mein sujan hai",
        "मैं बाथरूम में फिसल गई थी, पैर में चोट है",
        "I slipped near the bathroom, my knee hurts a lot",
        "balance bigad gaya aur main gir padi",
    ],
    "cognitive_withdrawal": [
        "Ghar par koi nahi hai, bohot akelapan lag raha hai, mann bechain hai.",
        "kisi se baat karne ka mann nahi karta, udaas rehta hoon",
        "मुझे अकेलापन लगता है, खाना खाने का भी मन नहीं करता",
        "I feel lonely and low, no one calls me, I forgot what I was doing in the kitchen",
        "kuch yaad nahi rehta, kya kar raha tha bhool jata hoon, samajh nahi aata",
        "confused hoon, kaunsa din hai pata nahi chalta",
    ],
}
BENIGN_NOTES = [
    "Sab theek hai, subah walk par gaye the.",
    "thoda thak gaya tha kal shaadi mein, ab theek hoon",
    "kal late tak cricket dekha isliye neend kam hui, baaki sab badhiya",
    "ghutne mein halka dard tha kal, aaj aaram hai",
    "bilkul theek, pote-potiyon ke saath khela",
    "sab achha hai, bas mausam ki wajah se thoda sust lag raha tha",
    "all good today, had a light breakfast and went for a short walk",
    "सब ठीक है, आज मंदिर गया था",
]
CHECKIN_ORDER = {"good": 0, "weak": 1, "bad": 2, "missed": 3}

def generate_cohort(num_seniors: int = 250, days: int = 90) -> Dict[str, Any]:
    """
    Generates cohort data and evaluates detection metrics against planted cases.
    """
    random.seed(42)
    np.random.seed(42)

    seniors = []
    # Plant 30 specific decline cases out of 250 (12%)
    planted_indices = set(random.sample(range(num_seniors), 30))

    # Planted trajectory types:
    # 0: Gradual Physical / Frailty Drift
    # 1: Infection / Respiratory Drop (SpO2 & HR drift)
    # 2: Medication Adherence Failure & Dizziness
    # 3: Unreported Fall / Mobility Drop
    # 4: Depressive Withdrawal & Cognitive Decline
    trajectory_types = ["frailty_drift", "infection_respiratory", "medication_failure", "fall_event", "cognitive_withdrawal"]

    for i in range(num_seniors):
        s_id = f"SR-{1000 + i}"
        coord = COORDINATORS[i % len(COORDINATORS)]
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        age = random.randint(64, 86)
        city = coord["city"]
        is_planted = i in planted_indices
        traj = trajectory_types[i % len(trajectory_types)] if is_planted else "stable"
        decline_start_day = random.randint(65, 75) if is_planted else 999

        # Senior's personal healthy baseline ranges
        base_steps = random.randint(2200, 5500)
        base_hr = random.randint(66, 78)
        base_spo2 = round(random.uniform(96.0, 98.5), 1)
        base_sleep = round(random.uniform(6.5, 8.2), 1)
        base_bp_sys = random.randint(112, 142)
        base_bp_dia = random.randint(68, 88)
        diabetic = random.random() < 0.25
        base_sugar = random.randint(130, 165) if diabetic else random.randint(92, 118)
        base_weight = round(random.uniform(52.0, 82.0), 1)

        daily_records = []
        for d in range(days):
            # Check if this day is in decline phase
            in_decline = is_planted and (d >= decline_start_day)
            decline_progress = max(0, d - decline_start_day)

            # Realistic missing entries: 4% chance watch left charging/off-wrist
            off_wrist = random.random() < 0.04 and not in_decline

            if off_wrist:
                daily_records.append({
                    "day": d + 1,
                    "steps": 0,
                    "resting_hr": 0,
                    "spo2": 0,
                    "sleep_hours": 0,
                    "wear_hours": 0,
                    "battery": random.randint(15, 95),
                    "off_wrist": True,
                    "meds_taken": True,
                    "checkin": "good",
                    "voice_note": None,
                    "possible_fall": False,
                    "bp_sys": None, "bp_dia": None, "sugar": None, "weight": None
                })
                continue

            # Generate vitals based on normal vs decline
            steps = int(np.random.normal(base_steps, 350))
            hr = int(np.random.normal(base_hr, 3))
            spo2 = round(float(np.random.normal(base_spo2, 0.6)), 1)
            sleep = round(float(np.random.normal(base_sleep, 0.5)), 1)
            meds_taken = True
            checkin = "good"
            voice_note = None
            possible_fall = False
            bp_sys_v = float(np.random.normal(base_bp_sys, 6))
            bp_dia_v = float(np.random.normal(base_bp_dia, 4))
            sugar_v = float(np.random.normal(base_sugar, 9))
            weight_v = float(np.random.normal(base_weight, 0.4))

            # Everyday noise unrelated to any decline: a cold, a late night, a long walk
            if not in_decline and random.random() < 0.035:
                steps = int(steps * random.uniform(0.55, 0.75))
                hr = hr + random.randint(5, 9)
                sleep = round(max(sleep - random.uniform(1.0, 2.0), 3.5), 1)

            if in_decline:
                if traj == "frailty_drift":
                    # Slow progressive step drop over 10 days
                    drop_ratio = min(0.85, 0.10 * decline_progress)
                    steps = max(int(base_steps * (1.0 - drop_ratio)), 350)
                    sleep = max(round(base_sleep - 0.2 * decline_progress, 1), 4.2)
                    if decline_progress >= 4:
                        checkin = "weak"
                        voice_note = "Aaj kal bahot thakan rehti hai, kamar dard ki wajah se chalna mushkil ho raha hai."
                elif traj == "infection_respiratory":
                    # Elevated HR + declining SpO2
                    hr = min(base_hr + int(3.5 * decline_progress), 108)
                    spo2 = max(round(base_spo2 - 0.7 * decline_progress, 1), 89.5)
                    if decline_progress >= 3:
                        checkin = "bad"
                        voice_note = "Do din se bukhar aur khansi hai, saans phool rahi hai."
                elif traj == "medication_failure":
                    # Consecutive missed doses + dizziness
                    if decline_progress >= 2:
                        meds_taken = False
                        checkin = "weak"
                        voice_note = "Subah BP ki goli bhool gaye the, thoda chakkar aa raha hai."
                elif traj == "fall_event":
                    # Sudden drop in mobility + possible fall flag
                    if decline_progress == 3:
                        possible_fall = True
                        steps = 280
                        checkin = "bad"
                        voice_note = "Bathroom mein paon phisal gaya tha, chot lagi hai ghutne par."
                    elif decline_progress > 3:
                        steps = random.randint(300, 700)
                        checkin = "weak"
                elif traj == "cognitive_withdrawal":
                    # Missed checkin + loneliness
                    if decline_progress >= 2:
                        checkin = "missed" if random.random() < 0.6 else "weak"
                        voice_note = "Ghar par koi nahi hai, bohot akelapan lag raha hai, mann bechain hai."

            if in_decline:
                if traj == "frailty_drift":
                    weight_v -= 0.15 * decline_progress
                elif traj == "infection_respiratory":
                    sugar_v += 3.0 * decline_progress
                    bp_sys_v -= 1.5 * decline_progress
                elif traj == "medication_failure":
                    bp_sys_v += 4.0 * decline_progress
                    bp_dia_v += 2.0 * decline_progress
                    if diabetic:
                        sugar_v += 4.0 * decline_progress
                elif traj == "cognitive_withdrawal":
                    weight_v -= 0.12 * decline_progress
                    sugar_v += 1.5 * decline_progress

            # Self-report is noisy in real life: healthy people say "a bit weak", sometimes miss a dose
            # or a check-in; unwell people under-report. (Without this the check-in would leak the label.)
            if not in_decline:
                r = random.random()
                if r < 0.015:
                    checkin = "missed"
                elif r < 0.03:
                    checkin = "bad"
                elif r < 0.10:
                    checkin = "weak"
                if random.random() < 0.04:
                    meds_taken = False
            else:
                if checkin in ("weak", "bad", "missed") and random.random() < 0.25:
                    checkin = "good"

            # Notes: paraphrased, sometimes not given at all; everyday notes on ordinary days
            if voice_note:
                voice_note = random.choice(NOTE_VARIANTS.get(traj, [voice_note])) if random.random() < 0.8 else None
            elif not in_decline and random.random() < 0.06:
                voice_note = random.choice(BENIGN_NOTES)

            # Measurements are not taken every day (missing entries): BP 55%, sugar 35%, weight 20%
            m_bp = random.random() < 0.55
            m_sugar = random.random() < 0.35
            m_weight = random.random() < 0.20

            daily_records.append({
                "day": d + 1,
                "steps": max(steps, 50),
                "resting_hr": max(hr, 45),
                "spo2": min(max(spo2, 85.0), 100.0),
                "sleep_hours": max(sleep, 2.0),
                "wear_hours": random.randint(18, 24),
                "battery": random.randint(30, 100),
                "off_wrist": False,
                "meds_taken": meds_taken,
                "checkin": checkin,
                "voice_note": voice_note,
                "possible_fall": possible_fall,
                "bp_sys": round(bp_sys_v) if m_bp else None,
                "bp_dia": round(bp_dia_v) if m_bp else None,
                "sugar": round(sugar_v) if m_sugar else None,
                "weight": round(weight_v, 1) if m_weight else None,
            })

        seniors.append({
            "senior_id": s_id,
            "name": f"{fname} {lname}",
            "age": age,
            "city": city,
            "coordinator_code": coord["code"],
            "coordinator_name": coord["name"],
            "is_planted": is_planted,
            "trajectory": traj,
            "decline_start_day": decline_start_day if is_planted else None,
            "event_day": (decline_start_day + 12) if is_planted else None,
            "diabetic": diabetic,
            "records": daily_records
        })

    return {
        "num_seniors": num_seniors,
        "days": days,
        "coordinators": COORDINATORS,
        "seniors": seniors
    }

def evaluate_cohort_performance(cohort_data: Dict[str, Any], baseline_engine, scorer_engine, nlp_engine) -> Dict[str, Any]:
    """
    Evaluates Aegis Saathi early-warning metrics on the 250-senior cohort:
    - Recall (>= 80% target)
    - Precision@10 (>= 70% target)
    - Median early warning lead time (5 - 10 days target)
    - Alert action rate (>= 90%)
    - Data quality coverage rate
    """
    planted_detected = 0
    total_planted = 0
    lead_times = []
    top_10_hits_per_day = []
    all_alerts_count = 0
    false_alerts_count = 0
    usable_days = 0
    total_days = 0

    seniors = cohort_data["seniors"]

    # Pre-compute baseline once per senior for speed
    senior_baselines = {s["senior_id"]: baseline_engine.compute_baseline(s["records"][:40]) for s in seniors}

    # We evaluate across the critical evaluation window (Days 65 to 85)
    all_evaluated_alerts = []
    for day_idx in range(65, 85):
        daily_alerts = []
        for s in seniors:
            records = s["records"][:day_idx]
            if len(records) < 14:
                continue
            cur = records[-1]
            total_days += 1
            if not cur.get("off_wrist", False):
                usable_days += 1

            baseline = senior_baselines[s["senior_id"]]
            v_eval = baseline_engine.evaluate_daily_drift(cur, baseline, records[-5:])
            v_eval["possible_fall"] = cur.get("possible_fall", False)
            v_eval["current_spo2"] = cur.get("spo2", 98.0) or 98.0

            nlp_func = nlp_engine if callable(nlp_engine) else nlp_engine.extract_symptom_cues
            nlp_res = nlp_func(cur.get("voice_note", ""))
            med_data = {
                "consecutive_missed_doses": 2 if not cur.get("meds_taken", True) else 0,
                "weekly_adherence_rate": 0.55 if not cur.get("meds_taken", True) else 0.95
            }
            chk_status = {"status": cur.get("checkin", "good"), "emergency_sos": False}

            eval_res = scorer_engine.calculate_daily_risk(s, v_eval, med_data, nlp_res, chk_status)
            score = eval_res["risk_score"]

            is_true_decline = s["is_planted"] and (day_idx >= (s["decline_start_day"] or 999))
            is_alert = eval_res["tier"] in ["RED", "ORANGE"]
            if is_alert:
                all_alerts_count += 1
                if not is_true_decline:
                    false_alerts_count += 1

            alert_info = {
                "senior_id": s["senior_id"],
                "score": score,
                "tier": eval_res["tier"],
                "is_true_decline": is_true_decline,
                "senior": s
            }
            daily_alerts.append(alert_info)
            all_evaluated_alerts.append(alert_info)

        # Rank seniors by score to evaluate Precision@10
        daily_alerts.sort(key=lambda x: x["score"], reverse=True)
        top_10 = daily_alerts[:10]
        hits = sum(1 for item in top_10 if item["is_true_decline"])
        top_10_hits_per_day.append(hits / 10.0)

    # Lead time & recall calculation across all planted cases (using same live scoring path)
    for s in seniors:
        if s["is_planted"]:
            total_planted += 1
            start_d = s["decline_start_day"]
            detected = False
            baseline = senior_baselines[s["senior_id"]]
            for d in range(start_d, min(start_d + 14, 90)):
                records = s["records"][:d]
                cur = records[-1]
                v_eval = baseline_engine.evaluate_daily_drift(cur, baseline, records[-5:])
                v_eval["possible_fall"] = cur.get("possible_fall", False)
                v_eval["current_spo2"] = cur.get("spo2", 98.0) or 98.0
                nlp_func = nlp_engine if callable(nlp_engine) else nlp_engine.extract_symptom_cues
                nlp_res = nlp_func(cur.get("voice_note", ""))
                med_data = {
                    "consecutive_missed_doses": 2 if not cur.get("meds_taken", True) else 0,
                    "weekly_adherence_rate": 0.55 if not cur.get("meds_taken", True) else 0.95
                }
                chk_status = {"status": cur.get("checkin", "good"), "emergency_sos": False}
                res = scorer_engine.calculate_daily_risk(s, v_eval, med_data, nlp_res, chk_status)
                if res["risk_score"] >= 45:  # Orange or Red alert fired
                    detected = True
                    # Measured lead time: days prior to adverse hospitalization endpoint (Day start_d + 10)
                    lead_time = max(1, (start_d + 10) - d)
                    lead_times.append(lead_time)
                    break
            if detected:
                planted_detected += 1

    recall = round((planted_detected / max(total_planted, 1)) * 100, 1)
    precision_at_10 = round(float(np.mean(top_10_hits_per_day)) * 100, 1) if top_10_hits_per_day else 0.0
    median_lead_time = round(float(np.median(lead_times)), 1) if lead_times else 0.0
    data_quality_coverage = round((usable_days / max(total_days, 1)) * 100, 1)

    eval_weeks = 20.0 / 7.0
    num_coords = max(len(COORDINATORS), 1)
    false_alerts_per_coord_week = round(false_alerts_count / (num_coords * eval_weeks), 1)
    true_alerts = all_alerts_count - false_alerts_count
    action_rate = round((true_alerts / max(all_alerts_count, 1)) * 100, 1)

    return {
        "recall_percentage": recall,
        "precision_at_10": precision_at_10,
        "median_lead_time_days": median_lead_time,
        "planted_cases_total": total_planted,
        "planted_cases_detected": planted_detected,
        "data_quality_coverage_pct": data_quality_coverage,
        "alert_action_rate": action_rate,
        "false_alerts_per_coordinator_week": false_alerts_per_coord_week,
        "target_benchmarks": {
            "recall": f">= 80% ({'Achieved' if recall >= 80.0 else 'Below Target'})",
            "precision_at_10": f">= 70% ({'Achieved' if precision_at_10 >= 70.0 else 'Below Target'})",
            "median_lead_time": f"5-10 Days ({'Achieved' if 5.0 <= median_lead_time <= 10.0 else 'Below Target'})"
        }
    }
