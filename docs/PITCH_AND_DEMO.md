# Five-minute pitch and live demo

## Before you start (2 minutes of prep)

1. `python run.py`, wait for "Application startup complete".
2. Open `http://localhost:8000/` (care portal) and `http://localhost:8000/phone` (phone simulator) in two windows. Demo logins are on the sign-in page.
3. Phone window: choose team **SAM-101**, pick a senior, press **Go online**.
4. Sign in to the portal as **SAM-101**.
5. Optional: Android app on the emulator, pointed at the server (menu, Server settings).
6. Have the Operations login (`OPS-1`) ready in a private window.

## The story (talk track)

**0:00 Problem (30 s).** "Decline in older people is gradual. A coordinator looks after fifty families and cannot tell from memory who is quietly getting worse. By the time it is obvious, it is an emergency."

**0:30 What it is (30 s).** "Aegis Saathi compares every senior with their own normal, combines vitals, medicines, check-ins and what they say in Hindi or English, and tells the coordinator who needs attention today, why, and what to do. It flags and routes to a human. It never diagnoses."

**1:00 Demo 1: the coordinator's morning (60 s).** Portal queue.
- Point at the four counts and the ranked list. "One screen, sorted by urgency."
- Click the top senior. "Why today": reasons in plain language with bars, including the one marked **AI**. "Do this next". The readings with 14-day trends.
- Toggle **हिं / EN**: "Reasons switch language."

**2:00 Demo 2: a senior who has no app skills (75 s).** Phone simulator.
- In the portal press **AI check-in call** for the senior you picked. The phone window rings.
- Answer. Speak or tap a reply: "chakkar aa raha hai". "It listens and talks; no buttons for the senior."
- Back in the portal: the live transcript appears, symptoms are extracted, the risk rises. "The coordinator watches it happen."

**3:15 Demo 3: safety (45 s).**
- On the phone (or Android app) press and hold SOS. "Three-second hold, then a five-second countdown with a big Cancel, then a thirty-second undo. Nobody triggers this by accident."
- The portal banner appears. Press **False alarm**. "Every SOS is tracked until a human closes it."

**4:00 Family and operations (30 s).**
- Family view: sign in with the code a senior generated. "The senior decides. No scores, no clinical detail. Switch consent off and access ends at once."
- Operations login: volumes by team and city, SOS response time, what the feedback loop learned, access log. "Aggregates only; they cannot open an individual."

**4:30 Honest results (30 s).** Open **Model quality**.
- "On 30 planted declines: all 30 caught, 91% precision, median nine days early, under one false alarm per coordinator per week."
- "Rules alone catch 28 of 30. ML alone catches all but cries wolf. Together is best."
- "Synthetic data. We say so, and we show the caveats on the page."

**5:00 Close.** "Low cost: CPU only, speech recognition on a laptop. Next: a pilot with real coordinators to turn these numbers into real ones."

## If something goes wrong

- Voice not working in the browser: type the reply in the phone window or tap a chip; the flow and the portal update identically.
- Server just restarted: first start trains the models for about a minute; wait for the health check at `/api/health`.
- Phone does not ring: it must say **Online**; press **Go online** again. The portal tells you if the phone is offline.

## Likely questions

**Is this a diagnosis tool?** No. It says what changed from the person's own normal and what to do; a human decides. The family view has no scores.

**Your results are on synthetic data.** Yes, and we say so on the page. We found and fixed a data leak in our own generator before reporting any number. The pilot is designed to give real figures.

**Why not a deeper model?** 250 seniors is small data. Logistic regression and Isolation Forest give honest, explainable reasons; a coordinator needs a reason, not a score.

**What about false alarms?** Two-day corroboration, a data-quality guard, a capped ML weight and a feedback loop. Measured at 0.93 per coordinator per week.

**Privacy?** Roles, team scoping, consent controlled by the senior, an audit log, local speech recognition, names removed before text leaves for the voice. Production adds encryption at rest and a real identity provider.

**Seniors without smartphones?** The AI call works on any phone, and a missed call can mark "I am fine". The Android app is for those who want more.

**Cost at 10,000 seniors?** CPU only. Roughly three small VMs; planning range INR 3 to 6 per senior per month in infrastructure. See the business module.

**Does the watch work?** The app connects, reconnects and reads standard heart-rate and battery data, and logs raw vendor packets. An experimental decoder for Moyoung/Da Fit steps, heart rate and oxygen is included, range-checked and unit-tested, but not yet verified on a physical band.
