import json
import logging
import re

import httpx

from app.core.config import settings
from app.services import ollama_lock
from app.prompts.triage_prompt import (
    TRIAGE_FALLBACK,
    build_gemma4_triage_prompt,
)

logger = logging.getLogger(__name__)

_DEFAULT_FOLLOWUP = [
    "Gaano na katagal ang mga sintomas mo?",
    "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
    "Allergic ka ba sa kahit anong gamot?",
]
_DEFAULT_DISCLAIMER = "For BHW reference only. This is not a doctor's diagnosis."


def _build_fallback_with_patient_data(patient_data: dict) -> dict:
    """Return TRIAGE_FALLBACK enriched with available patient data and is_fallback flag."""
    complaint = patient_data.get("chief_complaint") or "Not recorded."
    answers = patient_data.get("followup_answers") or {}

    s_parts = [f"Chief complaint: {complaint}"]
    if answers:
        for q, a in answers.items():
            s_parts.append(f"Q: {q} — A: {a}")
    soap_s = " | ".join(s_parts)

    vitals = []
    if patient_data.get("bp"):
        vitals.append(f"BP: {patient_data['bp']}")
    if patient_data.get("temperature"):
        vitals.append(f"Temp: {patient_data['temperature']}°C")
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
        "followup_questions": TRIAGE_FALLBACK["followup_questions"],
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
            return resp.json().get("response", "").strip()


def _normalize_condition(c: dict, idx: int) -> dict:
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
    try:
        triage_prompt = build_gemma4_triage_prompt(patient_data)
        raw = await _call_gemma(triage_prompt, num_predict=4096, num_ctx=8192, temperature=1.0)
        logger.info(f"[Stage 1a] Gemma 4 triage ({len(raw)} chars): {raw[:500]}")

        result = _parse_triage_json(raw)
        logger.info(
            f"Initial triage done: level={result['triage_level']}, "
            f"qs={len(result['followup_questions'])}"
        )
        return result

    except Exception as e:
        logger.error(f"Initial triage failed: {e}. Returning fallback.")
        return _build_fallback_with_patient_data(patient_data)


async def _run_refined_triage(patient_data: dict) -> dict:
    """
    Stage 2a: Gemma 4 refined triage using Q&A answers.
    Kicks off MedGemma enrichment prefetch as a background task so PDF
    generation can use the cached result instead of waiting.
    """
    try:
        triage_prompt = build_gemma4_triage_prompt(patient_data)
        raw = await _call_gemma(triage_prompt, num_predict=4096, num_ctx=8192, temperature=1.0)
        logger.info(f"[Stage 2a] Gemma 4 refined triage ({len(raw)} chars): {raw[:500]}")

        result = _parse_triage_json(raw)
        result["followup_questions"] = []  # Q&A phase complete
        logger.info(f"Refined triage done: level={result['triage_level']}")

        # Pre-fetch MedGemma enrichment in background — PDF will use cache
        try:
            from app.services.enrichment_cache import prefetch
            prefetch(result)
        except Exception as cache_err:
            logger.warning(f"Enrichment prefetch failed to start: {cache_err}")

        return result

    except Exception as e:
        logger.error(f"Refined triage failed: {e}. Returning fallback.")
        return _build_fallback_with_patient_data(patient_data)


async def run_triage(patient_data: dict) -> dict:
    """
    Routes to the correct pipeline stage.
    Initial triage (no followup_answers): Stage 1a only — questions included in same call.
    Refined triage (has followup_answers): Stage 2a + background enrichment prefetch.
    """
    if patient_data.get("followup_answers"):
        return await _run_refined_triage(patient_data)
    return await _run_initial_triage(patient_data)
