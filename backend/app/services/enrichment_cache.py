import asyncio
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

_cache: dict[str, asyncio.Task] = {}
_MAX_CACHE = 20


def _make_key(triage_result: dict) -> str:
    conditions = triage_result.get("top_conditions", [])
    return hashlib.md5(json.dumps(conditions, sort_keys=True).encode()).hexdigest()


def is_done(triage_result: dict) -> bool:
    """Return True if enrichment finished successfully and is cached."""
    task = _cache.get(_make_key(triage_result))
    return bool(task and task.done() and not task.cancelled() and not task.exception())


def prefetch(triage_result: dict) -> None:
    """Fire MedGemma enrichment as a background task after Stage 2a completes."""
    from app.services.medgemma_enrichment_service import enrich_triage

    key = _make_key(triage_result)
    if key in _cache:
        return  # already running or done

    if len(_cache) >= _MAX_CACHE:
        oldest = next(iter(_cache))
        del _cache[oldest]

    _cache[key] = asyncio.create_task(enrich_triage(triage_result))
    logger.info(f"Enrichment prefetch started (key={key[:8]})")


async def get_or_fetch(triage_output: dict) -> list:
    """Return pre-fetched enrichment if ready, otherwise run it now."""
    from app.services.medgemma_enrichment_service import enrich_triage

    key = _make_key(triage_output)
    task = _cache.get(key)
    if task:
        try:
            result = await task
            logger.info(f"Enrichment cache hit (key={key[:8]})")
            return result
        except Exception as e:
            logger.warning(f"Enrichment cache task failed ({e}), re-running")
            del _cache[key]

    return await enrich_triage(triage_output)
