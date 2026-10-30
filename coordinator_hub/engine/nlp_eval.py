"""
Labelled test set for the code-mixed (Hindi / Hinglish / English / Devanagari) symptom extractor.

Written by hand and kept SEPARATE from the synthetic cohort's note pools, so it measures the extractor
on phrasings it was not tuned on. Includes negations ("dard nahi hai"), benign mentions and
sentences with several cues. Each item: (text, set of expected categories).
Run:  python -m engine.nlp_eval
"""

from typing import Any, Dict, List, Set, Tuple

from .nlp_extractor import extract_symptom_cues

TEST_SET: List[Tuple[str, Set[str]]] = [
    # pain
    ("mere ghutne mein bahut dard hai", {"pain"}),
    ("kamar dard ki wajah se neend nahi aayi", {"pain", "poor_sleep"}),
    ("my back is paining since morning", {"pain"}),
    ("सिर में दर्द है", {"pain"}),
    ("pet mein dard aur ulti jaisa lag raha hai", {"pain", "low_appetite"}),
    # dizziness
    ("uthte hi chakkar aa jata hai", {"dizziness"}),
    ("I feel dizzy when I stand up", {"dizziness"}),
    ("सिर घूम रहा है और चक्कर आ रहे हैं", {"dizziness"}),
    ("aankhon ke aage andhera ho gaya tha", {"dizziness"}),
    # weakness
    ("bahut kamzori lag rahi hai", {"weakness"}),
    ("I am very tired and weak today", {"weakness"}),
    ("थकान रहती है, हिम्मत नहीं है", {"weakness"}),
    ("aaj bilkul energy nahi hai", {"weakness"}),
    # sleep
    ("raat bhar neend nahi aayi", {"poor_sleep"}),
    ("I could not sleep last night", {"poor_sleep"}),
    ("नींद नहीं आती आजकल", {"poor_sleep"}),
    ("slept badly again", {"poor_sleep"}),
    # appetite
    ("bhookh nahi lagti, khana nahi khaya", {"low_appetite"}),
    ("I have no appetite since two days", {"low_appetite"}),
    ("भूख नहीं लगती", {"low_appetite"}),
    # falls
    ("bathroom mein phisal gaye the", {"fall"}),
    ("I slipped and fell near the stairs", {"fall"}),
    ("मैं गिर गई थी रात को", {"fall"}),
    ("balance chala gaya aur gir padi", {"fall"}),
    # loneliness
    ("akelapan lagta hai, koi baat karne wala nahi", {"loneliness"}),
    ("I feel very lonely and low", {"loneliness"}),
    ("मुझे अकेलापन लगता है", {"loneliness"}),
    ("mann udaas rehta hai", {"loneliness"}),
    # confusion
    ("kuch yaad nahi rehta, bhool jata hoon", {"confusion"}),
    ("I feel confused, forgot what I was doing", {"confusion"}),
    ("मुझे याद नहीं रहता कुछ", {"confusion"}),
    ("samajh nahi aata kaunsa din hai", {"confusion"}),
    # fever / infection
    ("do din se bukhar aur khansi hai", {"fever_infection"}),
    ("I have a cough and fever", {"fever_infection"}),
    ("बुखार और खाँसी है, सांस फूल रही है", {"fever_infection"}),
    ("thand lag rahi hai aur chills aa rahe hain", {"fever_infection"}),
    # medication
    ("dawa nahi li kal se", {"medication_issue"}),
    ("forgot dose yesterday", {"medication_issue"}),
    ("goli khatam ho gayi hai", {"medication_issue"}),
    ("दवा भूल गए थे", {"medication_issue"}),
    # several cues
    ("chakkar aa raha hai aur bukhar bhi hai", {"dizziness", "fever_infection"}),
    ("khansi hai aur bahut kamzori bhi", {"fever_infection", "weakness"}),
    ("akelapan hai, bhookh nahi lagti, neend nahi aati", {"loneliness", "low_appetite", "poor_sleep"}),
    ("gir gaye the aur ghutne mein dard hai", {"fall", "pain"}),
    # negations and benign text: must give NOTHING
    ("dard nahi hai ab", set()),
    ("koi chakkar nahi aa raha", set()),
    ("no pain today, feeling fine", set()),
    ("not dizzy anymore", set()),
    ("सब ठीक है, कोई तकलीफ़ नहीं", set()),
    ("sab theek hai, subah walk par gaye the", set()),
    ("I fall asleep quickly and slept well", set()),
    ("went on a trip to the market and came back happy", set()),
    ("kal shaadi mein khoob naache", set()),
    ("bhookh achhi lagti hai, sab badhiya", set()),
    ("I wake up at six every day, feeling good", set()),
    ("all good, had a light breakfast", set()),
    ("aaj mandir gaya tha, mann khush hai", set()),
    ("cough nahi hai ab, bilkul theek hoon", set()),
]


def evaluate() -> Dict[str, Any]:
    cats = sorted({c for _, exp in TEST_SET for c in exp} | {"pain", "dizziness", "weakness", "poor_sleep",
                                                             "low_appetite", "fall", "loneliness", "confusion",
                                                             "fever_infection", "medication_issue"})
    tp = {c: 0 for c in cats}
    fp = {c: 0 for c in cats}
    fn = {c: 0 for c in cats}
    exact = 0
    misses: List[Dict[str, Any]] = []
    for text, expected in TEST_SET:
        got = set(extract_symptom_cues(text).get("categories", []))
        if got == expected:
            exact += 1
        else:
            misses.append({"text": text, "expected": sorted(expected), "got": sorted(got)})
        for c in cats:
            tp[c] += int(c in got and c in expected)
            fp[c] += int(c in got and c not in expected)
            fn[c] += int(c not in got and c in expected)
    per = {}
    for c in cats:
        p = tp[c] / (tp[c] + fp[c]) if tp[c] + fp[c] else 1.0
        r = tp[c] / (tp[c] + fn[c]) if tp[c] + fn[c] else 1.0
        per[c] = {"precision": round(p, 2), "recall": round(r, 2), "support": tp[c] + fn[c]}
    TP, FP, FN = sum(tp.values()), sum(fp.values()), sum(fn.values())
    micro_p = TP / (TP + FP) if TP + FP else 1.0
    micro_r = TP / (TP + FN) if TP + FN else 1.0
    return {
        "examples": len(TEST_SET),
        "exact_match_pct": round(100 * exact / len(TEST_SET), 1),
        "micro_precision": round(micro_p, 3), "micro_recall": round(micro_r, 3),
        "micro_f1": round(2 * micro_p * micro_r / (micro_p + micro_r), 3) if micro_p + micro_r else 0.0,
        "per_category": per, "misses": misses[:15],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
