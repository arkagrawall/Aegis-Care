"""
Demo only (AEGIS_DEMO_MODE=1): four weeks of earlier check-in calls for one simulated senior, so the care portal's
"Memory & mood" view has a history to show on first run. The calls are marked demo=True and caller_type
"demo_history"; nothing is written for real (dynamic) seniors.

The story: lively, detailed answers in the first two weeks; then shorter answers, the same story retold, forgetting
medicines, and feeling alone.
"""
import time
from typing import Any, Dict, List

from .speech_signals import analyse_call

EARLY = [
    ["आज सुबह मैं पार्क गई थी, वहाँ शर्मा जी की पत्नी से बहुत देर बात हुई, उनकी पोती की शादी अगले महीने है",
     "नाश्ते में पोहा बनाया था और दवाई भी समय पर ले ली", "शाम को बेटी का फ़ोन आया था, बच्चों के स्कूल की बातें हुईं"],
    ["कल मंदिर में भजन था, मैंने भी दो भजन गाए, सबको बहुत अच्छा लगा", "नींद ठीक आई, सुबह छह बजे उठ गई थी",
     "बगीचे में तुलसी और गुलाब को पानी दिया, नया गमला भी लगाया"],
    ["आज बाज़ार गई थी सब्ज़ी लेने, लौकी और टमाटर लाई, दाम बहुत बढ़ गए हैं", "दवाई सुबह और रात दोनों ले रही हूँ",
     "पड़ोस के बच्चे आए थे, उनको कहानी सुनाई राजा और तोते वाली"],
    ["बहुत अच्छा लग रहा है, घुटने का दर्द कम है", "आज रेडियो पर पुराने गाने सुने, लता जी के गाने मुझे बहुत पसंद हैं",
     "बेटे ने नई ऐनक भिजवाई है, अब अख़बार अच्छे से पढ़ पाती हूँ"],
    ["सुबह योग वाली आंटी के साथ टहलने गई, फिर चाय पी", "खाना ठीक खा रही हूँ, आज दाल चावल बनाए थे",
     "शाम को सत्संग में गई थी, वहाँ बहुत लोग मिले"],
]
LATE = [
    ["ठीक हूँ", "हम्म वो क्या कहते हैं वो दवाई, याद नहीं ली या नहीं", "पड़ोस के बच्चे आए थे, उनको कहानी सुनाई राजा और तोते वाली"],
    ["ठीक है", "अकेला लगता है, कोई नहीं आता", "पड़ोस के बच्चे आए थे, उनको कहानी सुनाई राजा और तोते वाली", "ठीक है"],
    ["हाँ", "भूल जाती हूँ आजकल", "मन नहीं लगता, अकेली रहती हूँ", "मन नहीं लगता, अकेली रहती हूँ"],
    ["ठीक", "वो क्या बोलते हैं, नाम याद नहीं आ रहा", "कोई बात नहीं करता"],
    ["हाँ ठीक हूँ", "पड़ोस के बच्चे आए थे, उनको कहानी सुनाई राजा और तोते वाली", "याद नहीं रहता अब"],
]
AI = ["नमस्ते जी, आज कैसा लग रहा है?", "दवाई ली आपने?", "और दिन कैसा रहा?", "आपका ध्यान रखिए, कल फिर बात करेंगे।"]


def _call(senior: Dict[str, Any], days_ago: int, said: List[str], mood: str, n: int) -> Dict[str, Any]:
    ts = time.time() - days_ago * 86400
    transcript = []
    for i, line in enumerate(said):
        transcript.append({"speaker": "ai", "text": AI[min(i, len(AI) - 1)], "time": "10:0%d:00" % i})
        transcript.append({"speaker": "senior", "text": line, "time": "10:0%d:20" % i})
    rec = {"call_id": f"DEMO-{senior['senior_id']}-{n:02d}", "senior_id": senior["senior_id"],
           "senior_name": senior.get("name", ""), "coordinator_code": senior.get("coordinator_code", ""),
           "caller_name": "Saathi", "caller_type": "demo_history", "demo": True, "status": "completed",
           "channel": "app", "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
           "end_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts + 180)), "duration_seconds": 180,
           "transcript": transcript, "mood": mood, "symptoms_reported": [],
           "summary": "Demo history call."}
    rec["speech"] = analyse_call(transcript, mood)
    return rec


def seed(store, senior: Dict[str, Any]) -> bool:
    if any(c.get("senior_id") == senior["senior_id"] and c.get("speech") for c in store.call_records):
        return False
    calls, n = [], 0
    for i, said in enumerate(EARLY + EARLY[:2]):
        n += 1
        calls.append(_call(senior, 28 - 2 * i, said, "good", n))
    for i, said in enumerate(LATE):
        n += 1
        calls.append(_call(senior, 13 - 3 * i if i < 4 else 1, said, "low" if i % 2 else "okay", n))
    store.call_records.extend(calls)
    return True
