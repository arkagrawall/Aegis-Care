# Aegis Saathi: business module

*Figures marked (A) are assumptions to validate in a pilot. Figures marked (M) were measured in this prototype. Nothing here is a forecast or a market study.*

## 1. The problem and who pays

India has over 150 million people aged 60 and above, and a growing share live alone or with a spouse while children work elsewhere (problem statement). Care providers such as Samarth support 40,000+ seniors across 350+ cities through coordinators who call and visit. Today the coordinator decides whom to call from memory and notes, so effort goes to routine calls and quiet decline is found late.

**Buyers and what they get**

| Segment | Buys | Because |
|---|---|---|
| **Care providers and senior-care programmes** (primary) | per-senior monthly software licence | coordinators spend time on the people who need it; fewer emergencies found late; measurable service quality |
| **Families** (add-on) | a monthly family subscription | a calm weekly view and an alert only when something is serious |
| **Hospitals, insurers, housing societies** (later) | pilot or outcome-linked agreements | earlier action after discharge or in a community |

## 2. Value to the buyer

1. **Coordinator capacity**: a ranked list replaces calling everyone. In the prototype, of about 50 seniors per coordinator roughly 5 (about one in ten) are on the urgent or attention list on a given day (M, synthetic). *Hypothesis to prove in a pilot:* routine calls fall materially while the number of declines caught early rises.
2. **Earlier action**: on the planted cases the median warning is 9 days before the emergency point (M, synthetic).
3. **Trust, not alert fatigue**: about 0.93 false alarms per coordinator per week (M, synthetic), and the system learns from "not useful" ratings.
4. **Reach**: seniors without smartphones are reached by an AI voice call and a missed-call check-in, so more of the book of business can be monitored.

## 3. Product packaging

| Tier | For | Includes |
|---|---|---|
| **Core** | provider | ranked queue, explainable alerts, AI check-in calls, SOS handling, family view, audit log |
| **Operations** | provider management | volumes, response times, outcomes, model quality, coordinator feedback analytics |
| **Family** | families of monitored seniors | weekly summary, serious-event alert, consent controls |
| **Wearable bundle** | optional | low-cost BLE band, customer-supplied or subsidised |

## 4. Pricing (A)

- **Provider licence**: INR 80 to 150 per monitored senior per month, tiered by volume. 90-day free pilot for up to 500 seniors.
- **Family add-on**: INR 99 to 199 per month per senior.
- **Pilot or outcome-linked agreements**: set after baseline measurements with the partner.

## 5. Unit economics at 10,000 seniors (A, with the measured inputs shown)

**Compute.** Speech recognition took about 1.3 s per answer on one core of a 4-core laptop (M). A daily AI call of about 6 answers is 60,000 answers a day. If calls cluster in a three-hour window that is about 5.6 answers per second at peak, which needs roughly 7 cores, so **two 4-vCPU worker nodes** plus one for the API and models. Off-peak they idle or scale down. Models train in about a minute and need no GPU (M).

**Cost lines (A).** Three small cloud VMs, voice (a local or licensed Indian-language TTS in production, because the current free voice is an unofficial endpoint), storage and monitoring. A reasonable planning range is **INR 3 to 6 of variable infrastructure per senior per month**, against a licence of INR 80 to 150.

**Margin sketch (A).** At INR 100 per senior per month, 10,000 seniors is INR 10 lakh a month in licences against roughly INR 30,000 to 60,000 of infrastructure. Software gross margin is high before support and customer success, which become the main costs. The dominant cost in this domain is human care, which the product aims to use better rather than replace.

## 6. Go-to-market

1. **Pilot with one provider** in two cities, about 500 seniors, 90 days.
   Success metrics, agreed up front: alert precision at or above 80% as rated by coordinators, median early warning of 5 days or more, no more than 3 false alarms per coordinator per week, daily check-in completion, coordinator minutes saved per senior.
2. **Expand within the provider** city by city using the operations view as the proof.
3. **Family pull**: families who see the weekly view ask for it for other relatives.
4. **Partnerships**: hospital discharge programmes and housing societies once pilot outcomes are public.

## 7. Moat

- **Personal baselines accumulate**: the longer a senior is on the platform, the better "their normal" is known.
- **Hindi and code-mixed voice** that works on basic phones.
- **Feedback loop**: coordinator ratings make alerts better for each provider.
- **Low cost to serve** and **privacy by design** (consent, roles, audit, local speech recognition), which providers and families increasingly require.

## 8. Risks and how they are handled

| Risk | Handling |
|---|---|
| Missed decline (false negative) | safety rules always escalate; ML adds recall; every alert goes to a human; measured recall reported honestly |
| Alert fatigue | corroboration over two days, capped ML weight, feedback loop, false-alarm rate tracked per coordinator-week |
| Health-data regulation | consent, minimisation, audit and local speech processing are built in; a legal review against India's data-protection law is needed before real deployment |
| Wearable fragmentation | standard Bluetooth profiles supported; vendor protocols added per device; app works without a watch |
| Voice quality | typed-reply fallback, repeat and silence handling, escalation to a human on request |
| Dependence on a free voice endpoint | swap to a local or licensed TTS in production (a configuration change in one function) |
| Results are on synthetic data | pilot is designed to produce real precision, recall and lead-time numbers |

## 9. Roadmap

- **0 to 30 days**: pilot setup, validate the experimental watch decoder on the chosen band, replace the voice endpoint, coordinator onboarding.
- **30 to 90 days**: validate on pilot data, retune the ML weight on a held-out set, validate phone fall detection on real data, encryption at rest, identity provider.
- **After the pilot**: family summaries written by a model (with identity masked), medicine-interaction flags routed to a human, regional languages beyond Hindi and English.
