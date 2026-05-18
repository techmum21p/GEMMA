# GEMMA: A Field Medic in Your Pocket — No Internet Required

**In a barangay health station between the doctor's weekly visit, a community health volunteer — alone, undertrained, and often without a signal — must decide: send a child with high fever and with stiff neck, or to the hospital. That decision window can be under five minutes. GEMMA was built to make those five minutes count.**

**Track:** Health & Sciences

---

## The Reality No Hackathon Slide Deck Should Ignore

The Philippines has over 42,000 barangays [[1]](https://www.dilg.gov.ph/facts-and-figures/Regional-and-Provincial-Summary-Number-of-Provinces-Cities-Municipalities-and-Barangays-as-of-30-September-2020/32), each served by a Barangay Health Station staffed not by physicians, but by Barangay Health Workers (BHWs) — community volunteers, not licensed clinicians. Doctors rotate from municipal health offices, visiting as infrequently as once a week [[2]](https://www.rappler.com/voices/ispeak/opinion-barangay-health-workers-need-more-than-recognition/). Under Republic Act 7883 [[3]](https://www.officialgazette.gov.ph/1995/02/20/republic-act-no-7883/), the DOH recommends one BHW per 20 households; in practice, a single health worker routinely manages 200 to 300 [[2]](https://www.rappler.com/voices/ispeak/opinion-barangay-health-workers-need-more-than-recognition/), in a system strained by chronic medicine shortages and inadequate infrastructure [[4]](https://pids.gov.ph/details/ph-lags-behind-asean-neighbors-in-terms-of-critical-health-outcome-access-indicators-pids-study). Half of all Filipinos cannot reach a primary care facility within 30 minutes [[5]](https://www.gmanetwork.com/news/topstories/nation/785638/half-of-filipinos-can-t-access-primary-healthcare-facilities-within-30-mins-doh/story/).

When a patient arrives between doctor visits — with chest pain, an infected wound, or a child with convulsions — the BHW must make a judgment call: manage at the station, refer to the Rural Health Unit, or send urgently to the hospital. GEMMA was built for exactly this moment — not to replace the physician, but to give the BHW structured clinical intelligence for that call, and to hand the doctor a proper SOAP-format assessment when they arrive.

---

## What GEMMA Does

**GEMMA — Guided Emergency & Medical Management Assistant** — is an offline-first Progressive Web App that gives BHWs AI-powered triage support in Filipino and Taglish, running entirely on local hardware. The AI backend (FastAPI + Ollama) runs on a shared station laptop; the BHW uses their Android phone over local Wi-Fi. No router beyond the laptop's hotspot. No ISP. No cloud dependency.

A BHW enters a patient's chief complaint, then captures a photo on the spot or selects one from the phone gallery — a patient who arrived with a wound photographed at home can have that image analyzed immediately. The app returns: a RED/YELLOW/GREEN triage level with a Taglish clinical justification, five ranked differential diagnoses in Filipino, three targeted follow-up questions to refine the assessment, and a SOAP-format handoff note for the physician. Every encounter is logged locally. At shift end, the Excel shift report downloads to the phone with one tap. The email to the physician coordinator is the only moment the app needs a connection.

---

## The AI Architecture: Two Models, Two Roles, One Safe Pipeline

GEMMA's core innovation is deploying two Gemma-family models with strictly separated responsibilities — making each model's contribution auditable and every failure mode safe.

**MedGemma 4B** (`medgemma:4b`) is the **visual specialist and clinical enricher**. It never outputs a triage level. It never touches the clinical decision.

**Gemma 4 E4B** (`gemma4:e4b`) is the **sole clinical decision-maker** — the only model that assigns a triage level, ranks differential diagnoses, writes the SOAP note, and generates follow-up questions.

Both models run locally via **Ollama**.

---

### Why Ollama Makes This Deployable

Ollama is the reason GEMMA can exist outside a research lab. Getting both models onto a barangay health station laptop requires exactly two commands:

```
ollama pull gemma4:e4b
ollama pull medgemma:4b
```

No GPU. No cloud account. No API key. No Docker. No dependency chain. Ollama ships as a single binary for macOS, Windows, and Linux, installs in minutes, and serves a local REST API at `http://localhost:11434` the moment `ollama serve` runs. That is the only external process GEMMA's FastAPI backend depends on — Gemma 4 inference uses `langchain-ollama`; MedGemma's multimodal image calls go directly to Ollama's `/api/generate` via `httpx`.

For a tool meant to run in Barangay Platero, this matters enormously. The person setting up the station laptop is not a DevOps engineer — it may be the BHW supervisor or a municipal health volunteer. Ollama's zero-configuration setup means the entire AI backend is running in under ten minutes by anyone who can follow a README. No inference server to configure, no CUDA driver conflicts, no firewall rules for an external API. The models are on disk, Ollama serves them, and GEMMA calls them — locally, offline, and reliably.

On tested hardware (16GB RAM laptop, Apple M2, no discrete GPU), a full Gemma 4 E4B triage inference completes in 35–40 seconds — well within the consultation window, and fast enough that the BHW can record vitals while the model reasons.

---

### Stage 0 — MedGemma: Structured Visual Intelligence

When a BHW captures or uploads a photo, MedGemma runs before any triage call. Its output is structured into four sections: an anatomical **Category** (WOUND, SKIN, EYE, ORAL, MUSCULOSKELETAL, RESPIRATORY, ABDOMINAL, or OTHER), clinical **Observations** of only visible findings, a **Visual Impression** with named conditions and specific visual rationale per finding, and a **Confidence rating** (HIGH, MEDIUM, or LOW).

This structured output is injected as a labeled evidence block into Gemma 4's prompt. The image category also selects a domain-specific context block — curated barangay-relevant differentials and red flags: a SKIN case brings scabies, impetigo, and Stevens-Johnson escalation criteria; a WOUND case brings infection staging, tetanus risk, and necrotizing fasciitis red flags. This keeps the base prompt lean while ensuring Gemma 4 receives the right clinical vocabulary per case. Vague images are handled gracefully — the injection marks `Cannot determine from image` and the domain block is still included so Gemma 4 reasons toward the right body system regardless.

---

### Stage 1a — Gemma 4: Confidence-Gated Clinical Reasoning

The initial triage call runs a **7-step ordered reasoning process**: demographics → symptoms → vitals → image findings → red-flag check → differential diagnosis → triage level assignment. Each step must complete before the next; the triage level is always last.

The defining innovation is **confidence-gated image weighting**. MedGemma's Visual Impression names clinical conditions. Gemma 4 applies explicit weights based on the confidence rating: HIGH-confidence impressions fold directly into the top differential; MEDIUM findings serve as supporting context, cross-referenced against vitals; LOW output is deprioritized in favor of the chief complaint. A blurry field photo cannot push a misdiagnosis — Gemma 4 discards weak visual evidence by design.

Gemma 4 also runs a **non-negotiable red-flag check** on every encounter. If stroke, TIA, MI, sepsis, or anaphylaxis appears in the differential and symptoms support it, the system prompt explicitly prohibits assigning below RED. The model cannot reason its way to YELLOW on a probable stroke.

Follow-up questions are **co-generated in the same Stage 1a call** — no additional inference, no added latency. Questions must target genuine clinical information gaps in conversational Taglish, and may never re-ask about symptoms already stated.

---

### Stage 2a — Refined Triage and Prefetched Enrichment

When the BHW submits answers, **Gemma 4 re-reasons the full differential with the initial assessment and Q&A context — potentially revising the triage level, reordering conditions, or updating the SOAP note.**

Immediately after a successful Stage 2a, **MedGemma enrichment fires as a background asyncio task**, pre-warming the PDF cache. By the time the BHW clicks "Generate PDF," MedGemma has already annotated each confirmed diagnosis with a clinical summary, priority workup tests, and specific red flags for escalation. The PDF generates without waiting — the enrichment happened while the health worker was still with the patient.

---

## Engineering for Failure, Not Success

A BHW in a remote barangay has no retry budget — a failed triage is a patient left with no answer.

GEMMA's parsing pipeline assumes failure. Gemma 4's output is parsed with `json.loads()`; on `JSONDecodeError`, a repair function regex-salvages the partial output. If repair also fails, or the triage level is not a valid RED/YELLOW/GREEN, a fallback builder runs: it auto-populates SOAP fields from everything the BHW already entered — complaint, vitals, Q&A answers — sets `is_fallback: True`, and returns YELLOW. The frontend responds with an amber banner and a manual RED/YELLOW/GREEN selector so the BHW can assign the level based on direct observation. No retry loops. No silent crashes. The BHW is never left without a clinical record or a path forward.

MedGemma failures are equally non-fatal: image analysis failure means triage proceeds on text evidence alone; enrichment failure means the PDF generates without the physician notes section and logs a warning. The system degrades gracefully — and never stops.


---

## Conclusion: Intelligence Where It Has Never Reached Before

GEMMA is built for the constraints of Philippine barangay health stations: no internet required, a shared laptop as the only compute, a BHW's Android phone as the interface, life-or-death decisions without a physician present.

**By pairing MedGemma's clinical vision with Gemma 4's structured reasoning** — and by engineering every failure mode to degrade safely rather than silently — GEMMA delivers triage decision support that is genuinely deployable where it is needed most. Not as a proof of concept. As a tool a BHW can open on a phone in Barangay Platero and trust.

The five minutes between a patient arriving and a triage decision have always belonged to the BHW alone. GEMMA puts structured clinical intelligence in those five minutes — offline, in Filipino, on a phone.
