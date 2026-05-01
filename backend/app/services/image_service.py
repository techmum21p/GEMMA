import base64
import logging
from pathlib import Path

from langchain_ollama import OllamaLLM

from app.core.config import settings
from app.prompts.image_prompt import IMAGE_SYSTEM_PROMPT, build_image_prompt

logger = logging.getLogger(__name__)

_llm: OllamaLLM | None = None


def _get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=settings.MEDGEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
        )
    return _llm


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def analyze_image(image_path: str, chief_complaint: str) -> str:
    llm = _get_llm()
    user_prompt = build_image_prompt(chief_complaint)

    try:
        b64 = _encode_image(image_path)
        full_prompt = (
            f"{IMAGE_SYSTEM_PROMPT}\n\n"
            f"{user_prompt}\n\n"
            f"[IMAGE_DATA:base64:{b64}]"
        )
        findings = await llm.ainvoke(full_prompt)
        return findings.strip()
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return "Hindi ma-analyze ang larawan. Mangyaring ilarawan ng BHW ang nakita."
