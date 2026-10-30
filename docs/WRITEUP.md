# Aegis Saathi: technical write-up

*DEV_104, Early Warning for Seniors Living at Home. Architecture, models, synthetic data, results.*

## 1. Idea in one paragraph

A coordinator looks after many families and cannot tell, from memory and call notes, who is quietly getting worse. Aegis Saathi turns everyday signals into **one daily risk score per senior**, measured against **that senior's own baseline**, and shows the coordinator a ranked list where every alert has plain-language reasons and a suggested action. Seniors give signals in the easiest way they can: a tap, a voice note, or an AI phone call in Hindi or English that listens and talks. The system **flags and routes to a human**; it never diagnoses.

## 2. Architecture

```
Senior phone / basic phone / watch ──▶ FastAPI hub ──▶ Care portal | Ops view | Family view
                                         │
   ingestion ─ vitals, medicine, notes ──┤
   voice: Vosk STT (local) → agent → neural TTS (names masked)
   scoring: baseline rules + NLP cues + adherence + ML ──▶ explainable factors ──▶ tier, action
   feedback: coordinator ratings re-weight reasons
   privacy: roles, consent, audit
```

- **Hub**: FastAPI, one process, JSON snapshot store (atomic writes, survives restarts). CPU only.
- **Senior app**: native Android (Kotlin), Hindi/English switch, custom icons and font, background service that keeps the call channel and the Bluetooth watch connected.
- **Portals**: dependency-free HTML/JS (works offline), coordinator, operations and family views.
- **Scale path**: the store swaps for Postgres, STT runs as separate workers; nothing in the design needs a GPU.

## 3. Signals and how they are understood

| Signal | Source | Handling |
|---|---|---|
| Steps, resting HR, SpO2, sleep | watch / app | robust personal median and spread; deviation as z-score; data-quality guard (off-wrist or flat battery pauses watch alerts) |
| Blood pressure, sugar, weight | typed in app, or voice | not measured daily, so the newest reading from the last 7 days (14 for weight) is compared with the personal baseline; absolute safety lines for very high BP and sugar and for low sugar |
| Medicines | one tap, or what they say on a call | consecutive missed doses, weekly adherence |
| Check-in, notes, calls | tap, voice note, AI call | speech-to-text then cue extraction |
| SOS | app | tracked event until a coordinator closes it |

**Language understanding.** Ten cue categories (pain, dizziness, weakness, poor sleep, low appetite, fall, loneliness, **confusion**, fever or infection, medicine issue) are matched with Hindi, Hinglish, English and Devanagari patterns, with negation ("dard nahi hai", "no pain") and benign-phrase guards ("fall asleep", "trip to the market"). On a 58-sentence hand-written test set the extractor scores precision 1.00, recall 1.00 (F1 1.00). That set was used to fix two gaps (the words *paining* and *udaas*), so the figure is optimistic; the honest takeaway is "good enough to build on, needs a larger set".

**Speech.** Vosk small models run on the CPU: Hindi and Indian English. The phone streams 16 kHz audio over a WebSocket while the senior speaks, so the words are recognised by the time they stop (about 30 ms to finalise, versus about 1.3 s when the whole recording was uploaded and then recognised). The agent's fixed sentences are pre-rendered to disk, so the spoken reply comes back on the same connection (about 0 ms); measured server time per turn is 20 to 180 ms (`tests/bench_call.py`, clean synthetic speech played in real time, so it says nothing about microphone noise or accents). The remaining delay is the phone's end-of-speech wait (0.7 s for short answers, 0.9 s for long ones) plus network round trip. A restricted yes/no vocabulary was tried and rejected: on test answers it invented words ("मैंने" became "नहीं"), so free recognition is used. Whisper `small` was tried and rejected for calls: about 10 s per answer, and the `base` model wrote Hindi in Urdu or Latin script that the cue extractor cannot use.

## 4. Risk scoring

The final 0-100 score adds four evidence sources, each kept as a named **factor** with English and Hindi text and points:

1. **Safety rules**: SOS, possible fall, SpO2 below 92%. These always escalate.
2. **Personal baseline drift**: steps, heart rate, SpO2, sleep, BP, sugar, weight, activity falling over days. Steps, heart rate and sleep use the **two-day average**, so one bad night does not raise an alert; oxygen is not smoothed.
3. **Adherence and words**: missed doses, one-tap status, cues from notes and calls.
4. **ML signal** (below), capped at 20 points and only counted above 0.7 confidence, so it supports the rules but cannot create an emergency alone.

Tiers: RED (or any safety rule), ORANGE (45 and up), YELLOW (25 and up), GREEN. Each tier maps to a concrete action: call now, call today, keep watching, routine. Reasons are sorted by points; the portal draws a bar for each.

### ML models

Both models see only **features that are already relative to the senior's own baseline** (13 of them: steps drop, heart-rate rise, oxygen drop, sleep drop, BP rise, sugar rise, weight loss, step trend, heart-rate trend, check-in severity, missed medicines, symptom score from notes, fall flag). A person is never compared with a population average.

- **Isolation Forest** (unsupervised anomaly detector), fitted only on ordinary pre-decline days of the cohort. Output: how rare today's deviation pattern is, as a percentile of normal days.
- **Logistic regression** (supervised), trained on planted declines. Chosen over a deeper model deliberately: 250 seniors is small data, and its coefficients give a faithful reason ("walking well below normal, they reported feeling unwell") because contribution = coefficient x standardised value.
- **Cross-fitting by senior**: two folds; a senior is only ever scored by a model that never saw them.

### Feedback loop

Coordinators mark an alert *useful*, *not useful* or *routine* when they log a follow-up. Each reason shown on that alert accumulates ratings; a reason's weight is multiplied by 1 + 0.5 x (useful - not useful) / (useful + not useful + 6), bounded to 0.6 to 1.25. The portal marks reasons that were turned down. The safety rules are never re-weighted.

## 5. Synthetic cohort: how it was built

250 seniors x 90 days (`engine/cohort_generator.py`, seed 42).

- **Personal baselines** per senior: steps 2,200 to 5,500, resting HR 66 to 78, SpO2 96 to 98.5, sleep 6.5 to 8.2 h, BP, sugar (25% diabetic), weight.
- **Realistic noise and gaps**: 4% of days the watch is off-wrist; BP is recorded on about 55% of days, sugar 35%, weight 20%; 3.5% of ordinary days are a "bad day" (a cold, a late night); the self-reported check-in is noisy (healthy people say "a bit weak", unwell people under-report 25% of the time); 4% of ordinary days miss a dose.
- **Notes** in Hindi, Hinglish, English and Devanagari, several paraphrases per trajectory, sometimes absent, plus harmless everyday notes. They are kept separate from the detector's patterns and from the test set.
- **30 planted decline cases** (12%), five clinically motivated trajectories: gradual frailty (steps, sleep, weight), respiratory infection (heart rate, SpO2, sugar), medication failure (missed doses, rising BP, dizziness), unreported fall, withdrawal and cognitive decline (missed check-ins, loneliness, confusion). Decline starts on day 66 to 76; the **event day is 12 days later**, the point where, unaided, the decline would become an emergency.

An early version of the generator made the self-reported check-in a perfect label (stable seniors always said "good"). The first ML result looked like 99.6% precision. This was a data leak, not a result; the generator was fixed before any number below was produced.

## 6. Results (planted decline cases)

Definitions: *alert* = risk of 45 or more. *Detected* = an alert inside the 12-day decline window. *Days early* = event day minus first alert. *False alarm* = a run of consecutive alert days for one senior that never touches a decline window. Window scored: days 61 to 90.

| Scorer | Recall | Alert-day precision | Median days early | False alarms per coordinator-week |
|---|---|---|---|---|
| Rules only | 93.3% (28/30) | 87.3% | 9 | 0.89 |
| ML only | 100% (30/30) | 64.3% | 9 | 4.25 |
| **Combined (product)** | **100% (30/30)** | **91.2%** | **9** | **0.93** |

What this shows: the rules alone are precise but miss two cases; the ML alone finds everything but cries wolf; **together they catch all 30 with about one false alarm per coordinator-week**, well under a 3-per-week alert-fatigue budget. Precision at 10 per day is about 40%, but only a few planted cases are active on any one day, so that figure has a low ceiling and is not the one to read. Watch data was usable on 96.6% of days.

**Caveats we state plainly.** Synthetic data, 30 cases, small numbers. The ML weight (cap 20, threshold 0.7) was chosen by a sweep on this same cohort, so the combined score is optimistic; a fresh cohort or real pilot data would give the honest figure. No public dataset (for example PhysioNet) was used for validation yet.

## 7. Privacy and safety

- **Roles**: senior device key, coordinator (code and PIN), family (code from the senior), operations. All requests pass one check; 27 automated access-control checks pass (team scoping, device-key scope, consent, aggregate-only operations).
- **Consent**: care-team access at setup, family sharing as a separate, revocable choice made by the senior. Revoking consent ends family access on the next request.
- **Minimisation**: speech recognition is local. Before any text reaches the external neural voice, the senior's name and phone numbers are removed. Operations users never see individual records.
- **Audit**: every view of a senior, action, login and consent change is logged and visible to operations.
- **Not a diagnosis tool**: text describes *what changed from the person's own normal* and *what to do*. The family view contains no scores.
- **SOS safeguards against false alarms**: 3-second hold on a small button; 5-second cancellable countdown; 30-second undo after sending; repeat presses merged into one event; stays active until a coordinator confirms or closes it; rates of false and cancelled SOS are reported to operations.

## 8. What is not done

An LLM-written family summary; validation of the phone fall detector on real or public motion data (it is checked only on synthetic traces, and the opt-in feature has not run on a real phone); validation of the experimental Moyoung/Da Fit decoder on a physical band (unit-tested on hand-built packets only); encryption at rest and a real identity provider; validation on real or public data.

## References and licences

- Alpha Cephei. *Vosk speech recognition toolkit*, models `vosk-model-small-hi-0.22` and `vosk-model-small-en-in-0.4` (Apache 2.0). https://alphacephei.com/vosk/models
- Pedregosa et al. *Scikit-learn: Machine Learning in Python*. JMLR 12, 2011 (BSD). Isolation Forest: Liu, Ting, Zhou. *Isolation Forest*. IEEE ICDM, 2008.
- Radford et al. *Robust Speech Recognition via Large-Scale Weak Supervision* (Whisper), 2022; `faster-whisper` (MIT). Evaluated, not used by default.
- Microsoft neural voices via the `edge-tts` package, for text-to-speech only, with identity removed from the text.
- Mukta typeface, Ek Type (SIL Open Font License).
- Datasets: **none used.** The cohort is generated by this project (method in section 5).
