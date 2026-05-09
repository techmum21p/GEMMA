# GEMMA AI Pipeline — How MedGemma and Gemma 4 Work Together

## Overview

GEMMA uses two models with strictly separated roles:

- **MedGemma 4B** (`medgemma:4b`) — visual observer (at intake) and clinical enricher (at PDF generation). It never assigns a triage level.
- **Gemma 4 E4B** (`gemma4:e4b`) — the sole clinical reasoner. It reads all available evidence, runs red-flag checks, ranks conditions, assigns triage level, and writes the SOAP note.

The two models never call each other. MedGemma's output is plain text that gets injected into Gemma 4's prompt as one more evidence source. Gemma 4 then explicitly reasons about how much weight to give it.

---

## Stage 0 — MedGemma: Visual Observer

**Trigger:** BHW captures a photo. Runs before any triage call.
**File:** `app/services/image_service.py` → `analyze_image()`

MedGemma receives the base64-encoded image and the chief complaint. Its system prompt instructs it to describe only what is **visibly observable** — it is explicitly forbidden from naming any disease or condition (no "infection", "fracture", "eczema", etc.).

Its output has two parts:
1. A category tag on the first line: `WOUND | SKIN | EYE | ORAL | MUSCULOSKELETAL | RESPIRATORY | ABDOMINAL | OTHER`
2. 4–6 sentences of structured clinical observations for that category (e.g. wound shape, discharge type, erythema extent; or lesion morphology, distribution, borders for skin cases)

The raw text is saved as `image_findings` and passed to Gemma 4 in the next stage.

If the image is unclear or not medical, MedGemma outputs `Category: OTHER` and states it cannot identify a finding. If it omits the category tag entirely, `_extract_image_category()` in `triage_prompt.py` falls back to a keyword scan over the raw text to infer the category.

---

## Stage 1a — Gemma 4: Initial Triage

**Trigger:** BHW submits the intake form (with or without a photo).
**File:** `app/services/triage_service.py` → `_run_initial_triage()`

`build_gemma4_triage_prompt()` assembles the full patient context:

- Demographics (age, sex)
- Chief complaint
- Vitals (BP, temperature, HR, SpO2 — whatever was taken)
- MedGemma's `image_findings` (if present), preceded by the `IMAGE_CLINICAL_CONTEXT` block for that category — a curated list of barangay-relevant differentials and red flags for that domain (e.g. the WOUND context injects Tetanus-prone Wound, Cellulitis, Retained Foreign Body, etc. as high-prior differentials)

Gemma 4's system prompt instructs it to reason through demographics, symptoms, vitals, and image findings **in order**, and to explicitly state whether image findings are specific or vague before factoring them into the differential. Specific findings get heavy weight; vague findings are noted as weak supporting evidence only.

Gemma 4 then:
- Runs a mandatory red-flag check (stroke/TIA, MI, anaphylaxis, SpO2 < 92%, BP ≥ 180/120, etc.)
- Produces a ranked differential of 5 real diagnoses (never symptoms like "fever" or "pain")
- Assigns **RED / YELLOW / GREEN** — the system prompt contains an escalation rule: if Stroke, TIA, MI, Sepsis, or Anaphylaxis appears in the top conditions and symptoms support it, RED is mandatory
- Writes a SOAP note: S = patient's own verbal report only; O = measurable vitals and observations; A = synthesized working diagnosis with differentials for the receiving doctor (English); P = triage level + specific BHW action + named red flags to watch
- Generates exactly 3 Taglish follow-up questions targeting genuine clinical information gaps that would differentiate the top conditions

The raw response is parsed by `_parse_triage_json()`. If `json.loads()` fails (e.g. truncated output), `_repair_truncated_json()` attempts to salvage the response via regex, extracting `triage_level`, `triage_reason`, conditions, questions, and SOAP fields from whatever arrived. If that also fails, or if `triage_level` is not one of `{RED, YELLOW, GREEN}`, the pipeline immediately returns `TRIAGE_FALLBACK` — a hardcoded YELLOW response with "Unable to assess" conditions. There is no retry.

---

## Stage 2a — Gemma 4: Refined Triage

**Trigger:** BHW submits answers to the 3 follow-up questions.
**File:** `app/services/triage_service.py` → `_run_refined_triage()`

`run_triage()` routes here when `followup_answers` is present in the patient data.

The prompt is built identically to Stage 1a, but now includes:
- The Q&A answers (`followup_answers`) as a structured block
- The Stage 1a result (`initial_assessment`) — its triage level, top 3 conditions, and SOAP-O — so Gemma 4 can see what it previously concluded and revise if the answers change the picture

Gemma 4 re-reasons the full differential with this richer context and may change the triage level, reorder conditions, or revise the SOAP note. `followup_questions` in the response is set to `[]` — the Q&A phase is complete.

After a successful Stage 2a, `enrichment_cache.prefetch()` fires MedGemma enrichment as a **background asyncio task** (`enrichment_cache.py`). The cache key is an MD5 hash of the `top_conditions` list. This pre-warms the result so PDF generation doesn't have to wait for MedGemma.

---

## PDF Time — MedGemma: Clinical Enricher

**Trigger:** BHW clicks "Generate PDF." Runs inside `pdf_service.py` via `enrichment_cache.get_or_fetch()`.
**File:** `app/services/medgemma_enrichment_service.py` → `enrich_triage()`

MedGemma receives Gemma 4's triage output (triage level, reason, top conditions, full SOAP note) and enriches each condition with three physician-facing fields:

- `clinical_summary` — one sentence linking the patient's evidence to that specific diagnosis
- `priority_workup` — 2–3 specific tests (e.g. "Non-contrast CT head, serum tryptase, CBC")
- `red_flags` — 2–3 specific warning signs requiring immediate escalation (e.g. "stridor, SpO2 < 88%, altered consciousness")

Before calling MedGemma, `enrich_triage()` filters out placeholder conditions (`"Condition 1"`, `"Unable to assess"`) so MedGemma only enriches real diagnoses. The enrichment prompt passes temperature 0.1 and `num_ctx: 4096` — low temperature for clinical precision.

`enrichment_cache.get_or_fetch()` returns the cached result if the Stage 2a prefetch already completed. If it hasn't (e.g. the BHW generated the PDF very quickly), it awaits the result synchronously. If a cached task failed, it deletes the entry and re-runs. MedGemma enrichment failure is non-fatal — the PDF generates without the clinical notes section, and a warning is logged.

---

## Concurrency

Both `_call_gemma()` (Stages 1a and 2a) and `enrich_triage()` (PDF enrichment) acquire `ollama_lock` before posting to Ollama — a shared asyncio semaphore in `app/services/ollama_lock.py` that prevents concurrent model calls from hammering a single local Ollama instance.

`analyze_image()` (Stage 0) does **not** acquire the lock — it calls Ollama directly. This is intentional: image analysis is a one-shot call that happens before the triage lock window.

---

## End-to-End Flow Summary

```
BHW captures photo (optional)
        │
        ▼
[Stage 0] MedGemma
  → Describes visual findings as plain text
  → Tags the category (WOUND, SKIN, EYE, etc.)
  → Output saved as image_findings
        │
        ▼
[Stage 1a] Gemma 4
  → Assembles all evidence: demographics + vitals + complaint + image findings + clinical context
  → Runs red-flag rules, ranks differential, assigns RED/YELLOW/GREEN
  → Outputs: triage_level, top_conditions, SOAP note, 3 follow-up questions
        │
        ▼
BHW asks 3 follow-up questions to patient
        │
        ▼
[Stage 2a] Gemma 4
  → Re-reasons with Q&A answers + initial assessment
  → Outputs revised triage_level, top_conditions, SOAP note
  → Triggers MedGemma enrichment prefetch in background
        │
        ├──────────────────────────────────────────────────────────┐
        │                                                          │
        ▼                                                          ▼
BHW saves patient record                         [Background] MedGemma enrichment
                                                   → Enriches each condition:
                                                     clinical_summary, priority_workup, red_flags
                                                   → Cached by conditions hash
        │
        ▼
BHW generates PDF
  → enrichment_cache.get_or_fetch() returns pre-fetched enrichment (or awaits it)
  → PDF includes Gemma 4 SOAP + MedGemma enrichment per condition
```

---

## Why Gemma 4 for Clinical Reasoning Instead of MedGemma

**MedGemma's strength is vision, not text reasoning.**
MedGemma 4B is a fine-tuned vision model trained on medical images — radiology, pathology, dermatology. Its image descriptions in Stage 0 are genuinely good. But for text-only cases (no photo), there's no reason to expect it to outperform a larger general model on multi-factor clinical reasoning. Roughly half of GEMMA's triage cases won't have an image at all.

**The triage prompt is extremely instruction-heavy.**
The Gemma 4 system prompt runs ~100 lines: ordered reasoning steps, red-flag condition lists, escalation rules, few-shot examples, differential diagnosis rules, SOAP note format constraints, language mixing rules (Taglish vs English per field), and a structured JSON schema. Gemma 4 E4B is significantly better at following long, complex instructions reliably and producing well-formed JSON output. Forcing that onto MedGemma 4B would likely produce more frequent format failures and fallbacks.

**You'd be fighting MedGemma's fine-tuning.**
The Stage 0 prompt explicitly tells MedGemma "do NOT name any disease or condition." That constraint exists because MedGemma has been trained to pattern-match to medical diagnoses from images — useful for description, but dangerous in community triage where overconfident image-based diagnoses without full clinical context can misdirect a BHW. The architecture intentionally redirects that tendency into a safe lane.

**Separation of concerns makes the system safer.**
By keeping all decision-making in Gemma 4, there is one model whose reasoning is fully prompt-engineered and validated. MedGemma enriches the input (Stage 0) and the output (PDF enrichment) but never touches the triage level. If MedGemma returns a vague or bad image description, Gemma 4 is explicitly instructed to downweight it. That is a much safer failure mode than having one model do everything.

**Hackathon constraint.**
The competition is Kaggle × Google DeepMind — Gemma 4 Good. Gemma 4 as the primary reasoning model is a core requirement. MedGemma's role was carved out specifically for what it does better than any text model: interpreting field photos taken on a mobile phone.

---

## Failure Handling

| Point of failure | Behavior |
|---|---|
| MedGemma image analysis fails | Returns Filipino fallback string; triage proceeds without image findings |
| Gemma 4 returns malformed JSON | `_repair_truncated_json()` attempts regex salvage |
| Repair also fails / invalid triage level | Immediate return of `TRIAGE_FALLBACK` (YELLOW, "Unable to assess" × 5) |
| MedGemma enrichment fails | PDF generates without clinical notes; warning logged |
| Ollama unreachable (any stage) | HTTP exception propagates to API route; frontend shows error state |
