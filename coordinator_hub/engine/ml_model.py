"""
Aegis Saathi - ML layer (anomaly detection + explainable supervised model)

Both models work on features that are ALREADY relative to the senior's own baseline (z-scores,
percent change, slopes), so they learn "what a decline looks like for anyone" without ever comparing
a person to a population average.

  IsolationForest      unsupervised anomaly detector, fitted only on ordinary (pre-decline) days of the
                       cohort. Output: how rare today's deviation pattern is (percentile of normal days).
  LogisticRegression   supervised on the synthetic cohort's planted declines. Chosen over a deeper
                       model on purpose: 250 seniors is small data, and its coefficients give a faithful,
                       plain-language "why" (contribution = coefficient x standardised value).

Evaluation protocol (see evaluation.py): 2-fold cross-fitting BY SENIOR. A senior is only ever scored
by a model that never saw that senior, so reported precision / recall are not inflated by leakage.
"""

import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .baseline_drift import latest_value
from .nlp_extractor import extract_symptom_cues

# Higher value = worse for every feature, so coefficients are directly readable.
FEATURES = [
    "steps_drop", "hr_up", "spo2_drop", "sleep_drop", "bp_up", "sugar_up", "weight_loss",
    "steps_trend_down", "hr_trend_up", "checkin_sev", "meds_missed", "nlp_score", "fall_flag",
]
FEATURE_TEXT = {
    "steps_drop": ("walking well below their normal", "चलना सामान्य से काफ़ी कम"),
    "hr_up": ("resting heart rate above their normal", "आराम की धड़कन सामान्य से ज़्यादा"),
    "spo2_drop": ("oxygen below their normal", "ऑक्सीजन सामान्य से कम"),
    "sleep_drop": ("sleeping less than usual", "नींद सामान्य से कम"),
    "bp_up": ("blood pressure above their normal", "ब्लड प्रेशर सामान्य से ज़्यादा"),
    "sugar_up": ("blood sugar above their normal", "शुगर सामान्य से ज़्यादा"),
    "weight_loss": ("weight below their usual", "वज़न सामान्य से कम"),
    "steps_trend_down": ("activity trending down over several days", "कई दिनों से गतिविधि घट रही है"),
    "hr_trend_up": ("heart rate trending up over several days", "कई दिनों से धड़कन बढ़ रही है"),
    "checkin_sev": ("they reported feeling unwell", "उन्होंने तबीयत ख़राब बताई"),
    "meds_missed": ("missed medicines recently", "हाल में दवा छूटी"),
    "nlp_score": ("symptoms mentioned in their own words", "अपने शब्दों में लक्षण बताए"),
    "fall_flag": ("a possible fall was reported", "गिरने का संकेत मिला"),
}
_CHECKIN_SEV = {"good": 0.0, "weak": 1.0, "bad": 2.0, "missed": 1.5}
_nlp_cache: Dict[str, float] = {}


def _nlp_points(note: Optional[str]) -> float:
    if not note:
        return 0.0
    if note not in _nlp_cache:
        _nlp_cache[note] = float(extract_symptom_cues(note).get("nlp_risk_score", 0.0))
    return _nlp_cache[note]


def build_features(records: List[Dict[str, Any]], idx: int, baseline: Dict[str, Any]) -> Optional[np.ndarray]:
    """Feature vector for day `idx` using only days <= idx. None if there is no usable watch data."""
    b = baseline.get("metrics", {})
    if "steps" not in b or "resting_hr" not in b:
        return None
    day = records[idx]
    win = [r for r in records[max(0, idx - 2): idx + 1] if not r.get("off_wrist") and (r.get("steps") or 0) > 50]
    if not win:
        return None

    def mean_of(key):
        v = [r[key] for r in win if r.get(key) not in (None, 0)]
        return float(np.mean(v)) if v else None

    def z(val, key, min_std):
        if val is None or key not in b:
            return 0.0
        return float(np.clip((val - b[key]["median"]) / max(b[key]["std"], min_std), -8, 8))

    steps3, hr3, sleep3 = mean_of("steps"), mean_of("resting_hr"), mean_of("sleep_hours")
    spo2_vals = [r["spo2"] for r in win if (r.get("spo2") or 0) > 70]
    spo2_min = min(spo2_vals) if spo2_vals else None

    recent = records[max(0, idx - 6): idx + 1]
    bp = latest_value("bp_sys", day, recent)
    sugar = latest_value("sugar", day, recent)
    weight = latest_value("weight", day, records[max(0, idx - 13): idx + 1], window=14)
    wt_pct = 0.0
    if weight is not None and "weight" in b:
        wt_pct = float(np.clip((weight - b["weight"]["median"]) / b["weight"]["median"] * 100.0, -15, 15))

    def slope(key, min_std):
        pts = [(i, r[key]) for i, r in enumerate(records[max(0, idx - 4): idx + 1])
               if not r.get("off_wrist") and (r.get(key) or 0) > (50 if key == "steps" else 35)]
        if len(pts) < 3 or key not in b:
            return 0.0
        xs, ys = zip(*pts)
        return float(np.clip(np.polyfit(xs, ys, 1)[0] / max(b[key]["std"], min_std), -3, 3))

    last2 = records[max(0, idx - 1): idx + 1]
    checkin = max((_CHECKIN_SEV.get(r.get("checkin", "good"), 0.0) for r in last2), default=0.0)
    missed = sum(1 for r in records[max(0, idx - 2): idx + 1] if r.get("meds_taken") is False)
    nlp = max((_nlp_points(r.get("voice_note")) for r in last2), default=0.0) / 50.0
    fall = 1.0 if any(r.get("possible_fall") for r in last2) else 0.0

    return np.array([
        -z(steps3, "steps", 300.0), z(hr3, "resting_hr", 3.0), -z(spo2_min, "spo2", 1.5), -z(sleep3, "sleep_hours", 1.0),
        z(bp, "bp_sys", 7.0), z(sugar, "sugar", 10.0), -wt_pct,
        -slope("steps", 300.0), slope("resting_hr", 3.0), checkin, float(missed), nlp, fall,
    ], dtype=float)


class MLRiskModel:
    """Fitted once at server start on the synthetic cohort; scores any senior afterwards."""

    def __init__(self) -> None:
        self.ready = False
        self.iso: Dict[Any, IsolationForest] = {}
        self.lr: Dict[Any, Tuple[StandardScaler, LogisticRegression]] = {}
        self.baseline_scores: Dict[Any, np.ndarray] = {}
        self.fold_of: Dict[str, int] = {}
        self.train_info: Dict[str, Any] = {}

    # ---------------------------------------------------------------- training
    def fit(self, seniors: List[Dict[str, Any]], baseline_engine, n_folds: int = 2) -> None:
        rows: List[Tuple[str, int, np.ndarray, int, bool]] = []   # senior, day, feats, label, is_baseline_day
        for s in seniors:
            recs = s["records"]
            base = baseline_engine.compute_baseline(recs[:40])
            start = s.get("decline_start_day")
            for idx in range(20, min(len(recs), 90)):
                f = build_features(recs, idx, base)
                if f is None:
                    continue
                label = 1 if (start is not None and idx >= start) else 0
                rows.append((s["senior_id"], idx, f, label, idx < 58))

        ids = sorted({r[0] for r in rows})
        self.fold_of = {sid: i % n_folds for i, sid in enumerate(ids)}
        X = np.vstack([r[2] for r in rows])
        y = np.array([r[3] for r in rows])
        fold = np.array([self.fold_of[r[0]] for r in rows])
        is_base = np.array([r[4] for r in rows]) & (y == 0)

        # one model per held-out fold (trained on the OTHER folds) + one "all" model for new seniors
        for held_out in list(range(n_folds)) + ["all"]:
            train = np.ones(len(rows), bool) if held_out == "all" else fold != held_out
            self._fit_one(held_out, X[train], y[train], is_base[train])
        self.ready = True
        self.train_info = {
            "training_days": int(len(rows)), "positive_days": int(y.sum()), "seniors": len(ids),
            "folds": n_folds, "features": FEATURES,
        }

    def _fit_one(self, key, X, y, base_mask) -> None:
        iso = IsolationForest(n_estimators=150, contamination=0.02, random_state=0)
        iso.fit(X[base_mask])
        self.iso[key] = iso
        self.baseline_scores[key] = np.sort(-iso.score_samples(X[base_mask]))
        scaler = StandardScaler().fit(X)
        lr = LogisticRegression(C=0.5, class_weight="balanced", max_iter=1000)
        lr.fit(scaler.transform(X), y)
        self.lr[key] = (scaler, lr)

    # ---------------------------------------------------------------- scoring
    def score_batch(self, X: np.ndarray, senior_ids: List[Optional[str]]) -> List[Dict[str, Any]]:
        """Vectorised score() for many days at once (probability / anomaly / score only, no reasons)."""
        out: List[Dict[str, Any]] = [{"available": False, "prob": 0.0, "anomaly": 0.0, "score": 0.0, "top": []}] * len(senior_ids)
        if not self.ready or len(senior_ids) == 0:
            return out
        keys = [self.fold_of.get(sid, "all") if sid is not None else "all" for sid in senior_ids]
        for key in set(keys):
            rows = [i for i, k in enumerate(keys) if k == key]
            Xk = X[rows]
            scaler, lr = self.lr[key]
            prob = lr.predict_proba(scaler.transform(Xk))[:, 1]
            raw = -self.iso[key].score_samples(Xk)
            base = self.baseline_scores[key]
            anomaly = np.searchsorted(base, raw) / max(len(base), 1)
            gate = np.clip((anomaly - 0.95) / 0.05, 0.0, 1.0)
            score = np.maximum(prob, 0.6 * gate)
            for j, i in enumerate(rows):
                out[i] = {"available": True, "prob": float(prob[j]), "anomaly": float(anomaly[j]),
                          "score": float(score[j]), "top": []}
        return out

    def score(self, features: Optional[np.ndarray], senior_id: Optional[str] = None) -> Dict[str, Any]:
        """ML signal for one day. A cohort senior is scored by the model that did not train on them."""
        if not self.ready or features is None:
            return {"available": False, "prob": 0.0, "anomaly": 0.0, "score": 0.0, "top": []}
        key = self.fold_of.get(senior_id, "all") if senior_id is not None else "all"
        if key != "all":
            # model trained WITHOUT this senior's fold
            key = key
        scaler, lr = self.lr[key]
        xs = scaler.transform(features.reshape(1, -1))
        prob = float(lr.predict_proba(xs)[0, 1])
        raw = float(-self.iso[key].score_samples(features.reshape(1, -1))[0])
        base = self.baseline_scores[key]
        anomaly = float(np.searchsorted(base, raw) / max(len(base), 1))
        gate = float(np.clip((anomaly - 0.95) / 0.05, 0.0, 1.0))   # only the rarest 5% of normal days count
        score = max(prob, 0.6 * gate)
        contrib = lr.coef_[0] * xs[0]
        top = []
        for i in np.argsort(-contrib)[:3]:
            if contrib[i] > 0.15 and features[i] > 0:
                en, hi = FEATURE_TEXT[FEATURES[i]]
                top.append({"feature": FEATURES[i], "en": en, "hi": hi, "contribution": round(float(contrib[i]), 2)})
        return {"available": True, "prob": round(prob, 3), "anomaly": round(anomaly, 3),
                "score": round(score, 3), "top": top}
