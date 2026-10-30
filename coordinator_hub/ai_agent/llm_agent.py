"""
Saathi as a real conversation: a Groq-hosted language model talks, the rule-based agent keeps it safe.

Per turn:
  1. The rule agent (`HealthCheckConversation`) hears every utterance first. It records symptoms / medicine exactly
     as before and is the SAFETY GATE: an emergency or "I need a person" is answered with its scripted line at once,
     without asking the model.
  2. Otherwise the model replies, streamed sentence by sentence, with the call's context (their recent health in
     words, notes from earlier calls, what is still to talk about).
  3. Each sentence passes the output guard (plain spoken text, no medicines/doses, length cap) before it is spoken.
  4. If the model is slow, rate-limited or fails, the rule agent's reply is used for that turn: the call never stalls.
After the call the model writes the care manager's notes and a memory note for the next call.

Same public API as HealthCheckConversation, so the server treats both alike.
"""

import json
import os
import re
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

try:
    from ai_agent.voice_agent import HealthCheckConversation, VOICES, ESCALATE_WORDS, _has_any, is_emergency, normalize_language
    from ai_agent.prompts import SYSTEM_PROMPT, CONTEXT_TEMPLATE, TURN_NOTE, SUMMARY_PROMPT
    from engine.nlp_extractor import extract_symptom_cues
except ImportError:  # imported as a package
    from .voice_agent import HealthCheckConversation, VOICES, ESCALATE_WORDS, _has_any, is_emergency, normalize_language
    from .prompts import SYSTEM_PROMPT, CONTEXT_TEMPLATE, TURN_NOTE, SUMMARY_PROMPT
    from ..engine.nlp_extractor import extract_symptom_cues

LANG_NAME = {"hi": "Hindi", "en": "English (Indian)"}
MAX_REPLY_WORDS = 50
WRAP_UP_TURN = 11
HARD_STOP_TURN = 18


# --------------------------------------------------------------------------------------------- settings
def load_env(path: str) -> None:
    """Minimal .env reader (KEY=VALUE lines). Values already set in the environment win."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


class GroqBackend:
    """
    Thin wrapper over the Groq chat API: model choice, streaming text, JSON answers.
    The free tier limits tokens per minute PER MODEL, so the conversation keeps a short list of good models and moves
    to the next one the moment one is rate-limited (each has its own budget); notes after the call use the last one,
    so they do not eat into the conversation's budget.
    """

    PREFERRED = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "meta-llama/llama-4-maverick-17b-128e-instruct",
                 "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "meta-llama/llama-4-scout-17b-16e-instruct",
                 "llama-3.1-8b-instant"]

    def __init__(self):
        self._client = None
        self._model: Optional[str] = None
        self._chain: Optional[List[str]] = None
        self._lock = threading.Lock()
        self._cool: Dict[str, float] = {}     # model -> time it may be used again after a rate limit
        self.last_error = ""

    @property
    def enabled(self) -> bool:
        return bool(os.getenv("GROQ_API_KEY")) and os.getenv("AEGIS_LLM", "on").lower() not in ("off", "0", "false")

    def client(self):
        with self._lock:
            if self._client is None:
                import httpx
                from groq import Groq
                # short read timeout: if the first words are not back in ~3 s the turn falls back to the rule agent
                self._client = Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=0,
                                    timeout=httpx.Timeout(12.0, connect=3.0, read=3.5))
            return self._client

    def chain(self) -> List[str]:
        """Usable models, best first (GROQ_MODEL, if set, goes first)."""
        if self._chain is None:
            try:
                available = {m.id for m in self.client().models.list().data}
                chain = [m for m in self.PREFERRED if m in available]
            except Exception as e:
                self.last_error = f"models: {e}"
                chain = self.PREFERRED[:3]
            pinned = os.getenv("GROQ_MODEL", "").strip()
            if pinned:
                chain = [pinned] + [m for m in chain if m != pinned]
            self._chain = chain or self.PREFERRED[:1]
        return self._chain

    def model(self) -> str:
        return self._model or self.chain()[0]

    def _ready(self) -> List[str]:
        now = time.time()
        ready = [m for m in self.chain() if self._cool.get(m, 0) <= now]
        return ready or sorted(self.chain(), key=lambda m: self._cool.get(m, 0))[:1]

    def _limited(self, model: str, e: Exception) -> None:
        wait = 20.0
        try:
            wait = float(getattr(e, "response").headers.get("retry-after") or wait)
        except Exception:
            pass
        self._cool[model] = time.time() + min(max(wait, 2.0), 60.0)

    def _extra(self, model: str) -> Dict[str, Any]:
        # reasoning models: keep the thinking short and out of the spoken text
        if "gpt-oss" in model:
            return {"reasoning_effort": "low", "reasoning_format": "hidden"}
        if "qwen3" in model:
            return {"reasoning_effort": "none", "reasoning_format": "hidden"}
        return {}

    def stream(self, messages: List[Dict[str, str]], max_tokens: int = 600, temperature: float = 0.6,
               prefer_last: bool = False) -> Iterator[str]:
        """Streams the reply text; a rate-limited model is skipped for the next one before any text was produced."""
        from groq import RateLimitError
        models = self._ready()
        if prefer_last:
            models = list(reversed(models))
        last: Optional[Exception] = None
        for model in models:
            try:
                resp = self.client().chat.completions.create(model=model, messages=messages, stream=True,
                                                             max_tokens=max_tokens, temperature=temperature,
                                                             **self._extra(model))
                self._model = model
                for chunk in resp:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except RateLimitError as e:
                self._limited(model, e)
                last = e
        if last:
            raise last

    def json(self, messages: List[Dict[str, str]], max_tokens: int = 1200) -> Dict[str, Any]:
        """JSON answer from the LAST usable model, keeping the conversation's model free for the next call."""
        from groq import RateLimitError
        last: Optional[Exception] = None
        for model in reversed(self._ready()):
            try:
                resp = self.client().with_options(timeout=30.0).chat.completions.create(
                    model=model, messages=messages, max_tokens=max_tokens, temperature=0.2,
                    response_format={"type": "json_object"}, **self._extra(model))
                return json.loads(resp.choices[0].message.content or "{}")
            except RateLimitError as e:
                self._limited(model, e)
                last = e
        raise last or RuntimeError("no model")


BACKEND = GroqBackend()


# --------------------------------------------------------------------------------------------- output guard
MARKER = re.compile(r"<\s*(END|FLAG)\b[^>]*>?", re.IGNORECASE)
FLAG = re.compile(r"<\s*FLAG\s+(urgent|soon|routine)\s*:?\s*([^>]*)>", re.IGNORECASE)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F2FF☀-⛿]")
MED_ADVICE = re.compile(
    r"\b\d+(\.\d+)?\s*(mg|ml|mcg|units?|tablets?|tabs?|capsules?|goli(yan|yaan)?|drops)\b|"
    r"\b(paracetamol|ibuprofen|aspirin|crocin|dolo|combiflam|disprin|metformin|amlodipine|atorvastatin|telmisartan|"
    r"losartan|insulin|antibiotics?|painkillers?|pain killers?|dosage|double the dose|stop taking|increase the dose|"
    r"reduce the dose|skip the medicine)\b|"
    r"\d+\s*गोली|गोली\s*\d+|पैरासिटामोल|एस्पिरिन|इंसुलिन|डोज़|खुराक",
    re.IGNORECASE)
SAFE_MED_LINE = {
    "hi": "दवा के बारे में सही सलाह आपके डॉक्टर या केयर मैनेजर ही देंगे, मैं उन्हें बता देती हूँ।",
    "en": "Your doctor or care manager is the right person to advise on medicines, and I'll let them know.",
}


def clean_spoken(text: str) -> str:
    """What may be said aloud: no markers, markdown, list numbering or emoji."""
    t = MARKER.sub("", text)
    t = re.sub(r"<[^>]*$", "", t)                # a marker cut off at the end of the stream
    t = EMOJI.sub("", t)
    t = re.sub(r"[*_#`~|]+", "", t)
    t = re.sub(r"(^|\s)(\d+[.)]|[-•])\s+", r"\1", t)
    t = no_dashes(t)
    return re.sub(r"\s{2,}", " ", t).strip()


def no_dashes(text: str) -> str:
    """Em dashes (and spaced en dashes used the same way) become a comma, so the voice pauses naturally
    and the written notes read like plain sentences."""
    t = re.sub(r"\s*[—―]\s*", ", ", text)
    t = re.sub(r"\s+–\s+", ", ", t)
    return re.sub(r",\s*([.,!?।])", r"\1", t)


def split_sentences(buffer: str):
    """(complete sentences, leftover) - a sentence ends at . ! ? । followed by a space, a line break, or (models
    sometimes glue sentences together) directly by a capital letter or Devanagari."""
    out = []
    while True:
        m = re.search(r"[.!?।]+[\"')\]]?(\s+|(?=[A-Z\u0900-\u097F]))", buffer)
        if not m:
            return out, buffer
        out.append(buffer[:m.end()].strip())
        buffer = buffer[m.end():]


# --------------------------------------------------------------------------------------------- conversation
TOPIC_PATTERNS = {
    "medicine": r"dawa|dawai|davai|medicine|tablet|goli|pill|दवा|दवाई|गोली",
    "sleep": r"neend|nind|sleep|slept|so pa|नींद|सो ",
    "food": r"khana|bhook|bhukh|eat|appetite|food|meal|खाना|भूख|खा ",
    "anything else": r"anything else|anything on your mind|aur kuch|kuch aur|और कुछ|कुछ और",
}


class LLMConversation:
    """A real, health-aware conversation driven by the language model, kept safe by the rule agent."""

    def __init__(self, senior_id: str, senior_name: str, language: str = "hi", backend: GroqBackend = None,
                 care_manager: str = "", gender: str = ""):
        self.senior_id = senior_id
        self.senior_name = senior_name
        self.language = normalize_language(language)
        self.backend = backend or BACKEND
        self.rule = HealthCheckConversation(senior_id, senior_name, self.language)
        self.first_name = (senior_name or "").split()[0] if senior_name else ""
        self.care_manager = (care_manager or "").split()[0] if care_manager else "your care manager"
        g = (gender or "").lower()
        self.gender = ("a woman" if g.startswith("f") else "a man" if g.startswith("m")
                       else "of unknown gender (use neutral, respectful forms)")
        self.transcript: List[Dict[str, str]] = []
        self.messages: List[Dict[str, str]] = []
        self.flags: List[Dict[str, str]] = []
        self.is_completed = False
        self.emergency_escalation = False
        self.ended_no_response = False
        self.turn = 0
        self.started = time.time()
        self.health_text = "Not available yet."
        self.memory_text = "No earlier calls."
        self._context_ready = threading.Event()
        self.llm_turns = 0
        self.fallback_turns = 0
        self.last_timing: Dict[str, Any] = {}
        self.notes: Dict[str, Any] = {}       # filled by summarize() after the call
        self.last_raw = ""                    # the model's last raw reply (debugging)

    # ------------------------------------------------------------------ same surface as the rule agent
    @property
    def voice(self) -> str:
        return VOICES[self.language]

    @property
    def expect(self) -> str:
        return "free"

    @property
    def stage(self) -> str:
        return "done" if self.is_completed else "talk"

    @property
    def step(self) -> int:
        return 4 if self.is_completed else 1

    @property
    def detected_symptoms(self) -> List[str]:
        return self.rule.detected_symptoms

    @property
    def meds_taken(self) -> Optional[bool]:
        if self.notes.get("meds_taken") is not None:
            return self.notes["meds_taken"]
        return self.rule.meds_taken

    @property
    def followup_notes(self) -> List[str]:
        return self.rule.followup_notes

    @property
    def other_notes(self) -> List[str]:
        return self.rule.other_notes

    # ------------------------------------------------------------------ context
    def set_context(self, health: str, memory: str) -> None:
        self.health_text = health or "Nothing notable recorded."
        self.memory_text = memory or "No earlier calls."
        self._context_ready.set()

    def _system_messages(self) -> List[Dict[str, str]]:
        self._context_ready.wait(timeout=2.0)
        ctx = CONTEXT_TEMPLATE.format(language_name=LANG_NAME[self.language], first_name=self.first_name or "unknown",
                                      gender=self.gender,
                                      care_manager=self.care_manager, today=time.strftime("%A, %d %B"),
                                      health=self.health_text, memory=self.memory_text)
        return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "system", "content": ctx}]

    def _turn_note(self) -> Dict[str, str]:
        said = " ".join(m["text"].lower() for m in self.transcript)
        uncovered = [k for k, p in TOPIC_PATTERNS.items() if not re.search(p, said)]
        minutes = (time.time() - self.started) / 60
        pace = ("It is time to wrap up: give your caring encouragement, say goodbye and end with <END>."
                if self.turn >= WRAP_UP_TURN or minutes > 5 else "There is no hurry.")
        if 2 <= self.turn <= 4 and "Nothing notable" not in self.health_text:
            pace += " If you have not yet, gently ask about the most important change in their recent health."
        return {"role": "system", "content": TURN_NOTE.format(turn=self.turn, uncovered=", ".join(uncovered) or "nothing",
                                                               pace=pace, language_name=LANG_NAME[self.language])}

    # ------------------------------------------------------------------ transcript
    def _add(self, speaker: str, text: str) -> None:
        if text:
            self.transcript.append({"speaker": speaker, "text": text, "time": time.strftime("%H:%M:%S")})
            self.messages.append({"role": "assistant" if speaker == "ai" else "user", "content": text})

    # ------------------------------------------------------------------ turns
    def get_greeting(self) -> str:
        g = self.rule.get_greeting()       # scripted and pre-recorded: plays instantly when they pick up
        self._add("ai", g)
        return g

    def process_silence(self) -> str:
        r = self.rule.process_silence()
        if self.rule.is_completed:
            self.is_completed = True
            self.ended_no_response = self.rule.ended_no_response
        self._add("ai", r)
        return r

    def process_user_turn(self, text: str) -> str:
        return " ".join(self.stream_user_turn(text))

    def stream_user_turn(self, text: str) -> Iterator[str]:
        """Yields Saathi's reply sentence by sentence (speak each as soon as it arrives)."""
        text = (text or "").strip()
        if self.is_completed:
            return
        if not text:
            yield self.process_silence()
            return
        self.turn += 1
        self._add("senior", text)
        t0 = time.time()

        # 1. Safety gate first (rules, instant, no model): emergency, a fall, "I want a person"
        low = text.lower()
        if is_emergency(low) or "fall" in extract_symptom_cues(text).get("categories", []):
            self.rule._collect(text)
            reply = self.rule._escalate()
            self.emergency_escalation = True
            self.is_completed = True
            self._add("ai", reply)
            self.last_timing = {"path": "safety", "ms": round((time.time() - t0) * 1000)}
            yield reply
            return
        # The rule agent hears every utterance too: symptoms/medicine for the record, and a ready fallback reply.
        # Once its own short script is over it only keeps collecting symptoms.
        if not self.rule.is_completed:
            rule_reply = self.rule.process_user_turn(text)
        else:
            self.rule._collect(text)
            rule_reply = self.rule.transcript[-1]["text"] if self.rule.transcript else ""

        # 2. The model talks (or the rule agent does, if the model is off or fails)
        spoken: List[str] = []
        raw = ""
        t_first = None
        reason = ""
        if self.backend.enabled and self.turn < HARD_STOP_TURN:
            try:
                msgs = self._system_messages() + self.messages + [self._turn_note()]
                buf, words, asked = "", 0, False
                said_before = {self._norm(x) for t in self.transcript if t["speaker"] == "ai"
                               for x in split_sentences(t["text"] + " ")[0]}
                for delta in self.backend.stream(msgs):
                    raw += delta
                    buf += delta
                    done, buf = split_sentences(buf)
                    for s in done:
                        s = self._guard(s)
                        # one question per reply; never repeat a sentence already said in this call
                        if asked or self._norm(s) in said_before:
                            continue
                        if s and (words == 0 or words + len(s.split()) <= MAX_REPLY_WORDS):
                            asked = "?" in s
                            said_before.add(self._norm(s))
                            s = " ".join(s.split()[:MAX_REPLY_WORDS])   # whole sentences; only a first one is ever cut
                            words += len(s.split())
                            if t_first is None:
                                t_first = time.time()
                            spoken.append(s)
                            yield s
                tail = self._guard(buf)
                if tail and not asked and self._norm(tail) not in said_before and \
                        (words == 0 or words + len(tail.split()) <= MAX_REPLY_WORDS):
                    tail = " ".join(tail.split()[:MAX_REPLY_WORDS])
                    if t_first is None:
                        t_first = time.time()
                    spoken.append(tail)
                    yield tail
            except Exception as e:
                reason = f"{type(e).__name__}: {str(e)[:120]}"
                self.backend.last_error = reason
        else:
            reason = "llm off" if not self.backend.enabled else "turn limit"

        self.last_raw = raw
        if spoken:
            self.llm_turns += 1
            self._apply_markers(raw, " ".join(spoken))
            self._add("ai", " ".join(spoken))
            self.last_timing = {"path": "llm", "first_sentence_ms": round(((t_first or time.time()) - t0) * 1000),
                                "total_ms": round((time.time() - t0) * 1000), "model": self.backend.model()}
            return

        # 3. Fallback: the rule agent's reply keeps the call going
        self.fallback_turns += 1
        if self.turn >= HARD_STOP_TURN and not self.rule.is_completed:
            rule_reply = self.rule._close()
        if self.rule.is_completed:
            self.is_completed = True
        self._add("ai", rule_reply)
        self.last_timing = {"path": "fallback", "reason": reason or "empty reply", "ms": round((time.time() - t0) * 1000)}
        print(f"[LLM] fallback turn ({self.last_timing['reason']})")
        yield rule_reply

    @staticmethod
    def _norm(sentence: str) -> str:
        return re.sub(r"[\W_]+", " ", sentence.lower()).strip()

    def _guard(self, sentence: str) -> str:
        s = clean_spoken(sentence)
        if not s:
            return ""
        if MED_ADVICE.search(s):
            self.flags.append({"urgency": "routine", "note": "Asked about or discussed medicines on the call"})
            return SAFE_MED_LINE[self.language]
        return s

    def _apply_markers(self, raw: str, spoken: str = "") -> None:
        for urgency, note in FLAG.findall(raw):
            note = note.strip()
            if len(note) < 4 or note.lower() in ("note", "...", "one line for the care manager"):
                note = "Raised on the call (see transcript)"
            if not any(f["urgency"] == urgency.lower() for f in self.flags if urgency.lower() == "urgent"):
                self.flags.append({"urgency": urgency.lower(), "note": note[:200]})   # one urgent flag per call is enough
            if urgency.lower() == "urgent":
                self.emergency_escalation = True
        if re.search(r"<\s*END\b", raw, re.IGNORECASE) and self._is_goodbye(spoken):
            self.is_completed = True

    @staticmethod
    def _is_goodbye(spoken: str) -> bool:
        """Models sometimes add <END> after a question. Only a reply that really says goodbye may end the call."""
        bye = re.search(r"\bbye\b|goodbye|take care|talk (to you )?(again|soon|tomorrow)|namaste|नमस्ते|अलविदा|"
                        r"ख़्याल रखिए|ख्याल रखिए|ध्यान रखिए|फिर बात करेंगे|बाद में फ़ोन|बाद में फोन", spoken, re.IGNORECASE)
        return bool(bye) or ("?" not in spoken and bool(spoken.strip()))

    # ------------------------------------------------------------------ after the call
    def summarize(self) -> Dict[str, Any]:
        """The care manager's notes and a memory note for next time (model, JSON). Rules win for medicine/emergency."""
        if not self.backend.enabled or not any(t["speaker"] == "senior" for t in self.transcript):
            return {}
        convo = "\n".join(f"{'Saathi' if t['speaker'] == 'ai' else 'Senior'}: {t['text']}" for t in self.transcript)
        try:
            notes = self.backend.json([{"role": "system", "content": SUMMARY_PROMPT},
                                       {"role": "user", "content": f"Call language: {LANG_NAME[self.language]}\n\n{convo}"}])
        except Exception as e:
            print(f"[LLM] summary failed: {type(e).__name__}: {str(e)[:120]}")
            return {}
        if self.rule.meds_taken is not None:          # an explicit yes/no the rules heard beats the model's reading
            notes["meds_taken"] = self.rule.meds_taken
        self.notes = notes
        return notes

    def get_summary(self) -> Dict[str, Any]:
        extra = " No response (ended after silence)." if self.ended_no_response else ""
        flags = f" Flags: {'; '.join(f['urgency'] + ': ' + f['note'] for f in self.flags)}." if self.flags else ""
        return {
            "senior_id": self.senior_id,
            "status": "completed",
            "duration_seconds": int(time.time() - self.started),
            "transcript": self.transcript,
            "symptoms": list(set(self.detected_symptoms)),
            "meds_taken": self.meds_taken,
            "emergency": self.emergency_escalation,
            "language": self.language,
            "summary": (f"Health check for {self.senior_name}. Symptoms: {', '.join(self.detected_symptoms) or 'None'}. "
                        f"Meds taken: {self.meds_taken}.{flags}{extra}"),
        }


# --------------------------------------------------------------------------------------------- health context
def _num(v, d=0):
    try:
        return round(float(v), d) if d else int(round(float(v)))
    except (TypeError, ValueError):
        return None


def build_health_context(store, senior_id: str) -> Dict[str, str]:
    """Their recent health and earlier calls in plain sentences, for Saathi to use gently. Never raw scores."""
    senior = store.dynamic_seniors.get(senior_id) or store.seniors_map.get(senior_id)
    if not senior:
        return {"health": "", "memory": "", "care_manager": ""}
    lines: List[str] = []
    try:
        row = next((r for r in store.get_coordinator_seniors(senior["coordinator_code"]) if r["senior_id"] == senior_id), None)
    except Exception:
        row = None
    if row:
        for w in row.get("why_today_en", [])[:5]:
            if "within their own normal" in w or "Learning" in w or "learning" in w:
                continue
            lines.append(w.replace("Unusual pattern compared with their normal:", "Overall pattern differs from their usual:"))
        v = row.get("current_vitals", {}) or {}
        if v.get("sleep_hours"):
            lines.append(f"Slept about {v['sleep_hours']} hours last night.")
        if v.get("bp"):
            lines.append(f"Latest blood pressure {v['bp']}.")
    records = senior.get("vitals_history") or (senior.get("records", [])[:80])
    last7 = records[-7:] if records else []
    if last7:
        taken = sum(1 for d in last7 if d.get("meds_taken", True))
        lines.append(f"Took their medicine on {taken} of the last {len(last7)} days.")
        steps = [d.get("steps") for d in last7 if d.get("steps") is not None]
        if steps:
            lines.append(f"Average about {_num(sum(steps) / len(steps))} steps a day over the last {len(steps)} days.")
    cur = senior.get("current_status") or (records[-1] if records else {})
    if cur.get("voice_note"):
        lines.append(f"Today they told the app: \"{str(cur['voice_note'])[:160]}\".")
    # earlier calls: memory notes first, else the first sentence of the summary
    memory = []
    calls = [c for c in reversed(store.call_records) if c.get("senior_id") == senior_id and c.get("status") == "completed"]
    for c in calls[:3]:
        # only the model's own notes: the rule agent's one-line summary carries nothing worth remembering
        note = (c.get("memory_note") or (c.get("ai_summary_en") or "").split(". ")[0]).strip().rstrip(".")
        if note:
            memory.append(f"{(c.get('start_time') or '')[:10]}: {note}.")
    return {"health": "\n".join(f"- {l}" for l in lines) or "Nothing notable recorded.",
            "memory": "\n".join(f"- {m}" for m in memory) or "No earlier calls.",
            "care_manager": senior.get("coordinator_name", "")}
