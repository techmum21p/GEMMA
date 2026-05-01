import base64
import logging

import httpx

from app.core.config import settings
from app.prompts.image_prompt import IMAGE_SYSTEM_PROMPT, build_image_prompt

logger = logging.getLogger(__name__)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def analyze_image(image_path: str, chief_complaint: str) -> str:
    user_prompt = build_image_prompt(chief_complaint)
    prompt_text = f"{IMAGE_SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        b64 = _encode_image(image_path)
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.MEDGEMMA_MODEL,
                    "prompt": prompt_text,
                    "images": [b64],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            resp.raise_for_status()
            findings = resp.json().get("response", "").strip()
            if not findings:
                raise ValueError("Empty response from MedGemma")
            logger.info(f"MedGemma findings ({len(findings)} chars): {findings[:200]}")
            return findings
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return "Hindi ma-analyze ang larawan. Mangyaring ilarawan ng BHW ang nakita."
