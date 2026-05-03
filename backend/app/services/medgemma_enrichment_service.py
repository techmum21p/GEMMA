import json
import logging
import re

import httpx

from app.core.config import settings
from app.prompts.triage_prompt import build_medgemma_enrichment_prompt
from app.services import ollama_lock

logger = logging.getLogger(__name__)


async def enrich_triage(triage_output: dict) -> list[dict]:
    """
    MedGemma enriches Gemma 4's triage output with clinical consult notes for the doctor.
    Called only during PDF generation — not part of the real-time triage pipeline.
    Returns a list of enrichment objects (one per condition) or [] on failure.
    """
    _PLACEHOLDER = re.compile(r'^condition\s*\d+$', re.IGNORECASE)
    _UNABLE = re.compile(r'unable to assess', re.IGNORECASE)
    conditions = [
        c for c in triage_output.get("top_conditions", [])
        if c.get("condition")
        and not _PLACEHOLDER.match(c["condition"].strip())
        and not _UNABLE.search(c["condition"])
    ]
    if not conditions:
        return []

    # Pass only valid conditions to MedGemma
    filtered_output = {**triage_output, "top_conditions": conditions}
    prompt = build_medgemma_enrichment_prompt(filtered_output)

    try:
        async with ollama_lock.get():
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": settings.MEDGEMMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 2048},
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("response", "").strip()
                if not raw:
                    raise ValueError("Empty response from MedGemma enrichment")

                data = json.loads(raw)
                enrichments = data.get("enrichments", data) if isinstance(data, dict) else data
                if isinstance(enrichments, list):
                    logger.info(f"MedGemma enrichment: {len(enrichments)} conditions enriched")
                    return enrichments
                raise ValueError(f"Unexpected enrichment format: {type(enrichments)}")

    except Exception as e:
        logger.warning(f"MedGemma enrichment failed: {e}. PDF will generate without clinical notes.")
        return []
