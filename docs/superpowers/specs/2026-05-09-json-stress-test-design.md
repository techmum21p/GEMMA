# JSON Stress Test & Safe Manual Fallback — Design Spec
**Date:** 2026-05-09
**Branch:** feat-tuning-gemma4

---

## Problem

When Gemma 4 returns malformed JSON or a hallucinated triage level, `TRIAGE_FALLBACK` fires silently. The BHW sees a YELLOW badge with "Unable to assess" conditions but has no indication the AI failed, no way to override it manually, and no live demo trigger exists to prove the safety net works for judges.

---

## Goal

1. Make AI failure **visible and recoverable** — BHW assigns the level manually.
2. Give the demo a **one-click stress-test trigger** that exercises the real production fallback chain end-to-end.
3. Ensure the fallback patient record is **still clinically useful** — auto-populated SOAP from entered data.

---

## Architecture

### Backend

#### `_build_fallback_with_patient_data(patient_data: dict) -> dict`
New helper in `triage_service.py`. Called wherever `TRIAGE_FALLBACK` was previously returned.

- Constructs SOAP from entered patient data:
  - `S` — chief complaint + any answered follow-up Q&A
  - `O` — BP, temperature, age, sex (whatever was entered)
  - `A` — "AI assessment failed — triage level assigned manually by BHW"
  - `P` — "Refer to physician for evaluation. Manual triage pending BHW input."
- Sets `triage_level = "YELLOW"` as safe default (BHW overrides in UI)
- Adds `is_fallback: true` to the response dict
- All other fields (`top_conditions`, `followup_questions`, `disclaimer`) carry over from `TRIAGE_FALLBACK` template

#### `run_fallback_stress_test(patient_data: dict) -> dict`
New function in `triage_service.py`.

- Feeds a deliberately broken string (`"{ triage_level: BANANA, top_conditions: [[[}"`) through the real `_parse_triage_json()` pipeline
- Catches the exception and calls `_build_fallback_with_patient_data(patient_data)`
- Returns the same response shape as a normal triage call
- No DB writes, no side effects

#### `POST /api/triage/test-fallback`
New route in `app/api/routes/triage.py`.

- Accepts optional JSON body with patient data (name, age, complaint, vitals)
- Calls `run_fallback_stress_test()`
- Returns response with `is_fallback: true`
- No auth required, idempotent, safe for demo use

#### Call sites updated
Both `_run_initial_triage()` and `_run_refined_triage()` replace their bare `return TRIAGE_FALLBACK` with `return _build_fallback_with_patient_data(patient_data)`.

---

### Frontend

#### `screen-result` — fallback detection
After triage API response arrives, JS checks `data.is_fallback === true`.

**If fallback:**
- Hide normal AI result content (triage badge, top-conditions list)
- Show full-width amber banner: `"AI Assessment Failed — Please assign the triage level manually"`
- Render three large tap buttons: **RED** / **YELLOW** / **GREEN** (min 64px height, same color coding as normal badges)
- Save Patient button disabled until one level is tapped
- On tap: selected level stored in app state, replaces `data.triage_level` before patient save

**Always visible in fallback mode:**
- SOAP note section (auto-populated from patient data by backend) — BHW can confirm captured data is correct before saving

#### Demo trigger — "Stress Test" button
- Added at the bottom of `screen-intake`, styled as a subtle text link (`text-xs text-gray-400 underline`)
- Label: `"Simulate AI Failure"`
- On click: calls `POST /api/triage/test-fallback` with currently entered patient data
- Result routes through the same `screen-result` fallback UI path

---

## Data Flow

```
[BHW fills intake form]
        │
        ▼
POST /api/triage/test-fallback   ← demo trigger
        │
        ▼
run_fallback_stress_test()
  → _parse_triage_json("{ BANANA [[[")
  → JSONDecodeError + invalid level
  → _build_fallback_with_patient_data(patient_data)
        │
        ▼
Response: { is_fallback: true, triage_level: "YELLOW", soap_summary: {...}, ... }
        │
        ▼
Frontend detects is_fallback
  → hides AI result
  → shows amber banner + RED/YELLOW/GREEN selector
        │
        ▼
BHW taps a level → Save Patient
  → patient saved with manual triage_level + auto-populated SOAP
```

---

## What Gets Saved

When BHW saves after manual selection:
- `triage_level` = BHW-chosen level (RED / YELLOW / GREEN)
- `handoff_summary` = SOAP auto-populated from patient data
- `top_conditions` = fallback template ("Unable to assess" × 5)
- `image_findings` = unchanged (if image was uploaded, MedGemma findings are preserved)
- `followup_qa` = any Q&A answers already captured

---

## Error Handling

- If `test-fallback` endpoint itself errors (e.g. import failure), return HTTP 500 with plain message — do not silently swallow
- If BHW somehow reaches Save without selecting a level (JS guard fails), backend validates `triage_level` ∈ {RED, YELLOW, GREEN} in the patient save schema — rejects with 422

---

## Out of Scope

- Retry logic (call Ollama again after fallback) — CLAUDE.md: "fallback immediately, no retry"
- Free-text BHW assessment note
- Logging the fallback to a separate audit table
