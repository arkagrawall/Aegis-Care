"""
Aegis Saathi - Multilingual NLP Cue Extractor (Hindi / Hinglish / English)
Extracts health symptoms, functional indicators, and psychosocial cues from senior check-in notes.
"""

import re
from typing import Dict, List, Any

# Vocabulary dictionaries with semantic categories
CUE_PATTERNS = {
    "pain": [
        r"दर्द", r"पीड़ा", r"सूजन",
        r"\bdard\b", r"\bpain(s|ing|ful)?\b", r"\bach(e|ing)\b", r"\bpeeth\s*dard\b", r"\bsar\s*dard\b",
        r"\bghutn(e|o)\s*mein\s*dard\b", r"\bdukh\s*raha\b", r"\bsoojan\b", r"\bswelling\b",
        r"\bdard\s*hai\b", r"\bbody\s*pain\b", r"\bkamar\s*dard\b",
        r"\bhurt(s|ing)?\b", r"\bsore\b", r"\b(head|back|stomach|tooth|ear)\s*ache\b", r"\bdukh(ta|ti|\s*rahi|\s*raha)\b",
        r"दुख\s*(रहा|रही|ता|ती)"
    ],
    "dizziness": [
        r"चक्कर", r"सिर\s*घूम",
        r"\bchakkar\b", r"\bchakar\b", r"\bdizz(y|iness)\b", r"\bgidd(y|iness)\b",
        r"\bsir\s*ghum\s*raha\b", r"\baankhon\s*ke\s*aage\s*andhera\b", r"\blightheaded\b"
    ],
    "weakness": [
        r"कमज़?ोर", r"थकान", r"थकावट", r"सुस्ती",
        r"\bkamzor(i)?\b", r"\bweak(ness)?\b", r"\bthak(an|awat|a)\b", r"\btired(ness)?\b",
        r"\bexhaust(ed|ion)\b", r"\benergy\s*nahi\b", r"\bhimm?at\s*nahi\b", r"\bsust(i)?\b",
        r"\bletharg(ic|y)\b", r"\bbistar\s*se\s*utha\s*nahi\s*gaya\b", r"\b(no|low)\s+energy\b"
    ],
    "poor_sleep": [
        r"\bslept\s+(badly|poorly)\b", r"\bcould\s*n[o']?t\s+sleep\b", r"\bcan'?t\s+sleep\b",
        r"\bdidn'?t\s+sleep\b", r"\bnot\s+sleeping\b", r"\bbad\s+sleep\b", r"\bno\s+sleep\b",
        r"नींद\s*नहीं", r"नींद\s*नही",
        r"\bneend\s*nahi\b", r"\bpoor\s*sleep\b", r"\binsomnia\b", r"\bso\s*nahi\s*p(aye|ayein)\b",
        r"\braat\s*bhar\s*jaag(te|e)\b", r"\bbechain(i)?\b", r"\bdisturbed\s*sleep\b",
        r"\b(repeatedly|frequently|middle\s+of\s+night)\s+wake\s*up\b",
        r"\bwak(e|ing)\s+up\s+(repeatedly|frequently|often)\b",
        r"\bdid\s*not\s+sleep\b", r"\bbarely\s+slept\b", r"\bnot\s+sleep(ing)?\s+well\b", r"\bslept\s+(very\s+)?little\b",
        r"\bneend\s*(kam|nahi\s*aayi|theek\s*nahi)\b", r"नींद\s*(कम|ठीक\s*नहीं)",
        # "मैं रात में नहीं सोया", "सो नहीं पाई", "रात भर जागता रहा": the नहीं is the complaint, not a denial
        r"(नहीं|नही)\s*(सोया|सोई|सोए|सो\s*(पाया|पाई|पाए|सका|सकी|सके))", r"सो\s*(नहीं|नही)\s*(पाया|पाई|पाए|सका|सकी|सके)",
        r"रात\s*(भर|को)?\s*जाग(ता|ती|ते)\s*(रहा|रही|रहे)", r"\bnahi\s*so(ya|yi|ye)\b", r"\bso\s*nahi\s*(paya|payi|saka|saki)\b"
    ],
    "low_appetite": [
        r"भूख\s*नहीं", r"भूख\s*नही", r"उल्टी", r"जी\s*मिचल",
        r"\bbhookh\s*nahi\b", r"\bkhana\s*nahi\s*khaya\b", r"\blow\s*appetite\b", r"\bno\s*appetite\b",
        r"\bkachha\s*mann\b", r"\bvomit\b", r"\bult(i)?\b", r"\bnausea\b", r"\bkhaye\s*bina\b",
        r"\bnot\s+(very\s+|feeling\s+)?hungry\b", r"\b(don'?t|do\s+not)\s+feel\s+like\s+eating\b", r"\b(eating|ate)\s+(very\s+)?(less|little)\b",
        r"\bnot\s+eating\b", r"\bbhoo?kh?\s*kam\b", r"\bbhukh\s*nahi\b", r"\bkhana\s*kam\b", r"\bkam\s*khaya\b",
        r"भूख\s*कम", r"खाना\s*कम"
    ],
    "fall": [
        r"गिर\s*(गए|गये|गई|गया|पड़ी|पड़ा)", r"फिसल\s*(गए|गये|गई|गया)", r"चोट\s*लग",
        r"\bgir\s*(gaye|gayi|pada|padi)\b",
        r"\b(had\s+a\s+fall|fallen\s+down|fell\s+down|fall\s+down|fall\s+over|fell\s+over)\b",
        r"\bphisal\s*gaye\b",
        r"\bslip(ped)?\s+(and\s+fell|down|over)\b",
        r"\bchot\s*lag(i)?\b",
        r"\bbalance\s*chala\s*gaya\b",
        r"\btrip(ped)?\s+(and\s+fell|over)\b"
    ],
    "loneliness": [
        r"अकेला", r"अकेली", r"अकेलापन", r"उदास", r"घबराहट",
        r"\bakel(a|apan|i)\b", r"\blonel(y|iness)\b", r"\budaa?s(i)?\b", r"\bdepressed\b",
        r"\bmann\s*nahi\s*lag\s*raha\b", r"\bkoi\s*baat\s*karne\s*wala\s*nahi\b", r"\bro\s*diye\b",
        r"\bgheepan\b", r"\banxious\b", r"\bghabrahat\b"
    ],
    "confusion": [
        r"\bkuch\s*yaad\s*nahi\b", r"\byaad\s*nahi\s*(rehta|raha|aa\s*raha)\b", r"\bbhool\s*(jata|jati)\s*(hoon|hu|hun)\b",
        r"\bkya\s*kar\s*raha\s*tha\s*bhool\b", r"\bsamajh\s*nahi\s*aa(ta|\s*raha)\b", r"\bpata\s*nahi\s*chalta\b",
        r"\bkaunsa\s*din\b", r"\bconfus(ed|ion)\b", r"\bdisorient(ed|ation)\b", r"\bforgot\s+what\s+i\s+was\s+doing\b",
        r"\blost\s+track\b", r"\bkaun\s*hai\s*yeh\b",
        r"याद\s*नहीं\s*(रहता|रहा|आ\s*रहा)", r"भूल\s*जाता", r"भ्रमित", r"समझ\s*नहीं\s*आता", r"पता\s*नहीं\s*चलता",
    ],
    "medication_issue": [
        r"दवा\s*नहीं\s*ली", r"दवा\s*भूल", r"गोली\s*खत्म",
        r"\bdawa\s*(nahi\s*li|bhool\s*gaye|chhoot\s*gayi)\b", r"\bgoli\s*khatam\b",
        r"\bmissed\s*medicine\b", r"\bforgot\s*dose\b", r"\bwrong\s*pill\b", r"\bmedicine\s*finished\b"
    ],
    "fever_infection": [
        r"बुखार", r"खांसी", r"खाँसी", r"सांस\s*फूल", r"साँस\s*फूल",
        r"\bbukhar\b", r"\bfever\b", r"\bthandi\s*lag\s*rahi\b", r"\bchills\b",
        r"\bkhan?si\b", r"\bcough\b", r"\bsaans\s*phool\s*rahi\b", r"\bbreathless(ness)?\b"
    ]
}

def _is_negated(text: str, match_start: int, match_end: int) -> bool:
    """
    Checks if a detected symptom cue is negated in English or Hindi/Hinglish.
    e.g. 'no pain', 'not dizzy', 'dard nahi hai', 'chakkar nahi'.
    """
    # Context window: up to 25 chars before and 25 chars after
    prefix = text[max(0, match_start - 25):match_start]
    suffix = text[match_end:min(len(text), match_end + 25)]

    # English negation prefixes: "no pain", "not feeling dizzy", "without any pain", "denies pain"
    if re.search(r"\b(no|not|neither|nor|without|never|zero|don'?t\s+have|denies|free\s+of)\s*$", prefix):
        return True

    # Hindi/Hinglish post-negation: "dard nahi hai", "chakkar nhi", "chot nahi lagi"
    if re.search(r"^\s*(nahi|nhi|na|mat)\b", suffix) or re.search(r"^\s*(नहीं|नही|मत)", suffix):
        return True

    # Hindi/Hinglish pre-negation: "koi dard nahi", "kuch nahi hua"
    if re.search(r"\b(koi|kuch|kisi\s+bhi)\s*$", prefix) and re.search(r"^\s*.*?\b(nahi|nhi)\b", suffix):
        return True

    return False

def extract_symptom_cues(text: str) -> Dict[str, Any]:
    """
    Extracts structured cues, identified categories, and risk-weight contribution.
    Accurately filters out negations and false positives.
    """
    if not text or not isinstance(text, str):
        return {
            "cues_found": [],
            "categories": [],
            "nlp_risk_score": 0.0,
            "sentiment": "neutral",
            "summary_hi": "Koi pareshani darj nahi ki gayi",
            "summary_en": "No reported complaints"
        }

    normalized = text.lower().strip()
    detected_categories = []
    matched_phrases = []

    # Category weights based on clinical urgency
    CATEGORY_WEIGHTS = {
        "fall": 35.0,
        "dizziness": 25.0,
        "fever_infection": 20.0,
        "pain": 15.0,
        "weakness": 15.0,
        "poor_sleep": 10.0,
        "low_appetite": 10.0,
        "medication_issue": 20.0,
        "confusion": 25.0,
        "loneliness": 10.0
    }

    total_score = 0.0
    for category, patterns in CUE_PATTERNS.items():
        found = False
        for pat in patterns:
            for match in re.finditer(pat, normalized, re.IGNORECASE):
                # Ignore self-contained intentional negative patterns like 'energy nahi'
                is_explicit_negative_pattern = "nahi" in pat or "नहीं" in pat or "नही" in pat
                if not is_explicit_negative_pattern and _is_negated(normalized, match.start(), match.end()):
                    continue
                found = True
                matched_phrases.append(match.group(0))
        if found:
            detected_categories.append(category)
            total_score += CATEGORY_WEIGHTS.get(category, 10.0)

    # Cap score at 50 from NLP cues alone (hybrid model will fuse with vitals & meds)
    nlp_score = min(total_score, 50.0)

    # Determine sentiment and human-readable summaries
    if len(detected_categories) == 0:
        sentiment = "positive" if any(w in normalized for w in ["theek", "good", "fine", "badhiya", "achha", "ठीक", "अच्छा", "बढ़िया"]) else "neutral"
        summary_hi = "Koi gambhir lakshan nahi mila"
        summary_en = "No severe symptoms reported"
    elif "fall" in detected_categories or "dizziness" in detected_categories:
        sentiment = "high_risk"
        summary_hi = f"Chakkar ya girne ke sanket: {', '.join(detected_categories)}"
        summary_en = f"High-risk alert cues: {', '.join(detected_categories)}"
    else:
        sentiment = "concerning"
        summary_hi = f"Darj kiye gaye lakshan: {', '.join(detected_categories)}"
        summary_en = f"Reported symptoms: {', '.join(detected_categories)}"

    return {
        "cues_found": matched_phrases,
        "categories": detected_categories,
        "nlp_risk_score": round(nlp_score, 1),
        "sentiment": sentiment,
        "summary_hi": summary_hi,
        "summary_en": summary_en
    }
