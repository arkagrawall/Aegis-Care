"""The demo features: memory & mood signs from calls, family voice messages (played in the call in their own voice),
the spoken family update, the decline replay, call languages, missed-call SOS and the doctor report.
Run from coordinator_hub/:  python tests/test_features.py"""
import io, os, sys, tempfile, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T = tempfile.gettempdir()
for k, f in (("AEGIS_DATA_FILE", "aegis_ft_store.json"), ("AEGIS_BILLING_FILE", "aegis_ft_bill.json"), ("AEGIS_AUTH_FILE", "aegis_ft_auth.json")):
    os.environ[k] = os.path.join(T, f)
    if os.path.exists(os.environ[k]): os.remove(os.environ[k])
os.environ.update({"AEGIS_LLM": "off", "AEGIS_CALL_ENGINE": "local", "AEGIS_DEMO_MODE": "1"})
os.environ.update({f"SARVAM_{k}{s}": "" for s in [""] + [f"_{i}" for i in range(2, 11)]
                   for k in ("API_KEY", "ORG_ID", "WORKSPACE_ID", "CHECKIN_APP_ID", "CHECKIN_APP_VERSION", "ALERT_APP_ID",
                             "ALERT_APP_VERSION", "CONNECTION_ID", "AGENT_PHONE")})      # never a real Sarvam call
import numpy as np
from fastapi.testclient import TestClient
import server
from engine import auth, speech_signals as SS, family_voice as FV
c = TestClient(server.app)
FAILS = []
def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: FAILS.append(name)

pin = {x["code"]: x["pin"] for x in c.get("/api/auth/demo").json()["coordinators"]}
login = lambda code: {"Authorization": "Bearer " + c.post("/api/auth/login", json={"role": "coordinator", "id": code, "secret": pin[code]}).json()["token"]}
H, H2 = login("SAM-101"), login("SAM-102")
SID = "SR-1070"

# ---------------------------------------------------------------- memory & mood
one = SS.analyse_call([{"speaker": "ai", "text": "कैसे हैं?"}, {"speaker": "senior", "text": "अकेला लगता है, कोई नहीं आता, भूल जाता हूँ"},
                       {"speaker": "senior", "text": "अकेला लगता है, कोई नहीं आता, भूल जाता हूँ"}])
ok("one call: repeats, forgetting, loneliness and low mood are counted from the senior's words",
   one["repeats"] == 1 and one["memory_mentions"] >= 1 and one["lonely"] >= 1 and one["mood"] == -1)
ok("the AI's own lines are ignored", SS.analyse_call([{"speaker": "ai", "text": "I forget nothing, alone"}]) is None)
DAYS = ["आज पार्क गई, बेटी से बात हुई, खाना अच्छा बना", "मंदिर में भजन था, सबसे मिली, बहुत अच्छा लगा", "बाज़ार से सब्ज़ी लाई, टमाटर महंगे हैं आजकल",
        "पोते का फ़ोन आया, उसकी परीक्षा अच्छी गई", "बगीचे में नए फूल लगाए, गुलाब खिल गया", "रेडियो पर पुराने गाने सुने, मन ख़ुश हुआ",
        "पड़ोसन चाय पर आई, गाँव की बातें हुईं", "सुबह योग किया, घुटने ठीक हैं", "शाम को सत्संग गई, कथा सुनी"]
steady = [{"start_time": f"2026-10-{d + 1:02d}", "speech": SS.analyse_call([{"speaker": "senior", "text": x}, {"speaker": "senior", "text": "दवाई समय पर ली"}], "good")}
          for d, x in enumerate(DAYS)]
tr = SS.trend(steady)
ok("a steady person raises nothing", tr["cognition"] == "steady" and tr["mood"] == "steady" and not tr["flags"])
d = c.get(f"/api/senior/{SID}/details", headers=H).json()
ok("the demo senior's page shows memory: worth a check, mood: low", d["speech"]["cognition"] == "watch" and d["speech"]["mood"] == "low")
ok("with plain reasons and a 'not a diagnosis' advice", any("shorter" in f["en"] for f in d["speech"]["flags"]) and "not a diagnosis" in d["speech"]["advice_en"])
ok("another team cannot read it", c.get(f"/api/senior/{SID}/details", headers=H2).status_code == 403)

# ---------------------------------------------------------------- family voice messages
s = server.store.seniors_map[SID]
s.update(family_code="FAM-TEST01", family_sharing_consent=True)
F = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"role": "family", "id": "FAM-TEST01"}).json()["token"]}
def wav(seconds=2.0, rate=48000):
    t = np.arange(int(seconds * rate)) / rate
    pcm = (np.sin(2 * np.pi * 220 * t) * 9000).astype("<i2")
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())
    return b.getvalue()
ok("a blank recording is refused", c.post("/api/family/voice-message", headers={**F, "Content-Type": "audio/webm"}, content=b"nonsense").status_code == 400)
r = c.post("/api/family/voice-message?from_name=Rahul&relation=son", headers={**F, "Content-Type": "audio/wav"}, content=wav())
m = r.json()
ok("the family's recording is saved as MP3, waiting for the next call", r.status_code == 200 and m["from"] == "Rahul" and not m["played_at"]
   and FV.read(m["id"])[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3") and 1.5 <= m["seconds"] <= 2.5)
ok("the family sees it in their list", c.get("/api/family/voice-messages", headers=F).json()[0]["id"] == m["id"])
ok("the family can play it back", c.get(f"/api/voice-messages/{m['id']}.mp3", headers=F).status_code == 200)
ok("another team's care manager cannot", c.get(f"/api/voice-messages/{m['id']}.mp3", headers=H2).status_code == 403)
ok("their own care manager can", c.get(f"/api/voice-messages/{m['id']}.mp3", headers=H).status_code == 200)

# the next in-app call (hub's own voice) opens with the message, in Rahul's voice
DEV = {"X-Device-Key": auth.issue_device_key(SID)}
cid = server.store.initiate_call(SID, "ai_health_check")["call"]["call_id"]
st = c.post(f"/api/calls/{cid}/start", headers=DEV).json()
ok("the call opens with 'a message from your son Rahul'", "Rahul" in st["reply"] and st["audio_url"].startswith(f"/api/calls/{cid}/opening.mp3"))
server.tts_audio = (lambda orig: (lambda text, voice: _fake_tts(text, voice)))(server.tts_audio)
async def _fake_tts(text, voice): return b"\xff\xfb\x90\x00" + b"\0" * 400           # no network in tests
audio = c.get(st["audio_url"] + "&token=" + DEV["X-Device-Key"])
ok("the opening audio is Saathi + the real recording + Saathi, as one MP3",
   audio.status_code == 200 and audio.headers["content-type"] == "audio/mpeg" and len(audio.content) > len(FV.read(m["id"])))
ok("the message is marked as played, in their own voice", next(x for x in s["family_messages"] if x["id"] == m["id"])["played_how"] == "recording_in_app")
ok("the live view shows it was played", any("🎧" in x["text"] for x in server.call_sessions[cid].transcript))
cid2 = server.store.initiate_call(SID, "ai_health_check")["call"]["call_id"]
ok("it is played once, not every call", "Rahul" not in c.post(f"/api/calls/{cid2}/start", headers=DEV).json()["reply"])
note = FV.agent_note({"from": "Rahul", "relation": "son", "text": "papa main sunday aaunga"}, False)
ok("for a phone call, the agent is told to pass the words on", "Rahul (son)" in note and "sunday" in note)

# spoken weekly update for the family, without names going to the voice service
v = c.get("/api/family/voice-summary?lang=en", headers=F).json()
ok("the family can listen to a short spoken update", "update from Saathi" in v["text"] and v["audio_url"].startswith("/api/calls/voice-audio?text="))
ok("it says their message was played", "voice message was played" in v["text"])
ok("and no name is sent to the voice service", "Sita" not in v["audio_url"] and "Yadav" not in v["audio_url"])
ok("in Hindi too", "साथी" in c.get("/api/family/voice-summary?lang=hi", headers=F).json()["text"])

# ---------------------------------------------------------------- replay
cases = c.get("/api/replay/cases", headers=H).json()
ok("all 30 simulated decline cases can be replayed", len(cases) == 30 and all(x["pattern_en"] for x in cases))
rp = c.get(f"/api/replay/{cases[0]['senior_id']}", headers=H).json()
ok("the replay shows the alert days before the emergency", rp["alert_day"] is not None and rp["alert_day"] < 0 and rp["lead_days"] == -rp["alert_day"]
   and rp["days"][-1]["day"] == 0 and any(x["risk"] >= rp["alert_at"] for x in rp["days"]))
ok("a normal week first, then the decline", rp["days"][0]["risk"] < rp["alert_at"] and rp["decline_day"] < 0)
ok("an ordinary senior is not a replay case", c.get("/api/replay/SR-1001", headers=H).status_code in (404,) or not server.store.seniors_map["SR-1001"].get("is_planted"))
ok("family cannot open replays", c.get("/api/replay/cases", headers=F).status_code == 403)

# ---------------------------------------------------------------- language
lang_url = f"/api/coordinator/seniors/{SID}/language"
ok("the care manager can switch the call language to Tamil", c.post(lang_url, headers=H, json={"language": "ta"}).json()["name"] == "Tamil")
ok("unknown languages are refused", c.post(lang_url, headers=H, json={"language": "xx"}).status_code == 400)
ok("another team cannot", c.post(lang_url, headers=H2, json={"language": "en"}).status_code == 403)
from engine.sarvam_api import language_name
from ai_agent.sarvam_call import agent_variables
ok("Sarvam calls are placed in that language", language_name(s["language"]) == "Tamil" and agent_variables(s, {}, "")["language"] == "Tamil")
c.post(lang_url, headers=H, json={"language": "hi"})

# ---------------------------------------------------------------- doctor report
rep = c.get(f"/api/senior/{SID}/report", headers=H).json()
ok("the doctor report has readings, calls and memory & mood", rep["vitals"]["steps"] and rep["vitals"]["steps"]["n"] > 0
   and rep["speech"]["cognition"] == "watch" and rep["calls"])
ok("another team cannot print it", c.get(f"/api/senior/{SID}/report", headers=H2).status_code == 403)

print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
