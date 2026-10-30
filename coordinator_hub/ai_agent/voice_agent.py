"""
Aegis Saathi - AI voice check-in agent (free, offline logic; Edge-TTS for the voice).

A short, warm phone conversation, not a questionnaire. Every reply is two parts:
  1. a reaction to what the senior actually said (their symptom, their medicine, their sleep, or plain warmth), then
  2. the next thing to talk about.

What it talks about, in order, skipping what the senior already covered on their own:
  how they feel -> a follow-up on anything worrying they mention -> medicine -> sleep and food
  -> "anything else on your mind?" -> goodbye
The senior can bring up a new problem at ANY point (also while Saathi is still talking: the phone
listens all the time). A new problem gets its own reaction and one follow-up question, then the
conversation picks up where it left off. Emergencies and "I want to talk to a person" are honoured at once.

It never diagnoses or advises treatment: it listens, records and hands over to the care manager.
Language ("hi" | "en") only changes what Saathi SAYS; it understands Hindi, Hinglish and English either way.
Saathi speaks as a woman in both languages (Hindi verb forms are feminine) to match the voices.
"""

import re
import time
from typing import Dict, Any, List, Optional
import edge_tts

try:
    from engine.nlp_extractor import extract_symptom_cues
except ImportError:
    from ..engine.nlp_extractor import extract_symptom_cues

# Voices: one warm female voice per language, a touch slower than default for older listeners
VOICE_HINDI = "hi-IN-SwaraNeural"
VOICE_ENGLISH = "en-IN-NeerjaNeural"
VOICES = {"hi": VOICE_HINDI, "en": VOICE_ENGLISH}
VOICE_RATE = "-6%"

# --------------------------------------------------------------------------- what the senior says
YES_WORDS = ["haan", "han", "ha", "haa", "ji haan", "le li", "kha li", "li thi", "le liya", "yes", "yeah", "yep", "yup",
             "taken", "liya", "done", "i did", "i have", "already", "of course", "sure",
             "ले ली", "खा ली", "ले लिया", "ली थी", "हाँ", "हां", "हा", "जी हाँ", "जी हां"]
NO_WORDS = ["nahi", "nahin", "nhi", "no", "not", "didn't", "didnt", "haven't", "havent", "chhut", "chhoot",
            "bhool", "bhul", "missed", "skipped", "forgot", "forgotten",
            "नहीं", "नही", "छूट", "भूल", "नहिं"]
# Emergencies and "I want a person". Phrases, not single words: "help" alone also appears in "how can I help you"
# or "the cane helps", and "care manager" in "my care manager called yesterday".
ESCALATE_WORDS = [
    "need help", "help me", "please help", "get help", "send help", "call for help", "i need someone",
    "emergency", "ambulance", "bachao", "madad chahiye", "madad karo", "madad kijiye", "madad bhejo",
    "talk to a human", "talk to a person", "talk to a real person", "speak to a real person", "speak to a person",
    "speak to someone", "talk to someone",
    "talk to my care manager", "call my care manager", "call the coordinator", "talk to the coordinator",
    "insaan se baat", "insan se baat", "kisi se baat karni", "kisi se baat karwa", "baat karwa do",
    "doctor chahiye", "doctor ko bulao", "need a doctor", "call a doctor", "bahut tez dard", "severe pain",
    "gir gaye", "gir gayi", "gir gaya", "gir padi", "gir pada", "i fell", "i have fallen", "fell down",
    "seene mein dard", "seene me dard", "chest pain", "saans nahi", "can't breathe", "cannot breathe",
    "hard to breathe", "behosh", "unconscious",
    "इंसान से बात", "किसी से बात करनी", "केयर मैनेजर से बात", "इमरजेंसी", "आपातकाल", "बचाओ", "बचाइए",
    "मदद चाहिए", "मदद करो", "मदद कीजिए", "मदद भेजो",
    "डॉक्टर चाहिए", "डॉक्टर को बुलाओ", "बहुत तेज़ दर्द", "बहुत तेज दर्द",
    "गिर गए", "गिर गई", "गिर गया", "गिर पड़ी", "गिर पड़ा", "सीने में दर्द", "सांस नहीं", "साँस नहीं", "बेहोश",
    # "I am dying" and other life-threatening words: these also ring the emergency contact (engine/emergency.py)
    "i am dying", "i'm dying", "im dying", "i think i am dying", "going to die", "gonna die", "i will die",
    "i'll die", "about to die", "heart attack", "can't move", "cannot move", "choking",
    "mar raha hoon", "mar raha hu", "mar rahi hoon", "mar rahi hu", "mar jaunga", "mar jaungi", "mar jaoonga",
    "mar jaoongi", "marne wala", "marne wali", "jaan ja rahi", "jaan nikal rahi", "dum ghut", "dil ka daura",
    "मर रहा", "मर रही", "मर जाऊँगा", "मर जाऊंगा", "मर जाऊँगी", "मर जाऊंगी", "मरने वाला", "मरने वाली",
    "जान जा रही", "जान निकल रही", "दम घुट", "दिल का दौरा",
    # English said on a Hindi call comes back in Devanagari: "I am dying" -> "आई एम डाइंग"
    "डाइंग", "डाईंग", "आई विल डाई", "गोइंग टू डाई", "हार्ट अटैक", "हार्ट अटेक", "चेस्ट पेन", "चेस्ट में दर्द",
    "हेल्प मी", "प्लीज़ हेल्प", "प्लीज हेल्प", "कांट ब्रीद", "कान्ट ब्रीद", "आई फेल", "आई हैव फॉलन",
    "एम्बुलेंस", "एंबुलेंस",
]
# Everyday idioms that use the same words; they are cut out of the text before the emergency check.
BENIGN_EMERGENCY = [
    r"dying (?:to|for)\b", r"dying of (?:laughter|boredom)", r"(?:laughing|laughed) to death",
    r"\bbored to death", r"hans hans ke mar\w*", r"bore ho(?:ke|kar)? mar\w*",
    r"हँस हँस के मर\S*", r"हंस हंस के मर\S*", r"बोर हो(?:के|कर)? मर\S*",
    r"डा(?:इ|ई)ंग (?:टू|फॉर|फोर)(?!\S)", r"हेयर डा(?:इ|ई)ंग",
]
REPEAT_WORDS = ["dobara", "dubara", "phir se", "fir se", "repeat", "kya kaha", "samajh nahi", "sunai nahi",
                "sun nahi", "again", "pardon", "say that again", "what did you say", "come again",
                "दोबारा", "दुबारा", "फिर से", "क्या कहा", "समझ नहीं", "सुनाई नहीं", "सुन नहीं"]
WHO_WORDS = ["kaun", "who is this", "who are you", "who is calling", "kahan se", "where are you calling",
             "कौन", "कहाँ से"]
BUSY_WORDS = ["baad mein", "baad me", "abhi nahi", "busy", "call later", "call me later", "not now", "later please",
              "बाद में", "अभी नहीं", "व्यस्त"]
GOOD_WORDS = ["theek", "thik", "achha", "accha", "acha", "badhiya", "fine", "good", "mast", "great", "well", "better",
              "okay", "alright", "normal", "sab theek", "ठीक", "अच्छा", "अच्छी", "बढ़िया", "सब ठीक"]
NOTHING_WORDS = ["nahi", "nahin", "kuch nahi", "bas", "no", "nothing", "that's all", "thats all", "nope", "all good",
                 "sab theek", "koi nahi", "नहीं", "कुछ नहीं", "बस", "सब ठीक", "कोई नहीं"]
CONTRAST_WORDS = ["but", "except", "however", "though", "par", "lekin", "magar", "bas thoda", "पर", "लेकिन", "मगर"]
UNWELL_WORDS = ["not well", "not good", "not fine", "unwell", "not feeling well", "bad", "not so good", "not great",
                "theek nahi", "thik nahi", "achha nahi", "tabiyat kharab", "tabiyat theek nahi", "kharab",
                "ठीक नहीं", "अच्छा नहीं", "ख़राब", "खराब"]
FILLERS = {"hmm", "hm", "um", "uh", "mm", "haan haan", "हम्म", "हूँ", "हूं", "ji", "जी"}

# --------------------------------------------------------------------------- what Saathi says
# Every reply = reaction + " " + next line. Both halves come from these tables only, so every possible reply
# can be rendered to voice ahead of time (static_lines) and plays without waiting for the voice service.
TEXT: Dict[str, Dict[str, Any]] = {
    "hi": {
        "greeting": "नमस्ते {name} जी! मैं साथी बोल रही हूँ, आपकी केयर टीम से। आज आपकी तबीयत कैसी है?",
        "who": "मैं साथी हूँ जी, आपके केयर मैनेजर की टीम से। बस आपका हालचाल पूछने के लिए फ़ोन किया है।",
        "hello": "हैलो? {name} जी, क्या मेरी आवाज़ आ रही है?",
        "silence_end": "लगता है अभी बात नहीं हो पा रही। कोई बात नहीं, मैं थोड़ी देर बाद फिर फ़ोन करूँगी। अपना ख़्याल रखिए, नमस्ते।",
        "busy_end": "ठीक है जी, कोई बात नहीं। मैं बाद में फिर फ़ोन करूँगी। अपना ख़्याल रखिए, नमस्ते।",
        "escalate": "{name} जी, मैं अभी आपके केयर मैनेजर को ख़बर कर रही हूँ, वे तुरंत आपसे बात करेंगे। घबराइए मत, मदद आ रही है।",
        "close_sym": "आपसे बात करके अच्छा लगा {name} जी। आपने जो बताया, वह मैं आपके केयर मैनेजर को बता दूँगी, वे जल्दी आपसे बात करेंगे। अपना ख़्याल रखिए, नमस्ते।",
        "close_ok": "आपसे बात करके बहुत अच्छा लगा {name} जी। ऐसे ही अपना ख़्याल रखिए। कल फिर बात करेंगे, नमस्ते।",
        "repeat_lead": "जी, मैं फिर से पूछती हूँ।",
        "fillers": ["जी, अच्छा।", "अच्छा, जी।"],
        # home-screen "tell us by voice"
        "note_good": "यह सुनकर अच्छा लगा! मैंने आपकी बात आपकी केयर टीम तक पहुँचा दी है।",
        "note_talk": "यह सुनकर चिंता हुई। आइए, थोड़ी बात करते हैं, मैं अभी आपसे जुड़ रही हूँ।",
        "note_emergency": "मैंने अभी आपके केयर मैनेजर को ख़बर कर दी है, वे तुरंत आपसे बात करेंगे। घबराइए मत।",
        "q": {
            "meds": ["और आज सुबह की दवा ले ली थी?", "अच्छा, और सुबह वाली दवा ले ली आपने?"],
            "life": ["रात को नींद कैसी आई, और खाना-पीना ठीक चल रहा है?", "नींद कैसी रही कल रात? और भूख ठीक लग रही है?"],
            "anything": ["इसके अलावा कोई और परेशानी हो, या कुछ बताना चाहें तो बताइए, मैं सुन रही हूँ।",
                         "और कुछ है जो आप बताना चाहेंगे? कोई भी बात हो।"],
            "meds_again": "माफ़ कीजिए, ठीक से समझ नहीं पाई। दवा ले ली थी आज, हाँ या नहीं?",
            "meds_soft": "और आज की दवा, वह ले ली थी?",
        },
        "react": {
            "good": ["यह सुनकर अच्छा लगा!", "वाह, बहुत अच्छी बात है।"],
            "neutral": ["अच्छा, जी।", "जी, समझ गई।"],
            "meds_yes": ["बहुत बढ़िया, दवा समय पर लेना बहुत अच्छा है।", "बढ़िया, ऐसे ही ध्यान रखिए।"],
            "meds_no": ["कोई बात नहीं। मैं केयर मैनेजर को बता दूँगी, ताकि वे दवा याद दिलाने में मदद कर सकें।"],
            "meds_unclear": ["ठीक है जी, कोई बात नहीं।"],
            "life_ok": ["अच्छी नींद और अच्छा खाना, यही तो असली दवा है।", "यह सुनकर तसल्ली हुई।"],
            "noted": ["जी, यह भी मैं केयर मैनेजर को बता दूँगी।", "समझ गई जी, मैंने यह बात लिख ली है।"],
            "followup_done": ["समझ गई जी। यह बात मैं आपके केयर मैनेजर को ज़रूर बताऊँगी।", "ठीक है जी, मैंने लिख लिया है, केयर मैनेजर तक पहुँचा दूँगी।"],
        },
        # what Saathi says on hearing a problem, then the one follow-up she asks about it
        "empathy": {
            "dizziness": "अरे, चक्कर आ रहे हैं? यह सुनकर चिंता हुई।",
            "pain": "ओह, दर्द हो रहा है? यह तो तकलीफ़ की बात है।",
            "fever_infection": "अच्छा, बुखार या खाँसी है? आराम करना ज़रूरी है।",
            "weakness": "कमज़ोरी लग रही है, अच्छा।",
            "loneliness": "अकेलापन लगता है, यह मैं समझ सकती हूँ।",
            "low_appetite": "भूख कम लग रही है, अच्छा।",
            "poor_sleep": "नींद ठीक से नहीं आ रही, अच्छा।",
            "confusion": "भूलने या उलझन की बात, अच्छा।",
            "medication_issue": "दवा को लेकर परेशानी है, अच्छा।",
            "unwell": "ओह, तबीयत ठीक नहीं लग रही?",
        },
        "followup": {
            "dizziness": "यह कब से हो रहा है? और अभी आप बैठे हुए हैं ना?",
            "pain": "दर्द कहाँ है, और कब से है?",
            "fever_infection": "यह कब से है?",
            "weakness": "यह कब से महसूस हो रही है?",
            "loneliness": "आज किसी से बात हुई? घर में कोई साथ है?",
            "low_appetite": "कितने दिनों से ऐसा है?",
            "poor_sleep": "कितने दिनों से नींद की परेशानी है?",
            "confusion": "यह कब से लग रहा है?",
            "medication_issue": "क्या दवा ख़त्म हो गई है, या कोई और दिक्कत है?",
            "unwell": "बताइए जी, क्या तकलीफ़ हो रही है?",
        },
    },
    "en": {
        "greeting": "Hello {name}! This is Saathi, from your care team. How are you feeling today?",
        "who": "I'm Saathi, from your care manager's team. I just called to see how you're doing.",
        "hello": "Hello? {name}, can you hear me?",
        "silence_end": "It seems now isn't a good time. That's alright, I'll call you a little later. Take care, bye for now.",
        "busy_end": "Of course, no problem at all. I'll call you back later. Take care, bye for now.",
        "escalate": "{name}, I'm letting your care manager know right now, and they will call you straight away. Don't worry, help is coming.",
        "close_sym": "It was lovely talking to you, {name}. I'll pass on what you told me to your care manager, and they'll be in touch soon. Take care, bye for now.",
        "close_ok": "It was lovely talking to you, {name}. Keep taking care of yourself, and we'll talk again tomorrow. Bye for now.",
        "repeat_lead": "Sure, let me ask again.",
        "fillers": ["Okay, I see.", "Alright."],
        # home-screen "tell us by voice"
        "note_good": "That's lovely to hear! I've shared it with your care team.",
        "note_talk": "I'm sorry to hear that. Let's talk for a moment, I'm connecting you now.",
        "note_emergency": "I've alerted your care manager right now, and they will call you straight away. Please don't worry.",
        "q": {
            "meds": ["And did you take your morning medicine today?", "And did you manage to take your medicine this morning?"],
            "life": ["How did you sleep last night, and are you eating well?", "How was your sleep last night? And how is your appetite?"],
            "anything": ["Is there anything else bothering you, or anything you'd like to tell me? I'm listening.",
                         "Anything else on your mind? Anything at all."],
            "meds_again": "Sorry, I didn't quite catch that. Did you take your medicine today, yes or no?",
            "meds_soft": "And your medicine today, did you take it?",
        },
        "react": {
            "good": ["That's lovely to hear!", "Oh, that's good to hear."],
            "neutral": ["I see.", "Alright."],
            "meds_yes": ["Wonderful, taking it on time really helps.", "Good, keep it up."],
            "meds_no": ["That's okay. I'll let your care manager know, so they can help you remember."],
            "meds_unclear": ["That's alright."],
            "life_ok": ["Good sleep and good food, that's the best medicine.", "That's reassuring to hear."],
            "noted": ["I'll make sure your care manager hears about that too.", "I understand, I've noted that down."],
            "followup_done": ["I understand. I'll make sure your care manager knows about this.", "Alright, I've noted it, and I'll pass it on to your care manager."],
        },
        "empathy": {
            "dizziness": "Oh, you're feeling dizzy? I'm sorry to hear that.",
            "pain": "Oh no, you're in pain? That must be hard.",
            "fever_infection": "A fever or a cough, I see. Rest is important.",
            "weakness": "Feeling weak, I see.",
            "loneliness": "Feeling lonely, I understand. That's not easy.",
            "low_appetite": "Not feeling hungry, I see.",
            "poor_sleep": "Not sleeping well, I see.",
            "confusion": "Feeling forgetful or confused, I see.",
            "medication_issue": "Some trouble with your medicine, I see.",
            "unwell": "Oh, you're not feeling well?",
        },
        "followup": {
            "dizziness": "Since when has this been happening? And are you sitting down right now?",
            "pain": "Where does it hurt, and since when?",
            "fever_infection": "Since when have you had it?",
            "weakness": "Since when have you been feeling this way?",
            "loneliness": "Have you spoken to anyone today? Is someone at home with you?",
            "low_appetite": "For how many days has it been like this?",
            "poor_sleep": "For how many days has your sleep been disturbed?",
            "confusion": "Since when have you noticed this?",
            "medication_issue": "Has the medicine run out, or is it something else?",
            "unwell": "Tell me, what's troubling you?",
        },
    },
}
FOLLOWUP_PRIORITY = ["dizziness", "pain", "fever_infection", "weakness", "confusion", "medication_issue",
                     "low_appetite", "poor_sleep", "loneliness", "unwell"]
MAX_FOLLOWUPS = 2          # keep the call short: at most two follow-up questions per call
FLOW = ["meds", "life", "anything"]


def normalize_language(lang: Optional[str]) -> str:
    return "en" if (lang or "").lower().startswith("en") else "hi"


def join(*parts: str) -> str:
    return " ".join(p for p in parts if p).strip()


def static_lines(language: str) -> List[str]:
    """Every sentence Saathi can say that does not depend on the senior's own words (with the name left out, as
    names are removed before text-to-speech anyway). Pre-rendered at startup so replies play instantly."""
    t = TEXT[normalize_language(language)]
    name = ""
    fixed = [t["greeting"], t["who"], t["hello"], t["silence_end"], t["busy_end"], t["escalate"], t["close_sym"], t["close_ok"]]
    fixed += t["fillers"]          # a short "okay, I see" while the language model is thinking
    fixed += [t["note_good"], t["note_talk"], t["note_emergency"]]
    out = [s.format(name=name) for s in fixed]
    questions = [q for k in FLOW for q in t["q"][k]] + [t["q"]["meds_again"], t["q"]["meds_soft"]]
    reactions = [""] + [r for rs in t["react"].values() for r in rs]
    out += [join(r, q) for r in reactions for q in questions]
    out += [join(t["empathy"][c], t["followup"][c]) for c in t["followup"]]
    asked = questions + list(t["followup"].values()) + [t["greeting"].format(name=name)]
    out += [join(t["who"], q) for q in asked]
    out += [join(t["repeat_lead"], q) for q in asked]
    out += [join(r, t["close_sym"].format(name=name)) for r in reactions] + [join(r, t["close_ok"].format(name=name)) for r in reactions]
    seen, uniq = set(), []
    for s in out:
        s = re.sub(r"\s{2,}", " ", re.sub(r"\s+([!?.,।])", r"\1", s)).strip()
        if s and s not in seen:
            seen.add(s); uniq.append(s)
    return uniq


def _has_any(text: str, words: List[str]) -> bool:
    """Whole-word match for Roman words; substring match for Devanagari (matras break \\b)."""
    for w in words:
        if re.search(r"[ऀ-ॿ]", w):
            if w in text:
                return True
        elif re.search(r"(?<![a-z0-9'])" + re.escape(w) + r"(?![a-z0-9'])", text):
            return True
    return False


# Asking for a person is an escalation to the care manager, not a danger: it never rings the family.
PERSON_WORDS = [
    "talk to a human", "talk to a person", "talk to a real person", "speak to a real person", "speak to a person",
    "speak to someone", "talk to someone", "talk to my care manager", "call my care manager", "call the coordinator",
    "talk to the coordinator", "insaan se baat", "insan se baat", "kisi se baat karni", "kisi se baat karwa",
    "baat karwa do", "इंसान से बात", "किसी से बात करनी", "केयर मैनेजर से बात",
]
DANGER_WORDS = [w for w in ESCALATE_WORDS if w not in PERSON_WORDS]


def _without_idioms(text: str) -> str:
    low = (text or "").lower()
    for pat in BENIGN_EMERGENCY:
        low = re.sub(pat, " ", low)
    return low


def is_danger(text: str) -> bool:
    """Words that mean the senior may be in danger ("I am dying", "chest pain", "I fell"): the family gets a call."""
    return _has_any(_without_idioms(text), DANGER_WORDS)


def is_emergency(text: str) -> bool:
    """An emergency or "I want a person" phrase, once everyday idioms ("dying to see him") are cut out."""
    return _has_any(_without_idioms(text), ESCALATE_WORDS)


class HealthCheckConversation:
    """A warm, safe, non-diagnostic check-in call. Same public API as before."""

    def __init__(self, senior_id: str, senior_name: str, language: str = "hi"):
        self.senior_id = senior_id
        self.senior_name = senior_name
        self.language = normalize_language(language)
        self._t = TEXT[self.language]
        self.stage = "feel"          # feel -> followup -> meds -> life -> anything -> done
        self.transcript: List[Dict[str, str]] = []
        self.detected_symptoms: List[str] = []
        self.meds_taken: Optional[bool] = None
        self.emergency_escalation: bool = False
        self.is_completed: bool = False
        self.ended_no_response: bool = False
        self.last_question: str = ""
        self.consecutive_silence = 0
        self.followup_notes: List[str] = []
        self.other_notes: List[str] = []     # things the senior raised that are not a known symptom
        self._concern = False                # something worrying was said that has no symptom word
        self._meds_retry = 0
        self._followups_asked = 0
        self._asked_about: List[str] = []    # symptoms already followed up
        self._followup_for: Optional[str] = None
        self._resume = "meds"                # where to continue after a follow-up
        self._done_topics: set = set()       # topics the senior already answered unprompted
        self._turn = 0                       # rotates phrasing so it never sounds like a loop

    # ------------------------------------------------------------------ helpers
    @property
    def voice(self) -> str:
        return VOICES[self.language]

    @property
    def expect(self) -> str:
        """What kind of answer the last question wants: 'yesno' (short) or 'free'."""
        return "yesno" if self.stage == "meds" else "free"

    @property
    def step(self) -> int:
        """Backward-compatible numeric step (1=feel/followup, 2=meds, 3=life/anything, 4=done)."""
        return {"feel": 1, "followup": 1, "meds": 2, "life": 3, "anything": 3, "done": 4}[self.stage]

    def _pick(self, options: List[str]) -> str:
        return options[self._turn % len(options)]

    def _react(self, kind: str) -> str:
        return self._pick(self._t["react"][kind])

    def _say(self, msg: str, question: Optional[str] = None) -> str:
        msg = re.sub(r"\s+([!?.,।])", r"\1", msg).strip()
        if question is not None:
            self.last_question = question
        self.transcript.append({"speaker": "ai", "text": msg, "time": time.strftime("%H:%M:%S")})
        self._turn += 1
        return msg

    def _escalate(self) -> str:
        self.emergency_escalation = True
        self.is_completed = True
        self.stage = "done"
        return self._say(self._t["escalate"].format(name=self.senior_name))

    def _close(self, reaction: str = "") -> str:
        self.is_completed = True
        self.stage = "done"
        worried = self.detected_symptoms or self.meds_taken is False or self._concern
        key = "close_sym" if worried else "close_ok"
        return self._say(join(reaction, self._t[key].format(name=self.senior_name)))

    def _collect(self, utterance: str) -> List[str]:
        """Symptom cues in this utterance; returns only the NEW ones (already-known ones are not re-asked)."""
        cues = extract_symptom_cues(utterance).get("categories", [])
        new = [c for c in cues if c not in self.detected_symptoms]
        for c in cues:
            if c not in self.detected_symptoms:
                self.detected_symptoms.append(c)
        return new

    def _next_topic(self) -> Optional[str]:
        for k in FLOW:
            if k not in self._done_topics:
                return k
        return None

    def _ask(self, topic: Optional[str], reaction: str) -> str:
        """Reaction to what was said + the next topic (or goodbye when everything is covered)."""
        if topic is None:
            return self._close(reaction)
        self.stage = topic
        q = self._pick(self._t["q"][topic])
        return self._say(join(reaction, q), question=q)

    def _maybe_followup(self, new_cues: List[str], resume: str) -> Optional[str]:
        """A newly mentioned problem gets empathy and one follow-up question (at most MAX_FOLLOWUPS per call)."""
        if self._followups_asked >= MAX_FOLLOWUPS:
            return None
        for c in FOLLOWUP_PRIORITY:
            if c in new_cues and c not in self._asked_about and c in self._t["followup"]:
                self._followups_asked += 1
                self._asked_about.append(c)
                self._followup_for = c
                self._resume = resume
                self.stage = "followup"
                q = self._t["followup"][c]
                return self._say(join(self._t["empathy"][c], q), question=q)
        return None

    def _mark_unprompted(self, low: str, new_cues: List[str]) -> None:
        """If the senior already talked about medicine / sleep / food on their own, don't ask about it again."""
        m = re.search(r"dawa|dawai|davai|medicine|tablet|goli|दवा|दवाई|गोली", low) if self.meds_taken is None else None
        if m:
            # only the words around "medicine" count: in "dawa le li, par neend nahi aayi" the "nahi" is about sleep
            near = low[max(0, m.start() - 30): m.end() + 30]
            if re.search(r"\b(took|taken|have taken|le li|le liya|kha li|li thi)\b|ले ली|ले लिया|खा ली|ली थी", near):
                self.meds_taken = True; self._done_topics.add("meds")
            elif _has_any(near, NO_WORDS):
                self.meds_taken = False; self._done_topics.add("meds")
            elif _has_any(near, YES_WORDS):
                self.meds_taken = True; self._done_topics.add("meds")
        if {"poor_sleep", "low_appetite"} & set(new_cues) and re.search(r"neend|nind|sleep|bhook|bhukh|khana|appetite|eat|नींद|भूख|खाना", low):
            self._done_topics.add("life")

    @staticmethod
    def _plainly_good(low: str) -> bool:
        return _has_any(low, GOOD_WORDS) and not _has_any(low, CONTRAST_WORDS) and not _has_any(low, UNWELL_WORDS)

    # ------------------------------------------------------------------ public API
    def get_greeting(self) -> str:
        self.stage = "feel"
        g = self._t["greeting"].format(name=self.senior_name)
        return self._say(g, question=g)

    def process_silence(self) -> str:
        """The senior said nothing for the listening window."""
        if self.is_completed:
            return self.transcript[-1]["text"] if self.transcript else ""
        self.consecutive_silence += 1
        if self.consecutive_silence >= 3 or (self.consecutive_silence >= 2 and self.stage == "feel"):
            self.ended_no_response = True
            self.is_completed = True
            self.stage = "done"
            return self._say(self._t["silence_end"])
        if self.consecutive_silence == 1:
            return self._say(self._t["hello"].format(name=self.senior_name))
        return self._say(join(self._t["repeat_lead"], self.last_question))

    def process_user_turn(self, user_utterance: str) -> str:
        """What the senior said -> Saathi's next line."""
        if self.is_completed:
            return self.transcript[-1]["text"] if self.transcript else ""

        text = (user_utterance or "").strip()
        low = text.lower()
        if not text or low in FILLERS:
            return self.process_silence()

        self.consecutive_silence = 0
        self.transcript.append({"speaker": "senior", "text": text, "time": time.strftime("%H:%M:%S")})
        words = len(low.split())

        # 1. Emergency or "I want a person": at any point, immediately
        if is_emergency(low):
            self._collect(text)
            return self._escalate()
        new = self._collect(text)
        if "fall" in new:
            return self._escalate()

        # 2. Short conversational moves: "who is this?", "say that again", "I'm busy"
        if words <= 6 and _has_any(low, WHO_WORDS):
            return self._say(join(self._t["who"], self.last_question), question=self.last_question)
        if words <= 4 and _has_any(low, REPEAT_WORDS):
            return self._say(join(self._t["repeat_lead"], self.last_question), question=self.last_question)
        if words <= 6 and _has_any(low, BUSY_WORDS) and not new:
            self.is_completed = True
            self.stage = "done"
            return self._say(self._t["busy_end"])

        self._mark_unprompted(low, new)

        # 3. The topic we are on
        if self.stage == "feel":
            unwell = ["unwell"] if not new and (_has_any(low, UNWELL_WORDS) or (_has_any(low, CONTRAST_WORDS) and words > 3)) else []
            fu = self._maybe_followup(new + unwell, resume="meds")
            if fu:
                return fu
            reaction = self._react("good") if self._plainly_good(low) and not self.detected_symptoms else self._react("neutral")
            return self._ask(self._next_topic(), reaction)

        if self.stage == "followup":
            self.followup_notes.append(text)
            if self._followup_for == "unwell" and not new:
                self.other_notes.append(text)       # a complaint we have no word for still reaches the care manager
                self._concern = True
            fu = self._maybe_followup(new, resume=self._resume)
            if fu:
                return fu
            return self._ask(self._next_topic(), self._react("followup_done"))

        if self.stage == "meds":
            if self.meds_taken is None:
                if _has_any(low, NO_WORDS):
                    self.meds_taken = False
                elif _has_any(low, YES_WORDS):
                    self.meds_taken = True
            if self.meds_taken is None and not new and self._meds_retry == 0:
                self._meds_retry = 1
                if words > 3:            # they told us something else: keep it, then gently come back
                    self.other_notes.append(text)
                    q = self._t["q"]["meds_soft"]
                    return self._say(join(self._react("neutral"), q), question=q)
                q = self._t["q"]["meds_again"]
                return self._say(q, question=q)
            self._done_topics.add("meds")
            fu = self._maybe_followup(new, resume="life")
            if fu:
                return fu
            kind = "meds_yes" if self.meds_taken else "meds_no" if self.meds_taken is False else ("noted" if new else "meds_unclear")
            return self._ask(self._next_topic(), self._react(kind))

        if self.stage == "life":
            self._done_topics.add("life")
            fu = self._maybe_followup(new, resume="anything")
            if fu:
                return fu
            if not new and not self._plainly_good(low) and (_has_any(low, CONTRAST_WORDS) or _has_any(low, UNWELL_WORDS)):
                self.other_notes.append(text)
                self._concern = True
                return self._ask(self._next_topic(), self._react("noted"))
            kind = "noted" if new else ("life_ok" if self._plainly_good(low) else "neutral")
            return self._ask(self._next_topic(), self._react(kind))

        # stage == "anything": the open question before goodbye
        self._done_topics.add("anything")
        fu = self._maybe_followup(new, resume="done")
        if fu:
            return fu
        if new:
            return self._close(self._react("noted"))
        if words <= 4 and _has_any(low, NOTHING_WORDS):
            return self._close()
        # something we don't have a word for (a family worry, a request): keep it for the care manager
        self.other_notes.append(text)
        self._concern = True
        return self._close(self._react("noted"))

    def get_summary(self) -> Dict[str, Any]:
        extra = " No response (ended after silence)." if self.ended_no_response else ""
        notes = f" Also said: {' | '.join(self.other_notes)}." if self.other_notes else ""
        return {
            "senior_id": self.senior_id,
            "status": "completed",
            "duration_seconds": len(self.transcript) * 12,
            "transcript": self.transcript,
            "symptoms": list(set(self.detected_symptoms)),
            "meds_taken": self.meds_taken,
            "emergency": self.emergency_escalation,
            "language": self.language,
            "summary": (
                f"Health check for {self.senior_name}. Symptoms: {', '.join(self.detected_symptoms) or 'None'}. "
                f"Meds taken: {self.meds_taken}.{notes}{extra}"
            ),
        }


async def synthesize_speech_file(text: str, output_path: str, voice: str = VOICE_HINDI) -> str:
    """Synthesizes speech to an MP3 file using free Edge-TTS."""
    communicate = edge_tts.Communicate(text, voice, rate=VOICE_RATE)
    await communicate.save(output_path)
    return output_path
