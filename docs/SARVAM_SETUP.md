# Sarvam Voice Agents setup

Saathi uses two Sarvam agents:

| Agent | What it does | Needs a phone number? |
|---|---|---|
| **Saathi check-in** | **Rings the senior's own phone number** for the daily check-in, so any phone works, even a basic one, and no app is needed. | Yes |
| **Saathi alert** | Rings the emergency contacts when the senior is in danger and tells them what happened. | Yes (the same number) |

**Which way calls go:**
- **Phone calls (default):** used once `SARVAM_CHECKIN_APP_ID`, `SARVAM_CHECKIN_APP_VERSION`, `SARVAM_CONNECTION_ID` and `SARVAM_AGENT_PHONE` are set and the senior has a phone number on file.
- **Inside the Saathi app:** for seniors with no number on file, or when `AEGIS_CALL_ENGINE=app` is set.
- **The hub's own voice:** if Sarvam isn't set up at all, the hub runs calls with Vosk speech-to-text, then Groq or the rule-based agent, then Edge TTS.

**Emergency fallback:** without the alert agent, an emergency makes the senior's app dial the contact itself after a 10-second countdown.

**Parents with a basic phone** are set up on the website, with no app. After paying, the family taps **Set up daily calls instead**, or opens `/subscribe#phone` later. They enter the Saathi code, the parent's number, a daily call time and their own number as the emergency contact. Saathi then rings that number every day at that time.

## 1. Keys and IDs in `coordinator_hub/.env`

```
SARVAM_API_KEY=            # Voice Agents key: indus.sarvam.ai/samvaad/settings/api-key (not the TTS/STT key)
SARVAM_ORG_ID=01a18b42-3919-7c45-8d74-a2cb93ecb2cd
SARVAM_WORKSPACE_ID=01a18b42-3922-7f59-ac44-a83989bb84af
SARVAM_CHECKIN_APP_ID=     # agent id of "Saathi check-in" (agent menu, Copy ID)
SARVAM_CHECKIN_APP_VERSION=   # committed version number; required for phone calls
SARVAM_ALERT_APP_ID=       # agent id of "Saathi alert"
SARVAM_ALERT_APP_VERSION=  # required for outbound calls
SARVAM_CONNECTION_ID=      # Deploy -> Phone Numbers -> your connection
SARVAM_AGENT_PHONE=        # the number Saathi calls from, e.g. +9180XXXXXXXX
# AEGIS_PUBLIC_URL=https://...   optional; otherwise the tunnel address start.py writes is used
# AEGIS_CALL_ENGINE=app          optional; calls inside the app instead of phone calls (local = the hub's own voice)
```

Then install the SDK and run the check from `coordinator_hub/`:

```bash
pip install sarvam-conv-ai-sdk
```

```bash
python sarvam_check.py
```

### More than one key

Add `SARVAM_API_KEY_2`, `SARVAM_API_KEY_3` … (up to `_10`). Every call picks a key at random. A key whose
account says "Insufficient Balance" is tried last for an hour, so calls keep going on the others.

- **All keys in the same Sarvam account:** add only the keys. Note that they share one balance.
- **A key from a second Sarvam account** (its own 100 credits): also add that account's own IDs with the same
  suffix: `SARVAM_ORG_ID_2`, `SARVAM_WORKSPACE_ID_2`, `SARVAM_CHECKIN_APP_ID_2`, `SARVAM_CHECKIN_APP_VERSION_2`,
  `SARVAM_ALERT_APP_ID_2`, `SARVAM_ALERT_APP_VERSION_2`, `SARVAM_CONNECTION_ID_2`, `SARVAM_AGENT_PHONE_2`.
  The second account needs the two agents (sections 2 and 3, incl. the `report_emergency` tool) and, for phone calls,
  its own number. A setting left out falls back to the first account's.

Restart the hub after editing `.env`. `/api/voice/status` shows `keys` and `keys_with_credit`.

### Smartphone or basic phone

On the senior's page in the care portal, **How Saathi calls** sets:

- **Smartphone (in app)**, the default: when the Saathi app is online the call rings inside the app (no phone
  charges); when it is offline Saathi rings their number.
- **Basic phone (normal call)**: always a normal call to their number.

When every key is out of credit, a phone call moves into the app if the app is online; a basic phone with no app
then misses the call and the portal says why.

### Other Indian languages

The care portal's **Language Saathi speaks** can be set to Hindi, English, Bengali, Gujarati, Kannada, Malayalam,
Marathi, Odia, Punjabi, Tamil or Telugu. Switch the same languages on in **both** agents' language settings in
Sarvam (then commit). Calls in the hub's own voice stay Hindi/English, so the other languages need a Sarvam call.

### Family voice messages

Nothing to set up. On a phone call, Saathi passes the family's message on in words through `memory_note`, which
the check-in agent already uses. In the app, the family's real recording plays before the agent speaks.

## 2. Agent "Saathi check-in"

In the Sarvam canvas, wherever `{{name}}` appears below, type `@` and pick that variable instead.

**Input variables:**
- `senior_first_name`
- `gender`
- `language`
- `health_summary`
- `memory_note`
- `todays_medicines`
- `care_manager_name`
- `reason_for_call` (usually "Daily check-in call."; after a worrying voice note it says what they said)
- `senior_id` and `call_id`: turn off **Send to LLM** for these two; they are only for the emergency tool

**Languages:** Hindi and English. Choose a warm female voice at a slightly slower speed.

**Greeting:** `Namaste {{senior_first_name}} ji, main Saathi bol rahi hoon. Aaj aap kaisa mehsoos kar rahe hain?`

**Instructions:**

> You are Saathi, a warm companion from Samarth who calls {{senior_first_name}} (a {{gender}} senior) every day. Speak {{language}} (Hindi in Devanagari-friendly simple words, or simple Indian English). Keep every turn to one or two short sentences and ask one question at a time.
> Cover gently, in a natural order: how they feel today, sleep, food, today's medicines ({{todays_medicines}}), and anything on their mind. Why you are calling: {{reason_for_call}}. Use what you know: {{health_summary}} and from last time: {{memory_note}}. Listen to worries and loneliness before moving on.
> Never diagnose, never name or change medicines or doses, never promise a visit. For anything medical say their care manager {{care_manager_name}} will follow up today. Encouragement only for everyday things (a short walk, water, meals, sleep routine, calling family), and none if they mention dizziness, pain, a fall or breathlessness.
> EMERGENCY: if they say they are dying, can't breathe, have chest pain, fell and can't get up, or need urgent help, first call tool:report_emergency, then say once, calmly: "I am getting help right now. Your care manager and your family are being called. If you can, please call 112." Then stay with them, keep them calm, and ask them not to move if they fell.
> End warmly when they are done, with one encouraging line.

**Tool `report_emergency`** (an API tool, run "During conversation"):
- **Description:** "Call immediately when the person says they are dying, cannot breathe, have chest pain, fell, or need urgent help."
- **Method and URL:** POST to the URL in `coordinator_hub/data/sarvam_tool_url.txt`. The hub writes that file at start. It holds a secret, so open the file and copy the URL from it.
- **Body (JSON):**
  - `call_id`: `@call_id`
  - `senior_id`: `@senior_id`
  - `transcript`: `@Call Transcript`
- **Max wait:** 5 s.
- **If it fails:** keep the same calm line.

The hub raises the SOS and the family call the moment this tool runs. If it doesn't fire, the hub still checks the transcript right after the call.

**Keep the tunnel address in mind.** A free `trycloudflare.com` tunnel gets a new address every time `start.py` restarts it. When that happens, paste the new URL from the file into the tool again. To avoid this, use a fixed address: put your free ngrok static domain in `AEGIS_PUBLIC_URL` and `ngrok.exe` in `tools/`, and `start.py` uses it every time (see the top of `start.py`). An always-on server is better still.

Commit a version and put its ID and version number in `SARVAM_CHECKIN_APP_ID` and `SARVAM_CHECKIN_APP_VERSION`.

## 3. Agent "Saathi alert"

**Input variables:**
- `senior_name`
- `her_his`
- `she_he`
- `contact_name`
- `relation`
- `what_they_said`
- `how_it_came`
- `time_text`
- `care_manager_name`
- `care_manager_phone`
- `location_known`

**Output variable:** `acknowledged`, a string with the extraction prompt *"What the person said they will do (for example 'going now', 'will call her', 'cannot go')."*

**Greeting:** `Hello, this is Saathi from Samarth Care, calling about {{senior_name}}. This is urgent.`

**Instructions:**

> You are calling {{contact_name}}, the {{relation}} of {{senior_name}}, because {{she_he}} may be in danger. Speak calmly, clearly and slowly, in the language the person answers in.
> Tell them: at {{time_text}}, {{senior_name}} said "{{what_they_said}}" {{how_it_came}}. {{her_his}} care manager {{care_manager_name}} has been alerted. Ask them to call {{senior_name}} or go to {{her_his}} home right now, and if they cannot reach {{her_his}}, to call 112 immediately.
> Then ask: "Will you go to {{her_his}} or call {{her_his}} now?" Note the answer. Repeat the key message once if they seem confused. If they ask, the care manager's number is {{care_manager_phone}}.
> Do not diagnose or guess what is wrong. Keep the call under one minute and end it once they have the message.

Commit a version and put the agent ID and version in `SARVAM_ALERT_APP_ID` and `SARVAM_ALERT_APP_VERSION`.

## 4. A number for calls

1. In Sarvam, go to **Deploy, then Phone Numbers**. Either **Rent from Sarvam** (KYC first, about ₹59 per 30 days) or connect Plivo, Exotel or Twilio.
2. Copy the connection ID into `SARVAM_CONNECTION_ID` and the number into `SARVAM_AGENT_PHONE`.
3. Place one test call to your own phone:

```bash
python sarvam_check.py --alert +9198XXXXXXXX
```

**Webhook:** the hub tells Sarvam where to report each call's outcome. That address is `AEGIS_PUBLIC_URL` (or the tunnel from `start.py`) plus `/api/sarvam/webhook` and a secret, so the hub must be reachable from the internet while alerts are on.

## What happens in an emergency

1. **Detection.** The senior says something like "I am dying", "मैं मर रहा हूँ", "saans nahi aa rahi" or "chest pain". It can come:
   - on a phone call (the agent's `report_emergency` tool, with the transcript checked after the call as a backup);
   - in a voice note;
   - by holding SOS;
   - when a fall screen goes unanswered.
2. **SOS.** The hub opens an SOS. It is red on the care manager's portal and shows what they said.
3. **Phone screen.** If the senior has the app, it shows **Help is coming**, with buttons to call the contact or 112.
4. **Alert calls.** The Saathi alert agent rings the emergency contacts in order: those marked as emergency contacts in the portal, then the number from setup.
   - No answer, busy or failed: it rings the next contact.
   - After the last one, it waits 2 minutes and tries one more round.
   - Every attempt shows on the SOS bar.
5. **Fallback.** If nobody is reached, or no number is configured, the phone dials the first contact itself.

**What doesn't count:** idioms like "dying to see my grandson" or "bore hoke mar gaya". Saying it again within 10 minutes doesn't start a second round. "I'm safe, cancel" (within 2 minutes) stops calls that haven't been placed yet.
