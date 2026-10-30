"""
Aegis Saathi - Server-side Speech-to-Text (free, runs on the laptop CPU)

Two interchangeable engines, both return Devanagari Hindi which nlp_extractor and
voice_agent understand:

  vosk     real-time (<1 s), small Hindi model in coordinator_hub/models/. Best for the short
           answers of a health-check call ("haan, le li", "chakkar aa raha hai").
  whisper  faster-whisper. More accurate on long free speech but ~10 s per answer on a 4-core
           CPU, so it is opt-in.

Env vars:
    AEGIS_STT_ENGINE      auto (default: vosk if its model is present, else whisper) | vosk | whisper
    AEGIS_VOSK_MODEL_HI / AEGIS_VOSK_MODEL_EN   Vosk model dirs (default models/vosk-model-small-*)
    AEGIS_WHISPER_MODEL   tiny | base | small (default) | medium
    AEGIS_WHISPER_LANG    hi (default)
"""

import io
import json
import os
import threading
import wave
import zlib
from typing import Any, Dict

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODELS = os.path.join(os.path.dirname(_HERE), "models")
_DEFAULT_VOSK = {
    "hi": os.path.join(_MODELS, "vosk-model-small-hi-0.22"),
    "en": os.path.join(_MODELS, "vosk-model-small-en-in-0.4"),
}

_WHISPER_PROMPT = {
    "hi": (
        "स्वास्थ्य जाँच बातचीत। दर्द, चक्कर, कमज़ोरी, बुखार, खाँसी, दवा ले ली, दवा नहीं ली, "
        "नींद, भूख, गिर गई, सीने में दर्द, सांस फूल रही है। हाँ, नहीं, ठीक हूँ।"
    ),
    "en": (
        "Health check conversation. Pain, dizzy, weak, fever, cough, took my medicine, did not take "
        "my medicine, sleep, appetite, I fell down, chest pain, short of breath. Yes, no, I am fine."
    ),
}


def _drop_if_repetitive(text: str) -> str:
    """Whisper can loop on a syllable ("बादा बादा बादा ...") for unclear audio - treat as unintelligible."""
    if not text:
        return text
    raw = text.encode("utf-8")
    if len(raw) > 40 and len(raw) / max(len(zlib.compress(raw)), 1) > 2.4:
        return ""
    words = text.split()
    if len(words) >= 8 and len(set(words)) / len(words) < 0.35:
        return ""
    return text


def decode_wav(wav_bytes: bytes) -> np.ndarray:
    """PCM16 WAV (any channels/rate) -> mono float32 at 16 kHz. Avoids PyAV/ffmpeg entirely."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            if w.getsampwidth() != 2:
                raise ValueError("WAV must be 16-bit PCM")
            rate, ch = w.getframerate(), w.getnchannels()
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    except wave.Error as e:
        raise ValueError(f"Not a valid WAV file: {e}")
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    audio = pcm.astype(np.float32) / 32768.0
    if rate != 16000 and len(audio) > 1:
        n = int(len(audio) * 16000 / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    return audio


# A restricted yes/no vocabulary was tried for the medicine question and MEASURED WORSE on spoken Hindi and
# English test answers: it turned "मैंने" into "नहीं" and "मुझे चक्कर आ रहे हैं" into "चक्कर नहीं है", i.e. it
# invents meaning. Free recognition stays. The hook is kept (empty) so a better-tested grammar can be added.
GRAMMARS: Dict[tuple, list] = {}


class LiveStream:
    """One utterance, recognised incrementally: feed() chunks as they are recorded, finish() when the senior stops."""

    def __init__(self, model, grammar=None) -> None:
        import vosk
        rec = None
        if grammar:
            try:
                rec = vosk.KaldiRecognizer(model, 16000, json.dumps(grammar, ensure_ascii=False))
            except Exception:
                rec = None  # model has no dynamic graph: fall back to free recognition
        self.rec = rec or vosk.KaldiRecognizer(model, 16000)
        self.rec.SetWords(True)
        self.bytes = 0

    def feed(self, pcm: bytes) -> None:
        self.bytes += len(pcm)
        self.rec.AcceptWaveform(pcm)

    def finish(self) -> Dict[str, Any]:
        res = json.loads(self.rec.FinalResult())
        words = [w for w in res.get("result", []) if w.get("word") != "[unk]"]
        conf = round(sum(w.get("conf", 0.0) for w in words) / len(words), 2) if words else 0.0
        text = " ".join(w["word"] for w in words) if words else ""
        if not text:
            text = res.get("text", "").replace("[unk]", "").strip()
        return {"text": text.strip(), "confidence": conf, "duration": round(self.bytes / 32000, 2)}


class SpeechToText:
    def __init__(self) -> None:
        self.whisper_size = os.getenv("AEGIS_WHISPER_MODEL", "small")
        lang = os.getenv("AEGIS_WHISPER_LANG", "hi")
        self.language = lang or None
        self.vosk_paths = {
            "hi": os.getenv("AEGIS_VOSK_MODEL_HI", _DEFAULT_VOSK["hi"]),
            "en": os.getenv("AEGIS_VOSK_MODEL_EN", _DEFAULT_VOSK["en"]),
        }
        self._requested = os.getenv("AEGIS_STT_ENGINE", "auto").lower()
        self._whisper = None
        self._vosk = {}
        self._lock = threading.Lock()
        self._model_lock = threading.Lock()

    # ---------------------------------------------------------------- availability
    @staticmethod
    def whisper_installed() -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:
            return False

    def vosk_ready(self, lang: str = "hi") -> bool:
        if not os.path.isdir(self.vosk_paths.get(lang, "")):
            return False
        try:
            import vosk  # noqa: F401
            return True
        except Exception:
            return False

    def engine_for(self, lang: str = "hi") -> str:
        """The engine that will actually be used for [lang]: 'vosk', 'whisper', or 'none'."""
        if self._requested == "vosk":
            return "vosk" if self.vosk_ready(lang) else "none"
        if self._requested == "whisper":
            return "whisper" if self.whisper_installed() else "none"
        if self.vosk_ready(lang):
            return "vosk"
        return "whisper" if self.whisper_installed() else "none"

    @property
    def engine(self) -> str:
        return self.engine_for("hi")

    @property
    def languages(self) -> list:
        return [l for l in ("hi", "en") if self.engine_for(l) != "none"]

    def installed(self) -> bool:
        return self.engine != "none"

    # ---------------------------------------------------------------- engines
    def _vosk_model(self, lang: str):
        """Loads a Vosk model once (loading takes seconds, so warm() does it at startup)."""
        import vosk
        vosk.SetLogLevel(-1)
        with self._model_lock:
            if lang not in self._vosk:
                self._vosk[lang] = vosk.Model(self.vosk_paths[lang])
            return self._vosk[lang]

    def warm(self, langs=("hi", "en")) -> None:
        """Load the models and push half a second of silence through them, so the first real turn is fast."""
        for lang in langs:
            if self.engine_for(lang) != "vosk":
                continue
            try:
                import vosk
                rec = vosk.KaldiRecognizer(self._vosk_model(lang), 16000)
                rec.AcceptWaveform(b"\x00\x00" * 8000)
                rec.FinalResult()
            except Exception as e:  # warming is an optimisation, never a failure
                print(f"[STT] warm-up for {lang} failed: {e}")

    def live(self, lang: str, expect: str = "free") -> "LiveStream":
        """A recogniser that is fed audio while the senior is still talking (see LiveStream)."""
        lang = "en" if (lang or "").lower().startswith("en") else "hi"
        if self.engine_for(lang) != "vosk":
            raise RuntimeError("Live recognition needs a Vosk model")
        return LiveStream(self._vosk_model(lang), GRAMMARS.get((lang, expect)))

    def _transcribe_vosk(self, audio: np.ndarray, lang: str) -> Dict[str, Any]:
        import vosk
        rec = vosk.KaldiRecognizer(self._vosk_model(lang), 16000)
        rec.SetWords(True)
        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        for i in range(0, len(pcm), 8000):
            rec.AcceptWaveform(pcm[i:i + 8000])
        res = json.loads(rec.FinalResult())
        words = res.get("result", [])
        conf = round(sum(w.get("conf", 0.0) for w in words) / len(words), 2) if words else 0.0
        return {"text": res.get("text", "").strip(), "confidence": conf}

    def _transcribe_whisper(self, audio: np.ndarray, lang: str) -> Dict[str, Any]:
        if self._whisper is None:
            from faster_whisper import WhisperModel
            self._whisper = WhisperModel(self.whisper_size, device="cpu", compute_type="int8",
                                         cpu_threads=os.cpu_count() or 4)
        segments, _info = self._whisper.transcribe(
            audio,
            language=lang if lang in ("hi", "en") else self.language,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            condition_on_previous_text=False,
            initial_prompt=_WHISPER_PROMPT.get(lang, _WHISPER_PROMPT["hi"]),
            temperature=0.0,
        )
        parts, probs = [], []
        for seg in segments:
            if getattr(seg, "no_speech_prob", 0.0) > 0.6:
                continue
            t = seg.text.strip()
            if t:
                parts.append(t)
                probs.append(2.718281828 ** seg.avg_logprob)
        text = _drop_if_repetitive(" ".join(parts).strip())
        conf = round(sum(probs) / len(probs), 2) if probs else 0.0
        if conf and conf < 0.25:  # Whisper hallucinates on near-silence
            text = ""
        return {"text": text, "confidence": conf}

    # ---------------------------------------------------------------- public
    def transcribe(self, wav_bytes: bytes, lang: str = "hi") -> Dict[str, Any]:
        """
        Returns {"text", "confidence", "duration", "engine"}. Empty text = nothing intelligible
        (silence/noise). Raises RuntimeError if no engine is available, ValueError for a bad WAV.
        """
        lang = "en" if (lang or "").lower().startswith("en") else "hi"
        engine = self.engine_for(lang)
        if engine == "none":
            raise RuntimeError(
                "No speech engine available: put a Vosk model in coordinator_hub/models/ "
                "or `pip install faster-whisper`"
            )
        audio = decode_wav(wav_bytes)
        duration = round(len(audio) / 16000, 2)
        if duration < 0.3:
            return {"text": "", "confidence": 0.0, "duration": duration, "engine": engine}
        with self._lock:  # one transcription at a time keeps CPU latency predictable
            res = (self._transcribe_vosk(audio, lang) if engine == "vosk"
                   else self._transcribe_whisper(audio, lang))
        res.update({"duration": duration, "engine": engine, "language": lang})
        return res


stt = SpeechToText()
