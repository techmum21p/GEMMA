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

### Git
- `.gitignore` created — excludes `.env`, `*.db`, `__pycache__`, generated exports, venv
- Local git repo initialized, initial commit on `main` branch
- **Not yet pushed to GitHub**

---

## Next Steps

1. **Push repo to GitHub**
   - Create empty repo at github.com (no README/gitignore)
   - Run:
     ```bash
     git remote add origin https://github.com/YOUR_USERNAME/GEMMA.git
     git push -u origin main
     ```

2. **UI Redesign**
   - Waiting on Google Stitch screens (blue/Maxicare-inspired colorway)
   - Changes planned: symptom checklist chips, bullet-entry text field, icons, English-first Taglish labels
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
