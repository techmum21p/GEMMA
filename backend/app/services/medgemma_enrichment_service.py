"""
MedGemma PDF Enrichment Service.

After Gemma 4 produces the final triage assessment (Stage 2a), this service
uses MedGemma 4B to generate compact clinical consult notes for each
differential diagnosis. These notes appear in the physician section of the
handoff PDF and are intended for the receiving doctor, not the BHW.

MedGemma 4B is a medically fine-tuned variant of Gemma optimised for
clinical language and medical imaging tasks. It is used here specifically
for its clinical note generation capability — Gemma 4 E4B handles all
primary triage reasoning because it outperforms MedGemma on general
clinical reasoning benchmarks (MedQA: Gemma 3 27B 85.3% vs MedGemma 4B
69.1%). MedGemma's strength is specialist clinical documentation.

Enrichment runs as a background prefetch (enrichment_cache.py) triggered
immediately after Stage 2a completes, so PDF generation is near-instant.
If MedGemma is unreachable or returns malformed output, enrich_triage()
returns [] and the PDF renders without the physician section — graceful
degradation with no impact on the BHW-facing triage flow.
"""
import json
import logging
import re
import time

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
    border = "─" * 62
    logger.info(
        f"\n┌{border}┐\n"
        f"│  GEMMA PIPELINE │ PDF Enrichment: MedGemma Clinical Notes  │\n"
        f"└{border}┘"
    )

    _PLACEHOLDER = re.compile(r'^condition\s*\d+$', re.IGNORECASE)
    _UNABLE = re.compile(r'unable to assess', re.IGNORECASE)
    conditions = [
        c for c in triage_output.get("top_conditions", [])
        if c.get("condition")
        and not _PLACEHOLDER.match(c["condition"].strip())
        and not _UNABLE.search(c["condition"])
    ]
    if not conditions:
        logger.info("  → No valid conditions to enrich — skipping MedGemma call")
        return []

    logger.info(f"  → Model      : {settings.MEDGEMMA_MODEL}")
    logger.info(f"  → Conditions : {len(conditions)} to enrich for physician section")
    for i, c in enumerate(conditions, 1):
        logger.info(f"    {i}. {c.get('condition', 'N/A')}")

    filtered_output = {**triage_output, "top_conditions": conditions}
    prompt = build_medgemma_enrichment_prompt(filtered_output)
    logger.info(f"  → Prompt length: {len(prompt)} chars")
    logger.info("  → Calling MedGemma for clinical consult notes…")

    t0 = time.perf_counter()
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
                    elapsed = time.perf_counter() - t0
                    logger.info(
                        f"  ✓ PDF enrichment complete in {elapsed:.2f}s — "
                        f"{len(enrichments)} condition(s) enriched with clinical notes"
                    )
                    return enrichments
                raise ValueError(f"Unexpected enrichment format: {type(enrichments)}")

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.warning(
            f"  ⚠ PDF enrichment failed after {elapsed:.2f}s: {e} — "
            f"PDF will generate without clinical notes"
        )
        return []
