"""
Family voice messages: a son records "Papa, I'm coming on Sunday" on the family page, and Saathi plays it to his
father in the next check-in call.

  in-app call (hub's own voice)   the real recording, stitched between Saathi's spoken lines (one MP3)
  in-app call (Sarvam)            the real recording streamed to the phone before the agent starts talking
  phone call (Sarvam)             Saathi reads the words out (a phone call cannot carry our audio), from the transcript

Recordings are converted once on upload to MP3 at the same format as Saathi's own voice (24 kHz mono), so the
pieces join seamlessly. Kept under data/family_voice/; the list lives on the senior's record.
"""
import io
import os
import time
import uuid
import wave
from typing import Any, Dict, List, Optional, Tuple

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "family_voice")
MAX_BYTES = 3_000_000
MAX_SECONDS = 45
RATE = 24000


def _decode(raw: bytes, rate: int):
    """Any browser recording (webm/opus, ogg, mp4/aac, wav) -> mono s16 numpy samples at [rate]."""
    import av
    import numpy as np
    out = []
    with av.open(io.BytesIO(raw)) as c:
        stream = next(s for s in c.streams if s.type == "audio")
        rs = av.AudioResampler(format="s16", layout="mono", rate=rate)
        for frame in c.decode(stream):
            for f in rs.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
        for f in rs.resample(None):
            out.append(f.to_ndarray().reshape(-1))
    return np.concatenate(out) if out else np.zeros(0, dtype="int16")


def to_mp3(raw: bytes) -> Tuple[bytes, float]:
    import av
    import numpy as np
    pcm = _decode(raw, RATE)
    if len(pcm) < RATE // 2:
        raise ValueError("The recording is too short")
    pcm = pcm[: RATE * MAX_SECONDS]
    peak = int(np.abs(pcm.astype("int32")).max() or 1)
    if peak < 12000:                                   # quiet phone mics: bring it up to Saathi's loudness
        pcm = np.clip(pcm.astype("float32") * min(12000 / peak, 6.0), -32768, 32767).astype("int16")
    buf = io.BytesIO()
    with av.open(buf, "w", format="mp3") as c:
        s = c.add_stream("libmp3lame", rate=RATE)
        s.layout = "mono"
        s.bit_rate = 48000
        for i in range(0, len(pcm), 1152 * 8):
            fr = av.AudioFrame.from_ndarray(pcm[i:i + 1152 * 8].reshape(1, -1), format="s16", layout="mono")
            fr.sample_rate = RATE
            for p in s.encode(fr):
                c.mux(p)
        for p in s.encode(None):
            c.mux(p)
    return buf.getvalue(), round(len(pcm) / RATE, 1)


def pcm16k(mp3: bytes) -> bytes:
    """Raw 16 kHz 16-bit mono PCM (for the Sarvam live call and speech recognition)."""
    return _decode(mp3, 16000).tobytes()


def wav16k(mp3: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm16k(mp3))
    return buf.getvalue()


def path(mid: str) -> str:
    return os.path.join(DIR, "".join(ch for ch in mid if ch.isalnum() or ch == "-") + ".mp3")


def read(mid: str) -> Optional[bytes]:
    try:
        with open(path(mid), "rb") as f:
            return f.read()
    except OSError:
        return None


def add(senior: Dict[str, Any], raw: bytes, from_name: str, relation: str, text: str = "",
        transcribe=None) -> Dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError("The recording is too long")
    mp3, secs = to_mp3(raw)
    os.makedirs(DIR, exist_ok=True)
    mid = "VM-" + uuid.uuid4().hex[:10].upper()
    with open(path(mid), "wb") as f:
        f.write(mp3)
    if not text and transcribe:
        try:
            text = transcribe(wav16k(mp3)) or ""
        except Exception as e:
            print(f"[Voice message] could not transcribe: {type(e).__name__}")
    msg = {"id": mid, "from": (from_name or "Family").strip()[:40], "relation": (relation or "").strip()[:30],
           "ts": time.time(), "seconds": secs, "text": (text or "").strip()[:400], "played_at": None, "played_how": None}
    senior.setdefault("family_messages", []).append(msg)
    senior["family_messages"] = senior["family_messages"][-20:]
    return msg


def pending(senior: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The oldest message not yet played (one per call)."""
    return next((m for m in (senior or {}).get("family_messages", []) if not m.get("played_at")), None)


def mark_played(msg: Dict[str, Any], how: str, call_id: str = "") -> None:
    msg.update(played_at=time.time(), played_how=how, call_id=call_id)


def who(msg: Dict[str, Any], hindi: bool) -> str:
    rel = msg.get("relation") or ""
    if hindi:
        return f"आपके {rel} {msg['from']}" if rel else msg["from"]
    return f"your {rel} {msg['from']}" if rel else msg["from"]


def intro(msg: Dict[str, Any], hindi: bool) -> str:
    return (f"आपके लिए एक प्यारा सा संदेश आया है, {who(msg, True)} की तरफ़ से। सुनिए।" if hindi
            else f"Before we start, there's a message for you from {who(msg, False)}. Have a listen.")


def agent_note(msg: Dict[str, Any], already_heard: bool) -> str:
    """For the Sarvam agent's memory_note: what to say about the message."""
    sender = f"{msg['from']}" + (f" ({msg['relation']})" if msg.get("relation") else "")
    words = f' The message says: "{msg["text"]}".' if msg.get("text") else ""
    if already_heard:
        return f"The senior has just heard a voice message from {sender}.{words} Mention it warmly at the start."
    return (f"Near the start of the call, tell the senior that {sender} sent them a voice message and pass it on "
            f"warmly in your own words.{words or ' They said they love them and are thinking of them.'}")


def public(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: m.get(k) for k in ("id", "from", "relation", "ts", "seconds", "text", "played_at", "played_how")}
            for m in reversed(msgs or [])]
