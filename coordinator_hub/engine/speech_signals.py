"""
Early signs of memory and mood change, from what the senior says on their daily calls.

Per call (the senior's own lines only):
  words_per_answer   how much they say in an answer; answers that keep getting shorter can mean withdrawal or tiredness
  vocab              word variety (moving type-token ratio over 20-word windows, so call length does not matter)
  repeats            the same sentence said again within one call
  word_finding       hesitations and "what is it called" moments
  memory_mentions    "I forget", "yaad nahi rehta"
  mood               -1 low, 0 neutral, +1 good: the after-call notes' mood when there is one, else word lists
  lonely             "akela", "nobody comes", "alone"

Across calls: the last 3 calls are compared with the person's own earlier calls, and the same story told in several
calls is noticed. The result is a screening signal for the care manager ("worth a memory check-up"), never a
diagnosis.
"""
import re
from statistics import mean, median
from typing import Any, Dict, List, Optional

_WORD = re.compile(r"[\wऀ-ॿ']+", re.UNICODE)

WORD_FINDING = ["um", "umm", "uh", "hmm", "हम्म", "वो क्या", "क्या कहते", "क्या बोलते", "kya kehte", "kya bolte",
                "naam yaad nahi", "नाम याद नहीं", "what's it called", "what is it called", "what do you call",
                "वो चीज़", "वो चीज", "wo cheez"]
MEMORY = ["bhool", "भूल", "याद नहीं", "yaad nahi", "yaad nahin", "याद नहीं रहता", "forgot", "forget", "can't remember",
          "cannot remember", "don't remember", "dont remember"]
LONELY = ["akela", "akeli", "अकेला", "अकेली", "अकेले", "alone", "lonely", "koi nahi aata", "कोई नहीं आता",
          "koi baat nahi karta", "कोई बात नहीं करता", "nobody comes", "no one comes", "no one to talk", "बात करने वाला"]
LOW = LONELY + ["udaas", "उदास", "sad", "man nahi", "मन नहीं", "bekaar", "बेकार", "hopeless", "no point", "kya fayda",
                "क्या फायदा", "क्या फ़ायदा", "dukhi", "दुखी", "rona", "रोना", "ro rahi", "ro raha", "tired of", "pareshan",
                "परेशान", "chinta", "चिंता", "worried", "dar lag", "डर लग"]
GOOD = ["achha", "accha", "अच्छा", "अच्छी", "khush", "खुश", "happy", "great", "badhiya", "बढ़िया", "mazaa", "मज़ा",
        "मजा", "fine", "theek", "ठीक", "wonderful", "nice", "shukriya", "शुक्रिया", "maza aaya"]


def _words(text: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def _count(text: str, phrases: List[str]) -> int:
    t = " " + (text or "").lower() + " "
    n = 0
    for p in phrases:
        if p.isascii() and len(p) <= 4:
            n += len(re.findall(r"(?<![\w])" + re.escape(p) + r"(?![\w])", t))
        else:
            n += t.count(p)
    return n


def _mattr(words: List[str], window: int = 20) -> Optional[float]:
    if len(words) < 8:
        return None
    if len(words) <= window:
        return len(set(words)) / len(words)
    return mean(len(set(words[i:i + window])) / window for i in range(len(words) - window + 1))


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa | sb), 1)


def analyse_call(transcript: List[Dict[str, Any]], llm_mood: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Signals for one call; None when the senior said too little to measure."""
    lines = [str(t.get("text") or "").strip() for t in transcript or []
             if isinstance(t, dict) and str(t.get("speaker", "")).lower() in ("senior", "user", "patient")]
    lines = [x for x in lines if x]
    words = [_words(x) for x in lines]
    total = sum(len(w) for w in words)
    if not lines or total < 4:
        return None
    text = " ".join(lines)
    repeats = 0
    for i, w in enumerate(words):
        if len(w) >= 3 and any(_jaccard(w, v) >= 0.7 for v in words[:i] if len(v) >= 3):
            repeats += 1
    low, good, lonely = _count(text, LOW), _count(text, GOOD), _count(text, LONELY)
    mood = {"good": 1, "okay": 0, "low": -1, "distressed": -1}.get(llm_mood or "", None)
    if mood is None:
        mood = -1 if low > good else 1 if good > low else 0
    flat = [x for w in words for x in w]
    vocab = _mattr(flat)
    return {
        "answers": len(lines), "words": total,
        "words_per_answer": round(total / len(lines), 1),
        "vocab": round(vocab, 3) if vocab is not None else None,
        "repeats": repeats,
        "word_finding": _count(text, WORD_FINDING),
        "memory_mentions": _count(text, MEMORY),
        "lonely": lonely,
        "mood": mood,
        "lines": [" ".join(w) for w in words if len(w) >= 5][:12],     # for "the same story in several calls"
    }


def _story_repeats(calls: List[Dict[str, Any]]) -> int:
    """How many of these calls retell a sentence (5+ words) already said in an earlier one of them."""
    n, seen = 0, []
    for c in calls:
        lines = [x.split() for x in (c.get("speech") or {}).get("lines", [])]
        if any(_jaccard(a, b) >= 0.75 for a in lines for b in seen):
            n += 1
        seen.extend(lines)
    return n


def trend(calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """[calls] oldest first, each with a "speech" dict. Compares the last 3 calls with the person's own earlier ones."""
    calls = [c for c in calls if c.get("speech")][-14:]
    series = [{"date": str(c.get("start_time") or "")[:10], **{k: c["speech"].get(k) for k in
               ("words_per_answer", "vocab", "repeats", "word_finding", "memory_mentions", "mood", "lonely")}}
              for c in calls]
    out: Dict[str, Any] = {"calls": len(calls), "series": series, "flags": [], "cognition": "steady", "mood": "steady",
                           "enough_data": len(calls) >= 5}
    if len(calls) < 3:
        out["cognition"] = out["mood"] = "not_enough"
        return out
    recent, base = calls[-3:], calls[:-3]
    sp = lambda cs, k: [c["speech"][k] for c in cs if c["speech"].get(k) is not None]
    flags: List[Dict[str, str]] = []
    if len(base) >= 3:
        b, r = median(sp(base, "words_per_answer")), mean(sp(recent, "words_per_answer"))
        if b and r < 0.7 * b:
            pct = round(100 * (1 - r / b))
            flags.append({"kind": "cognition", "en": f"Answers are {pct}% shorter than their usual",
                          "hi": f"जवाब सामान्य से {pct}% छोटे हो गए हैं"})
        bv, rv = sp(base, "vocab"), sp(recent, "vocab")
        if bv and rv and mean(rv) < median(bv) - 0.08:
            flags.append({"kind": "cognition", "en": "Using fewer different words than before",
                          "hi": "पहले से कम अलग-अलग शब्द इस्तेमाल कर रहे हैं"})
        bw, rw = sp(base, "word_finding"), sp(recent, "word_finding")
        if rw and mean(rw) >= 1 and mean(rw) > (median(bw) if bw else 0) + 1:
            flags.append({"kind": "cognition", "en": "More pauses searching for words",
                          "hi": "शब्द ढूँढने में ज़्यादा रुकावट"})
    last5 = calls[-5:]
    rep_calls = sum(1 for c in last5 if c["speech"].get("repeats", 0) > 0)
    if rep_calls >= 2:
        flags.append({"kind": "cognition", "en": f"Repeated the same thing within a call in {rep_calls} of the last {len(last5)} calls",
                      "hi": f"पिछली {len(last5)} में से {rep_calls} कॉल में एक ही बात दोहराई"})
    story = _story_repeats(last5)
    if story >= 2:
        flags.append({"kind": "cognition", "en": f"Told the same story again in {story} calls",
                      "hi": f"{story} कॉल में वही बात फिर से बताई"})
    mem = sum(1 for c in last5 if c["speech"].get("memory_mentions", 0) > 0)
    if mem >= 2:
        flags.append({"kind": "cognition", "en": f"Mentioned forgetting things in {mem} calls",
                      "hi": f"{mem} कॉल में भूलने की बात कही"})
    last7 = calls[-7:]
    lowc = sum(1 for c in last7 if c["speech"].get("mood", 0) < 0)
    if lowc >= 3:
        flags.append({"kind": "mood", "en": f"Sounded low in {lowc} of the last {len(last7)} calls",
                      "hi": f"पिछली {len(last7)} में से {lowc} कॉल में उदास लगे"})
    lon = sum(1 for c in last7 if c["speech"].get("lonely", 0) > 0)
    if lon >= 2:
        flags.append({"kind": "mood", "en": f"Talked about feeling alone in {lon} calls",
                      "hi": f"{lon} कॉल में अकेलेपन की बात की"})
    out["flags"] = flags
    if sum(f["kind"] == "cognition" for f in flags) >= 2:
        out["cognition"] = "watch"
    if any(f["kind"] == "mood" for f in flags):
        out["mood"] = "low"
    if out["cognition"] == "watch":
        out["advice_en"] = "Worth a gentle memory check-up with their doctor. This is a screening signal, not a diagnosis."
        out["advice_hi"] = "डॉक्टर से एक सामान्य याददाश्त जाँच करवाना ठीक रहेगा। यह केवल संकेत है, निदान नहीं।"
    elif out["mood"] == "low":
        out["advice_en"] = "Ask family to call or visit more this week; consider a talk with their doctor about mood."
        out["advice_hi"] = "इस हफ़्ते परिवार से ज़्यादा फ़ोन या मिलने को कहें; मूड के बारे में डॉक्टर से बात करें।"
    return out
