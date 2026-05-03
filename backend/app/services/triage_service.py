import json
import logging

from langchain_ollama import OllamaLLM

from app.core.config import settings
from app.prompts.triage_prompt import (
    TRIAGE_FALLBACK,
    build_gemma4_triage_prompt,
    build_gemma_followup_prompt,
)

logger = logging.getLogger(__name__)

# Stage 1a / 2a — Gemma 4 as primary clinical reasoning engine
# Higher token budget for full triage JSON; lower temperature for determinism
_gemma_triage_llm: OllamaLLM | None = None

# Stage 1b — Gemma 4 for follow-up question generation (tiny output)
_gemma_questions_llm: OllamaLLM | None = None

_DEFAULT_FOLLOWUP = [
    "Gaano na katagal ang mga sintomas mo?",
    "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
    "Allergic ka ba sa kahit anong gamot?",
]
_DEFAULT_DISCLAIMER = "For BHW reference only. This is not a doctor's diagnosis."


def _get_gemma_triage_llm() -> OllamaLLM:
    global _gemma_triage_llm
    if _gemma_triage_llm is None:
        _gemma_triage_llm = OllamaLLM(
            model=settings.GEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.2,
            format="json",
            num_ctx=8192,
            num_predict=2048,
        )
    return _gemma_triage_llm


def _get_gemma_questions_llm() -> OllamaLLM:
    global _gemma_questions_llm
    if _gemma_questions_llm is None:
        _gemma_questions_llm = OllamaLLM(
            model=settings.GEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.35,
            format="json",
            num_ctx=4096,
            num_predict=512,
        )
    return _gemma_questions_llm


def _parse_triage_json(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1].lstrip("json").strip()
    result = json.loads(clean)
    if result.get("triage_level") not in {"RED", "YELLOW", "GREEN"}:
        raise ValueError(f"Invalid triage level: {result.get('triage_level')}")
    return result


def _format_triage_for_followup(triage: dict) -> str:
    conditions = "\n".join(
        f"{c['rank']}. {c['condition']} — {c['plain_explanation']}"
        for c in triage.get("top_conditions", [])
    )
    return (
        f"Triage Level: {triage.get('triage_level', '')}\n"
        f"Reason: {triage.get('triage_reason', '')}\n"
        f"Top Conditions:\n{conditions}"
    )


async def _run_initial_triage(patient_data: dict) -> dict:
    """
    Stage 1a: Gemma 4 -> full triage JSON (conditions, triage level, SOAP)
    Stage 1b: Gemma 4 -> 3 Taglish follow-up questions
    """
    triage_llm = _get_gemma_triage_llm()
    questions_llm = _get_gemma_questions_llm()

    try:
        # Stage 1a — Gemma 4 clinical reasoning
        triage_prompt = build_gemma4_triage_prompt(patient_data)
        raw = await triage_llm.ainvoke(triage_prompt)
        logger.info(f"[Stage 1a] Gemma 4 triage ({len(raw)} chars)")
        logger.debug(f"[Stage 1a] Gemma 4 output:\n{raw}")

        result = _parse_triage_json(raw)

        # Stage 1b — Gemma 4 follow-up question generation
        clinical_summary = _format_triage_for_followup(result)
        followup_prompt = build_gemma_followup_prompt(clinical_summary, patient_data)
        raw_qs = await questions_llm.ainvoke(followup_prompt)
        logger.info(f"[Stage 1b] Gemma 4 questions raw: {raw_qs[:300]}")

        try:
            clean_qs = raw_qs.strip()
            if clean_qs.startswith("```"):
                clean_qs = clean_qs.split("```")[1].lstrip("json").strip()
            data = json.loads(clean_qs)
            if isinstance(data, dict):
                raw_list = data.get("questions") or data.get("followup_questions") or []
            elif isinstance(data, list):
                raw_list = data
            else:
                raise ValueError(f"Unexpected type: {type(data)}")
            questions = [str(q).strip() for q in raw_list if str(q).strip()][:3]
            if not questions:
                raise ValueError("Empty after filtering")
        except Exception as qe:
            logger.warning(f"[Stage 1b] Question parse failed ({qe}), using defaults")
            questions = _DEFAULT_FOLLOWUP

        result["followup_questions"] = questions if questions else _DEFAULT_FOLLOWUP
        logger.info(f"Initial triage done: level={result['triage_level']}, qs={len(result['followup_questions'])}")
        return result

    except Exception as e:
        logger.error(f"Initial triage failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK


async def _run_refined_triage(patient_data: dict) -> dict:
    """
    Stage 2a: Gemma 4 -> refined triage JSON using Q&A answers
    No follow-up questions generated — Q&A phase is complete.
    """
    triage_llm = _get_gemma_triage_llm()

    try:
        triage_prompt = build_gemma4_triage_prompt(patient_data)
        raw = await triage_llm.ainvoke(triage_prompt)
        logger.info(f"[Stage 2a] Gemma 4 refined triage ({len(raw)} chars)")
        logger.debug(f"[Stage 2a] Gemma 4 output:\n{raw}")

        result = _parse_triage_json(raw)
        result["followup_questions"] = []
        logger.info(f"Refined triage done: level={result['triage_level']}")
        return result

    except Exception as e:
        logger.error(f"Refined triage failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK


async def run_triage(patient_data: dict) -> dict:
    """
    Routes to the correct pipeline stage based on whether follow-up answers exist.

    Initial triage  (no followup_answers): Stage 1a Gemma 4 -> Stage 1b Gemma 4 Qs
    Refined triage  (has followup_answers): Stage 2a Gemma 4 (no question step)
    """
    if patient_data.get("followup_answers"):
        return await _run_refined_triage(patient_data)
    return await _run_initial_triage(patient_data)
