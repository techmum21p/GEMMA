"""
Ollama concurrency gate — shared asyncio semaphore for all model calls.

Ollama loads one model at a time in GPU VRAM. When a second model is
requested while the first is loaded, Ollama unloads the first and loads the
second. If two requests arrive concurrently (e.g. a MedGemma enrichment
prefetch overlapping with a new Gemma 4 triage call), the model swap can
corrupt the in-progress generation.

This module exposes a single Semaphore(1) shared by every Ollama call site
(triage_service.py, medgemma_enrichment_service.py, image_service.py).
All callers use `async with ollama_lock.get(): ...` to queue their requests
and guarantee only one model call is active at any moment.
"""
import asyncio

_semaphore = asyncio.Semaphore(1)


def get() -> asyncio.Semaphore:
    """Return the shared Semaphore(1) that serialises all Ollama API calls."""
    return _semaphore
