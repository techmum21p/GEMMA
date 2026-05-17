# GEMMA: A Field Medic in Your Pocket — No Internet Required

**In a barangay health station between the doctor's weekly visit, a community health volunteer — alone, undertrained, and often without a signal — must decide: send a child with high fever and a stiff neck home, or to the hospital. That decision window can be under five minutes. GEMMA was built to make those five minutes count.**

**Track:** Health & Sciences

---

## The Reality No Hackathon Slide Deck Should Ignore

The Philippines has over 42,000 barangays [[1]](https://www.dilg.gov.ph/facts-and-figures/Regional-and-Provincial-Summary-Number-of-Provinces-Cities-Municipalities-and-Barangays-as-of-30-September-2020/32), each served by a Barangay Health Station staffed by community volunteers — not licensed clinicians. Doctors rotate from municipal health offices, visiting individual stations as infrequently as once a week [[2]](https://www.rappler.com/voices/ispeak/opinion-barangay-health-workers-need-more-than-recognition/). Under Republic Act 7883 [[3]](https://www.officialgazette.gov.ph/1995/02/20/republic-act-no-7883/), the DOH recommends one BHW per 20 households; in practice, a single health worker routinely covers 200 to 300 [[2]](https://www.rappler.com/voices/ispeak/opinion-barangay-health-workers-need-more-than-recognition/) in a system strained by chronic shortages and inadequate infrastructure [[4]](https://pids.gov.ph/details/ph-lags-behind-asean-neighbors-in-terms-of-critical-health-outcome-access-indicators-pids-study). Half of all Filipinos cannot reach a primary care facility within 30 minutes [[5]](https://www.gmanetwork.com/news/topstories/nation/785638/half-of-filipinos-can-t-access-primary-healthcare-facilities-within-30-mins-doh/story/).

When a patient arrives between doctor visits — with chest pain, an infected wound, or a child with convulsions — the BHW must decide alone: manage at the station, refer to the Rural Health Unit, or send urgently to the hospital. GEMMA was built for exactly this moment — not to replace the physician, but to give the BHW structured clinical intelligence for that call, and to hand the doctor a proper SOAP note when they arrive.

---

## What GEMMA Does

GEMMA — Guided Emergency & Medical Management Assistant — is an offline-first Progressive Web App giving BHWs AI-powered triage support in Filipino and Taglish, running entirely on local hardware. The AI backend (FastAPI + Ollama) runs on a shared station laptop; the BHW uses their Android phone over a local Wi-Fi hotspot. No internet required.

A BHW enters a chief complaint, then captures a photo on the spot or selects one from the phone gallery — a patient who arrived with a wound photographed at home can have that image analyzed immediately. The app returns: a RED/YELLOW/GREEN triage level with a Taglish clinical justification, five ranked differential diagnoses in Filipino, three targeted follow-up questions, and a SOAP-format handoff note for the physician. Shift data is logged locally; the Excel report downloads to the phone in one tap; PDFs are emailed to the physician — the only moment the app needs a connection.

---

## The AI Architecture: Two Models, Two Roles

GEMMA deploys two Gemma-family models with strictly separated responsibilities.

**MedGemma 4B** (`medgemma:4b`) is the **visual specialist and clinical enricher**. It never outputs a triage level. It never touches the clinical decision.

**Gemma 4 E4B** (`gemma4:e4b`) is the **sole clinical decision-maker** — the only model that assigns a triage level, ranks conditions, writes the SOAP note, and generates follow-up questions.

### Stage 0 — MedGemma: Structured Visual Intelligence

When a BHW captures or uploads a photo at intake, MedGemma runs first. Its prompt instructs it to output four structured sections: an image **Category** (one of eight anatomical domains), **Observations** (4–6 sentences describing only what is visible), a **Visual Impression** with named conditions and visual rationale, and a **Confidence rating** (HIGH, MEDIUM, or LOW) with a one-sentence basis.

This output is parsed into a labeled evidence block injected into Gemma 4's prompt. The image category also selects a domain-specific clinical context block — curated barangay-relevant differentials and red flags per body system — keeping the base prompt lean while ensuring Gemma 4 has the right clinical vocabulary for every case.

### Stage 1a — Gemma 4: How We Specifically Used It

Gemma 4's system prompt opens with the `<|think|>` token, activating its native chain-of-thought mode. The model reasons internally before emitting JSON; the thinking block is stripped before parsing. All Gemma 4 calls use direct `httpx` to Ollama's `/api/generate` with `format="json"`, `num_predict=4096`, and `num_ctx=8192` — not LangChain, for reasons explained below.

The triage call runs a **7-step ordered reasoning process**: demographics → symptoms → vitals → image findings → red-flag check → differential → triage level assignment. The triage level is always last, built on every preceding layer of evidence.

The defining innovation is **confidence-gated image weighting**. Gemma 4 applies explicit weights to MedGemma's Visual Impression based on confidence: HIGH-confidence findings fold into the top differential as high-specificity evidence; MEDIUM findings serve as supporting context; LOW output is deprioritized in favor of the chief complaint. A blurry photo cannot push a misdiagnosis.

Gemma 4 also runs a **non-negotiable red-flag check**. If stroke, TIA, MI, sepsis, or anaphylaxis appears in the differential and symptoms support it, assigning below RED is explicitly named in the system prompt as a patient safety failure. Follow-up questions are **co-generated in the same call** — no additional inference, no added latency.

### Stage 2a — Refined Triage and Prefetched Enrichment

When the BHW submits follow-up answers, Gemma 4 re-reasons the full differential with Q&A context. Immediately after, **MedGemma enrichment fires as a background asyncio task**, pre-warming the PDF cache with physician-facing clinical notes per diagnosis. By the time the BHW clicks "Generate PDF," the enrichment is already done.

---

## Challenges That Shaped the Architecture

The design evolved from real failures, not theory.

**Under-triage of a probable stroke.** Our original model — MedGemma — assigned YELLOW to a patient we called Nestor: 86 years old, BP 160/100, sudden bilateral numbness of both arms and legs. Stroke was #2 in its own differential. The model anchored on blood pressure and discarded the neurological deficit. Published benchmarks confirmed the root cause: MedGemma 4B scores 69.1% on MedQA versus Gemma 3 27B at 85.3%, and its MMLU Pro score *dropped* from 39.1% to 33.8% after medical fine-tuning — specialization for imaging reduced general clinical reasoning. We replaced MedGemma with Gemma 4 E4B as the sole triage decision-maker the same day. MedGemma was reassigned to what it genuinely excels at: interpreting field photos and writing physician-facing clinical notes.

**LangChain silently dropped `num_predict`.** The LangChain OllamaLLM wrapper was ignoring the token limit parameter, causing Gemma 4 to truncate its JSON output unpredictably. Switching to direct `httpx` calls gave us guaranteed control. To further protect critical data, we reordered the JSON schema so SOAP appears before `top_conditions` — if the model truncates, it drops a lower-ranked condition, not the physician's handoff note.

**Concurrent model-swap corruption.** Running two Ollama calls simultaneously caused model-swap errors that forced every overlapping request into fallback. We added a shared `asyncio.Semaphore(1)` in `ollama_lock.py` — all Gemma 4 and MedGemma calls serialize through it. Stage 0 image analysis is intentionally exempt to prevent deadlocks.

---

## Engineering for Failure, Not Success

A BHW has no retry budget. GEMMA's parsing pipeline assumes failure: Gemma 4's output is cleaned (thinking blocks stripped, markdown fences removed), then parsed with `json.loads()`. On `JSONDecodeError`, `_repair_truncated_json()` regex-salvages the partial output. If repair also fails or the triage level is invalid, `_build_fallback_with_patient_data()` runs — SOAP fields auto-populated from whatever the BHW already entered, `is_fallback: True` set, and YELLOW returned. The frontend shows an amber banner and a manual RED/YELLOW/GREEN selector so the BHW can assign the level based on direct observation. No silent crashes. No patient left without a record.

MedGemma failures are non-fatal: image failure means triage proceeds on text alone; enrichment failure means the PDF generates without physician notes. On CPU-only hardware (8GB RAM, no GPU), a full Gemma 4 inference completes in 35–40 seconds — long enough for the BHW to record vitals, short enough for a real consultation queue.

---

## Conclusion

GEMMA is built from the ground up for Philippine barangay constraints: no internet, a shared laptop, a BHW's phone, life-or-death decisions without a physician present.

By pairing MedGemma's clinical vision with Gemma 4's structured reasoning — and engineering every failure mode to degrade safely rather than silently — GEMMA delivers triage decision support that is genuinely deployable where it is needed most. Not as a proof of concept. As a tool a BHW can open on a phone in Barangay Platero and trust.

The five minutes between a patient arriving and a triage decision have always belonged to the BHW alone. GEMMA puts structured clinical intelligence in those five minutes — offline, in Filipino, on a phone.
