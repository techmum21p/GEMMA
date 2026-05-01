---
name: GEMMA project scaffold
description: GEMMA project fully scaffolded — what was built, current state, and hackathon context
type: project
---

Full project scaffold completed May 1, 2026.

**Why:** Kaggle × Google DeepMind Gemma 4 Good Hackathon 2026. Deadline May 18, 2026.

**How to apply:** Project is in Week 1 (AI pipeline + database). Next focus is testing AI pipeline with real Ollama models, then UI refinement.

All 30+ files created per CLAUDE.md build order. Backend complete, frontend complete. Next steps:
1. Install deps: `pip install -r requirements.txt`
2. Copy `.env.example` → `.env` and fill in SMTP credentials
3. Pull Ollama models: `ollama pull gemma4:e4b && ollama pull medgemma:4b`
4. Run: `uvicorn main:app --reload`
5. Seed test data: `python scripts/seed_db.py`
