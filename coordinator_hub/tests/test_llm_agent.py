"""LLM conversation plumbing with a fake model (no network): safety gate, fallback, markers, output guard.
Run from coordinator_hub/:  python tests/test_llm_agent.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_agent.llm_agent import LLMConversation, clean_spoken, split_sentences

FAILS = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


class FakeBackend:
    """Replies from a script; 'RAISE' simulates a timeout / rate limit."""
    enabled = True
    last_error = ""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.seen = []

    def model(self):
        return "fake"

    def stream(self, messages, **kw):
        self.calls += 1
        self.seen.append(messages)
        r = self.replies.pop(0) if self.replies else "Okay."
        if r == "RAISE":
            raise TimeoutError("read timeout")
        for i in range(0, len(r), 7):        # arrive in small pieces, like a real stream
            yield r[i:i + 7]

    def json(self, messages, **kw):
        return {"summary_en": "ok", "meds_taken": None, "memory_note": "Ask about the walk."}


def conv(replies, lang="en"):
    b = FakeBackend(replies)
    c = LLMConversation("S", "Kamla Devi", lang, backend=b, care_manager="Rajesh Verma")
    c.set_context("- Steps are 85% below their normal.", "No earlier calls.")
    c.get_greeting()
    return c, b


c, b = conv(["Oh, I'm sorry to hear that. How long have you been feeling lonely?"])
out = list(c.stream_user_turn("I feel very lonely these days"))
check("the model's reply is spoken sentence by sentence", out == ["Oh, I'm sorry to hear that.", "How long have you been feeling lonely?"])
check("loneliness is still recorded for the care manager", "loneliness" in c.detected_symptoms)
check("the model sees the health context and a turn note", "85% below" in b.seen[0][1]["content"] and "Turn 1" in b.seen[0][-1]["content"])

c, b = conv(["This should never be asked."])
r = c.process_user_turn("I fell down in the bathroom")
check("a fall escalates instantly without asking the model", c.emergency_escalation and c.is_completed and b.calls == 0)
c, b = conv(["This should never be asked."])
c.process_user_turn("I want to talk to a human")
check("'I want a person' is handled by the safety gate", c.emergency_escalation and b.calls == 0)

c, b = conv(["Happy to chat. How are you feeling?", "Nice. Did you sleep well?"])
c.process_user_turn("I'm fine, how can I help you?")
c.process_user_turn("the rest and my cane help a lot")
check("'how can I help you' / 'the cane helps' are not emergencies", not c.emergency_escalation and b.calls == 2)
c, b = conv(["I'm the care team's AI assistant. How are you feeling?"])
c.process_user_turn("Are you a real person or a robot?")
check("'are you a real person or a robot?' is answered by the model, not escalated", not c.emergency_escalation and b.calls == 1)
c, b = conv(["never"])
c.process_user_turn("I want to talk to a real person")
check("'I want to talk to a real person' still reaches a human", c.emergency_escalation and b.calls == 0)

c, b = conv(["How did you sleep last night?I'm an AI assistant. How is your knee?Okay, I understand."])
r = c.process_user_turn("I am fine")
check("glued drafts are split and only one question is asked", r == "How did you sleep last night?")

c, b = conv(["RAISE", "Glad to hear it. Did you sleep well?"])
r1 = c.process_user_turn("I am fine today")
check("a model failure falls back to the rule agent's reply", c.fallback_turns == 1 and "medicine" in r1.lower())
r2 = c.process_user_turn("yes I took it")
check("the next turn goes back to the model", c.llm_turns == 1 and "sleep" in r2.lower())

c, b = conv(["Take care and have a lovely evening, goodbye! <END>"])
r = c.process_user_turn("nothing else, thank you")
check("<END> ends the call and is never spoken", c.is_completed and "<" not in r and "END" not in r)

c, b = conv(["I'm letting your care manager know right away. <FLAG urgent: breathless since morning>"])
c.process_user_turn("I can't catch my breath properly since morning")
check("an urgent flag escalates and keeps the note", c.emergency_escalation and c.flags and "breathless" in c.flags[0]["note"])

c, b = conv(["You should take 2 tablets of paracetamol now. Rest well."])
r = c.process_user_turn("I have a headache")
check("medicine advice is replaced by a safe line and flagged", "paracetamol" not in r.lower() and "doctor" in r.lower() and c.flags)

check("markdown, list numbers and emoji are stripped", clean_spoken("**Hello** 😊 1. walk a bit <FLAG soon: x>") == "Hello walk a bit")
check("sentences split on . ! ? and the Hindi danda", split_sentences("नमस्ते जी। कैसी हैं? ok")[0] == ["नमस्ते जी।", "कैसी हैं?"])

c, b = conv(["Word " * 80 + "end."])
r = c.process_user_turn("tell me something")
check("very long replies are cut to a phone-length answer", len(r.split()) <= 50)

c, b = conv([])
c.backend.enabled = False
r = c.process_user_turn("I am fine")
check("with the model off, the rule agent runs the call", c.fallback_turns == 1 and r)

c, b = conv(["Lovely. How did you sleep?"])
c.process_user_turn("I took my medicine, all fine")
notes = c.summarize()
check("summary merges: an explicit 'took my medicine' wins over the model", c.meds_taken is True and notes.get("memory_note"))

print("\n%d check(s) failed" % len(FAILS) if FAILS else "\nALL CHECKS PASSED")
sys.exit(1 if FAILS else 0)
