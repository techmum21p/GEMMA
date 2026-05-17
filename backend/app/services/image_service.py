"""
MedGemma Image Analysis Service — Stage 0 of the GEMMA triage pipeline.

When a BHW takes a field photo (wound, rash, eye condition, etc.), this
service sends the base64-encoded image to MedGemma 4B via Ollama's
multimodal /api/generate endpoint. MedGemma produces a structured four-
section report: Category, Observations, Visual Impression, and Confidence.

The findings text is injected into the patient_data dict before Gemma 4's
Stage 1a call. Gemma 4 then applies specificity-weighted image evidence
rules defined in the triage prompt:
  HIGH confidence  → fold conditions directly into differential
  MEDIUM confidence → use as supporting evidence
  LOW confidence   → treat as weak context only; prioritise verbal report

Stage 0 is optional — triage proceeds normally when no image is provided.
On any MedGemma failure, a Filipino-language fallback string is returned so
the BHW is informed without the pipeline crashing.
"""
import base64
import logging
import time

import httpx

from app.core.config import settings
from app.prompts.image_prompt import IMAGE_SYSTEM_PROMPT, build_image_prompt

logger = logging.getLogger(__name__)


def _encode_image(image_path: str) -> str:
    """Read an image file and return its base64-encoded string for the Ollama images array."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def analyze_image(image_path: str, chief_complaint: str) -> str:
    """
    Stage 0: Send a field photo to MedGemma 4B for visual assessment.

    Posts the image as a base64 array to Ollama's multimodal /api/generate
    endpoint. MedGemma returns a structured plain-text report with four
    sections (Category, Observations, Visual Impression, Confidence).

    The returned string is injected into patient_data["image_findings"] before
    Gemma 4's Stage 1a prompt is built. Gemma 4 applies specificity-weighting
    rules to decide how much the image findings shift its differential.

    Returns a Filipino-language fallback string on any failure so the BHW
    is informed and the pipeline can continue without the image findings.
    """
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
