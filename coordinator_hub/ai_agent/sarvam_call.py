"""
The in-app Saathi call, spoken by a Sarvam Voice Agent. The hub sits in the middle so the API key never reaches
the phone:

   phone  --16 kHz PCM-->  hub  --send_audio-->  Sarvam agent
   phone  <--PCM + captions--  hub  <--audio/transcript callbacks--  Sarvam agent

Every line the senior says is appended to the same conversation object the local engine uses, so the call record,
the live portal view, the NLP, the risk score and the after-call notes work unchanged. Danger words ("I am dying")
are caught here by our own rules, whatever the agent replies.
"""
import base64
from typing import Any, Awaitable, Callable, Dict, Optional

from pydantic import SecretStr

try:
    from engine.sarvam_api import POOL, language_name
except ImportError:  # pragma: no cover
    from ..engine.sarvam_api import POOL, language_name



def agent_variables(senior: Dict[str, Any], context: Dict[str, str], medicines: str) -> Dict[str, Any]:
    """What the check-in agent knows. First name only; no IDs, numbers or addresses."""
    first = (senior.get("name") or "").split()[0] if senior.get("name") else ""
    cm = (senior.get("coordinator_name") or "").split()[0] if senior.get("coordinator_name") else ""
    return {
        "senior_first_name": first,
        "gender": str(senior.get("gender") or ""),
        "language": language_name(senior.get("language")),
        "health_summary": (context.get("health") or "Nothing notable recorded.")[:900],
        "memory_note": (context.get("memory") or "No earlier calls.")[:500],
        "todays_medicines": medicines or "None listed.",
        "care_manager_name": cm or "your care manager",
    }


class SarvamCallBridge:
    """One live call. `send_json` / `send_bytes` go to the phone's socket."""

    def __init__(self, call_id: str, senior: Dict[str, Any], variables: Dict[str, Any],
                 send_json: Callable[[dict], Awaitable[None]], send_bytes: Callable[[bytes], Awaitable[None]],
                 on_line: Callable[[str, str], None]):
        self.call_id = call_id
        self.senior = senior
        self.variables = variables
        self.send_json = send_json
        self.send_bytes = send_bytes
        self.on_line = on_line              # (speaker "senior" | "ai", text): record it, check for danger
        self.agent = None
        self.ended = False
        self.out_rate: Optional[int] = None
        self.interaction_id: Optional[str] = None
        self.account = ""                   # which Sarvam key ran the call
        self.close_reason = ""              # Sarvam's close code and reason, when it hangs up

    async def start(self, timeout: float = 5.0) -> bool:
        """Connects with a randomly picked key; a key that cannot connect (often: out of credit) hands over to the
        next. False when none can: the caller runs the call on the hub's own voice instead."""
        for c in POOL.order():
            try:
                if await self._start_with(c, timeout):
                    POOL.mark(c, True)
                    self.account = c.name
                    return True
            except Exception as e:
                print(f"[Sarvam] key {c.name} could not start the call: {type(e).__name__}: {str(e)[:120]}")
            POOL.mark(c, False)
        return False

    async def _start_with(self, c, timeout: float) -> bool:
        from sarvam_conv_ai_sdk import AsyncSamvaadAgent, InteractionConfig, InteractionType
        from sarvam_conv_ai_sdk.messages.types import UserIdentifierType
        lang = language_name(self.senior.get("language"))
        config = InteractionConfig(
            user_identifier_type=UserIdentifierType.CUSTOM,
            user_identifier=self.senior["senior_id"],          # our ID, never the phone number
            org_id=c.org_id, workspace_id=c.workspace_id, app_id=c.checkin_app,
            version=c.checkin_version,
            interaction_type=InteractionType.CALL,
            sample_rate=16000,
            agent_variables=self.variables,
            initial_language_name=lang,
        )
        self.agent = AsyncSamvaadAgent(api_key=SecretStr(c.api_key), config=config,
                                       audio_callback=self._audio, transcript_callback=self._transcript,
                                       event_callback=self._event)
        await self.agent.start()
        ok = await self.agent.wait_for_connect(timeout=timeout)
        if not ok:
            await self.stop()
        else:
            self._watch_close()
        return bool(ok)

    def _watch_close(self) -> None:
        """The SDK drops Sarvam's close code and reason; keep them so the hub log says why a call was cut."""
        ws = getattr(self.agent, "_ws", None)
        if ws is None:
            return
        recv = ws.recv

        async def watched(*a, **k):
            try:
                return await recv(*a, **k)
            except Exception as e:
                frame = getattr(e, "rcvd", None)
                self.close_reason = f"{getattr(frame, 'code', '?')} {getattr(frame, 'reason', '') or type(e).__name__}"
                raise
        ws.recv = watched

    async def feed(self, pcm: bytes) -> None:
        if self.agent and not self.ended:
            try:
                await self.agent.send_audio(pcm)
            except Exception:
                # Sarvam hung up on its side: end the call on the phone instead of streaming into nothing
                self.ended = True
                print(f"[Sarvam] call {self.call_id} closed by Sarvam: {self.close_reason or 'no reason given'}")
                await self.send_json({"type": "end"})

    async def stop(self) -> None:
        if self.agent:
            try:
                self.interaction_id = self.agent.get_interaction_id()
                await self.agent.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------ Sarvam -> phone
    async def _audio(self, msg) -> None:
        if not msg.audio_base64:
            return
        rate = int(msg.sample_rate or 16000)
        if rate != self.out_rate:                        # tell the phone before the first chunk at a new rate
            self.out_rate = rate
            print(f"[Sarvam] call {self.call_id}: agent audio at {rate} Hz")
            await self.send_json({"type": "audio_format", "sample_rate": rate, "encoding": "pcm16"})
        await self.send_bytes(base64.b64decode(msg.audio_base64))

    async def _transcript(self, msg) -> None:
        speaker = "senior" if str(msg.role) == "user" else "ai"
        text = (msg.content or "").strip()
        if not text:
            return
        self.on_line(speaker, text)
        await self.send_json({"type": "caption", "speaker": speaker, "text": text})

    async def _event(self, event) -> None:
        kind = str(getattr(event, "type", ""))
        if kind == "server.event.user_interrupt":
            await self.send_json({"type": "interrupt"})          # stop playback: the senior is talking
        elif kind == "server.action.interaction_end":
            detail = {k: v for k, v in (event.model_dump() if hasattr(event, "model_dump") else {}).items()
                      if k not in ("type", "agent_variables")}
            print(f"[Sarvam] call {self.call_id}: Sarvam ended the interaction {str(detail)[:200]}")
            self.ended = True
            await self.send_json({"type": "end"})
