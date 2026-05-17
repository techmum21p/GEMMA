# GEMMA AI Pipeline — How MedGemma and Gemma 4 Work Together

## Overview

GEMMA uses two models with strictly separated roles:

- **MedGemma 4B** (`medgemma:4b`) — visual specialist (Stage 0) and clinical enricher (PDF time). When an image is present, it produces structured observations and a confidence-rated visual impression. At PDF generation, it annotates each confirmed diagnosis with physician-facing workup and escalation notes.
- **Gemma 4 E4B** (`gemma4:e4b`) — the sole clinical decision-maker. It reads all available evidence, runs red-flag checks, ranks conditions, assigns the triage level, writes the SOAP note, and generates follow-up questions. It is the only model that outputs a triage level.

The two models never call each other. MedGemma's output is structured text that gets parsed and injected into Gemma 4's prompt as a labeled evidence block. Gemma 4 is then explicitly instructed to reason about how much weight to give each component based on confidence.

---

## Stage 0 — MedGemma: Visual Specialist

**Trigger:** BHW captures a photo at intake. Runs before any triage call.
**File:** `app/services/image_service.py` → `analyze_image()`
**Call:** Direct `httpx` POST to Ollama `/api/generate` with base64 image array. Temperature 0.1. No lock acquired (intentional — runs before the triage lock window).

MedGemma receives the base64-encoded image and the chief complaint. Its system prompt (`IMAGE_SYSTEM_PROMPT` in `image_prompt.py`) instructs it to output **exactly four labeled sections**:

1. **Category** — one of: `WOUND | SKIN | EYE | ORAL | MUSCULOSKELETAL | RESPIRATORY | ABDOMINAL | OTHER`
2. **Observations** — 4–6 sentences of structured clinical description using only observable findings (wound shape, discharge type, lesion morphology, distribution, borders, etc.). Describes what is **visible**, not what it implies.
3. **Visual Impression** — MedGemma's trained medical assessment: 1–3 named conditions with specific visual rationale per condition (e.g. "1. Herpes Zoster — unilateral dermatomal vesicular distribution with erythematous base."). If the image is unclear or insufficient, outputs `Cannot determine from image`.
4. **Confidence + Confidence Basis** — `HIGH | MEDIUM | LOW` with a one-sentence rationale. Rules: HIGH = clear image AND classic recognizable pattern; MEDIUM = adequate quality but pattern partially obscured or broad spectrum; LOW = poor quality, unclear finding, or no recognizable pattern.

The raw text is saved as `image_findings` on the patient record. If MedGemma returns an empty response or throws, `analyze_image()` returns a Filipino fallback string and triage proceeds without image evidence.

### Parsing — `_parse_medgemma_findings()` (`triage_prompt.py`)

Before injecting into Gemma 4's prompt, `build_patient_context()` calls `_parse_medgemma_findings()`, which regex-extracts all four sections into a structured dict: `category`, `observations`, `visual_impression`, `confidence`, `confidence_basis`.

Category extraction has a two-tier fallback:
1. Parse the `Category:` tag directly
2. If missing, `_extract_image_category()` runs a keyword scan over the full text (e.g. "LACERATION" → WOUND, "VESICLE" → SKIN) and falls back to OTHER

---

## Stage 0 → Stage 1a Integration

**File:** `app/prompts/triage_prompt.py` → `build_patient_context()`

When image findings are present, the prompt injected into Gemma 4 contains:

```
Visual Observation — MedGemma field photo analysis [Category: SKIN]:

Clinical Observations:
[4–6 sentence structured description of visible findings]

MedGemma Visual Impression: 1. Herpes Zoster — unilateral dermatomal vesicular pattern...
Confidence: HIGH
Confidence Basis: Classic dermatomal vesicular pattern in predictable distribution

Image Clinical Context for [SKIN] — use to guide differential:
Dermatology case confirmed by image.
Key focus: lesion morphology, distribution (localized/dermatomal/symmetrical/sun-exposed), infectious vs inflammatory vs allergic...
Common barangay differentials: Scabies, Impetigo, Tinea, Atopic Dermatitis, Varicella, Herpes Zoster, Urticaria...
RED FLAG: rapidly spreading skin redness + fever + skin peeling → possible Stevens-Johnson or Necrotizing Fasciitis → refer.
```

The `IMAGE_CLINICAL_CONTEXT` dict (`triage_prompt.py`) maps each category to a curated clinical context block — relevant barangay differentials, domain-specific red flags, and an illustrative example case. This keeps the system prompt lean (no per-domain content baked in) while injecting the right clinical vocabulary per case.

If `visual_impression` is `Cannot determine from image`, the injection shows that explicitly and still includes the clinical context block so Gemma 4 uses the image domain to guide its differential.

---

## Stage 1a — Gemma 4: Initial Triage

**Trigger:** BHW submits the intake form (with or without a photo).
**File:** `app/services/triage_service.py` → `_run_initial_triage()`
**Call:** `_call_gemma()` with `num_predict=4096`, `num_ctx=8192`, `temperature=1.0`, `format="json"`. Acquires `ollama_lock` semaphore before posting.

`build_gemma4_triage_prompt()` assembles the full patient context block:
- Demographics (age, sex)
- Chief complaint
- Vital signs (BP, temperature, HR, SpO2 — whatever was taken; "Not taken" if none)
- Parsed MedGemma image block (if photo was captured) — Observations, Visual Impression, Confidence, Confidence Basis, Category Clinical Context
- Initial assessment from Stage 1a (only present in Stage 2a — see below)
- Follow-up Q&A answers (only present in Stage 2a)

Gemma 4's system prompt (`GEMMA4_TRIAGE_SYSTEM_PROMPT`) opens with the `<|think|>` token, which activates Gemma 4's chain-of-thought reasoning mode. The model reasons internally before emitting the JSON output; `_parse_triage_json()` strips the thinking block (`<|channel>thought\n...<channel|>`) before parsing. The prompt runs ~100 lines and instructs a **7-step ordered reasoning process**:
1. Demographics — how age and sex shift diagnosis probability
2. Symptoms — each symptom individually and in combination
3. Vitals — threshold crossings (BP, SpO2, HR, temp)
4. Image findings — explicitly state whether specific or vague, and the weight assigned
5. Red-flag check — mandatory pass through the RED FLAG CONDITIONS list
6. Differential — rank by clinical probability; most dangerous included even if less likely
7. Triage level assignment — must be supported by the preceding reasoning

### Confidence-Weighted Image Integration

Gemma 4 is explicitly instructed to apply confidence-gated weights to MedGemma's Visual Impression:
- **HIGH**: Weight named conditions heavily — fold them directly into the top differential
- **MEDIUM**: Use as supporting evidence; confirm against chief complaint and vitals
- **LOW**: Treat as weak context only; prioritize chief complaint and vitals

If chief complaint and a HIGH-confidence MedGemma Visual Impression match, Gemma 4 treats this as high-specificity combined evidence and does not default to generic conditions.

### Red-Flag Rules (in system prompt)

Gemma 4 runs a non-negotiable red-flag check against:
- **Neurological**: Sudden-onset headache + any neurological deficit; unilateral or bilateral sudden numbness/weakness; age 60+ with sudden headache + dizziness + any deficit
- **Cardiovascular**: Chest pain + dyspnea; BP ≥ 180/120 with any symptom; irregular rapid pulse + syncope
- **Respiratory**: SpO2 < 92%; cyanosis; severe dyspnea at rest
- **Trauma/Abdomen**: Major trauma, uncontrolled bleeding, shock signs; board-like rigidity
- **Other**: Unconscious, seizing, anaphylaxis, any condition where delay > 1 hour risks permanent disability

**Escalation rule (hard):** If Stroke, TIA, MI, Sepsis, or Anaphylaxis appears in the top conditions AND symptoms support it → RED is mandatory. Assigning YELLOW to a probable stroke is named in the prompt as a patient safety failure.

### Output Schema

Gemma 4 returns a single JSON object (no markdown, no preamble):

```json
{
  "triage_level": "RED | YELLOW | GREEN",
  "triage_reason": "Short Taglish explanation",
  "soap_summary": {
    "S": "Patient's own verbal report only — no vitals or exam findings",
    "O": "Measurable vitals and physical observations with exact values",
    "A": "Working Dx: [condition] — [specific evidence]. R/O [differential] — [differentiating factor]. English. For the receiving doctor.",
    "P": "Triage level. Specific BHW action. Watch for: named red flags."
  },
  "followup_questions": ["Taglish question 1?", "Taglish question 2?", "Taglish question 3?"],
  "top_conditions": [
    {"rank": 1, "condition": "Exact Diagnosis Name", "plain_explanation": "Taglish explanation"},
    ...up to 5
  ],
  "disclaimer": "For BHW reference only. This is not a doctor's diagnosis."
}
```

**Follow-up questions are co-generated in the same Stage 1a call** — there is no separate question-generation inference. Questions must target genuine clinical information gaps that differentiate the top conditions, in conversational BHW-friendly Taglish, never re-asking about already-stated symptoms or measured vitals.

**Differential rules:** Top conditions must be actual medical diagnoses — never symptoms (Fever, Pain, Dizziness are forbidden as conditions). At least one serious/dangerous condition must be included even if less likely.

### JSON Parsing — `_parse_triage_json()`

1. Strip Gemma 4 thinking block if present (`<|channel>thought\n...<channel|>`)
2. Strip markdown code fences if present
3. `json.loads()` on the cleaned string
4. If `JSONDecodeError` → `_repair_truncated_json()` attempts regex salvage: extracts `triage_level`, `triage_reason`, conditions, questions, and SOAP fields from partial output
5. If repair also fails, or `triage_level ∉ {RED, YELLOW, GREEN}` → `ValueError` is raised and propagates to the caller (`_run_initial_triage` or `_run_refined_triage`), which catches any exception and returns `_build_fallback_with_patient_data(patient_data)`. No retry.

`_build_fallback_with_patient_data()` produces a patient-aware fallback: SOAP fields are auto-populated from available patient data (complaint, Q&A answers, vitals) and `is_fallback: True` is set. The `top_conditions` list is taken from the hardcoded `TRIAGE_FALLBACK` constant ("Unable to assess" × 5). This is distinct from returning `TRIAGE_FALLBACK` directly.

### `is_fallback` and Frontend Behavior

`TriageResponse` includes `is_fallback: bool = False`. It is set to `True` only by `_build_fallback_with_patient_data()`. When the frontend receives `is_fallback: True`, it shows:
- An amber banner: "Hindi ma-process ang AI assessment. Kailangan ng manu-manong pagtukoy ng triage level."
- A manual RED / YELLOW / GREEN selector so the BHW can assign the level themselves

Network failures (`_call_gemma()` throws), malformed JSON that survives repair, and invalid triage levels all route through `_build_fallback_with_patient_data()` and therefore set `is_fallback: True`.

---

## Stage 2a — Gemma 4: Refined Triage

**Trigger:** BHW submits answers to the 3 follow-up questions.
**File:** `app/services/triage_service.py` → `_run_refined_triage()`

`run_triage()` routes here when `followup_answers` is present in patient data.

The prompt is built by the same `build_gemma4_triage_prompt()`, but the patient context now includes two additional blocks:

```
Initial Assessment (before follow-up questions):
- Triage Level: YELLOW
- Top Conditions: Hypertensive Urgency, Anxiety Disorder, Migraine
- Initial SOAP-O: BP: 170/110 mmHg | Temp: 36.8 C | HR: 88 bpm | SpO2: 98%

Follow-up Q&A (use to refine the assessment):
Q: Matagal na ba ang sakit ng ulo — ilang oras o araw?
A: Dalawang araw na
Q: Mayroon bang panghihina o pamamanhid sa mukha, kamay, o paa?
A: Wala
Q: Nagkaroon ba ng pagsusuka o pagbabago ng paningin?
A: Hindi
```

Gemma 4 re-reasons the full differential with this richer context. It may change the triage level, reorder conditions, or revise the SOAP note. `followup_questions` in the response is set to `[]` — the Q&A phase is complete.

After a successful Stage 2a, `enrichment_cache.prefetch()` fires MedGemma enrichment as a **background asyncio task** (`enrichment_cache.py`). The cache key is an MD5 hash of the serialized `top_conditions` list. This pre-warms the enrichment result so PDF generation doesn't wait for MedGemma.

---

## PDF Time — MedGemma: Clinical Enricher

**Trigger:** BHW clicks "Generate PDF." Runs inside `pdf_service.py` via `enrichment_cache.get_or_fetch()`.
**File:** `app/services/medgemma_enrichment_service.py` → `enrich_triage()`
**Call:** Ollama `/api/generate` with `format="json"`, `temperature=0.1`, `num_ctx=4096`, `num_predict=2048`. Acquires `ollama_lock`.

MedGemma receives Gemma 4's final triage output — triage level, reason, top conditions, full SOAP note — and enriches each condition with three physician-facing fields:

- `clinical_summary` — one sentence linking the patient's specific evidence to that diagnosis
- `priority_workup` — 2–3 specific tests (e.g. "Non-contrast CT head, serum tryptase, CBC with differential")
- `red_flags` — 2–3 specific escalation signs (e.g. "stridor, SpO2 < 88%, altered consciousness")

Before calling MedGemma, `enrich_triage()` filters out placeholder conditions (`"Condition 1"`, `"Unable to assess"`) — MedGemma only enriches real diagnoses.

`enrichment_cache.get_or_fetch()` returns the cached result if the Stage 2a prefetch already completed. If not (e.g. BHW generated PDF before prefetch finished), it awaits the result synchronously. If a cached task failed, the entry is deleted and re-run. Enrichment failure is non-fatal — the PDF generates without the clinical notes section and a warning is logged.

---

## Concurrency

Both `_call_gemma()` (Stages 1a and 2a) and `enrich_triage()` (PDF enrichment) acquire `ollama_lock` before posting to Ollama — a shared asyncio semaphore in `app/services/ollama_lock.py` that prevents concurrent model calls from queuing up against a single local Ollama instance.

`analyze_image()` (Stage 0) does **not** acquire the lock. This is intentional: image analysis is a one-shot call that completes before the triage lock window opens, and not acquiring it here prevents a deadlock if image analysis and a concurrent triage are running.

---

## End-to-End Flow

```
BHW captures photo (optional)
        │
        ▼
[Stage 0] MedGemma — visual specialist
  → Outputs 4 sections: Category | Observations | Visual Impression (named conditions) | Confidence
  → Parsed by _parse_medgemma_findings() into structured dict
  → Category used to select IMAGE_CLINICAL_CONTEXT block (domain differentials + red flags)
  → Saved as image_findings on patient record
        │
        ▼
[Stage 1a] Gemma 4 — initial triage
  → Receives: demographics + vitals + complaint + parsed MedGemma block + clinical context
  → 7-step ordered reasoning: demographics → symptoms → vitals → image → red flags → differential → level
  → Applies confidence-gated weights to MedGemma's Visual Impression (HIGH/MEDIUM/LOW)
  → Outputs: triage_level, triage_reason, top_conditions (5), SOAP note, 3 follow-up questions
  → JSON parsed by _parse_triage_json(); fallback chain: json.loads → regex repair → TRIAGE_FALLBACK
        │
        ▼
BHW reads 3 follow-up questions aloud to patient, records answers
        │
        ▼
[Stage 2a] Gemma 4 — refined triage
  → Same prompt structure + initial assessment + Q&A answers
  → Re-reasons full differential; may revise triage level, conditions, SOAP
  → followup_questions set to [] (Q&A complete)
  → Triggers MedGemma enrichment prefetch in background (asyncio task, cache key = MD5 of conditions)
        │
        ├─────────────────────────────────────────────────────────────┐
        │                                                             │
        ▼                                                             ▼
BHW saves patient record                          [Background] MedGemma enrichment
to DB; views result screen                          → Filters placeholder conditions
                                                    → Enriches each real diagnosis:
                                                      clinical_summary, priority_workup, red_flags
                                                    → Cached by conditions MD5 hash
        │
        ▼
BHW generates PDF
  → enrichment_cache.get_or_fetch() returns pre-fetched result (or awaits if not ready)
  → PDF includes: Gemma 4 SOAP note + MedGemma per-condition clinical enrichment
  → Cached to disk; subsequent requests for the same patient serve the file directly
```

---

## Why Gemma 4 as the Clinical Reasoner

**MedGemma's strength is vision, not multi-factor text reasoning.**
MedGemma 4B is fine-tuned on medical images — radiology, pathology, dermatology. Its Stage 0 Visual Impressions are genuinely useful clinical hypotheses when confidence is HIGH. But roughly half of GEMMA's triage cases will have no photo at all, and for those cases there is no reason to expect a 4B vision model to outperform a larger general model on complex multi-factor clinical reasoning.

**The triage prompt is extremely instruction-heavy.**
The Gemma 4 system prompt runs ~100 lines: a 7-step ordered reasoning process, red-flag condition lists with hard escalation rules, few-shot examples (stroke vs hypertensive urgency), differential diagnosis rules, SOAP note format constraints with field-by-field language rules (Taglish vs English per field), and a structured JSON schema. Gemma 4 E4B follows long, complex instruction sets reliably and produces well-formed JSON. Running this on MedGemma 4B would produce more frequent format failures, worse instruction following, and more fallbacks.

**Confidence gating makes the vision contribution safe.**
MedGemma's Visual Impression now does name conditions — but Gemma 4 is the gatekeeper. A HIGH-confidence impression gets heavy weight; a LOW-confidence one is explicitly labeled weak context. This means a blurry or irrelevant field photo cannot push a misdiagnosis — Gemma 4 will downweight it by design. The architecture makes the failure mode of a poor image safe rather than dangerous.

**Separation of concerns keeps clinical accountability clear.**
All triage level decisions go through one model — Gemma 4 — whose reasoning is fully prompt-engineered, validated on few-shot examples, and constrained by hard escalation rules. MedGemma enriches the input (Stage 0) and the output (PDF enrichment) but never touches the triage level. This is a much safer architecture for community health use than one model doing everything.

**Hackathon context.**
The competition is Kaggle × Google DeepMind — Gemma 4 Good. Gemma 4 as the primary reasoning model is a core requirement. MedGemma's role was defined specifically for what it does better than any text model: interpreting field photos taken on a mobile phone in a barangay health center.

---

## Failure Handling

| Point of failure | Behavior |
|---|---|
| MedGemma image analysis fails / empty response | Returns Filipino fallback string; `image_findings` is null; triage proceeds without image evidence |
| MedGemma omits the `Category:` tag | `_extract_image_category()` keyword-scans full text; falls back to OTHER if no match |
| MedGemma Visual Impression = "Cannot determine from image" | Injected explicitly; clinical context block still added for domain guidance; Gemma 4 ignores the visual impression |
| Gemma 4 returns malformed JSON | `_parse_triage_json()` strips thinking block and fences, then `_repair_truncated_json()` regex-salvages what arrived |
| Repair also fails or invalid triage_level | `ValueError` propagates; caller returns `_build_fallback_with_patient_data(patient_data)` — YELLOW, patient-aware SOAP, `is_fallback: True`, "Unable to assess" × 5. No retry. |
| `is_fallback: True` received by frontend | Amber banner displayed; manual RED / YELLOW / GREEN selector shown for BHW to assign triage level |
| MedGemma enrichment fails | PDF generates without clinical notes section; warning logged; non-fatal |
| Ollama unreachable (any stage) | HTTP exception propagates; caller returns `_build_fallback_with_patient_data()` with `is_fallback: True`; frontend shows amber banner |
| PDF already generated for patient | `GET /api/export/pdf/{id}` serves existing file from disk; MedGemma enrichment is NOT re-run |

### Demo: `POST /api/triage/test-fallback`

A dedicated endpoint for demoing the fallback system without triggering a real Ollama call. It feeds the hardcoded broken JSON string (`_STRESS_TEST_BROKEN_JSON`) through the real `_parse_triage_json()` chain, which correctly rejects it, then always returns `_build_fallback_with_patient_data()` with `is_fallback: True`. Safe to call repeatedly. No DB writes.
