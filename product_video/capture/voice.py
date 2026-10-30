"""Narration: one MP3 per scene with word timings (Microsoft neural voice via edge-tts).
python voice.py  ->  ../assets/voice/sNN.mp3 and ../assets/voice/words.json"""
import asyncio, io, json, os
import av
import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "voice")
os.makedirs(OUT, exist_ok=True)
VOICE, RATE = "en-IN-NeerjaNeural", "+0%"


def duration(path):
    with av.open(path) as c:
        return float(c.duration / av.time_base)


async def one(scene):
    mp3, words = bytearray(), []
    async for ch in edge_tts.Communicate(scene["text"], VOICE, rate=RATE, boundary="WordBoundary").stream():
        if ch["type"] == "audio":
            mp3 += ch["data"]
        elif ch["type"] == "WordBoundary":
            s = ch["offset"] / 1e7
            words.append({"text": ch["text"], "start": round(s, 3), "end": round(s + ch["duration"] / 1e7, 3)})
    path = os.path.join(OUT, scene["id"] + ".mp3")
    open(path, "wb").write(mp3)
    return {"id": scene["id"], "file": f"assets/voice/{scene['id']}.mp3", "duration": round(duration(path), 3), "words": words}


async def main():
    script = json.load(open(os.path.join(HERE, "script.json"), encoding="utf-8"))
    res = [await one(s) for s in script]
    json.dump(res, open(os.path.join(OUT, "words.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for r in res:
        print(r["id"], r["duration"], len(r["words"]))
    print("total", round(sum(r["duration"] for r in res), 1))

asyncio.run(main())
