"""
Call-speed and recognition benchmark against a RUNNING hub (python start.py --local).   python tests/bench_call.py

Speech is synthesised with the neural voice (played back in real time, clean audio, so this measures the pipeline's latency and its
handling of real Hindi/English sentences, not microphone noise or accents). For each sentence it streams
16 kHz PCM over /ws/calls/{id}/audio in 100 ms chunks (like the phone does) and reports, after the last chunk:
  - stt_finish  time to get the final text (streaming: small)
  - agent       conversation logic
  - tts         voice for the reply (cache hit: ~0)
  - wait        wall-clock from the last chunk to the reply audio frame arriving at the client
"""
import asyncio
import io
import json
import statistics
import sys
import urllib.request

import av
import edge_tts
import numpy as np
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"


def http(path, data=None, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


async def speak(text, voice):
    mp3 = bytearray()
    async for ch in edge_tts.Communicate(text, voice).stream():
        if ch["type"] == "audio":
            mp3 += ch["data"]
    c = av.open(io.BytesIO(bytes(mp3)))
    rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
    out = bytearray()
    for frame in c.decode(audio=0):
        for f in rs.resample(frame):
            out += bytes(f.planes[0])[: f.samples * 2]
    return bytes(out)


async def run(lang, answers):
    demo = http("/api/auth/demo")
    co = demo["coordinators"][0]
    tok = http("/api/auth/login", {"role": "coordinator", "id": co["code"], "secret": co["pin"]})["token"]
    ob = http("/api/senior/onboard", {"name": "Bench Senior", "age": 70, "coordinator_code": co["code"], "language": lang})
    sid, key = ob["senior"]["senior_id"], ob["device_key"]
    call = http("/api/calls/initiate", {"senior_id": sid}, token=tok)["call_id"]
    start = urllib.request.Request(BASE + f"/api/calls/{call}/start", data=b"{}", headers={"X-Device-Key": key, "Content-Type": "application/json"})
    greet = json.loads(urllib.request.urlopen(start, timeout=30).read())
    voice = "hi-IN-MadhurNeural" if lang == "hi" else "en-IN-PrabhatNeural"
    rows = []
    async with websockets.connect(f"{WS}/ws/calls/{call}/audio?token={key}", max_size=None) as ws:
        for said in answers:
            pcm = await speak(said, voice)
            pcm += b"\x00\x00" * 8000
            for i in range(0, len(pcm), 3200):          # 100 ms chunks
                await ws.send(pcm[i:i + 3200])
                await asyncio.sleep(0.1)                  # real time, like a live microphone
            t0 = asyncio.get_event_loop().time()
            await ws.send(json.dumps({"type": "end"}))
            turn = json.loads(await ws.recv())
            audio = await ws.recv() if turn.get("has_audio") else b""
            wait = (asyncio.get_event_loop().time() - t0) * 1000
            rows.append((said, turn["heard"], turn["timing_ms"], round(wait), len(audio)))
            print(f"[{lang}] said={said!r}\n      heard={turn['heard']!r}  server={turn['timing_ms']}  wait={round(wait)} ms  audio={len(audio)}B")
            if turn["is_completed"]:
                break
    return rows


async def main():
    hi = ["मुझे थोड़ा चक्कर आ रहा है", "पिछले दो दिन से", "हाँ मैंने दवा ले ली", "नींद ठीक आई और भूख भी ठीक है"]
    en = ["I am feeling a little weak today", "since yesterday", "yes I took my medicine", "I slept well and my appetite is fine"]
    rows = await run("hi", hi) + await run("en", en)
    waits = [r[3] for r in rows]
    print(f"\nturns={len(rows)}  wait after speech ends: median {statistics.median(waits)} ms, max {max(waits)} ms")
    sys.exit(0)


asyncio.run(main())
