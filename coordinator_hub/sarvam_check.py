"""
Checks the Sarvam Voice Agents setup in coordinator_hub/.env without printing any key.

  python sarvam_check.py                       settings, then opens and closes one session with the check-in agent
  python sarvam_check.py --alert +9198XXXXXXXX  also places ONE real "Saathi alert" test call to that number

See docs/SARVAM_SETUP.md.
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ai_agent.llm_agent import load_env  # noqa: E402

load_env(os.path.join(HERE, ".env"))
from engine.sarvam_api import CONFIG, SarvamClient, public_url  # noqa: E402


def line(ok: bool, text: str) -> None:
    print(("  OK   " if ok else "  --   ") + text)


async def try_session() -> bool:
    from pydantic import SecretStr
    from sarvam_conv_ai_sdk import AsyncSamvaadAgent, InteractionConfig, InteractionType
    from sarvam_conv_ai_sdk.messages.types import UserIdentifierType
    heard = []

    async def transcript(msg):
        heard.append(msg.content)

    cfg = InteractionConfig(user_identifier_type=UserIdentifierType.CUSTOM, user_identifier="setup-check",
                            org_id=CONFIG.org_id, workspace_id=CONFIG.workspace_id, app_id=CONFIG.checkin_app,
                            version=CONFIG.checkin_version, interaction_type=InteractionType.CALL, sample_rate=16000,
                            agent_variables={"senior_first_name": "Kamla", "gender": "Female", "language": "English",
                                             "health_summary": "Nothing notable recorded.", "memory_note": "No earlier calls.",
                                             "todays_medicines": "None listed.", "care_manager_name": "Rajesh"})
    agent = AsyncSamvaadAgent(api_key=SecretStr(CONFIG.api_key), config=cfg, transcript_callback=transcript)
    try:
        await agent.start()
        ok = await agent.wait_for_connect(timeout=8.0)
        if ok:
            await asyncio.sleep(4)            # let the greeting arrive
        return bool(ok)
    finally:
        await agent.stop()
        if heard:
            print("       agent said: " + heard[0][:120])


def main() -> int:
    print("Sarvam Voice Agents")
    line(bool(CONFIG.api_key), "SARVAM_API_KEY set")
    line(bool(CONFIG.org_id and CONFIG.workspace_id), "SARVAM_ORG_ID and SARVAM_WORKSPACE_ID set")
    line(bool(CONFIG.checkin_app), "SARVAM_CHECKIN_APP_ID set (check-in agent)")
    line(CONFIG.checkin_version is not None, "SARVAM_CHECKIN_APP_VERSION set (needed for daily phone calls)")
    line(CONFIG.alert_app != "" and CONFIG.alert_version is not None, "SARVAM_ALERT_APP_ID and _VERSION set (family alert)")
    line(bool(CONFIG.connection_id and CONFIG.agent_phone), "SARVAM_CONNECTION_ID and SARVAM_AGENT_PHONE set (needed for phone and alert calls)")
    line(bool(public_url()), f"public URL for webhooks: {public_url() or 'none (set AEGIS_PUBLIC_URL or run start.py)'}")
    print(f"  calls: {CONFIG.status()['calls']} | family alert calls: {CONFIG.status()['family_alert_calls']}")
    line(os.path.exists(os.path.join(HERE, "data", "sarvam_tool_url.txt")),
         "emergency tool URL in data/sarvam_tool_url.txt (paste into the check-in agent's report_emergency tool)")
    if CONFIG.calls_ready():
        try:
            ok = asyncio.run(try_session())
            line(ok, "check-in agent session opened and closed")
        except Exception as e:
            line(False, f"check-in agent session failed: {type(e).__name__}: {str(e)[:200]}")
            return 1
    if "--alert" in sys.argv:
        to = sys.argv[sys.argv.index("--alert") + 1]
        if not CONFIG.alerts_ready():
            line(False, "alert call skipped: alert agent or number not configured")
            return 1
        attempt = SarvamClient().outbound_call(to, {
            "senior_name": "Kamla Devi (TEST)", "her_his": "her", "she_he": "she", "contact_name": "", "relation": "Daughter",
            "what_they_said": "this is only a test of the alert call", "how_it_came": "in a setup test",
            "time_text": "now", "care_manager_name": "Rajesh Verma", "care_manager_phone": "", "location_known": "no"},
            "English")
        line(True, f"test alert call placed (attempt {attempt})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
