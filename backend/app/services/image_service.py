import base64
import logging
import time

import httpx

from app.core.config import settings
from app.prompts.image_prompt import IMAGE_SYSTEM_PROMPT, build_image_prompt

logger = logging.getLogger(__name__)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def analyze_image(image_path: str, chief_complaint: str) -> str:
    border = "─" * 62
    logger.info(
        f"\n┌{border}┐\n"
        f"│  GEMMA PIPELINE │ Stage 0: MedGemma Image Analysis      │\n"
        f"└{border}┘"
    )
    logger.info(f"  → Model     : {settings.MEDGEMMA_MODEL}")
    logger.info(f"  → Image     : {image_path}")
    logger.info(f"  → Complaint : \"{chief_complaint[:80]}\"")

    user_prompt = build_image_prompt(chief_complaint)
    prompt_text = f"{IMAGE_SYSTEM_PROMPT}\n\n{user_prompt}"

    t0 = time.perf_counter()
    try:
        b64 = _encode_image(image_path)
        img_kb = len(b64) * 3 / 4 / 1024
        logger.info(f"  → Image encoded: ~{img_kb:.1f} KB (base64 ready)")
        logger.info(f"  → Calling MedGemma… (vision + medical reasoning)")

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

        elapsed = time.perf_counter() - t0
        logger.info(
            f"  ✓ Stage 0 complete in {elapsed:.2f}s — {len(findings)} chars\n"
            f"  → Findings preview: \"{findings[:120]}{'…' if len(findings) > 120 else ''}\""
        )
        return findings
    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(f"  ✗ Stage 0 failed after {elapsed:.2f}s: {e}")
        return "Hindi ma-analyze ang larawan. Mangyaring ilarawan ng BHW ang nakita."
