"""
GEMMA AI Triage Pipeline — Core orchestration module.

Implements the two-stage Gemma 4 E4B triage workflow that powers GEMMA's
decision-support system for Barangay Health Workers (BHWs):

  Stage 1a — Initial triage:
    Single Gemma 4 call → full triage JSON (triage_level, top_conditions,
    followup_questions, SOAP note). Questions are generated in the same
    inference as the clinical assessment, eliminating a separate round-trip.

  Stage 2a — Refined triage (after BHW answers follow-up questions):
    Second Gemma 4 call with Q&A answers appended → updated triage JSON.
    Immediately triggers a background MedGemma enrichment prefetch so the PDF
    physician section is ready by the time the BHW clicks "Generate PDF".

MedGemma (image analysis and PDF enrichment) is coordinated via:
  image_service.py    — Stage 0, optional visual assessment before Stage 1a
  enrichment_cache.py — background prefetch after Stage 2a

All Ollama calls use direct httpx POST to /api/generate with format="json"
to guarantee num_predict and num_ctx are honoured. LangChain OllamaLLM
silently ignores these parameters, which caused output truncation in testing.

Fallback safety: any JSON parse or validation failure triggers
_build_fallback_with_patient_data(), which returns is_fallback=True so the
frontend surfaces an amber banner and a manual RED/YELLOW/GREEN selector,
keeping the BHW operational even if the model is unreachable.
"""
import json
import logging
import re
import time

import httpx

from app.core.config import settings
from app.services import ollama_lock
from app.prompts.triage_prompt import (
    TRIAGE_FALLBACK,
    build_gemma4_triage_prompt,
)

logger = logging.getLogger(__name__)


def _stage_header(stage: str, description: str) -> None:
    line = f"  GEMMA PIPELINE │ {stage}: {description}"
    border = "─" * max(60, len(line) + 2)
    logger.info(f"\n┌{border}┐\n│{line.ljust(len(border))}│\n└{border}┘")

_DEFAULT_FOLLOWUP = [
    "Gaano na katagal ang mga sintomas mo?",
    "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
    "Allergic ka ba sa kahit anong gamot?",
]
_DEFAULT_DISCLAIMER = "For BHW reference only. This is not a doctor's diagnosis."
_STRESS_TEST_BROKEN_JSON = '{ triage_level: BANANA, top_conditions: [[[}'


def _build_fallback_with_patient_data(patient_data: dict) -> dict:
    """Return TRIAGE_FALLBACK enriched with available patient data and is_fallback flag."""
    complaint = patient_data.get("chief_complaint") or "Not recorded."
    answers = patient_data.get("followup_answers") or {}

    s_parts = [f"Chief complaint: {complaint}"]
    if answers:
        for q, a in answers.items():
            s_parts.append(f"Q: {q} — A: {a or 'No answer.'}")
    soap_s = " | ".join(s_parts)

    vitals = []
    if patient_data.get("bp"):
        vitals.append(f"BP: {patient_data['bp']}")
    if patient_data.get("temperature"):
        temp_val = str(patient_data['temperature']).rstrip('C').rstrip('°').rstrip()
        vitals.append(f"Temp: {temp_val}°C")
    if patient_data.get("heart_rate"):
        vitals.append(f"HR: {patient_data['heart_rate']} bpm")
    if patient_data.get("spo2"):
        vitals.append(f"SpO2: {patient_data['spo2']}%")
    if patient_data.get("age"):
        vitals.append(f"Age: {patient_data['age']}")
    if patient_data.get("sex"):
        vitals.append(f"Sex: {patient_data['sex']}")
    soap_o = ", ".join(vitals) if vitals else "No vitals recorded."

    return {
        "triage_level": "YELLOW",
        "triage_reason": "Hindi ma-process ang AI assessment. Kailangan ng manu-manong pagtukoy ng triage level.",
        "is_fallback": True,
        "top_conditions": TRIAGE_FALLBACK["top_conditions"],
        "followup_questions": list(TRIAGE_FALLBACK["followup_questions"]),
        "soap_summary": {
            "S": soap_s,
            "O": soap_o,
            "A": "AI assessment failed — triage level assigned manually by BHW.",
            "P": "Refer to physician for evaluation. Manual triage level pending BHW selection.",
        },
        "disclaimer": _DEFAULT_DISCLAIMER,
    }


async def _call_gemma(
    prompt: str,
    num_predict: int = 4096,
    num_ctx: int = 8192,
    temperature: float = 1.0,
) -> str:
    """Direct Ollama API call — guarantees num_predict and num_ctx are honored."""
    logger.info(
        f"  → Sending prompt to {settings.GEMMA_MODEL} "
        f"({len(prompt)} chars | num_predict={num_predict} | temp={temperature})"
    )
    t0 = time.perf_counter()
    async with ollama_lock.get():
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.GEMMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": temperature,
                        "top_p": 0.95,
                        "top_k": 64,
                        "num_ctx": num_ctx,
                        "num_predict": num_predict,
                    },
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
    elapsed = time.perf_counter() - t0
    logger.info(f"  ✓ {settings.GEMMA_MODEL} responded in {elapsed:.2f}s — {len(raw)} chars returned")
    return raw


def _normalize_condition(c: dict, idx: int) -> dict:
    """
    Normalise a condition entry from Gemma 4 output into the canonical schema.

    Gemma 4 occasionally uses alternate field names (e.g. "name", "diagnosis",
    "disease") despite the prompt specifying "condition". This function maps all
    observed variants to the standard {"rank", "condition", "plain_explanation"}
    shape expected by the frontend and PDF generator.
    """
    if not isinstance(c, dict):
        return {"rank": idx + 1, "condition": f"Condition {idx + 1}", "plain_explanation": ""}
    condition = (
        c.get("condition") or c.get("name") or c.get("diagnosis")
        or c.get("condition_name") or c.get("conditionName")
        or c.get("disease") or c.get("disease_name")
        or c.get("Condition") or c.get("Name")
        or f"Condition {idx + 1}"
    )
    explanation = (
        c.get("plain_explanation") or c.get("explanation")
        or c.get("description") or c.get("details")
        or c.get("plain_Explanation") or ""
    )
    try:
        rank = int(c.get("rank") or (idx + 1))
    except (ValueError, TypeError):
        rank = idx + 1
    return {"rank": rank, "condition": condition, "plain_explanation": explanation}


def _repair_truncated_json(raw: str) -> dict:
    """Salvage a truncated triage response by regex-extracting what arrived."""
    level_m = re.search(r'"triage_level"\s*:\s*"(RED|YELLOW|GREEN)"', raw)
    if not level_m:
        raise ValueError("triage_level missing from truncated output")
    triage_level = level_m.group(1)

    reason_m = re.search(r'"triage_reason"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    triage_reason = reason_m.group(1) if reason_m else ""

    conditions = []
    for m in re.finditer(
        r'"rank"\s*:\s*(\d+)\s*,\s*"condition"\s*:\s*"((?:[^"\\]|\\.)+)"\s*,\s*"plain_explanation"\s*:\s*"((?:[^"\\]|\\.)*)"',
        raw,
    ):
        conditions.append({
            "rank": int(m.group(1)),
            "condition": m.group(2),
            "plain_explanation": m.group(3),
        })

    # Try to rescue followup questions
    questions = []
    fq_m = re.search(r'"followup_questions"\s*:\s*\[(.*?)\]', raw, re.DOTALL)
    if fq_m:
        for q in re.finditer(r'"((?:[^"\\]|\\.)+)"', fq_m.group(1)):
            questions.append(q.group(1))

    # Try to rescue SOAP fields
    def _soap_field(key: str) -> str:
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        return m.group(1) if m else ""

    soap_s = _soap_field("S")
    soap_o = _soap_field("O")
    soap_a = _soap_field("A")
    soap_p = _soap_field("P")

    if not any([soap_s, soap_o, soap_a, soap_p]):
        soap_s = "See chief complaint and follow-up Q&A above."
        soap_o = "See vitals in patient information above."
        soap_a = f"See top conditions above (SOAP not generated — output truncated)."
        soap_p = f"Triage level: {triage_level}. Refer to triage reason above."

    logger.warning(
        f"Repaired truncated JSON: level={triage_level}, "
        f"conditions rescued={len(conditions)}, soap_rescued={bool(soap_s and soap_a)}"
    )
    return {
        "triage_level": triage_level,
        "triage_reason": triage_reason,
        "top_conditions": conditions,
        "followup_questions": questions or _DEFAULT_FOLLOWUP,
        "soap_summary": {"S": soap_s, "O": soap_o, "A": soap_a, "P": soap_p},
        "disclaimer": _DEFAULT_DISCLAIMER,
    }


def _parse_triage_json(raw: str) -> dict:
    """
    Parse and validate raw JSON output from Gemma 4.

    Handles three common Gemma 4 output quirks:
      1. Thinking blocks:  <|channel>thought\\n...<channel|> prefixes stripped
      2. Markdown fences:  ```json ... ``` wrappers stripped
      3. Truncated output: falls back to _repair_truncated_json() which
         regex-extracts whatever fields arrived before the cutoff

    Raises ValueError if triage_level is not one of RED, YELLOW, GREEN —
    the caller catches this and activates the patient-data fallback.
    """
    clean = raw.strip()
    # Strip Gemma 4 thinking block if present: <|channel>thought\n...<channel|>
    clean = re.sub(r'<\|channel>thought\n.*?<channel\|>\s*', '', clean, flags=re.DOTALL).strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1].lstrip("json").strip()
    if not clean.startswith("{"):
        start = clean.find("{")
        if start != -1:
            clean = clean[start:]
    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        result = _repair_truncated_json(clean)

    if result.get("triage_level") not in {"RED", "YELLOW", "GREEN"}:
        raise ValueError(f"Invalid triage level: {result.get('triage_level')}")

    result["top_conditions"] = [
        _normalize_condition(c, i)
        for i, c in enumerate(result.get("top_conditions") or [])
    ]

    # Ensure followup_questions is a clean list of strings
    raw_qs = result.get("followup_questions") or []
    if isinstance(raw_qs, list):
        questions = [str(q).strip() for q in raw_qs if str(q).strip()][:3]
        result["followup_questions"] = questions if questions else _DEFAULT_FOLLOWUP
    else:
        result["followup_questions"] = _DEFAULT_FOLLOWUP

    if not result.get("disclaimer"):
        result["disclaimer"] = _DEFAULT_DISCLAIMER
    return result


async def _run_initial_triage(patient_data: dict) -> dict:
    """
    Stage 1a: single Gemma 4 call → full triage JSON including followup_questions.
    followup_questions are now generated in the same inference as the triage,
    eliminating the separate Stage 1b call.
    """
    _stage_header("Stage 1a", "Initial Triage Assessment — Gemma 4 E4B")
    complaint = (patient_data.get("chief_complaint") or "")[:80]
    age = patient_data.get("age") or "?"
    sex = patient_data.get("sex") or "?"
    vitals = []
    if patient_data.get("bp"):
        vitals.append(f"BP={patient_data['bp']}")
    if patient_data.get("temperature"):
        vitals.append(f"Temp={patient_data['temperature']}")
    if patient_data.get("heart_rate"):
        vitals.append(f"HR={patient_data['heart_rate']}")
    if patient_data.get("spo2"):
        vitals.append(f"SpO2={patient_data['spo2']}%")
    if patient_data.get("image_findings"):
        vitals.append("image_findings=YES")
    logger.info(f"  → Patient  : age={age}, sex={sex}, complaint=\"{complaint}\"")
    if vitals:
        logger.info(f"  → Vitals   : {', '.join(vitals)}")

    t0 = time.perf_counter()
    try:
        triage_prompt = build_gemma4_triage_prompt(patient_data)
        raw = await _call_gemma(triage_prompt, num_predict=4096, num_ctx=8192, temperature=1.0)

        parse_t0 = time.perf_counter()
        result = _parse_triage_json(raw)
        logger.info(f"  → JSON parsed in {time.perf_counter() - parse_t0:.3f}s")

        elapsed = time.perf_counter() - t0
        level = result["triage_level"]
        top1 = result["top_conditions"][0]["condition"] if result.get("top_conditions") else "N/A"
        num_qs = len(result.get("followup_questions") or [])
        logger.info(
            f"  ✓ Stage 1a complete in {elapsed:.2f}s\n"
            f"    Triage level   : {level}\n"
            f"    Top condition  : {top1}\n"
            f"    Follow-up Qs   : {num_qs} generated"
        )
        return result

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(f"  ✗ Stage 1a failed after {elapsed:.2f}s: {e} — activating fallback")
        return _build_fallback_with_patient_data(patient_data)


async def _run_refined_triage(patient_data: dict) -> dict:
    """
    Stage 2a: Gemma 4 refined triage using Q&A answers.
    Kicks off MedGemma enrichment prefetch as a background task so PDF
    generation can use the cached result instead of waiting.
    """
    _stage_header("Stage 2a", "Refined Triage with Q&A Answers — Gemma 4 E4B")
    qa = patient_data.get("followup_answers") or {}
    logger.info(f"  → Q&A answers received: {len(qa)} responses")
    for q, a in list(qa.items())[:3]:
        logger.info(f"    Q: {str(q)[:60]}  →  A: {str(a)[:60]}")

    t0 = time.perf_counter()
    try:
        triage_prompt = build_gemma4_triage_prompt(patient_data)
        raw = await _call_gemma(triage_prompt, num_predict=4096, num_ctx=8192, temperature=1.0)

        parse_t0 = time.perf_counter()
        result = _parse_triage_json(raw)
        logger.info(f"  → JSON parsed in {time.perf_counter() - parse_t0:.3f}s")

        result["followup_questions"] = []
        elapsed = time.perf_counter() - t0
        level = result["triage_level"]
        top1 = result["top_conditions"][0]["condition"] if result.get("top_conditions") else "N/A"
        logger.info(
            f"  ✓ Stage 2a complete in {elapsed:.2f}s\n"
            f"    Final triage level : {level}\n"
            f"    Top condition      : {top1}\n"
            f"    SOAP note          : generated"
        )

        logger.info("  → Launching MedGemma enrichment prefetch in background (for PDF)…")
        try:
            from app.services.enrichment_cache import prefetch
            prefetch(result)
            logger.info("  ✓ Enrichment prefetch task started")
        except Exception as cache_err:
            logger.warning(f"  ⚠ Enrichment prefetch failed to start: {cache_err}")

        return result

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(f"  ✗ Stage 2a failed after {elapsed:.2f}s: {e} — activating fallback")
        return _build_fallback_with_patient_data(patient_data)


async def run_triage(patient_data: dict) -> dict:
    """
    Routes to the correct pipeline stage.
    Initial triage (no followup_answers): Stage 1a only — questions included in same call.
    Refined triage (has followup_answers): Stage 2a + background enrichment prefetch.
    """
    stage = "Stage 2a (refined)" if patient_data.get("followup_answers") else "Stage 1a (initial)"
    logger.info(f"  ▶ run_triage called → routing to {stage}")
    if patient_data.get("followup_answers"):
        return await _run_refined_triage(patient_data)
    return await _run_initial_triage(patient_data)


async def run_fallback_stress_test(patient_data: dict) -> dict:
    """
    Feeds deliberately broken JSON through the real _parse_triage_json chain to
    demonstrate the two-layer parser (json.loads → _repair_truncated_json → ValueError).
    Always returns _build_fallback_with_patient_data regardless of parse outcome —
    this is intentional: the endpoint exists to showcase the fallback UI, not produce
    a real triage.
    """
    broken = _STRESS_TEST_BROKEN_JSON
    try:
        _parse_triage_json(broken)
    except Exception as e:
        logger.warning(f"[stress-test] Parser correctly rejected broken input: {e}")
    return _build_fallback_with_patient_data(patient_data)
