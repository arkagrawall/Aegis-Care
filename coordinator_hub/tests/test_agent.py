"""Scripted voice-agent conversations (Hindi, Hinglish, English, silence, repeat, escalation).
Run from coordinator_hub/:  python tests/test_agent.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_agent.voice_agent import HealthCheckConversation as H

FAILS = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def run(lang, turns):
    c = H("S", "Kamla", lang)
    c.get_greeting()
    for t in turns:
        if c.is_completed:
            break
        c.process_silence() if t is None else c.process_user_turn(t)
    return c


c = run("hi", ["theek hoon", "nahi, dawa nahi li", "chakkar aa raha hai"])
check("Hindi: 'nahi' is not read as yes; dizziness found", c.meds_taken is False and "dizziness" in c.detected_symptoms)
c = run("hi", ["सिर में दर्द है", "कल रात से", "हाँ ले ली", "सब ठीक है"])
check("Devanagari: pain found, medicine taken", "pain" in c.detected_symptoms and c.meds_taken is True)
c = run("hi", ["main gir gayi"])
check("fall escalates immediately", c.emergency_escalation and c.is_completed)
c = run("hi", [None, None])
check("two silences end the call politely", c.ended_no_response and c.is_completed)
c = run("hi", ["kya kaha", "theek hoon"])
check("repeat request re-asks instead of advancing", c.stage == "meds")
c = run("hi", ["koi dard nahi hai", "haan", "theek"])
check("negation: 'no pain' is not a symptom", "pain" not in c.detected_symptoms)
c = run("en", ["I am feeling a little dizzy", "since morning", "no I did not take my medicine", "I slept badly"])
check("English call: dizzy, missed medicine, poor sleep", c.meds_taken is False and {"dizziness", "poor_sleep"} <= set(c.detected_symptoms))
check("English call speaks English", "Hello" in c.transcript[0]["text"] and c.voice.startswith("en-IN"))
c = run("en", ["I need a doctor"])
check("English: asking for a doctor escalates", c.emergency_escalation)
c = run("en", ["I'm okay but my knee has been hurting", "two days", "yes", "good", "no"])
check("a problem in the first answer gets a follow-up, not 'good to hear'", "pain" in c.detected_symptoms and "good to hear" not in c.transcript[2]["text"].lower())
c = run("hi", ["theek hoon", "haan le li, par sar mein dard ho raha hai", "subah se", "theek", "bas"])
check("a problem raised while answering about medicine is still followed up", c.meds_taken is True and "pain" in c.detected_symptoms and len(c.followup_notes) == 1)
c = run("en", ["not feeling well today", "my stomach feels upset", "yes", "fine", "no"])
check("'not well' without a named symptom is asked about and kept for the care manager", c.other_notes == ["my stomach feels upset"])
c = run("en", ["fine", "who is this?", "yes", "good", "nothing"])
check("'who is this?' is answered and the question asked again", "Saathi" in c.transcript[4]["text"] and c.meds_taken is True)
c = run("hi", ["baad mein baat karna"])
check("'call later' ends politely", c.is_completed and not c.emergency_escalation)
c = run("en", ["good", "yes", "good", "my son hasn't visited in weeks"])
check("the open question before goodbye records worries in the senior's own words", c.other_notes == ["my son hasn't visited in weeks"])
c = run("en", ["fine", "yes I took it", "slept well and eating fine", "nothing"])
check("a calm call covers medicine, sleep and 'anything else' and ends warmly", c.is_completed and "talk again tomorrow" in c.transcript[-1]["text"])
print("\n%d check(s) failed" % len(FAILS) if FAILS else "\nALL CHECKS PASSED")
sys.exit(1 if FAILS else 0)
