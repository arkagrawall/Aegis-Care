"""
Aegis Saathi - FastAPI Server & Coordinator Early Warning Hub
Handles Senior Android App ingestion, BLE watch data streams, and the Coordinator Dashboard.
"""

import os
import re
import time
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import edge_tts

from engine.coordinator_store import CoordinatorStore
from engine import auth
from ai_agent.voice_agent import (HealthCheckConversation, static_lines, VOICES, VOICE_RATE, TEXT as AGENT_TEXT,
                                  ESCALATE_WORDS, UNWELL_WORDS, CONTRAST_WORDS, _has_any, is_emergency, is_danger, normalize_language)
from ai_agent.llm_agent import LLMConversation, BACKEND as LLM, build_health_context, load_env
import threading
load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
import asyncio
import hashlib
import json
from engine.stt import stt
from engine.nlp_extractor import extract_symptom_cues
from collections import OrderedDict
from urllib.parse import quote
from fastapi.concurrency import run_in_threadpool

app = FastAPI(
    title="Aegis Saathi - Coordinator Early Warning Hub",
    description="Early-warning system for seniors living at home combining wearable BLE data, daily check-ins, and coordinator workflows.",
    version="1.0.0"
)

# Enable CORS for mobile app & local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize persistence store with synthetic 250 cohort
store = CoordinatorStore()

# -------------------------------------------------------------
# Authentication / role-based access (see engine/auth.py)
# -------------------------------------------------------------
DEMO_MODE = os.getenv("AEGIS_DEMO_MODE", "1") == "1"
from engine import speech_signals, demo_history, family_voice, replay as replay_engine
if DEMO_MODE:      # a few weeks of earlier calls for one simulated senior, so "Memory & mood" has a history to show
    _demo_sr = store.seniors_map.get(os.getenv("AEGIS_DEMO_SPEECH_SENIOR", "SR-1070"))
    if _demo_sr and demo_history.seed(store, _demo_sr):
        store.save()
        print(f"[Demo] memory & mood history added for {_demo_sr['name']} ({_demo_sr['senior_id']}, {_demo_sr['coordinator_code']})")
CREDS = auth.load_credentials(list(store.coordinators.keys()))
from engine.billing import Billing
billing = Billing(store, CREDS, auth.save_credentials)      # subscriptions: plan -> Razorpay -> coordinator code
from engine.emergency import EmergencyDispatcher
from engine.sarvam_api import CONFIG as SARVAM, POOL as SARVAM_POOL, LANGUAGES, language_name, no_credit, public_url
import hmac as _hmac
SARVAM_HOOK_KEY = _hmac.new(auth._secret(), b"sarvam-webhook", hashlib.sha256).hexdigest()[:32]
_MAIN_LOOP: Dict[str, Any] = {}


def _notify_phone_sync(senior_id: str, message: dict) -> None:
    """Sends a socket message to the phone from any thread (the emergency dispatcher runs off the event loop)."""
    loop = _MAIN_LOOP.get("loop")
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.send_to_senior(senior_id, message), loop)


dispatcher = EmergencyDispatcher(store, _notify_phone_sync, audit=store.audit, webhook_secret=SARVAM_HOOK_KEY)
print(f"[Sarvam] calls: {SARVAM.status()['calls']} | family alert calls: {SARVAM.status()['family_alert_calls']}")


def _write_tool_url() -> None:
    """The check-in agent's emergency tool URL (it carries the secret), for pasting into Sarvam. Never printed."""
    if public_url():
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sarvam_tool_url.txt"), "w") as f:
                f.write(f"{public_url()}/api/sarvam/tools/emergency?k={SARVAM_HOOK_KEY}" + "\n")
        except OSError:
            pass


_write_tool_url()
if DEMO_MODE:
    print("[Auth] DEMO MODE: logins are listed on the sign-in page (set AEGIS_DEMO_MODE=0 to hide them)")


def who(request: Request, *roles: str) -> "auth.Principal":
    p = auth.principal_from_request(request)
    if p is None:
        raise HTTPException(status_code=401, detail="Please sign in")
    if roles and p.role not in roles:
        raise HTTPException(status_code=403, detail="Your role cannot do this")
    return p


def _senior_obj(senior_id: str) -> Dict[str, Any]:
    s = store.dynamic_seniors.get(senior_id) or store.seniors_map.get(senior_id)
    if not s:
        raise HTTPException(status_code=404, detail="Senior not found")
    return s


def _own(request: Request, senior_id: str) -> "auth.Principal":
    """A senior's phone may only act on its own record."""
    p = who(request, "senior")
    if p.sub != senior_id:
        raise HTTPException(status_code=403, detail="This device belongs to a different senior")
    return p


def _coord(request: Request, code: str) -> "auth.Principal":
    p = who(request, "coordinator")
    if p.sub != (code or "").upper():
        raise HTTPException(status_code=403, detail="Not your team")
    return p


def _coord_of_senior(request: Request, senior_id: str, audit: str = "") -> Dict[str, Any]:
    p = who(request, "coordinator")
    s = _senior_obj(senior_id)
    if s.get("coordinator_code") != p.sub:
        raise HTTPException(status_code=403, detail="This senior is not on your team")
    if audit:
        store.audit("coordinator", p.sub, audit, senior_id)
    return s


def _call_owner(request: Request, call_id: str) -> Dict[str, Any]:
    rec = store.get_call(call_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Call not found")
    p = who(request, "senior")
    if rec["senior_id"] != p.sub:
        raise HTTPException(status_code=403, detail="Not your call")
    return rec


def mask_for_tts(text: str, senior_name: str) -> str:
    """Names and phone numbers never go to the external voice service."""
    import re as _re
    out = text
    for tok in sorted({senior_name, *[t for t in senior_name.split() if len(t) > 2]}, key=len, reverse=True):
        out = out.replace(tok, "")
    out = _re.sub(r"\+?\d[\d\s-]{8,}\d", "", out)
    out = _re.sub(r"\s+([!?.,।])", r"\1", out)
    out = _re.sub(r"^[\s,]+", "", out)
    return _re.sub(r"\s{2,}", " ", out).strip()


# -------------------------------------------------------------
# WebSocket Connection Manager for Senior Android Clients
# -------------------------------------------------------------
class SeniorConnectionManager:
    def __init__(self):
        self.active_sockets: Dict[str, WebSocket] = {}

    async def connect(self, senior_id: str, websocket: WebSocket):
        await websocket.accept()
        old_socket = self.active_sockets.get(senior_id)
        if old_socket and old_socket != websocket:
            try:
                await old_socket.close()
            except Exception:
                pass
        self.active_sockets[senior_id] = websocket
        print(f"[WS] Senior connected: {senior_id} (Total online: {len(self.active_sockets)})")

    def disconnect(self, senior_id: str, websocket: WebSocket = None):
        if senior_id in self.active_sockets:
            # Only remove if the disconnecting socket is the currently registered socket
            if websocket is None or self.active_sockets[senior_id] == websocket:
                del self.active_sockets[senior_id]
                print(f"[WS] Senior disconnected: {senior_id} (Total online: {len(self.active_sockets)})")

    def is_online(self, senior_id: str) -> bool:
        return senior_id in self.active_sockets

    async def send_to_senior(self, senior_id: str, message: dict) -> bool:
        ws = self.active_sockets.get(senior_id)
        if ws:
            try:
                await ws.send_json(message)
                return True
            except Exception as e:
                print(f"[WS] Failed sending to {senior_id}: {e}")
                self.disconnect(senior_id, ws)
        return False

ws_manager = SeniorConnectionManager()

# Edge-TTS audio cache (repeated phrases like greetings/acks are served instantly)
_tts_cache: "OrderedDict[tuple, bytes]" = OrderedDict()

TTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tts_cache")


async def tts_audio(text: str, voice: str) -> bytes:
    """Neural voice for [text] (already name-masked). Memory cache, then a disk cache that survives restarts."""
    key = (text, voice)
    hit = _tts_cache.get(key)
    if hit is not None:
        _tts_cache.move_to_end(key)
        return hit
    path = os.path.join(TTS_DIR, hashlib.md5((voice + "|" + VOICE_RATE + "|" + text).encode("utf-8")).hexdigest() + ".mp3")
    if os.path.exists(path):
        with open(path, "rb") as f:
            audio = f.read()
    else:
        audio_data = bytearray()
        async for chunk in edge_tts.Communicate(text, voice, rate=VOICE_RATE).stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        audio = bytes(audio_data)
        if not audio:
            raise RuntimeError("empty audio from voice service")
        os.makedirs(TTS_DIR, exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(audio)
        os.replace(tmp, path)
    _tts_cache[key] = audio
    while len(_tts_cache) > 400:
        _tts_cache.popitem(last=False)
    return audio


async def _prewarm_voice() -> None:
    """Background: render every fixed agent sentence once, so most replies are a file read instead of a cloud call."""
    sem = asyncio.Semaphore(3)
    done = 0

    async def one(text: str, voice: str):
        nonlocal done
        async with sem:
            try:
                await tts_audio(mask_for_tts(text, "\u0000"), voice)
                done += 1
            except Exception:
                pass

    jobs = [one(line, VOICES[lang]) for lang in ("hi", "en") for line in static_lines(lang)]
    await asyncio.gather(*jobs)
    print(f"[TTS] voice cache ready ({done}/{len(jobs)} fixed lines)")


@app.on_event("startup")
async def warm_up() -> None:
    """Load speech models and pre-render the voice in the background so the first call is as fast as the tenth."""
    async def go():
        await run_in_threadpool(stt.warm)
        print("[STT] speech models loaded")
        await _prewarm_voice()
    asyncio.create_task(go())


# Live voice-agent conversations keyed by call_id (in-memory, demo scale)
call_sessions: Dict[str, Any] = {}


def new_conversation(senior: Dict[str, Any]):
    """The language-model conversation when a Groq key is set (rules stay as its safety gate and fallback),
    otherwise the rule-based conversation. The health summary is prepared while the greeting plays."""
    lang = senior.get("language", "hi")
    if not LLM.enabled:
        return HealthCheckConversation(senior["senior_id"], senior["name"], lang)
    conv = LLMConversation(senior["senior_id"], senior["name"], lang, care_manager=senior.get("coordinator_name", ""),
                           gender=senior.get("gender", ""))

    def prepare():
        try:
            ctx = build_health_context(store, senior["senior_id"])
            conv.set_context(ctx["health"], ctx["memory"])
        except Exception as e:
            print(f"[LLM] context: {e}")
            conv.set_context("", "")
    threading.Thread(target=prepare, daemon=True).start()
    return conv

class CallTurnRequest(BaseModel):
    text: str = ""
    silence: bool = False   # senior said nothing during the listening window

# -------------------------------------------------------------
# Request Models
# -------------------------------------------------------------
class SeniorOnboardRequest(BaseModel):
    name: str
    age: int
    gender: Optional[str] = "Female"
    city: Optional[str] = "Delhi NCR"
    emergency_contact: Optional[str] = "+91 98765 43210"
    language: Optional[str] = "hi"
    coordinator_code: str
    watch_mac: Optional[str] = "DA:F1:70:01:23:45"
    watch_model: Optional[str] = "Da Fit / Moyoung Band"
    battery: Optional[int] = 92
    initial_steps: Optional[int] = 1420
    initial_hr: Optional[int] = 72
    initial_spo2: Optional[float] = 98.0
    phone: Optional[str] = ""          # the senior's own number (missed-call check-ins)
    consent: Optional[bool] = True     # agreed that their care manager can see their data

class VitalsSyncRequest(BaseModel):
    senior_id: str
    steps: Optional[int] = None
    heart_rate: Optional[int] = None
    spo2: Optional[float] = None
    battery: Optional[int] = None
    sleep_hours: Optional[float] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    sugar: Optional[float] = None
    weight: Optional[float] = None
    source: Optional[str] = None   # "watch" | "demo" | "manual"

class FallReportRequest(BaseModel):
    senior_id: str
    outcome: str                    # false_alarm | ok_but_fell | need_help | no_response
    impact_g: Optional[float] = 0.0

class SosResolveRequest(BaseModel):
    status: str                    # confirmed | false_alarm | resolved
    coordinator_code: str
    note: Optional[str] = ""

class CheckinRequest(BaseModel):
    senior_id: str
    checkin_type: str  # 'one_tap', 'missed_call', 'voice'
    status: str        # 'good', 'weak', 'bad', 'missed'
    voice_text: Optional[str] = None

class MedicationRequest(BaseModel):
    senior_id: str
    action: str        # 'taken', 'skipped', 'later'
    med_name: Optional[str] = "Morning Blood Pressure Tablet (Amlodipine 5mg)"

class CoordinatorActionRequest(BaseModel):
    senior_id: str
    coordinator_code: str
    action_taken: str  # 'call_completed', 'nurse_dispatched', 'med_reviewed'
    outcome: str       # 'issue_confirmed', 'no_issue', 'escalated'
    feedback: str      # 'useful', 'not_useful', 'routine'
    notes: Optional[str] = ""
    factor_codes: Optional[List[str]] = []   # the reasons shown on the alert being rated

class CallInitiateRequest(BaseModel):
    senior_id: str
    caller_type: Optional[str] = "ai_health_check"

class CallCompleteRequest(BaseModel):
    call_id: str
    senior_id: str
    status: Optional[str] = "completed"  # completed, declined, missed
    duration_seconds: Optional[int] = 45
    transcript: Optional[List[Dict[str, str]]] = []
    summary: Optional[str] = ""
    meds_taken: Optional[bool] = None
    emergency: Optional[bool] = False

class SeniorSosRequest(BaseModel):
    senior_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class CallScheduleRequest(BaseModel):
    senior_id: str
    schedule_time: str  # e.g., "09:30"
    recurring: Optional[bool] = True

# -------------------------------------------------------------
# REST Endpoints
# -------------------------------------------------------------

@app.get("/api/coordinators")
def get_coordinators():
    """Demo-only list of care teams (codes + names) for the phone simulator."""
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Disabled outside demo mode")
    return [{"code": c["code"], "name": c["name"], "city": c["city"], "senior_count": c["senior_count"]}
            for c in store.list_coordinators()]

@app.post("/api/senior/onboard")
def onboard_senior(payload: SeniorOnboardRequest):
    """
    Onboards a senior citizen who entered a Coordinator Code in the Android app.
    Links the senior to the assigned coordinator.
    """
    data = payload.dict()
    saathi = None
    if billing.is_saathi_code(payload.coordinator_code):
        # a family bought Saathi for this parent: the code links the phone to the care manager assigned at purchase
        chk = billing.check_redeem(payload.coordinator_code)
        if "error" in chk:
            raise HTTPException(status_code=400, detail=chk["error"])
        saathi = payload.coordinator_code.strip().upper()
        data["coordinator_code"] = chk["coordinator_code"]
    elif billing.active(payload.coordinator_code) is False:
        raise HTTPException(status_code=400, detail="This care manager's subscription has ended.")
    senior = store.register_senior(data)
    if "error" in senior:
        raise HTTPException(status_code=400, detail=senior["error"])
    if saathi:
        billing.mark_redeemed(saathi, senior["senior_id"])
        sub = billing.state["subscriptions"][saathi]
        senior.update(saathi_code=saathi, plan=sub["plan"], plan_valid_until=sub["valid_until"])
        store.save()
    return {
        "status": "success",
        "message": f"Successfully linked to Coordinator {senior['coordinator_name']} ({senior['coordinator_code']})",
        "senior": {k: v for k, v in senior.items() if k not in ("vitals_history", "family_code")},
        "device_key": auth.issue_device_key(senior["senior_id"]),   # sent by the phone with every later request
    }

class PhoneOnboardRequest(BaseModel):
    saathi_code: str
    name: str
    phone: str                         # the parent's own number: Saathi rings it every day
    age: Optional[int] = 70
    gender: Optional[str] = "Female"
    city: Optional[str] = ""
    language: Optional[str] = "hi"
    emergency_name: Optional[str] = ""
    emergency_relation: Optional[str] = ""
    emergency_phone: Optional[str] = ""
    call_time: Optional[str] = "10:00"


@app.post("/api/senior/onboard-phone")
def onboard_senior_by_phone(payload: PhoneOnboardRequest):
    """
    Setup without the app, for parents with a basic (feature) phone: the family redeems the Saathi code on the website,
    gives the parent's number and a time, and Saathi calls that number every day. Saathi codes only.
    """
    if not billing.is_saathi_code(payload.saathi_code):
        raise HTTPException(status_code=400, detail="Please enter the Saathi code from your purchase.")
    if len(_digits(payload.phone)) < 10:
        raise HTTPException(status_code=400, detail="Please enter your parent's 10-digit mobile number.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Please enter your parent's name.")
    if store.find_by_phone(payload.phone):
        raise HTTPException(status_code=409, detail="Saathi is already set up for this number.")
    res = onboard_senior(SeniorOnboardRequest(
        name=payload.name.strip(), age=payload.age, gender=payload.gender, city=payload.city or "Delhi NCR",
        language=payload.language if payload.language in LANGUAGES else "hi", coordinator_code=payload.saathi_code,
        phone=payload.phone.strip(), emergency_contact=(payload.emergency_phone or "").strip(), consent=True,
        watch_mac="", watch_model=""))
    sid = res["senior"]["senior_id"]
    senior = store.dynamic_seniors[sid]
    senior["channel"] = "phone"
    if len(_digits(payload.emergency_phone)) >= 10:
        store.save_contact(sid, {"name": (payload.emergency_name or "").strip() or "Family", "phone": payload.emergency_phone,
                                 "relation": (payload.emergency_relation or "").strip(), "is_emergency": True})
    sched = store.schedule_call(sid, payload.call_time or "10:00", True)
    if "error" in sched:
        store.schedule_call(sid, "10:00", True)
    store.save()
    return {"status": "success", "senior_id": sid, "name": senior["name"], "coordinator_name": senior["coordinator_name"],
            "call_time": payload.call_time if "error" not in sched else "10:00", "calls_by_phone": SARVAM.phone_calls_ready()}


@app.post("/api/senior/sos")
def trigger_emergency_sos(payload: SeniorSosRequest, request: Request):
    _own(request, payload.senior_id)
    """
    Emergency SOS from the senior's app (press-and-hold + countdown on the phone).
    Creates a tracked event that stays ACTIVE (RED, top of the queue) until a coordinator closes it.
    Repeat presses within 10 minutes are the same event, so one scare cannot flood the queue.
    """
    res = dispatcher.raise_emergency(payload.senior_id, "senior_hold", "", payload.latitude, payload.longitude)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return {
        "family_ai_call": res.get("family_ai_call", False),
        "status": "emergency_triggered",
        "duplicate": res["duplicate"],
        "event_id": res["event"]["id"],
        "message": "Emergency SOS sent to your care coordinator.",
        "senior_id": payload.senior_id,
    }

@app.post("/api/senior/fall")
def report_fall(payload: FallReportRequest, request: Request):
    """The senior's answer on the phone's 'Did you fall?' screen (see FallDetector.kt)."""
    _own(request, payload.senior_id)
    res = store.report_fall(payload.senior_id, payload.outcome, payload.impact_g or 0.0)
    if "error" in res:
        raise HTTPException(status_code=400 if "Invalid" in res["error"] else 404, detail=res["error"])
    if payload.outcome in ("need_help", "no_response"):
        dispatcher.raise_emergency(payload.senior_id, "fall_" + payload.outcome)
    return res

@app.post("/api/senior/sos/cancel")
def cancel_emergency_sos(payload: SeniorSosRequest, request: Request):
    _own(request, payload.senior_id)
    """'I pressed it by mistake' - allowed for 2 minutes after sending."""
    res = store.cancel_sos(payload.senior_id)
    if "error" in res:
        raise HTTPException(status_code=409, detail=res["error"])
    dispatcher.cancel(payload.senior_id)
    return {"status": "cancelled", "event_id": res["event"]["id"]}

@app.post("/api/sarvam/webhook")
async def sarvam_webhook(request: Request, k: str = ""):
    """Sarvam reports how a family alert call went. No signature is documented, so the URL carries a secret."""
    if not _hmac.compare_digest(k, SARVAM_HOOK_KEY):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad JSON")
    if ((payload.get("webhook_config") or {}).get("metadata") or {}).get("kind") == "checkin":
        return await run_in_threadpool(_on_checkin_webhook, payload)
    return await run_in_threadpool(dispatcher.on_webhook, payload)


class EmergencyToolIn(BaseModel):
    call_id: str
    senior_id: str
    said: Optional[str] = ""
    transcript: Optional[str] = ""


@app.post("/api/sarvam/tools/emergency")
def sarvam_emergency_tool(payload: EmergencyToolIn, k: str = ""):
    """
    The check-in agent's "report_emergency" tool, called DURING a phone call when the senior says they are dying,
    cannot breathe, have chest pain or fell. SOS for the care manager + the family alert call, at once.
    """
    if not _hmac.compare_digest(k, SARVAM_HOOK_KEY):
        raise HTTPException(status_code=403, detail="Forbidden")
    rec = store.get_call(payload.call_id)
    if not rec or rec["senior_id"] != payload.senior_id or rec.get("channel") != "phone" \
            or time.time() - rec.get("rang_at", 0) > 7200:
        raise HTTPException(status_code=404, detail="No such call")
    said = (payload.said or "").strip() or (payload.transcript or "").strip()[-300:] or "said they need urgent help"
    if not rec.get("family_alerted"):
        rec["family_alerted"] = True
        rec["escalation_flag"] = True
        store.save()
        dispatcher.raise_emergency(payload.senior_id, "call", said)
    return {"status": "ok", "message": "Help is being called: the care manager and the family."}


@app.get("/api/voice/status")
def voice_status():
    """Which engine runs calls and whether family alert calls are on (no secrets)."""
    return SARVAM.status()


@app.get("/api/coordinator/{code}/sos")
def list_coordinator_sos(code: str, request: Request, active_only: bool = True):
    _coord(request, code)
    if not store.get_coordinator(code):
        raise HTTPException(status_code=404, detail="Coordinator code not found")
    return store.list_sos(code, active_only)

@app.post("/api/sos/{event_id}/resolve")
def resolve_sos_event(event_id: str, payload: SosResolveRequest, request: Request):
    _coord(request, payload.coordinator_code)
    ev = next((e for e in store.sos_events if e["id"] == event_id), None)
    if ev and ev.get("coordinator_code") != payload.coordinator_code.upper():
        raise HTTPException(status_code=403, detail="Not your team's alert")
    store.audit("coordinator", payload.coordinator_code.upper(), "sos_" + payload.status, event_id)
    res = store.resolve_sos(event_id, payload.status, payload.coordinator_code, payload.note or "")
    if "error" in res:
        raise HTTPException(status_code=404 if "not found" in res["error"] else 400, detail=res["error"])
    return res

@app.post("/api/senior/vitals")
def sync_vitals(payload: VitalsSyncRequest, request: Request):
    _own(request, payload.senior_id)
    """Syncs live BLE watch sensor data (Da Fit GATT services)."""
    clean_dict = {k: v for k, v in payload.dict().items() if v is not None}
    res = store.update_senior_vitals(payload.senior_id, clean_dict)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.post("/api/senior/checkin")
def submit_checkin(payload: CheckinRequest, request: Request):
    _own(request, payload.senior_id)
    """Logs daily check-in (One-tap / Missed call / Voice note)."""
    res = store.record_checkin(payload.senior_id, payload.checkin_type, payload.status, payload.voice_text)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.post("/api/senior/medication")
def submit_medication(payload: MedicationRequest, request: Request):
    _own(request, payload.senior_id)
    """Logs medication adherence (Taken / Skipped / Later)."""
    res = store.record_medication(payload.senior_id, payload.action, payload.med_name)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.get("/api/coordinator/{code}/seniors")
def get_coordinator_queue(code: str, request: Request):
    _coord(request, code)
    """Returns ranked priority queue for the Care Coordinator dashboard."""
    coord = store.get_coordinator(code)
    if not coord:
        raise HTTPException(status_code=404, detail="Coordinator code not found")
    seniors = store.get_coordinator_seniors(code)
    
    # Calculate quick stats
    total = len(seniors)
    red_count = sum(1 for s in seniors if s["tier"] == "RED")
    orange_count = sum(1 for s in seniors if s["tier"] == "ORANGE")
    yellow_count = sum(1 for s in seniors if s["tier"] == "YELLOW")
    green_count = sum(1 for s in seniors if s["tier"] == "GREEN")

    return {
        "coordinator": coord,
        "summary": {
            "total_assigned": total,
            "urgent_red": red_count,
            "attention_orange": orange_count,
            "monitor_yellow": yellow_count,
            "stable_green": green_count
        },
        "seniors": seniors
    }

@app.get("/api/senior/{senior_id}/details")
def get_senior_details(senior_id: str, request: Request):
    """Everything a coordinator needs about one senior (their own team only; every view is audited)."""
    senior = _coord_of_senior(request, senior_id, "view_senior")
    history = senior.get("vitals_history", []) if senior.get("is_dynamic") else senior.get("records", [])[:80]
    cur = senior.get("current_status") or (history[-1] if history else {})
    recent = history[-14:]
    timeline = {
        "days": [f"Day {d.get('day', i + 1)}" for i, d in enumerate(recent)],
        "steps": [d.get("steps", 0) for d in recent],
        "heart_rate": [d.get("resting_hr", 72) for d in recent],
        "spo2": [d.get("spo2", 98) for d in recent],
        "sleep": [d.get("sleep_hours", 7.0) for d in recent],
        "meds": [1 if d.get("meds_taken", True) else 0 for d in recent],
        "bp_sys": [d.get("bp_sys") for d in recent], "bp_dia": [d.get("bp_dia") for d in recent],
        "sugar": [d.get("sugar") for d in recent], "weight": [d.get("weight") for d in recent],
    }
    profile = {k: senior.get(k) for k in ("senior_id", "name", "age", "gender", "city", "language",
                                          "coordinator_code", "coordinator_name", "emergency_contact", "is_dynamic")}
    profile["family_sharing"] = bool(senior.get("family_sharing_consent"))
    profile.update(call_mode=_call_mode(senior), app_online=ws_manager.is_online(senior_id),
                   has_number=len(_digits(senior.get("phone"))) >= 10, phone_calls=SARVAM.phone_calls_ready())
    return {
        "senior": profile, "current_status": cur, "timeline_14d": timeline,
        "calls": store.get_call_history(senior_id)[:5],
        "sos": [e for e in store.list_sos() if e["senior_id"] == senior_id][:5],
        "actions": [a for a in reversed(store.action_logs) if a.get("senior_id") == senior_id][:5],
        "medicines": store.dose_days(senior_id, 14),
        "contacts": store.list_contacts(senior_id),
        "speech": speech_trend(senior_id),
    }

@app.get("/api/senior/{senior_id}/report")
def doctor_report(senior_id: str, request: Request):
    """30 days on one page for their doctor: readings, medicines, what came up on calls, memory & mood, alerts."""
    senior = _coord_of_senior(request, senior_id, "doctor_report")
    history = (senior.get("vitals_history", []) if senior.get("is_dynamic") else senior.get("records", [])[:80])[-30:]

    def stat(key):
        vals = [float(d[key]) for d in history if isinstance(d.get(key), (int, float))]
        if not vals:
            return None
        first, last = vals[:7], vals[-7:]
        return {"n": len(vals), "avg": round(sum(vals) / len(vals), 1), "min": min(vals), "max": max(vals),
                "first_week": round(sum(first) / len(first), 1), "last_week": round(sum(last) / len(last), 1)}
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))
    calls = [c for c in store.get_call_history(senior_id) if str(c.get("start_time") or "") >= since]
    symptoms: Dict[str, int] = {}
    for c in calls:
        for x in c.get("symptoms_reported") or []:
            symptoms[x] = symptoms.get(x, 0) + 1
    coord = store.coordinators.get(senior.get("coordinator_code") or "", {})
    return {
        "generated": time.strftime("%d %b %Y, %H:%M"),
        "senior": {k: senior.get(k) for k in ("name", "age", "gender", "city", "language")},
        "care_manager": {"name": coord.get("name") or senior.get("coordinator_name", ""), "phone": coord.get("phone", "")},
        "contacts": [{"name": c.get("name"), "relation": c.get("relation"), "phone": c.get("phone")}
                     for c in store.emergency_contacts(senior_id)][:3],
        "days": len(history),
        "vitals": {k: stat(k) for k in ("steps", "resting_hr", "spo2", "sleep_hours", "bp_sys", "bp_dia", "sugar", "weight")},
        "medicines": store.dose_days(senior_id, 30),
        "calls": [{"date": str(c.get("start_time"))[:16], "status": c.get("status"), "mood": c.get("mood"),
                   "summary": c.get("ai_summary_en") or c.get("summary") or "", "symptoms": c.get("symptoms_reported") or []}
                  for c in calls[:12]],
        "symptoms": sorted(symptoms.items(), key=lambda kv: -kv[1]),
        "speech": speech_trend(senior_id),
        "sos": [{"time": e.get("time"), "source": e.get("source"), "said": e.get("said"), "status": e.get("status")}
                for e in store.list_sos() if e["senior_id"] == senior_id][:5],
    }

@app.post("/api/coordinator/action")
def log_coordinator_action(payload: CoordinatorActionRequest, request: Request):
    """Records coordinator action & feedback loop."""
    _coord(request, payload.coordinator_code)
    _coord_of_senior(request, payload.senior_id)
    store.audit("coordinator", payload.coordinator_code.upper(), "action_" + payload.action_taken, payload.senior_id)
    return store.record_action(payload.dict())

# -------------------------------------------------------------
# AI Voice Calling & WebSocket Signaling (100% Free / Zero-Cloud)
# -------------------------------------------------------------
@app.websocket("/ws/seniors/{senior_id}")
async def websocket_senior_listener(websocket: WebSocket, senior_id: str):
    """
    Persistent WebSocket connection from Senior Android App's CallListenerService.
    Delivers sub-15ms incoming call events and wakes locked screens.
    """
    p = auth.verify(websocket.query_params.get("token") or websocket.headers.get("x-device-key"))
    if p is None or p.role != "senior" or p.sub != senior_id:
        await websocket.close(code=4001, reason="Unauthorized device")
        return
    senior = store.dynamic_seniors.get(senior_id) or store.seniors_map.get(senior_id)
    if not senior:
        await websocket.close(code=4004, reason="Senior ID not registered")
        return

    await ws_manager.connect(senior_id, websocket)
    for pending in store.pending_calls(senior_id):
        if await ws_manager.send_to_senior(senior_id, _incoming_call_message(pending)):
            store.set_call_status(pending["call_id"], "ringing")
            print(f"[Call] delivered queued call {pending['call_id']} on reconnect")
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            call_id = data.get("call_id")
            if event == "CALL_DECLINED":
                store.record_call_outcome(call_id, {
                    "senior_id": senior_id,
                    "status": "declined",
                    "summary": "Senior declined call from lock screen"
                })
            elif event == "CALL_MISSED":
                store.record_call_outcome(call_id, {
                    "senior_id": senior_id,
                    "status": "missed",
                    "duration_seconds": 30,
                    "summary": "Call rang for 30 seconds but was not answered"
                })
            elif event == "CALL_ACCEPTED":
                store.set_call_status(call_id, "connected")
                print(f"[Call] Senior {senior_id} accepted call {call_id}")
            elif event == "CALL_COMPLETED":
                store.record_call_outcome(call_id, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(senior_id, websocket)
    except Exception as e:
        print(f"[WS Error] {senior_id}: {e}")
        ws_manager.disconnect(senior_id, websocket)

def _incoming_call_message(call: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": "INCOMING_CALL",
        "call_id": call["call_id"],
        "senior_id": call["senior_id"],
        "caller_name": call["caller_name"],
        "caller_type": call["caller_type"],
        "channel_name": f"call_room_{call['senior_id']}",
        "timestamp": call["start_time"]
    }


def _digits(n: Any) -> str:
    return "".join(ch for ch in str(n or "") if ch.isdigit())


def _call_mode(senior: Optional[Dict[str, Any]]) -> str:
    """The care manager's setting. "phone": a basic (feature) phone, always rung on its number.
    "app" (the default): a smartphone with Saathi, called inside the app whenever the app is online."""
    return "phone" if (senior or {}).get("call_mode") == "phone" else "app"


def _rings_by_phone(senior: Optional[Dict[str, Any]]) -> bool:
    """Check-ins ring the senior's own number when Sarvam can place it and either they have a basic phone or their
    Saathi app is not online right now (the in-app call is free of phone charges, so it comes first)."""
    if not (senior and SARVAM.phone_calls_ready() and len(_digits(senior.get("phone"))) >= 10):
        return False
    return _call_mode(senior) == "phone" or not ws_manager.is_online(senior["senior_id"])


def _place_phone_call(senior: Dict[str, Any], caller_type: str, reason: str = "") -> Dict[str, Any]:
    """Saathi rings the senior's number from the Sarvam number; how it went arrives on the webhook."""
    from ai_agent.sarvam_call import agent_variables
    sid = senior["senior_id"]
    call_res = store.initiate_call(sid, caller_type)
    if "error" in call_res:
        return call_res
    call = call_res["call"]
    call["channel"] = "phone"
    variables = agent_variables(senior, build_health_context(store, sid), _todays_medicines(sid))
    variables.update(senior_id=sid, call_id=call["call_id"], reason_for_call=reason or "Daily check-in call.")
    msg = family_voice.pending(senior)
    if msg:      # a phone call cannot carry our audio: Saathi passes the family's message on in words
        variables["memory_note"] = (family_voice.agent_note(msg, False) + " " + variables["memory_note"])[:700]
        call["family_message_id"] = msg["id"]
    lang = language_name(senior.get("language"))
    meta = {"kind": "checkin", "call_id": call["call_id"]}
    try:
        attempt = dispatcher.client.outbound_call(
            senior["phone"], variables, lang, f"{public_url()}/api/sarvam/webhook?k={SARVAM_HOOK_KEY}", meta, agent="checkin")
        call.update(status="ringing", sarvam_attempt_id=attempt, sarvam_key=meta.get("acct", ""), rang_at=time.time())
        store.save()
        return {"call": call, "is_online": True, "sent": True, "channel": "phone"}
    except Exception as e:
        print(f"[Sarvam] check-in call to {sid} not placed: {str(e)[:160]}")
        if no_credit(e):
            return {"call": call, "is_online": False, "sent": False, "channel": "phone", "no_credit": True,
                    "phone_error": "Every Sarvam key is out of credit; top one up to place phone calls."}
        return _phone_call_missed(call, "The phone call could not be placed.")


def _phone_call_missed(call: Dict[str, Any], why: str) -> Dict[str, Any]:
    store.record_call_outcome(call["call_id"], {"senior_id": call["senior_id"], "status": "missed", "duration_seconds": 0,
                                                "transcript": [], "summary": why, "meds_taken": None, "emergency": False})
    return {"call": call, "is_online": False, "sent": False, "channel": "phone", "phone_error": why}


def _phone_call_in_thread(senior: Dict[str, Any], caller_type: str, reason: str = "") -> None:
    """For callers that cannot wait: an out-of-credit phone call is then recorded as missed."""
    res = _place_phone_call(senior, caller_type, reason)
    if res.get("no_credit"):
        _phone_call_missed(res["call"], res["phone_error"])


def _on_checkin_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sarvam reports a finished check-in phone call: save it like any other call (transcript, NLP, notes, risk)."""
    meta = (payload.get("webhook_config") or {}).get("metadata") or {}
    rec = store.get_call(str(meta.get("call_id") or ""))
    if not rec or rec.get("sarvam_attempt_id") != payload.get("attempt_id") or rec.get("phone_result"):
        return {"status": "ignored"}
    status = str(payload.get("status") or "failed")
    rec["phone_result"] = status
    rec["sarvam_interaction_id"] = payload.get("interaction_id")
    turns = []
    if status == "connected" and rec.get("family_message_id"):
        _s, m = _find_voice_message(rec["family_message_id"])
        if m and not m.get("played_at"):
            family_voice.mark_played(m, "read_on_phone_call", rec["call_id"])
    if status == "connected":
        try:     # the words as spoken (Hindi stays Hindi); the webhook itself carries only an English rendering
            acct = SARVAM_POOL.get(meta.get("acct") or rec.get("sarvam_key") or "")
            msgs = dispatcher.client.transcript(acct.checkin_app, payload.get("interaction_id") or "",
                                                account=acct.name).get("messages") or []
            turns = [("senior" if m.get("role") == "user" else "ai", m.get("content", "")) for m in msgs]
        except Exception as e:
            print(f"[Sarvam] transcript fetch failed: {str(e)[:120]}")
        if not turns:
            turns = [("senior" if t.get("role") == "user" else "ai", t.get("en_text", ""))
                     for t in (payload.get("interaction_transcript") or [])]
    senior = store.dynamic_seniors.get(rec["senior_id"]) or store.seniors_map.get(rec["senior_id"])
    conv = new_conversation(senior)
    stamp = time.strftime("%H:%M:%S")
    for speaker, text in turns:
        text = (text or "").strip()
        if not text:
            continue
        conv.transcript.append({"speaker": speaker, "text": text, "time": stamp})
        if speaker == "senior":
            for c in extract_symptom_cues(text).get("categories", []):
                if c not in conv.detected_symptoms:
                    conv.detected_symptoms.append(c)
            if is_emergency(text):
                conv.emergency_escalation = True
            _check_call_danger(rec, conv.senior_id, text)    # in case the agent's emergency tool did not fire
    # and Sarvam's English rendering of each line, so danger words are caught whatever script the words came back in
    for t in payload.get("interaction_transcript") or []:
        en = (t.get("en_text") or "").strip()
        if t.get("role") == "user" and en:
            if is_emergency(en):
                conv.emergency_escalation = True
            _check_call_danger(rec, conv.senior_id, en)
    conv.ended_no_response = not any(sp == "senior" for sp, _ in turns)
    conv.is_completed = True
    if status != "connected":
        rec["summary"] = {"no_answer": "Not answered.", "busy": "The line was busy."}.get(
            status, "The phone call could not be connected." + (f" ({payload.get('failure_reason')})" if payload.get("failure_reason") else ""))
    _finish_session(rec["call_id"], conv, int(payload.get("duration") or 0))
    return {"status": "ok"}


async def place_call(senior_id: str, caller_type: str = "ai_health_check") -> Dict[str, Any]:
    """Creates the call and rings the senior: inside the Saathi app when the care manager marked a smartphone and the
    app is online; otherwise on their own phone number through Sarvam (works on any phone). If every Sarvam key is
    out of credit the call moves into the app (no phone charges); a basic phone with no app then misses it.
    Without Sarvam: the app over its live connection; offline phones get it when they reconnect."""
    senior = store.dynamic_seniors.get(senior_id) or store.seniors_map.get(senior_id)
    call = None
    if _rings_by_phone(senior):
        res = await run_in_threadpool(_place_phone_call, senior, caller_type)
        if not res.get("no_credit"):
            return res
        call = res["call"]
        if not ws_manager.is_online(senior_id) and _call_mode(senior) == "phone":
            return await run_in_threadpool(_phone_call_missed, call, res["phone_error"] + " The Saathi app is not online either.")
        call["channel"] = "app"
        call["note"] = "Sarvam out of credit: called in the app instead"
    if call is None:
        call_res = store.initiate_call(senior_id, caller_type)
        if "error" in call_res:
            return call_res
        call = call_res["call"]
        call["channel"] = "app"
    is_online = ws_manager.is_online(senior_id)
    sent = await ws_manager.send_to_senior(senior_id, _incoming_call_message(call))
    if not sent:
        call["status"] = "queued"
    store.save()
    out = {"call": call, "is_online": is_online, "sent": sent, "channel": "app"}
    if call.get("note"):
        out["phone_error"] = ("Sarvam is out of credit, so Saathi is calling inside the app instead." if sent else
                              "Sarvam is out of credit and the Saathi app is offline: the call will ring in the app when it comes online.")
    return out


async def _scheduler_loop() -> None:
    """Places scheduled check-in calls at their time, every day; an unanswered one is tried once more after 10 min."""
    while True:
        try:
            _write_tool_url()          # the tunnel address can change after start
            for rec in store.call_records:
                if rec.get("channel") == "phone" and rec.get("status") == "ringing" and time.time() - rec.get("rang_at", time.time()) > 900:
                    store.record_call_outcome(rec["call_id"], {"senior_id": rec["senior_id"], "status": "missed", "duration_seconds": 0,
                                                              "transcript": [], "summary": "No report from the phone call.",
                                                              "meds_taken": None, "emergency": False})
            for job in store.due_schedules() + store.schedules_to_retry():
                res = await place_call(job["senior_id"], "scheduled_check_in")
                cid = res.get("call", {}).get("call_id")
                store.note_schedule_call(job["schedule_id"], cid)
                state = "rang" if res.get("sent") else "queued (phone offline)" if cid else res.get("error")
                print(f"[Schedule] {job['schedule_time']} call to {ascii(job['senior_name'])}: {state}"
                      + (" (retry)" if job.get("retries") else ""))
        except Exception as e:
            print(f"[Schedule] {type(e).__name__}: {e}")
        await asyncio.sleep(20)


@app.on_event("startup")
async def start_scheduler() -> None:
    _MAIN_LOOP["loop"] = asyncio.get_running_loop()
    asyncio.create_task(_scheduler_loop())


@app.post("/api/calls/initiate")
async def initiate_ai_call(payload: CallInitiateRequest, request: Request):
    _coord_of_senior(request, payload.senior_id, "ai_call")
    """
    Initiates an AI health-check call to a senior.
    Signals the phone via persistent WebSocket for instant locked-screen ringing.
    """
    senior_id = payload.senior_id
    res = await place_call(senior_id, payload.caller_type)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    call, is_online, sent = res["call"], res["is_online"], res["sent"]

    return {
        "status": "success",
        "call_id": call["call_id"],
        "senior_id": senior_id,
        "device_online": is_online,
        "signaled": sent,
        "message": res.get("phone_error") or ("Call signaled to senior device" if sent else "Senior device currently offline, call queued"),
        "channel": res.get("channel", "app"), "note": res.get("phone_error", "")
    }

def _finish_session(call_id: str, conv: HealthCheckConversation, duration: int, partial: bool = False):
    summary = conv.get_summary()
    spoke = any(t.get("speaker") == "senior" for t in summary["transcript"])
    payload = {
        "senior_id": conv.senior_id,
        "status": "completed" if (spoke or not conv.ended_no_response) else "missed",
        "duration_seconds": duration,
        "transcript": summary["transcript"],
        "summary": summary["summary"] + (" (call ended early by senior)" if partial else ""),
        "meds_taken": summary["meds_taken"],
        "emergency": summary["emergency"],
    }
    call_sessions.pop(call_id, None)
    out = store.record_call_outcome(call_id, payload)
    _attach_speech(call_id)
    if isinstance(conv, LLMConversation):
        def notes():
            store.attach_call_notes(call_id, conv.summarize(), conv.flags)
            _attach_speech(call_id)            # again, now with the notes' mood
        threading.Thread(target=notes, daemon=True).start()
    return out


def _attach_speech(call_id: str) -> None:
    """Memory and mood signals from the senior's own words on this call (engine/speech_signals.py)."""
    rec = store.get_call(call_id)
    if rec and rec.get("status") == "completed":
        sp = speech_signals.analyse_call(rec.get("transcript") or [], rec.get("mood"))
        if sp:
            rec["speech"] = sp
            store.save()


def speech_trend(senior_id: str) -> Dict[str, Any]:
    calls = sorted((c for c in store.call_records if c.get("senior_id") == senior_id and c.get("speech")),
                   key=lambda c: c.get("start_time") or "")
    return speech_signals.trend(calls)

@app.post("/api/calls/{call_id}/start")
def start_call_conversation(call_id: str, request: Request, engine: str = ""):
    _call_owner(request, call_id)
    """Senior answered: start the Hindi health-check agent and return its greeting."""
    rec = store.get_call(call_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Call not found")
    if rec["status"] not in ("ringing", "queued", "connected"):
        raise HTTPException(status_code=409, detail=f"Call already {rec['status']}")
    senior = store.dynamic_seniors.get(rec["senior_id"]) or store.seniors_map.get(rec["senior_id"])
    conv = new_conversation(senior)
    store.save()
    call_sessions[call_id] = conv
    rec["status"] = "connected"
    rec["started_at"] = time.time()
    if SARVAM.calls_ready() and engine != "local":
        # Sarvam speaks first and runs the conversation; the phone opens the live socket next
        return {"engine": "sarvam", "live_path": f"/ws/calls/{call_id}/live", "language": conv.language,
                "is_completed": False}
    opener = rec.pop("opener", None)
    # opened from "tell us by voice": Saathi answers what they just said instead of a generic greeting
    greeting = conv.process_user_turn(opener) if opener else conv.get_greeting()
    msg = None if opener else family_voice.pending(senior)
    if msg and family_voice.read(msg["id"]):
        # a family voice message: Saathi's intro, the real recording, then the greeting, as one MP3
        intro = family_voice.intro(msg, conv.language == "hi")
        conv.transcript.insert(max(len(conv.transcript) - 1, 0), {"speaker": "ai", "time": time.strftime("%H:%M:%S"),
                               "text": f"{intro} [🎧 {msg['from']}: {msg.get('text') or 'voice message'}]"})
        family_voice.mark_played(msg, "recording_in_app", call_id)
        rec.update(family_message_id=msg["id"], opening=[intro, msg["id"], greeting], opening_voice=conv.voice)
        store.save()
        return {"reply": f"{intro} … {greeting}", "audio_url": f"/api/calls/{call_id}/opening.mp3?m={msg['id']}",
                "language": conv.language, "is_completed": False, "engine": "local", "family_message": msg["from"]}
    return {
        "reply": greeting,
        "audio_url": "/api/calls/voice-audio?text=" + quote(mask_for_tts(greeting, conv.senior_name)[:350]) + "&voice=" + conv.voice,
        "language": conv.language,
        "is_completed": False,
        "engine": "local",
    }

@app.get("/api/calls/{call_id}/opening.mp3")
async def call_opening_audio(call_id: str, request: Request, m: str = ""):
    """Saathi's intro + the family's own recording + the greeting, joined (all 24 kHz mono MP3)."""
    rec = _call_owner(request, call_id)
    parts = rec.get("opening") or []
    if len(parts) != 3:
        raise HTTPException(status_code=404, detail="No opening for this call")
    name = rec.get("senior_name", "")
    voice = rec.get("opening_voice") or "hi-IN-SwaraNeural"
    first = await tts_audio(mask_for_tts(parts[0], name)[:350], voice)
    last = await tts_audio(mask_for_tts(parts[2], name)[:350], voice)
    return Response(content=first + (family_voice.read(parts[1]) or b"") + last, media_type="audio/mpeg")


# -------------------------------------------------------------------------------- family voice messages
def _find_voice_message(mid: str):
    for s in list(store.dynamic_seniors.values()) + list(store.seniors_map.values()):
        for m in s.get("family_messages") or []:
            if m["id"] == mid:
                return s, m
    return None, None


def _family_senior(request: Request) -> Dict[str, Any]:
    p = who(request, "family")
    senior = store.find_by_family_code(p.sub)            # consent is re-checked on every request
    if not senior:
        raise HTTPException(status_code=403, detail="Sharing was switched off by the senior")
    return senior


@app.post("/api/family/voice-message")
async def family_voice_message(request: Request, from_name: str = "", relation: str = ""):
    """The family records a message; Saathi plays it in the next check-in call."""
    senior = _family_senior(request)
    raw = await request.body()
    lang = "en" if str(senior.get("language", "hi")).startswith("en") else "hi"

    def words(wav: bytes) -> str:
        return stt.transcribe(wav, lang).get("text", "") if stt.installed() else ""
    try:
        msg = await run_in_threadpool(family_voice.add, senior, raw, from_name, relation, "", words)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Voice message] not saved: {type(e).__name__}: {str(e)[:120]}")
        raise HTTPException(status_code=400, detail="Could not read that recording. Please try again.")
    store.save()
    store.audit("family", senior.get("family_code", ""), "voice_message", senior["senior_id"])
    return family_voice.public([msg])[0]


@app.get("/api/family/voice-messages")
def family_voice_messages(request: Request):
    return family_voice.public(_family_senior(request).get("family_messages"))


@app.get("/api/voice-messages/{mid}.mp3")
def voice_message_audio(mid: str, request: Request):
    p = who(request, "family", "coordinator", "senior")
    s, m = _find_voice_message(mid)
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    allowed = ((p.role == "family" and p.scope == s["senior_id"] and s.get("family_sharing_consent"))
               or (p.role == "coordinator" and s.get("coordinator_code") == p.sub)
               or (p.role == "senior" and p.sub == s["senior_id"]))
    audio = family_voice.read(mid) if allowed else None
    if audio is None:
        raise HTTPException(status_code=404 if allowed else 403, detail="Not available")
    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/family/voice-summary")
def family_voice_summary(request: Request, lang: str = "en"):
    """A short spoken update for the family: how they sounded, medicines, walking. Never what was said."""
    senior = _family_senior(request)
    d = store.family_overview(senior["senior_id"])
    hi = lang.startswith("hi")
    calls = [c for c in d.get("calls_7d") or [] if c.get("done")]
    last = sorted(calls, key=lambda c: c["date"])[-1] if calls else None
    mood = {"good": ("cheerful", "ख़ुश"), "okay": ("calm and okay", "ठीक"), "low": ("a little low", "थोड़े उदास"),
            "distressed": ("upset, and the care team is following up", "परेशान, और केयर टीम संपर्क में है")}
    steps = int(d.get("avg_daily_steps") or 0)
    adh = d.get("adherence_rate") or ""
    played = [m for m in senior.get("family_messages") or [] if m.get("played_at") and time.time() - m["played_at"] < 7 * 86400]
    if hi:
        parts = ["साथी की ओर से इस हफ़्ते का हाल।"]
        if last:
            parts.append(f"आख़िरी कॉल में वे {mood.get(last.get('mood'), ('', 'ठीक'))[1]} लगे।")
        parts.append(f"इस हफ़्ते {len(calls)} चेक-इन कॉल हुईं।" if calls else "इस हफ़्ते अभी कोई चेक-इन कॉल नहीं हुई।")
        if adh:
            parts.append(f"दवा {adh} समय पर ली।")
        if steps:
            parts.append(f"रोज़ औसतन {steps} कदम चले।")
        if played:
            parts.append("आपका संदेश उन्हें सुना दिया गया।")
        if d.get("serious_alert"):
            parts.append("अभी केयर टीम एक अलर्ट देख रही है।")
    else:
        parts = ["Here's this week's update from Saathi."]
        if last:
            parts.append(f"On the last call they sounded {mood.get(last.get('mood'), ('okay', ''))[0]}.")
        parts.append(f"{len(calls)} check-in call{'s' if len(calls) != 1 else ''} this week." if calls else "No check-in calls yet this week.")
        if adh:
            parts.append(f"Medicines taken: {adh}.")
        if steps:
            parts.append(f"About {steps:,} steps a day.")
        if played:
            parts.append("Your voice message was played to them.")
        if d.get("serious_alert"):
            parts.append("The care team is handling an alert right now.")
    text = " ".join(parts)[:340]
    voice = "hi-IN-SwaraNeural" if hi else "en-IN-NeerjaNeural"
    return {"text": text, "audio_url": "/api/calls/voice-audio?text=" + quote(mask_for_tts(text, senior.get("name", ""))) + "&voice=" + voice}


def _check_call_danger(rec: Optional[Dict[str, Any]], senior_id: str, said: str) -> None:
    """The senior said something like "I am dying" on a call: SOS and the family alert call, once per call."""
    if not said or rec is None or rec.get("family_alerted"):
        return
    if is_danger(said) or "fall" in extract_symptom_cues(said).get("categories", []):
        rec["family_alerted"] = True
        store.save()
        dispatcher.raise_emergency(senior_id, "call", said)


def _turn_response(call_id: str, conv: HealthCheckConversation, reply: str, heard: str = ""):
    """Shared tail of every conversation turn: sync live view, finish if done, build the reply."""
    rec = store.get_call(call_id)
    _check_call_danger(rec, conv.senior_id, heard)
    # keep the coordinator's live view in sync while the call is in progress
    if rec is not None:
        rec["transcript"] = list(conv.transcript)
        rec["symptoms_reported"] = sorted(set(conv.detected_symptoms))
        store.save()
    result = None
    if conv.is_completed:
        duration = int(time.time() - rec.get("started_at", time.time())) if rec else 0
        result = _finish_session(call_id, conv, duration)
    return {
        "heard": heard,
        "reply": reply,
        "audio_url": "/api/calls/voice-audio?text=" + quote(mask_for_tts(reply, conv.senior_name)[:350]) + "&voice=" + conv.voice,
        "is_completed": conv.is_completed,
        "emergency": conv.emergency_escalation,
        "symptoms": sorted(set(conv.detected_symptoms)),
        "meds_taken": conv.meds_taken,
        "call": result["call"] if result and "call" in result else None,
    }

@app.post("/api/calls/{call_id}/turn")
def call_conversation_turn(call_id: str, payload: CallTurnRequest, request: Request):
    _call_owner(request, call_id)
    """One senior utterance (text) in, next agent reply out. `silence: true` = nothing was said."""
    conv = call_sessions.get(call_id)
    if not conv:
        raise HTTPException(status_code=404, detail="No active conversation for this call")
    text = payload.text.strip()[:500]
    if payload.silence or not text:
        reply = conv.process_silence()
    else:
        reply = conv.process_user_turn(text)
    return _turn_response(call_id, conv, reply, heard=text)

@app.post("/api/calls/{call_id}/audio")
async def call_conversation_audio(call_id: str, request: Request):
    _call_owner(request, call_id)
    """
    One senior utterance as WAV bytes (16 kHz mono) -> Whisper -> agent -> reply.
    Empty transcription (silence / noise) is handled like silence so the agent re-prompts.
    """
    conv = call_sessions.get(call_id)
    if not conv:
        raise HTTPException(status_code=404, detail="No active conversation for this call")
    wav = await request.body()
    if len(wav) < 1000:
        raise HTTPException(status_code=400, detail="Audio too short")
    if len(wav) > 3_000_000:
        raise HTTPException(status_code=413, detail="Audio too long")
    try:
        res = await run_in_threadpool(stt.transcribe, wav, conv.language)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    text = res["text"].strip()
    reply = conv.process_user_turn(text) if text else conv.process_silence()
    out = _turn_response(call_id, conv, reply, heard=text)
    out["stt_confidence"] = res["confidence"]
    return out

async def _stream_turn(websocket: WebSocket, call_id: str, conv: LLMConversation, text: str, res: Dict[str, Any],
                       t0: float, t_stt: float) -> None:
    """
    Streams Saathi's reply sentence by sentence: {"type":"say","seq","text","filler"} + one MP3 frame each, in order,
    then the usual turn JSON with "streamed": true. The model runs in a thread; each sentence's voice is rendered as
    soon as the sentence exists, so sentence one plays while the next is still being written. If nothing is ready
    after ~0.9 s, a short pre-recorded "okay, I see" goes first (never two turns running), as a person would.
    """
    loop = asyncio.get_running_loop()
    sentences: asyncio.Queue = asyncio.Queue()
    clips: asyncio.Queue = asyncio.Queue()

    def produce():
        try:
            gen = conv.stream_user_turn(text) if text else iter([conv.process_silence()])
            for sent in gen:
                loop.call_soon_threadsafe(sentences.put_nowait, sent)
        except Exception as e:
            print(f"[LLM] stream: {e}")
        finally:
            loop.call_soon_threadsafe(sentences.put_nowait, None)
    threading.Thread(target=produce, daemon=True).start()

    first_audio = {"ms": None}

    async def sender():
        seq = 0
        while True:
            item = await clips.get()
            if item is None:
                return
            sent, task, filler = item
            try:
                audio = await task
            except Exception as e:
                print(f"[TTS] {e}")
                audio = None
            await websocket.send_json({"type": "say", "seq": seq, "text": sent, "filler": filler, "has_audio": audio is not None})
            if audio:
                await websocket.send_bytes(audio)
                if first_audio["ms"] is None:
                    first_audio["ms"] = round((time.time() - t0) * 1000)
            seq += 1
    send_task = asyncio.create_task(sender())

    spoken, filler_sent = [], False
    while True:
        # a filler only when she is clearly slow (0.9 s), and never two turns in a row: fewer and less noticeable
        wait = 0.9 if (text and not spoken and not filler_sent and getattr(conv, "_filler_turn", -9) < conv.turn - 1) else None
        try:
            sent = await asyncio.wait_for(sentences.get(), timeout=wait - (time.time() - t0 - t_stt) if wait else None)
        except asyncio.TimeoutError:
            fillers = AGENT_TEXT[conv.language]["fillers"]
            f = fillers[conv.turn % len(fillers)]
            clips.put_nowait((f, asyncio.create_task(tts_audio(f, conv.voice)), True))
            filler_sent = True
            conv._filler_turn = conv.turn
            continue
        if sent is None:
            break
        spoken.append(sent)
        clips.put_nowait((sent, asyncio.create_task(tts_audio(mask_for_tts(sent, conv.senior_name)[:350], conv.voice)), False))
    clips.put_nowait(None)
    await send_task

    out = _turn_response(call_id, conv, " ".join(spoken), heard=text)
    out["type"] = "turn"
    out["streamed"] = True
    out["has_audio"] = False
    out["stt_confidence"] = res.get("confidence", 0.0)
    out["timing_ms"] = {"stt_finish": round(t_stt * 1000), "first_audio": first_audio["ms"],
                        "server_total": round((time.time() - t0) * 1000), **getattr(conv, "last_timing", {})}
    print(f"[Turn] {call_id[-6:]} heard={ascii(text[:40])} timing_ms={out['timing_ms']}")
    await websocket.send_json(out)


def _todays_medicines(senior_id: str) -> str:
    try:
        rows = store.today_doses(senior_id)
    except Exception:
        return ""
    by: Dict[str, List[str]] = {}
    for r in rows:
        by.setdefault(r["name"], []).append(r["time"])
    return "; ".join(f"{n} at {', '.join(t)}" for n, t in by.items())


@app.websocket("/ws/calls/{call_id}/live")
async def call_live_stream(websocket: WebSocket, call_id: str):
    """
    The Sarvam call. The phone streams 16 kHz 16-bit mono PCM; it gets back the agent's PCM (binary frames, rate
    announced by {"type":"audio_format"}), captions, {"type":"interrupt"} (stop playback) and {"type":"end"}.
    If Sarvam cannot be reached the phone gets {"type":"fallback"} and runs the local engine for this call.
    """
    from ai_agent.sarvam_call import SarvamCallBridge, agent_variables
    p = auth.verify(websocket.query_params.get("token") or websocket.headers.get("x-device-key"))
    rec = store.get_call(call_id)
    if p is None or p.role != "senior" or rec is None or rec["senior_id"] != p.sub:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    conv = call_sessions.get(call_id)
    if not conv:
        await websocket.close(code=4004, reason="No active conversation")
        return
    await websocket.accept()
    senior = store.dynamic_seniors.get(rec["senior_id"]) or store.seniors_map.get(rec["senior_id"])
    ctx = await run_in_threadpool(build_health_context, store, rec["senior_id"])

    def on_line(speaker: str, text: str) -> None:
        conv.transcript.append({"speaker": speaker, "text": text, "time": time.strftime("%H:%M:%S")})
        if speaker == "senior":
            cues = extract_symptom_cues(text).get("categories", [])
            for c in cues:
                if c not in conv.detected_symptoms:
                    conv.detected_symptoms.append(c)
            if is_emergency(text):
                conv.emergency_escalation = True
            _check_call_danger(rec, conv.senior_id, text)
        rec["transcript"] = list(conv.transcript)
        rec["symptoms_reported"] = sorted(set(conv.detected_symptoms))
        store.save()

    async def send_bytes(b: bytes) -> None:
        await websocket.send_bytes(b)

    variables = agent_variables(senior, ctx, _todays_medicines(rec["senior_id"]))
    msg = family_voice.pending(senior)
    if msg and family_voice.read(msg["id"]):
        # the family's own recording plays before the agent starts; the agent then knows it was heard
        hindi = not str(senior.get("language", "hi")).startswith("en")
        intro = family_voice.intro(msg, hindi)
        try:
            spoken = await tts_audio(mask_for_tts(intro, senior.get("name", "")), "hi-IN-SwaraNeural" if hindi else "en-IN-NeerjaNeural")
            pcm = await run_in_threadpool(lambda: family_voice.pcm16k(spoken) + b"\0" * 9600 + family_voice.pcm16k(family_voice.read(msg["id"])))
            await websocket.send_json({"type": "audio_format", "sample_rate": 16000, "encoding": "pcm16"})
            await websocket.send_json({"type": "caption", "speaker": "ai", "text": f"{intro} 🎧"})
            for i in range(0, len(pcm), 6400):
                await websocket.send_bytes(pcm[i:i + 6400])
            await asyncio.sleep(len(pcm) / 32000 + 0.4)
            family_voice.mark_played(msg, "recording_in_app", call_id)
            rec["family_message_id"] = msg["id"]
            on_line("ai", f"{intro} [🎧 {msg['from']}: {msg.get('text') or 'voice message'}]")
            variables["memory_note"] = (family_voice.agent_note(msg, True) + " " + variables["memory_note"])[:700]
        except Exception as e:
            print(f"[Voice message] not played: {type(e).__name__}: {str(e)[:120]}")
    bridge = SarvamCallBridge(call_id, senior, variables, websocket.send_json, send_bytes, on_line)
    try:
        ok = await bridge.start()
    except Exception as e:
        print(f"[Sarvam] call {call_id} could not start: {type(e).__name__}: {str(e)[:160]}")
        ok = False
    if not ok:
        await websocket.send_json({"type": "fallback"})
        await websocket.close()
        return
    rec["engine"] = "sarvam"
    rec["sarvam_key"] = bridge.account
    hung_up = False
    try:
        while not bridge.ended:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                hung_up = True
                break
            if msg.get("bytes") is not None:
                await bridge.feed(msg["bytes"])
            elif json.loads(msg.get("text") or "{}").get("type") == "hangup":
                hung_up = True
                break
    except Exception as e:
        print(f"[Sarvam] call {call_id} socket: {type(e).__name__}: {str(e)[:160]}"
              + (f" | Sarvam closed: {bridge.close_reason}" if bridge.close_reason else ""))
    finally:
        if hung_up:
            print(f"[Sarvam] call {call_id}: the phone hung up")
        await bridge.stop()
        rec["sarvam_interaction_id"] = bridge.interaction_id
        conv.is_completed = True
        if call_id in call_sessions:
            duration = int(time.time() - rec.get("started_at", time.time()))
            await run_in_threadpool(_finish_session, call_id, conv, duration, hung_up)
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws/calls/{call_id}/audio")
async def call_audio_stream(websocket: WebSocket, call_id: str):
    """
    Low-latency turn loop. The phone streams 16 kHz PCM while the senior speaks, so the words are already
    recognised when they stop; then it sends {"type":"end"} and gets back the turn (JSON) and the spoken
    reply (one binary MP3 frame) on the same connection: no second request for the audio.
    """
    p = auth.verify(websocket.query_params.get("token") or websocket.headers.get("x-device-key"))
    rec = store.get_call(call_id)
    if p is None or p.role != "senior" or rec is None or rec["senior_id"] != p.sub:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    conv = call_sessions.get(call_id)
    if not conv:
        await websocket.close(code=4004, reason="No active conversation")
        return
    await websocket.accept()
    stream = None
    t_first = None
    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if stream is None:
                    stream = await run_in_threadpool(stt.live, conv.language, conv.expect)
                    t_first = time.time()
                await run_in_threadpool(stream.feed, msg["bytes"])
                continue
            data = json.loads(msg.get("text") or "{}")
            if data.get("type") == "reset":
                stream = None
                continue
            if data.get("type") != "end":
                continue
            t0 = time.time()
            res = {"text": "", "confidence": 0.0}
            if stream is not None and not data.get("silence"):
                res = await run_in_threadpool(stream.finish)
            stream = None
            t_stt = time.time() - t0
            text = res["text"].strip()
            if data.get("stream") and isinstance(conv, LLMConversation):
                await _stream_turn(websocket, call_id, conv, text, res, t0, t_stt)
                if conv.is_completed:
                    break
                continue
            t1 = time.time()
            reply = (await run_in_threadpool(conv.process_user_turn, text)) if text else conv.process_silence()
            out = _turn_response(call_id, conv, reply, heard=text)
            t_agent = time.time() - t1
            t2 = time.time()
            audio = None
            try:
                audio = await tts_audio(mask_for_tts(reply, conv.senior_name)[:350], conv.voice)
            except Exception as e:
                print(f"[TTS] {e}")
            t_tts = time.time() - t2
            out["stt_confidence"] = res.get("confidence", 0.0)
            out["has_audio"] = audio is not None
            out["timing_ms"] = {"stt_finish": round(t_stt * 1000), "agent": round(t_agent * 1000), "tts": round(t_tts * 1000),
                                "server_total": round((time.time() - t0) * 1000)}
            print(f"[Turn] {call_id[-6:]} heard={ascii(text[:40])} timing_ms={out['timing_ms']}")
            await websocket.send_json(out)
            if audio:
                await websocket.send_bytes(audio)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS audio] {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


class LanguageRequest(BaseModel):
    senior_id: str
    language: str   # "hi" | "en"

@app.post("/api/senior/language")
def set_senior_language(payload: LanguageRequest, request: Request):
    _own(request, payload.senior_id)
    """The app's language switch: future AI calls to this senior use this language."""
    senior = store.dynamic_seniors.get(payload.senior_id) or store.seniors_map.get(payload.senior_id)
    if not senior:
        raise HTTPException(status_code=404, detail="Senior not found")
    senior["language"] = "en" if payload.language.lower().startswith("en") else "hi"
    store.save()
    return {"status": "ok", "language": senior["language"]}

class CallModeRequest(BaseModel):
    call_mode: str   # "phone" (basic / feature phone) | "app" (smartphone with Saathi)

@app.post("/api/coordinator/seniors/{senior_id}/call-mode")
def set_call_mode(senior_id: str, payload: CallModeRequest, request: Request):
    """The care manager's toggle: ring a basic phone on its number, or call a smartphone inside the Saathi app."""
    senior = _coord_of_senior(request, senior_id, "set_call_mode")
    if payload.call_mode not in ("phone", "app"):
        raise HTTPException(status_code=400, detail="call_mode must be 'phone' or 'app'")
    senior["call_mode"] = payload.call_mode
    store.save()
    return {"status": "ok", "call_mode": senior["call_mode"], "app_online": ws_manager.is_online(senior_id),
            "phone_calls": SARVAM.phone_calls_ready(), "has_number": len(_digits(senior.get("phone"))) >= 10}

class CallLanguageRequest(BaseModel):
    language: str    # hi, en, bn, gu, kn, ml, mr, od, pa, ta, te

@app.post("/api/coordinator/seniors/{senior_id}/language")
def set_call_language(senior_id: str, payload: CallLanguageRequest, request: Request):
    """The language Saathi speaks on their calls. Hindi and English work everywhere; the other Indian languages need
    a Sarvam call (phone, or the app with Sarvam), since the hub's own voice speaks Hindi and English."""
    senior = _coord_of_senior(request, senior_id, "set_language")
    code = payload.language.lower()[:2]
    if code not in LANGUAGES:
        raise HTTPException(status_code=400, detail="Unknown language")
    senior["language"] = code
    store.save()
    return {"status": "ok", "language": code, "name": LANGUAGES[code]}

@app.get("/api/stt/status")
def stt_status():
    """Lets the app / dashboard check whether server-side speech recognition is ready."""
    return {"installed": stt.installed(), "engine": stt.engine, "languages": stt.languages}

CALL_WORDS = ("call", "phone", "ring", "dial", "फ़ोन", "फोन", "कॉल", "बात करा", "बात कर", "baat kara", "phone karo", "phone lagao", "लगाओ", "लगा दो")
RELATION_WORDS = {
    "son": ("son", "beta", "bete", "बेटा", "बेटे", "बेटे को"), "daughter": ("daughter", "beti", "बेटी"),
    "wife": ("wife", "patni", "पत्नी"), "husband": ("husband", "pati", "पति"), "brother": ("brother", "bhai", "भाई"),
    "sister": ("sister", "behen", "बहन"), "grandson": ("grandson", "pota", "पोता"), "granddaughter": ("granddaughter", "poti", "पोती"),
    "neighbour": ("neighbour", "neighbor", "padosi", "पड़ोसी"), "doctor": ("doctor", "डॉक्टर"),
}
CARE_WORDS = ("care manager", "coordinator", "केयर मैनेजर", "कोऑर्डिनेटर")


def _dial_intent(senior_id: str, low: str) -> Optional[Dict[str, str]]:
    """Whom the senior asked to call, from their own contact list (or the care manager); None if not a call request."""
    def has(w: str) -> bool:      # whole words for English ("son" is not in "person"), plain match for Hindi
        return bool(re.search(r"\b" + re.escape(w) + r"\b", low)) if w.isascii() else w in low
    if not any(has(w) for w in CALL_WORDS) or is_emergency(low):
        return None
    s = _senior_obj(senior_id)
    if any(has(w) for w in CARE_WORDS):
        coord = store.coordinators.get(s.get("coordinator_code"), {})
        return {"name": coord.get("name", ""), "phone": coord.get("phone", "")} if coord.get("phone") else None
    for c in store.list_contacts(senior_id):
        first = (c.get("name") or "").split(" ")[0].lower()
        rel = (c.get("relation") or "").lower()
        words = next((v for k, v in RELATION_WORDS.items() if k in rel), ())
        if (first and len(first) > 2 and has(first)) or any(has(w) for w in words) or (rel and has(rel)):
            return {"name": c.get("name") or c.get("relation"), "phone": c.get("phone", "")}
    return None


@app.post("/api/senior/voice-note")
async def senior_voice_note(request: Request, senior_id: str, lang: Optional[str] = None):
    _own(request, senior_id)
    """Home-screen 'speak to tell us' button: WAV bytes -> text -> check-in for the coordinator."""
    from engine.nlp_extractor import extract_symptom_cues
    wav = await request.body()
    if len(wav) < 1000:
        raise HTTPException(status_code=400, detail="Audio too short")
    if len(wav) > 3_000_000:
        raise HTTPException(status_code=413, detail="Audio too long")
    senior = store.dynamic_seniors.get(senior_id) or store.seniors_map.get(senior_id)
    if not senior:
        raise HTTPException(status_code=404, detail="Senior not found")
    try:
        res = await run_in_threadpool(stt.transcribe, wav, lang or senior.get("language", "hi"))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    text = res["text"].strip()
    low = text.lower()
    # "call my son" / "बेटे को फ़ोन करो": open the phone's dialer for that person instead of a check-in
    who_to_call = _dial_intent(senior_id, low) if text else None
    if who_to_call:
        lang = normalize_language(senior.get("language", "hi"))
        say = (f"{who_to_call['name']} को फ़ोन लगा रही हूँ।" if lang == "hi" else f"Calling {who_to_call['name']} for you.")
        return {"heard": text, "status": "good", "symptoms": [], "action": "dial", "phone": who_to_call["phone"], "name": who_to_call["name"],
                "reply": say, "audio_url": "/api/calls/voice-audio?text=" + quote(say[:350]) + "&voice=" + VOICES[lang]}
    cues = extract_symptom_cues(text).get("categories", []) if text else []
    unwell = _has_any(low, UNWELL_WORDS) or _has_any(low, CONTRAST_WORDS)
    emergency = bool(text) and (is_emergency(low) or "fall" in cues)
    if emergency or any(c in cues for c in ("fall", "dizziness")):
        status = "bad"
    elif cues or unwell:
        status = "weak"
    else:
        status = "good"
    if text:
        out = store.record_checkin(senior_id, "voice", status, text)
        if "error" in out:
            raise HTTPException(status_code=404, detail=out["error"])
    reply = {"heard": text, "status": status, "symptoms": cues}
    if not text:
        return reply
    # Saathi answers, and does something useful with it:
    #  an emergency -> SOS to the care manager; anything worrying -> a conversation opens right away, starting
    #  with what they said; good news -> a warm acknowledgement.
    lang = normalize_language(senior.get("language", "hi"))
    t = AGENT_TEXT[lang]
    if emergency:
        if is_danger(text) or "fall" in cues:
            dispatcher.raise_emergency(senior_id, "voice_note", text)     # SOS + the family is phoned
        else:
            store.create_sos(senior_id, source="voice_note")               # "I want a person": care manager only
        say = t["note_emergency"]
        reply["sos"] = True
    elif status != "good" and _rings_by_phone(senior):
        threading.Thread(target=_phone_call_in_thread, args=(senior, "voice_note_follow_up",
                                                         f"They just sent a voice note saying: {text[:300]}"), daemon=True).start()
        say = t["note_talk"]
    elif status != "good":
        call = store.initiate_call(senior_id, "voice_note_follow_up").get("call")
        if call:
            call["opener"] = text
            store.save()
            reply.update(start_call=True, call_id=call["call_id"])
        say = t["note_talk"]
    else:
        say = t["note_good"]
    reply["reply"] = say
    reply["audio_url"] = "/api/calls/voice-audio?text=" + quote(mask_for_tts(say, senior["name"])[:350]) + "&voice=" + VOICES[lang]
    return reply

@app.post("/api/calls/{call_id}/end")
def end_call_conversation(call_id: str, request: Request):
    _call_owner(request, call_id)
    """Senior hung up mid-call: save what was said so far."""
    conv = call_sessions.get(call_id)
    rec = store.get_call(call_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Call not found")
    if not conv:
        return {"status": "ok", "call": rec}
    duration = int(time.time() - rec.get("started_at", time.time()))
    return _finish_session(call_id, conv, duration, partial=True)

@app.get("/api/calls/state/{call_id}")
def get_call_state(call_id: str, request: Request):
    p = who(request, "coordinator", "senior")
    _rec = store.get_call(call_id)
    if _rec and ((p.role == "coordinator" and _rec.get("coordinator_code") != p.sub)
                 or (p.role == "senior" and _rec["senior_id"] != p.sub)):
        raise HTTPException(status_code=403, detail="Not your call")
    """Live call record (status + transcript so far); polled by the coordinator dashboard."""
    rec = store.get_call(call_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Call not found")
    return rec

@app.post("/api/calls/complete")
def complete_ai_call(payload: CallCompleteRequest, request: Request):
    _own(request, payload.senior_id)
    """
    Logs completed call transcript, extracts NLP symptom cues, updates meds,
    and recalculates clinical triage risk.
    """
    res = store.record_call_outcome(payload.call_id, payload.dict())
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.post("/api/calls/schedule")
def schedule_ai_call(payload: CallScheduleRequest, request: Request):
    _coord_of_senior(request, payload.senior_id)
    """Schedules a daily recurring check-in call (HH:MM, hub's local time)."""
    res = store.schedule_call(payload.senior_id, payload.schedule_time, payload.recurring)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@app.get("/api/calls/schedule/{senior_id}")
def list_ai_call_schedules(senior_id: str, request: Request):
    _coord_of_senior(request, senior_id)
    return store.list_schedules(senior_id)


@app.delete("/api/calls/schedule/{schedule_id}")
def cancel_ai_call_schedule(schedule_id: str, request: Request):
    e = next((x for x in store.scheduled_calls if x.get("schedule_id") == schedule_id), None)
    if not e:
        raise HTTPException(status_code=404, detail="Schedule not found")
    _coord_of_senior(request, e["senior_id"])
    store.cancel_schedule(schedule_id)
    return {"status": "ok"}

# -------------------------------------------------------------
# Medicines (set by the care manager, answered on the phone) and family contacts
# -------------------------------------------------------------
class MedicineIn(BaseModel):
    id: Optional[str] = None
    name: str
    dose_text: Optional[str] = ""
    times: List[str]
    with_food: Optional[bool] = False


class DoseIn(BaseModel):
    senior_id: str
    med_id: str
    time: str
    status: str            # taken | skipped | later


class ContactIn(BaseModel):
    id: Optional[str] = None
    name: str
    relation: Optional[str] = ""
    phone: str
    is_emergency: Optional[bool] = False


def _result(res: Dict[str, Any]) -> Dict[str, Any]:
    if "error" in res:
        raise HTTPException(status_code=404 if "not found" in res["error"] else 400, detail=res["error"])
    return res


@app.get("/api/seniors/{senior_id}/medicines")
def coord_list_medicines(senior_id: str, request: Request):
    _coord_of_senior(request, senior_id)
    return store.dose_days(senior_id, 14)


@app.post("/api/seniors/{senior_id}/medicines")
async def coord_save_medicine(senior_id: str, payload: MedicineIn, request: Request):
    _coord_of_senior(request, senior_id, "medicine_saved")
    res = _result(store.save_medicine(senior_id, payload.dict()))
    await _notify_phone(senior_id, "medicines_changed")
    return res


@app.delete("/api/seniors/{senior_id}/medicines/{med_id}")
async def coord_delete_medicine(senior_id: str, med_id: str, request: Request):
    _coord_of_senior(request, senior_id, "medicine_removed")
    res = _result(store.delete_medicine(senior_id, med_id))
    await _notify_phone(senior_id, "medicines_changed")
    return res


@app.get("/api/seniors/{senior_id}/contacts")
def coord_list_contacts(senior_id: str, request: Request):
    _coord_of_senior(request, senior_id)
    return store.list_contacts(senior_id)


@app.post("/api/seniors/{senior_id}/contacts")
async def coord_save_contact(senior_id: str, payload: ContactIn, request: Request):
    _coord_of_senior(request, senior_id, "contact_saved")
    res = _result(store.save_contact(senior_id, payload.dict()))
    await _notify_phone(senior_id, "contacts_changed")
    return res


@app.delete("/api/seniors/{senior_id}/contacts/{contact_id}")
async def coord_delete_contact(senior_id: str, contact_id: str, request: Request):
    _coord_of_senior(request, senior_id, "contact_removed")
    res = _result(store.delete_contact(senior_id, contact_id))
    await _notify_phone(senior_id, "contacts_changed")
    return res


@app.get("/api/senior/medicines")
def device_medicines(senior_id: str, request: Request):
    """The phone's copy: the medicines (to set alarms), today's doses and the last 7 days."""
    _own(request, senior_id)
    week = store.dose_days(senior_id, 7)
    days = []
    for i, day in enumerate(week["dates"]):
        cells = [c["status"] for m in week["medicines"] for c in m["days"][i]["doses"]]
        counted = [c for c in cells if c in ("taken", "skipped", "missed")]
        days.append({"date": day, "state": "none" if not counted and "due" not in cells else
                     "due" if not counted else "taken" if all(c == "taken" for c in counted) else
                     "some" if "taken" in counted else "missed"})
    return {"medicines": store.list_medicines(senior_id), "today": store.today_doses(senior_id), "week": days,
            "server_time": time.time()}     # lets the phone correct a wrong clock


@app.post("/api/senior/medicines/dose")
def device_dose(payload: DoseIn, request: Request):
    _own(request, payload.senior_id)
    return _result(store.record_dose(payload.senior_id, payload.med_id, payload.time, payload.status))


@app.get("/api/senior/contacts")
def device_contacts(senior_id: str, request: Request):
    _own(request, senior_id)
    s = _senior_obj(senior_id)
    coord = store.coordinators.get(s.get("coordinator_code"), {})
    return {"care_manager": {"name": coord.get("name", s.get("coordinator_name", "")), "phone": coord.get("phone", "")},
            "contacts": store.list_contacts(senior_id)}


async def _notify_phone(senior_id: str, event: str) -> None:
    """Tells the phone (if it is online) to fetch the new list, so alarms change without waiting for a refresh."""
    try:
        await ws_manager.send_to_senior(senior_id, {"event": event})
    except Exception:
        pass


@app.get("/api/calls/history/{senior_id}")
def get_call_history(senior_id: str, request: Request):
    _coord_of_senior(request, senior_id)
    """Returns past AI call transcripts and outcomes for a senior."""
    return store.get_call_history(senior_id)

@app.get("/api/calls/active-seniors")
def get_active_seniors(request: Request):
    p = who(request, "coordinator")
    """Returns list of seniors currently connected via WebSocket."""
    return {
        "online_seniors": [sid for sid in ws_manager.active_sockets
                           if (store.dynamic_seniors.get(sid) or store.seniors_map.get(sid) or {}).get("coordinator_code") == p.sub],
        "online_count": sum(1 for sid in ws_manager.active_sockets
                            if (store.dynamic_seniors.get(sid) or store.seniors_map.get(sid) or {}).get("coordinator_code") == p.sub)
    }

@app.get("/api/calls/voice-audio")
async def get_voice_audio(request: Request, text: str, voice: Optional[str] = "hi-IN-MadhurNeural"):
    who(request, "senior", "coordinator", "family")
    """
    Synthesizes and streams spoken voice audio via Edge-TTS (100% Free / Zero API keys).
    Bounded input size to prevent abuse.
    """
    clean_text = text.strip()
    if not clean_text or len(clean_text) > 350:
        raise HTTPException(status_code=400, detail="Text must be between 1 and 350 characters.")

    allowed_voices = ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural", "en-IN-PrabhatNeural", "en-IN-NeerjaNeural"]
    selected_voice = voice if voice in allowed_voices else "hi-IN-MadhurNeural"

    try:
        audio = await tts_audio(clean_text, selected_voice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return Response(content=audio, media_type="audio/mpeg")


# -------------------------------------------------------------
# Sign-in, consent, family, operations, phone gateway
# -------------------------------------------------------------
class LoginRequest(BaseModel):
    role: str                  # coordinator | ops | family
    id: str                    # coordinator code | OPS-1 | family code
    secret: Optional[str] = "" # PIN (coordinator / ops)

class ConsentRequest(BaseModel):
    consent: bool

class MissedCallRequest(BaseModel):
    from_number: str
    kind: Optional[str] = ""       # "sos" when the gateway's SOS number was called; else the "I am fine" number

MISSED_CALL_SOS_WINDOW_S = 120

from build_stamp import build_stamp

BUILD = build_stamp()

@app.middleware("http")
async def no_stale_pages(request: Request, call_next):
    """Portals must never run an old copy (phones behind a tunnel cache aggressively)."""
    resp = await call_next(request)
    path = request.url.path
    if path == "/" or path in ("/family", "/phone") or (path.startswith("/static/") and not path.startswith("/static/fonts/")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp

@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE, "build": BUILD,
            "llm": {"on": LLM.enabled, "provider": "groq" if LLM.enabled else None}}

@app.post("/api/auth/login")
def login(payload: LoginRequest):
    role = payload.role.lower()
    if role in ("coordinator", "ops"):
        ident = payload.id.strip().upper()
        if not auth.check_pin(CREDS, role, ident, payload.secret or ""):
            store.audit(role, ident, "login_failed")
            raise HTTPException(status_code=401, detail="Wrong code or PIN")
        if role == "coordinator" and billing.active(ident) is False:
            raise HTTPException(status_code=402, detail="Your subscription has ended. Renew it on the website to continue.")
        store.audit(role, ident, "login")
        info = store.get_coordinator(ident) if role == "coordinator" else {"name": "Operations", "code": ident}
        return {"token": auth.issue_session(role, ident), "role": role, "code": ident, "name": info["name"],
                "city": (info or {}).get("city")}
    if role == "family":
        senior = store.find_by_family_code(payload.id)
        if not senior:
            store.audit("family", payload.id.strip().upper(), "login_failed")
            raise HTTPException(status_code=401, detail="Family code not valid, or sharing was switched off")
        code = payload.id.strip().upper()
        store.audit("family", code, "login", senior["senior_id"])
        return {"token": auth.issue_session("family", code, scope=senior["senior_id"]), "role": "family",
                "code": code, "name": senior["name"], "senior_id": senior["senior_id"]}
    raise HTTPException(status_code=400, detail="Unknown role")

@app.get("/api/auth/me")
def whoami(request: Request):
    p = who(request)
    return {"role": p.role, "sub": p.sub, "scope": p.scope}

@app.get("/api/auth/demo")
def demo_logins():
    """Judges' convenience: lists the sign-ins when DEMO MODE is on. Hidden in production."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not available")
    return {
        "coordinators": [{"code": c, "name": store.coordinators[c]["name"], "pin": pin}
                         for c, pin in CREDS["coordinators"].items() if billing.active(c) is None],
        "ops": [{"code": c, "pin": pin} for c, pin in CREDS["ops"].items()],
    }

@app.get("/api/auth/demo-seniors")
def demo_seniors(code: str):
    """Demo only: names of one team's seniors so the phone simulator can pick whose phone to play."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not available")
    rows = [s for s in list(store.dynamic_seniors.values()) + list(store.seniors_map.values())
            if s.get("coordinator_code") == code.upper()]
    rows.sort(key=lambda s: (not s.get("is_dynamic"), s["name"]))
    return [{"senior_id": s["senior_id"], "name": s["name"], "is_dynamic": bool(s.get("is_dynamic"))} for s in rows[:60]]

@app.get("/api/auth/dev-device-key")
def dev_device_key(senior_id: str):
    """Demo only: lets the browser phone simulator act as a senior's phone."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not available")
    _senior_obj(senior_id)
    return {"device_key": auth.issue_device_key(senior_id)}

@app.post("/api/senior/family-consent")
def family_consent(payload: ConsentRequest, request: Request):
    """The senior (not the coordinator) decides whether family may see a weekly summary."""
    p = who(request, "senior")
    res = store.set_family_consent(p.sub, payload.consent)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.get("/api/family/overview")
def family_overview(request: Request):
    p = who(request, "family")
    senior = store.find_by_family_code(p.sub)       # consent is re-checked on EVERY request
    if not senior:
        raise HTTPException(status_code=403, detail="Sharing was switched off by the senior")
    store.audit("family", p.sub, "view_summary", senior["senior_id"])
    return store.family_overview(senior["senior_id"])

@app.get("/api/family/summary/{senior_id}")
def get_family_summary(senior_id: str, request: Request):
    """Coordinators may preview what the family sees; family may only read their own senior."""
    p = who(request, "coordinator", "family")
    s = _senior_obj(senior_id)
    if p.role == "coordinator" and s.get("coordinator_code") != p.sub:
        raise HTTPException(status_code=403, detail="Not your team")
    if p.role == "family" and (p.scope != senior_id or not s.get("family_sharing_consent")):
        raise HTTPException(status_code=403, detail="Not shared with you")
    return store.family_overview(senior_id)

@app.get("/api/ops/overview")
def ops_overview(request: Request):
    """Aggregated volumes, response times, outcomes and model quality. No individual health records."""
    p = who(request, "ops")
    store.audit("ops", p.sub, "view_overview")
    return store.ops_overview()

@app.get("/api/ops/metrics")
def get_ops_metrics(request: Request):
    who(request, "ops", "coordinator")
    return store.eval_metrics

_replay_cases: List[Dict[str, Any]] = []

@app.get("/api/replay/cases")
def replay_cases(request: Request):
    """The simulated decline cases, for "Watch Saathi catch a decline"."""
    who(request, "ops", "coordinator")
    if not _replay_cases:
        _replay_cases.extend(replay_engine.cases(store))
    return _replay_cases

@app.get("/api/replay/{senior_id}")
def replay_case(senior_id: str, request: Request):
    who(request, "ops", "coordinator")
    res = replay_engine.replay(store, senior_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.get("/api/ops/audit")
def ops_audit(request: Request, limit: int = 100):
    who(request, "ops")
    return list(reversed(store.audit_log[-min(limit, 500):]))

@app.post("/api/gateway/missed-call")
def gateway_missed_call(payload: MissedCallRequest, request: Request):
    """
    No-app check-in. A phone/SIM gateway forwards the number of anyone who gives the 'I am fine' missed
    call; the key is the gateway's secret (data/auth.json -> gateway_key).
    """
    if request.headers.get("x-gateway-key") != CREDS.get("gateway_key"):
        raise HTTPException(status_code=401, detail="Bad gateway key")
    senior = store.find_by_phone(payload.from_number)
    if not senior:
        raise HTTPException(status_code=404, detail="Number not registered")
    # missed-call SOS for basic phones: a missed call to the SOS number, or two missed calls within 2 minutes
    now, prev = time.time(), senior.get("last_missed_call_ts") or 0
    senior["last_missed_call_ts"] = now
    if (payload.kind or "").lower() == "sos" or now - prev < MISSED_CALL_SOS_WINDOW_S:
        senior["last_missed_call_ts"] = 0
        store.save()
        res = dispatcher.raise_emergency(senior["senior_id"], "missed_call")
        return {"status": "sos", "senior": senior["name"], "family_ai_call": res.get("family_ai_call", False)}
    store.record_checkin(senior["senior_id"], "missed_call", "good", None)
    return {"status": "ok", "senior": senior["name"]}

@app.post("/api/ops/sweep-missed-checkins")
def sweep_missed(request: Request):
    who(request, "ops")
    return {"marked_missed": store.sweep_missed_checkins()}

# Mount static directory for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/family")
def serve_family():
    with open(os.path.join(static_dir, "family.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/phone")
def serve_phone():
    """Senior phone simulator for testing the AI voice call end to end."""
    with open(os.path.join(static_dir, "phone.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# -------------------------------------------------------------
# Subscriptions (Razorpay, test keys only for now)
# -------------------------------------------------------------
class OrderRequest(BaseModel):
    plan: str
    name: str                      # the family member who pays
    email: str
    phone: str
    elder_name: str                # the parent Saathi will look after
    elder_city: str
    elder_language: Optional[str] = "hi"


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@app.get("/api/billing/config")
def billing_config():
    return billing.config()


@app.post("/api/billing/order")
def billing_order(payload: OrderRequest):
    res = billing.create_order(payload.plan, payload.dict())
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@app.post("/api/billing/verify")
def billing_verify(payload: VerifyRequest):
    res = billing.verify(payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    store.audit("billing", res["saathi_code"], "subscribed", f'{res["plan"]} -> {res["coordinator_code"]}')
    return res


def _page(name: str) -> HTMLResponse:
    with open(os.path.join(static_dir, name), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/subscribe")
def serve_subscribe():
    return _page("subscribe.html")


@app.get("/portal")
def serve_portal():
    return _page("index.html")


@app.get("/")
def serve_index():
    index_file = os.path.join(static_dir, "landing.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Aegis Saathi Backend Running</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
