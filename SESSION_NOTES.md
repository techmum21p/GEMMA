# GEMMA — Session Notes

_Last updated: 2026-05-01_

---

## What We Built / Changed This Session

### Project Scaffold
- Full GEMMA project scaffolded from scratch (45 files)
- Stack: FastAPI + SQLite + LangChain + Ollama (Gemma4:e4b + MedGemma:4b)
- Frontend: single-page PWA (HTML + Tailwind CDN), 6 screens, service worker

### Structure
- Reorganized into `backend/` and `frontend/` top-level folders for clean separation and future independent deployment

### Dependencies
- `requirements.txt` updated to latest package versions (May 2026)
- Fixed startup crash: `greenlet==3.5.0` added (required by SQLAlchemy async engine)
- All packages confirmed installed in `/Users/aireesm4/Python_Projects/venv_gemma`

### Git & Repo
- `.gitignore` created — excludes `.env`, `*.db`, `__pycache__`, generated exports, venv
- Local git repo initialized, initial commit on `main` branch
- `SESSION_NOTES.md` added and committed
- **Not yet pushed to GitHub**

### AI Prompts (MedGemma paper-informed)
- Read MedGemma paper (arxiv 2507.05201) — key insight: model is trained heavily on radiology, not field photos
- Updated `backend/app/prompts/image_prompt.py`:
  - Grounds MedGemma in field photo context (not clinical/radiology)
  - Structured observation format: Location → Appearance → Size → Skin → Discharge → Impression
  - Output explicitly labeled as AI-generated visual observation
- Updated `backend/app/prompts/triage_prompt.py`:
  - SOAP notes in English (for receiving doctor), triage reason + conditions in Taglish (for BHW)
  - Image findings injected as `[Visual Observation from MedGemma]` with AI-generated warning
  - Added rule: upgrade triage level if visual findings suggest more urgency than complaint alone
  - Follow-up questions now target answers that would change the triage level
  - Fallback response is cleaner and more actionable

---

## Next Steps

1. **Push repo to GitHub** ← do this first
   - Create empty repo at github.com (no README/gitignore)
   - Run:
     ```bash
     git remote add origin https://github.com/YOUR_USERNAME/GEMMA.git
     git push -u origin main
     ```

2. **UI Redesign**
   - Waiting on Google Stitch screens (blue/Maxicare-inspired colorway)
   - Stitch prompt already written — screens being generated
   - Changes planned: symptom checklist chips, bullet-entry for custom symptoms, icons, English-first Taglish, fully responsive (mobile-first, scales to desktop)
   - Once Stitch screens are ready → update `frontend/templates/index.html` + `frontend/static/js/app.js`

3. **AI Pipeline Test**
   - Pull Ollama models: `ollama pull gemma4:e4b && ollama pull medgemma:4b`
   - End-to-end triage test via `/api/triage`

4. **Hackathon Deliverables** (deadline: May 18, 2026)
   - Working demo
   - Public GitHub repo
   - Technical write-up
   - Demo video

---

## How to Run

```bash
source /Users/aireesm4/Python_Projects/venv_gemma/bin/activate
cd /Users/aireesm4/Python_Projects/GEMMA/backend
uvicorn main:app --reload
# Open http://localhost:8000
```
