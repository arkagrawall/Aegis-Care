# Aegis Saathi (एजिस साथी)

**An early-warning system that tells a Care Coordinator which senior needs attention today, why, and what to do next, using signals seniors can give without an app.**

Hackathon problem statement DEV_104, Samarth Life Management: *Early Warning for Seniors Living at Home*.

Most decline in older people is gradual: a missed tablet, poorer sleep, eating less, a fall nobody reported, a low mood. Each signal is small. Aegis Saathi compares every senior with **their own normal** (never a population average), fuses vitals, medicines, check-ins and what they say in Hindi, Hinglish or English, and gives the coordinator a ranked list with plain-language reasons and a concrete next step.

| Result on the planted decline cases (synthetic cohort, 250 seniors x 90 days) | Value |
|---|---|
| Recall (planted declines caught before the emergency point) | **100%** (30 of 30) |
| Alert precision | **91%** |
| Median early warning | **9 days** (of a 12-day window) |
| False alarms per coordinator per week | **0.93** |

Full method, the rules-only and ML-only comparison, and the honest caveats are in [docs/WRITEUP.md](docs/WRITEUP.md).

---

## Who it is for

| User | What they get |
|---|---|
| **Care Coordinator** | A ranked daily list. Each alert shows the top reasons (with how much each weighed), the recommended action, 14-day trends, call transcripts, and one-tap follow-up logging. Live SOS banner. |
| **Senior** | Android app in **Hindi or English** with one-tap check-in, medicine, a **voice note**, BP/sugar/weight entry, a smartwatch card, and a safe SOS. Plus an **AI phone call** that listens and talks, with no buttons to press. |
| **Family** | A short, plain-language weekly view with a code the **senior** generates. No scores, no clinical detail. Switching consent off ends access immediately. |
| **Operations manager** | Alert volumes by team and city, SOS outcomes and response time, coordinator actions, AI-call stats, what the feedback loop has learned, model quality, and an access log. Aggregates only; no individual records. |

## What is built (against the brief)

**Core requirements**
1. **Signal ingestion**: vitals (steps, heart rate, SpO2, sleep, **BP, sugar, weight**), medicine logs, free-text and **voice** notes, check-ins, watch data over Bluetooth LE.
2. **Unstructured understanding**: Hindi, Hinglish, English and Devanagari cue extraction (pain, dizziness, weakness, sleep, appetite, **confusion**, loneliness, fever, falls, missed medicine) with negation handling. F1 = 1.0 on a 58-sentence labelled set (optimistic; see caveats).
3. **Risk scoring**: rules + personal-baseline drift **plus two ML models** (Isolation Forest anomaly detector and an explainable logistic regression), cross-fitted by senior.
4. **Explainable action**: every alert lists its top reasons in English and Hindi, with points, and a recommended next step; sorted by urgency.

**Stretch goals delivered**: Hindi/English **voice check-in bot that calls the senior** and logs answers; **coordinator feedback loop** that re-weights reasons; **missed-dose and low-adherence** flags; weekly **family summary**; inactivity and activity-decline detection from steps.
**Not built**: an LLM-written family summary. Phone fall detection and the Da Fit decoder exist but are unproven on real devices (see below).

**Constraints, and how each is met**

| Constraint | Approach |
|---|---|
| Not a diagnosis tool | Wording says what changed and what to do; never names a condition. Family sees no scores. See [Privacy and safety](#privacy-and-safety). |
| Low-tech seniors | Voice call that needs no taps, missed-call check-in endpoint for basic phones, big-button Hindi-first app. |
| Alert fatigue | Two-day corroboration, data-quality suppression (watch off-wrist), ML weight capped, SOS safeguards, feedback loop, measured false-alarm rate. |
| Privacy | Roles, team scoping, consent for family, audit log, names masked before text leaves for the voice service, speech recognition runs locally. |
| Low cost | CPU-only. Speech is recognised while the senior is still talking; after they stop, the server needs about 50 ms to have the reply text and voice ready (measured on a laptop, `coordinator_hub/tests/bench_call.py`). See [docs/BUSINESS_MODEL.md](docs/BUSINESS_MODEL.md). |

## Architecture

```
  Senior (Android, Hindi/English)              Basic phone              Family
  - check-in / medicine / voice note           - missed-call            /family
  - AI call (listens + talks)                  - AI call
  - watch (BLE) + readings                          |
  - SOS (hold + countdown + undo)                   |  gateway
        |  device key                               |
        v                                           v
  +-------------------------------------------------------------------------+
  |                      FastAPI hub (coordinator_hub/)                      |
  |  auth + roles + audit  |  ingestion  |  voice agent  |  JSON store      |
  |                                                                         |
  |  Vosk STT (hi/en, local) -> agent state machine -> Edge-TTS (masked)     |
  |                                                                         |
  |  per-senior baseline -> rule factors ---+                               |
  |  NLP cue extractor ---------------------+--> hybrid scorer --> tier,    |
  |  medicine adherence --------------------+     score, reasons, action   |
  |  ML: Isolation Forest + logistic reg ---+            ^                  |
  |                                          feedback weights (learned)      |
  +-------------------------------------------------------------------------+
        |                    |                         |
        v                    v                         v
  Care portal (/)      Operations view          Family view (/family)
  queue, detail,       volumes, outcomes,       weekly summary,
  live call, SOS       model quality, audit     consent-gated
```

## Run it

Needs Python 3.10+ (tested on 3.13). No GPU, no cloud account.

```bash
pip install -r coordinator_hub/requirements.txt
python coordinator_hub/download_models.py      # one-time, ~80 MB of Vosk speech models
python run.py          # or:  python start.py   (hub + free public tunnel, restarts a stale hub, prints LAN/emulator addresses)
```

The first start trains and evaluates the models (about a minute). Then:

| URL | What |
|---|---|
| `http://localhost:8000/` | Care portal. Demo logins are listed on the sign-in page (random PINs created on first run, stored in `coordinator_hub/data/`). Set `AEGIS_DEMO_MODE=0` to hide them. |
| `http://localhost:8000/family` | Family view (needs a code a senior generated in the app) |
| `http://localhost:8000/phone` | Browser phone simulator for the AI voice call |

**Android app** (`android_app/`): open in Android Studio and run. In the app, menu (three dots) -> *Server settings* to point at the server (for another network use a tunnel, e.g. `powershell .\start_tunnel.ps1`, then paste the https address). The language switch is at the top of every screen.

**AI conversation (optional, free)**: put a [Groq](https://console.groq.com/keys) API key in `coordinator_hub/.env` (`GROQ_API_KEY=...`; the file is git-ignored) and restart. Saathi then holds a real conversation with a language model: she reacts to what the senior says, stays with feelings like loneliness, brings up changes in their own health ("you've been walking less this week, how are your legs?"), remembers what was said in earlier calls and closes with a fitting, gentle encouragement. Emergencies, "I want a person" and falls are still handled instantly by fixed rules, medicine advice is filtered out, and if the model is slow or unavailable the built-in conversation takes over for that turn. After each call the model writes the care manager's notes (summary, mood, concerns) shown on the portal. Without a key the built-in conversation runs.

**Tests** (run from `coordinator_hub/`): `python tests/test_access_control.py` (27 role, consent, SOS, feedback and masking checks), `python tests/test_agent.py` (built-in conversations in Hindi, Hinglish, English), `python tests/test_llm_agent.py` (AI conversation plumbing with a fake model: safety gate, fallback, filters), `python tests/sim_calls.py` (real Groq calls against simulated seniors; needs the key), `python -m engine.nlp_eval` (58-sentence cue test). The full cohort evaluation also runs on every start.

## Five-minute demo

See [docs/PITCH_AND_DEMO.md](docs/PITCH_AND_DEMO.md) for the click-by-click script and likely questions.

## Privacy and safety

- **Roles**: senior phone (per-device key), coordinator (code + PIN), family (code from the senior), operations. Coordinators see only their own team; operations see aggregates only. Every view of an individual is written to an audit log.
- **Consent**: the senior consents to care-team access at setup and separately decides on family sharing. Revoking it invalidates family logins on the next request.
- **No external exposure of identity**: speech recognition is local (Vosk). The neural voice gets text with the senior's name and any phone number removed. With the optional AI conversation, the call's words, the senior's first name and a plain-language health summary are sent to Groq; no IDs, phone numbers or addresses. A production deployment needs a data-processing agreement with the provider or a self-hosted model.
- **AI conversation guardrails**: fixed rules answer emergencies and falls before the model is asked; the model may not diagnose, name medicines or doses, or promise visits; a filter replaces any medicine advice and flags it for the care manager; encouragement is limited to everyday things (a gentle walk, water, regular meals, sleep routine, calling family) and is withheld when the senior mentions dizziness, pain, a fall or breathlessness.
- **Not a diagnosis tool**: the system flags risk and routes to a human. Reasons describe *changes from the person's own normal*. The family view shows no scores.
- **SOS safeguards**: 3-second hold on a small button, 5-second cancellable countdown, 30-second "pressed by mistake" undo, duplicate presses merged, alert stays active until a coordinator confirms or closes it.

## Honest limitations

- All results are on **synthetic data**. They show the method works on a controlled cohort, not on real patients. No public dataset (e.g. PhysioNet) was used for validation yet.
- 30 planted cases is small; treat percentages as indicative. The ML weight was tuned on the same cohort, so the combined score is optimistic.
- **Da Fit / Moyoung watches**: the app connects, reconnects and reads standard heart-rate and battery services, plus an **experimental** decoder for the Moyoung vendor protocol (steps, heart rate, SpO2), written from the public Gadgetbridge documentation and unit-tested on hand-built packets (`android_app/tools/MoyoungDecoderTest.kt`). It has **not been tried on a physical band**; decoded values are range-checked and the raw packets stay in the log.
- **Phone fall detection** (opt-in, ⋮ menu): accelerometer analysed on the phone (impact, then stillness) opens a 30-second "Did you fall?" screen; "I'm OK" sends nothing, "I fell but I'm OK" flags a possible fall for a human, "I need help" or no answer raises a tracked SOS. On simulated traces (`android_app/tools/FallDetectorSim.kt`, 300 runs each) it triggers on 100% of falls and 0% of walking, jogging, sitting hard, lying down and stumbles, 2% on vehicle bumps; a dropped phone does trigger, which the confirmation screen absorbs. Traces are synthetic; validation on SisFall/MobiAct and a pilot is next. A built-in Demo watch is clearly labelled and flagged as demo on the portal.
- Voice quality depends on the microphone and room; Vosk small models are fast but less accurate than larger ones. A typed-reply fallback exists.
- The neural voice uses an unofficial endpoint. Production should use a local or licensed Indian-language TTS.
- Auth is prototype-grade (signed tokens, random PINs). Production needs a real identity provider, encryption at rest and a legal review.

## Repository map

```
run.py                       start the hub
coordinator_hub/
  server.py                  API, auth, WebSocket signalling
  engine/                    baseline_drift, hybrid_scorer, ml_model, evaluation, nlp_extractor,
                             nlp_eval, cohort_generator, coordinator_store, stt, auth
  ai_agent/voice_agent.py    Hindi/English check-in conversation
  static/                    care portal, family view, phone simulator
android_app/                 senior app (Kotlin, view binding, custom icons and Mukta font)
docs/                        WRITEUP, BUSINESS_MODEL, PITCH_AND_DEMO
```

## Credits and licences

Vosk (Alpha Cephei, Apache 2.0) for local speech recognition; scikit-learn (BSD) for Isolation Forest and logistic regression; Mukta typeface (SIL OFL); Edge-TTS for the neural voice. All icons are drawn for this project. See the references in [docs/WRITEUP.md](docs/WRITEUP.md).
