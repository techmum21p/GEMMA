import json
import logging

from langchain_ollama import OllamaLLM

from app.core.config import settings
from app.prompts.triage_prompt import (
    TRIAGE_FALLBACK,
    build_format_prompt,
    build_medgemma_prompt,
)

logger = logging.getLogger(__name__)

_medgemma_llm: OllamaLLM | None = None
_gemma_llm: OllamaLLM | None = None

_DEFAULT_FOLLOWUP = [
    "Gaano na katagal ang mga sintomas mo?",
    "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
    "Allergic ka ba sa kahit anong gamot?",
]
_DEFAULT_DISCLAIMER = "For BHW reference only. This is not a doctor's diagnosis."


def _get_medgemma_llm() -> OllamaLLM:
    global _medgemma_llm
    if _medgemma_llm is None:
        _medgemma_llm = OllamaLLM(
            model=settings.MEDGEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.2,
            num_ctx=4096,
            num_predict=2048,
        )
    return _medgemma_llm


def _get_gemma_llm() -> OllamaLLM:
    global _gemma_llm
    if _gemma_llm is None:
        _gemma_llm = OllamaLLM(
            model=settings.GEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
            format="json",
            num_ctx=8192,
            num_predict=4096,
        )
    return _gemma_llm


def _repair_truncated_json(raw: str) -> dict:
    """
    Handle truncation where the model runs out of tokens mid-string.
    Finds the last clean comma at depth 1 and closes the object there.
    """
    depth = 0
    in_string = False
    last_comma_at_depth_1 = -1
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == '"' and (i == 0 or raw[i - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if c in ("{", "["):
                depth += 1
            elif c in ("}", "]"):
                depth -= 1
            elif c == "," and depth == 1:
                last_comma_at_depth_1 = i
        i += 1

    if last_comma_at_depth_1 > 0:
        candidate = raw[:last_comma_at_depth_1].rstrip() + "\n}"
        return json.loads(candidate)
    raise ValueError("JSON repair found no recovery point")


def _parse_triage_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), attempting truncation repair…")
        data = _repair_truncated_json(raw)

    critical = {"triage_level", "top_conditions", "soap_summary"}
    missing_critical = critical - data.keys()
    if missing_critical:
        raise ValueError(f"Missing critical keys: {missing_critical}")

    data.setdefault("triage_reason", "Assessment based on available information.")
    data.setdefault("followup_questions", _DEFAULT_FOLLOWUP)
    data.setdefault("disclaimer", _DEFAULT_DISCLAIMER)

    if data["triage_level"] not in {"RED", "YELLOW", "GREEN"}:
        data["triage_level"] = "YELLOW"

    raw_conditions = data.get("top_conditions", [])
    conditions = []
    for i, item in enumerate(raw_conditions):
        rank_val = item.get("rank")
        condition_val = item.get("condition")
        if isinstance(rank_val, str) and not condition_val:
            conditions.append({
                "rank": i + 1,
                "condition": rank_val,
                "plain_explanation": item.get("plain_explanation", "Kailangan ng karagdagang pagsusuri ng doktor."),
            })
        else:
            try:
                rank_int = int(rank_val)
            except (TypeError, ValueError):
                rank_int = i + 1
            conditions.append({
                "rank": rank_int,
                "condition": condition_val or "Additional assessment needed",
                "plain_explanation": item.get("plain_explanation", "Kailangan ng karagdagang pagsusuri ng doktor."),
            })

    while len(conditions) < 5:
        rank = len(conditions) + 1
        conditions.append({
            "rank": rank,
            "condition": "Additional assessment needed",
            "plain_explanation": "Kailangan ng karagdagang pagsusuri ng doktor.",
        })
    data["top_conditions"] = conditions[:5]

    return data


async def run_triage(patient_data: dict) -> dict:
    """
    Two-stage pipeline:
      Stage 1 — MedGemma: clinical reasoning from structured patient dict → plain text
      Stage 2 — Gemma: format plain text clinical assessment → strict JSON
    """
    medgemma = _get_medgemma_llm()
    gemma = _get_gemma_llm()

    medgemma_prompt = build_medgemma_prompt(patient_data)

    try:
        clinical_text = await medgemma.ainvoke(medgemma_prompt)
        logger.info(f"MedGemma clinical analysis ({len(clinical_text)} chars)")

        raw_json = await gemma.ainvoke(build_format_prompt(clinical_text))
        result = _parse_triage_response(raw_json)
        logger.info(f"Triage succeeded: level={result['triage_level']}, conditions={len(result.get('top_conditions', []))}")
        return result
    except Exception as e:
        logger.warning(f"Triage attempt 1 failed: {e}. Retrying…")

    try:
        clinical_text = await medgemma.ainvoke(medgemma_prompt)
        format_prompt = (
            build_format_prompt(clinical_text)
            + "\n\nCRITICAL: Output ONLY the JSON object. Close all brackets and braces properly."
        )
        raw_json = await gemma.ainvoke(format_prompt)
        result = _parse_triage_response(raw_json)
        logger.info(f"Triage retry succeeded: level={result['triage_level']}")
        return result
    except Exception as e:
        logger.error(f"Triage retry also failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK
