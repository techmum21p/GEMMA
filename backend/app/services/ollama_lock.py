import asyncio

# Single semaphore shared across all Ollama calls.
# Prevents Gemma 4 and MedGemma from running simultaneously,
# which forces Ollama to swap models and can corrupt output.
_semaphore = asyncio.Semaphore(1)


def get() -> asyncio.Semaphore:
    return _semaphore
