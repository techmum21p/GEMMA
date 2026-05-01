import json
import logging

from langchain_ollama import OllamaLLM
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.prompts.triage_prompt import TRIAGE_SYSTEM_PROMPT, build_triage_prompt, TRIAGE_FALLBACK

logger = logging.getLogger(__name__)

_llm: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=settings.GEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
            format="json",
        )
    return _llm


def _parse_triage_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)

    required_keys = {"triage_level", "triage_reason", "top_conditions", "followup_questions", "soap_summary", "disclaimer"}
    if not required_keys.issubset(data.keys()):
        raise ValueError(f"Missing required keys: {required_keys - data.keys()}")

    if data["triage_level"] not in {"RED", "YELLOW", "GREEN"}:
        data["triage_level"] = "YELLOW"

    if len(data.get("top_conditions", [])) < 5:
        raise ValueError("top_conditions must have 5 entries")

    return data


async def run_triage(
    chief_complaint: str,
    image_findings: str | None = None,
    followup_answers: dict | None = None,
) -> dict:
    llm = _get_llm()
    user_prompt = build_triage_prompt(chief_complaint, image_findings, followup_answers)

    full_prompt = f"{TRIAGE_SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        raw = await llm.ainvoke(full_prompt)
        result = _parse_triage_response(raw)
        return result
    except Exception as e:
        logger.warning(f"Triage attempt 1 failed: {e}. Retrying...")

    try:
        raw = await llm.ainvoke(full_prompt + "\n\nIMPORTANT: Output valid JSON only, no extra text.")
        result = _parse_triage_response(raw)
        return result
    except Exception as e:
        logger.error(f"Triage retry also failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK
