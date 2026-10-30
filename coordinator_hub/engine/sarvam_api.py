"""
Sarvam Voice Agents (Samvaad): settings from .env and the REST calls the hub makes.

  SARVAM_API_KEY                      Voice Agents key (X-API-Key). Separate from Sarvam's TTS/STT keys.
  SARVAM_ORG_ID, SARVAM_WORKSPACE_ID  from the Sarvam dashboard
  SARVAM_CHECKIN_APP_ID / _VERSION    the daily check-in agent (in-app call, ai_agent/sarvam_call.py)
  SARVAM_ALERT_APP_ID / _VERSION      the "Saathi alert" agent that phones the family in an emergency
  SARVAM_CONNECTION_ID, SARVAM_AGENT_PHONE   a Sarvam (or Plivo/Exotel/Twilio) number; needed only for alert calls
  AEGIS_PUBLIC_URL                    where Sarvam can reach the hub for webhooks (else tunnel_url.txt from start.py)

More keys: SARVAM_API_KEY_2, SARVAM_API_KEY_3 ... (up to _10). Each call picks a key at random; a key whose account
says "insufficient balance" is tried last for an hour. Any other setting can carry the same suffix (SARVAM_ORG_ID_2,
SARVAM_CHECKIN_APP_ID_2 ...) when that key belongs to a different Sarvam account; without it the plain setting is used.

The key never leaves the hub: the phone talks to the hub, the hub talks to Sarvam.
"""
import os
import random
import threading
import time
from typing import Any, Dict, List, Optional

import requests

BASE = "https://apps.sarvam.ai/api"
_HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO_CREDIT_SKIP_S = 3600


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _int(value: str) -> Optional[int]:
    try:
        return int(value.lower().lstrip("v"))      # the dashboard shows versions as "v2"
    except ValueError:
        return None


# the languages Sarvam's agents speak (each must be switched on in the agent's language settings)
LANGUAGES = {"hi": "Hindi", "en": "English", "bn": "Bengali", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
             "mr": "Marathi", "od": "Odia", "pa": "Punjabi", "ta": "Tamil", "te": "Telugu"}


def language_name(code: Any) -> str:
    return LANGUAGES.get(str(code or "hi")[:2].lower(), "Hindi")


def no_credit(err: Any) -> bool:
    """Sarvam's answer when the account has run out of credit."""
    return "402" in str(err) or "balance" in str(err).lower()


class SarvamConfig:
    """One Sarvam account. suffix "" reads SARVAM_API_KEY etc.; "_2" reads SARVAM_API_KEY_2, and for every other
    setting SARVAM_..._2 if set, else the plain one."""

    def __init__(self, suffix: str = ""):
        self.suffix = suffix
        self.name = suffix.lstrip("_") or "1"

    def _get(self, name: str) -> str:
        return (_env(name + self.suffix) or _env(name)) if self.suffix else _env(name)

    @property
    def api_key(self) -> str:
        return _env("SARVAM_API_KEY" + self.suffix)

    @property
    def org_id(self) -> str:
        return self._get("SARVAM_ORG_ID")

    @property
    def workspace_id(self) -> str:
        return self._get("SARVAM_WORKSPACE_ID")

    @property
    def checkin_app(self) -> str:
        return self._get("SARVAM_CHECKIN_APP_ID")

    @property
    def checkin_version(self) -> Optional[int]:
        return _int(self._get("SARVAM_CHECKIN_APP_VERSION"))

    @property
    def alert_app(self) -> str:
        return self._get("SARVAM_ALERT_APP_ID")

    @property
    def alert_version(self) -> Optional[int]:
        return _int(self._get("SARVAM_ALERT_APP_VERSION"))

    def _own_account(self) -> bool:
        """A key with its own SARVAM_ORG_ID_n is a separate Sarvam account: the first account's number is not its."""
        return bool(self.suffix and _env("SARVAM_ORG_ID" + self.suffix))

    def _phone_get(self, name: str) -> str:
        return _env(name + self.suffix) if self._own_account() else self._get(name)

    @property
    def connection_id(self) -> str:
        return self._phone_get("SARVAM_CONNECTION_ID")

    @property
    def agent_phone(self) -> str:
        return self._phone_get("SARVAM_AGENT_PHONE")

    def has_phone(self) -> bool:
        """This account can place phone calls; one without a number runs only in-app calls."""
        return bool(self.connection_id and self.agent_phone)

    def base_ready(self) -> bool:
        return bool(self.api_key and self.org_id and self.workspace_id)

    def phone_calls_ready(self) -> bool:
        """Daily check-ins ring the senior's own number (any phone, even a basic one) from the Sarvam number."""
        if _env("AEGIS_CALL_ENGINE").lower() in ("local", "app"):
            return False
        return self.base_ready() and bool(self.checkin_app and self.checkin_version is not None
                                          and self.connection_id and self.agent_phone)

    def calls_ready(self) -> bool:
        """The in-app check-in call can run on Sarvam: set up, and some key still has credit (else the hub's own
        voice runs the call, which costs nothing)."""
        if _env("AEGIS_CALL_ENGINE").lower() == "local":
            return False
        return self.base_ready() and bool(self.checkin_app) and POOL.has_credit()

    def alerts_ready(self) -> bool:
        """The hub can phone the family: needs the alert agent, its version and a number to call from."""
        return self.base_ready() and bool(self.alert_app and self.alert_version is not None
                                          and self.connection_id and self.agent_phone)

    def status(self) -> Dict[str, Any]:
        return {"calls": "phone" if self.phone_calls_ready() else "sarvam_app" if self.calls_ready() else "local",
                "family_alert_calls": "on" if self.alerts_ready() else "off",
                "keys": len(POOL.accounts()), "keys_with_credit": len(POOL.usable()),
                "public_url": bool(public_url())}


class SarvamPool:
    """Every account that has a key. order() is random, with the accounts known to be out of credit last."""

    def __init__(self, base: SarvamConfig):
        self.base = base
        self._empty: Dict[str, float] = {}
        self._lock = threading.Lock()

    def accounts(self) -> List[SarvamConfig]:
        return [a for a in [self.base] + [SarvamConfig(f"_{i}") for i in range(2, 11)] if a.api_key]

    def get(self, name: str = "") -> SarvamConfig:
        return next((a for a in self.accounts() if a.name == str(name or "1")), self.base)

    def _is_empty(self, a: SarvamConfig) -> bool:
        with self._lock:
            return time.time() - self._empty.get(a.name, 0) < NO_CREDIT_SKIP_S

    def usable(self) -> List[SarvamConfig]:
        return [a for a in self.accounts() if not self._is_empty(a)]

    def has_credit(self) -> bool:
        return bool(self.usable())

    def order(self) -> List[SarvamConfig]:
        good, empty = self.usable(), [a for a in self.accounts() if self._is_empty(a)]
        random.shuffle(good)
        return good + empty          # still tried last, so a topped-up account is found again

    def mark(self, a: SarvamConfig, has_credit: bool) -> None:
        with self._lock:
            if has_credit:
                self._empty.pop(a.name, None)
            else:
                self._empty[a.name] = time.time()


CONFIG = SarvamConfig()
POOL = SarvamPool(CONFIG)


def public_url() -> str:
    """The hub's public https address, for Sarvam's webhooks."""
    url = _env("AEGIS_PUBLIC_URL")
    if not url:
        try:
            with open(os.path.join(os.path.dirname(_HUB), "tunnel_url.txt"), encoding="utf-8") as f:
                url = f.read().strip()
        except OSError:
            url = ""
    return url.rstrip("/")


def e164(phone: str) -> str:
    """'98100 12345' or '+91 98100 12345' -> '+919810012345' (Indian numbers when no country code is given)."""
    raw = (phone or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if raw.startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "+91" + digits[1:]
    return "+" + digits


class SarvamClient:
    """The REST side: instant outbound calls and transcripts. Raises on any failure; callers decide what follows."""

    def __init__(self, config: SarvamConfig = CONFIG, timeout: float = 10.0):
        self.config = config
        self.timeout = timeout

    def _accounts(self) -> List[SarvamConfig]:
        return POOL.order() if self.config is CONFIG else [self.config]

    @staticmethod
    def _headers(c: SarvamConfig) -> Dict[str, str]:
        return {"X-API-Key": c.api_key, "Content-Type": "application/json"}

    def outbound_call(self, phone: str, variables: Dict[str, Any], language: str = "English",
                      webhook_url: str = "", metadata: Optional[Dict[str, Any]] = None, agent: str = "alert") -> str:
        """Rings [phone] with the alert agent (or agent="checkin" for the daily call); returns Sarvam's attempt_id.
        Keys are tried in random order; the next one only when an account is out of credit. Accounts without a
        phone number of their own are skipped (they run only in-app calls). The key used goes into
        metadata["acct"], which Sarvam hands back on the webhook. The outcome arrives on the webhook."""
        metadata = metadata if metadata is not None else {}
        last: Optional[Exception] = None
        for c in self._accounts():
            if not c.has_phone():
                continue
            metadata["acct"] = c.name
            try:
                attempt = self._outbound(c, phone, variables, language, webhook_url, metadata, agent)
            except Exception as e:
                if not no_credit(e):
                    raise
                POOL.mark(c, False)
                print(f"[Sarvam] key {c.name} is out of credit; trying the next one")
                last = e
                continue
            POOL.mark(c, True)
            return attempt
        raise last or RuntimeError("sarvam outbound: no account with an API key and a phone number")

    def _outbound(self, c: SarvamConfig, phone: str, variables: Dict[str, Any], language: str,
                  webhook_url: str, metadata: Dict[str, Any], agent: str) -> str:
        app_id, version = (c.checkin_app, c.checkin_version) if agent == "checkin" else (c.alert_app, c.alert_version)
        body: Dict[str, Any] = {
            "app_config": {
                "app_id": app_id,
                "app_version": version,
                "connection_config": {"connection_id": c.connection_id, "agent_phone_number": e164(c.agent_phone)},
                "agent_variables": variables,
                "app_overrides": {"initial_language_name": language},
            },
            "user_config": {"user_phone_number": e164(phone)},
        }
        if webhook_url:
            body["webhook_config"] = {"url": webhook_url, "metadata": metadata}
        url = f"{BASE}/outbounds/v1/orgs/{c.org_id}/workspaces/{c.workspace_id}/outbounds"
        r = requests.post(url, json=body, headers=self._headers(c), timeout=self.timeout)
        if r.status_code >= 300:
            raise RuntimeError(f"sarvam outbound {r.status_code}: {r.text[:300]}")
        return str(r.json()["attempt_id"])

    def transcript(self, app_id: str, interaction_id: str, account: str = "") -> Dict[str, Any]:
        """[account]: the key that placed the call (metadata["acct"] on the webhook)."""
        c = POOL.get(account) if self.config is CONFIG else self.config
        iid = requests.utils.quote(interaction_id, safe="")
        url = f"{BASE}/analytics/v1/{c.org_id}/{c.workspace_id}/{app_id}/transcripts/{iid}"
        r = requests.get(url, headers=self._headers(c), timeout=self.timeout)
        r.raise_for_status()
        return r.json()
