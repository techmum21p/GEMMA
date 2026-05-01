# GEMMA — Session Notes

_Last updated: 2026-05-01_

---

## Session 1 — Scaffold & Setup

### What We Built
- Full GEMMA project scaffolded from scratch (45 files)
- Stack: FastAPI + SQLite + LangChain + Ollama (Gemma4:e4b + MedGemma:4b)
- Frontend: single-page PWA (HTML + Tailwind CDN), 6 screens, service worker
- Reorganized into `backend/` and `frontend/` top-level folders
- `requirements.txt` pinned to latest package versions (May 2026)
- Fixed startup crash: `greenlet==3.5.0` added (required by SQLAlchemy async engine)
- `.gitignore` created, local git repo initialized on `main`

### AI Prompt Improvements (MedGemma paper-informed)
- Read MedGemma paper (arxiv 2507.05201): model trained on radiology, not field photos
- `image_prompt.py` — grounded in field context, structured observation format
- `triage_prompt.py` — SOAP in English (for doctor), triage/conditions in Taglish (for BHW)
  - Image findings injected with AI-generated warning
  - Triage level auto-upgrades if image findings suggest more urgency
  - Follow-up questions target answers that would change the triage level

---

## Session 2 — AI Fixes, UX Overhaul, PDF, DB Cleanup

### Bug Fixes
- **500 on POST /api/triage** — Gemma put condition name in `rank` field and omitted `condition` key.
  Fixed with normalization loop in `triage_service.py:_parse_triage_response()`.
- **MedGemma not analyzing photos** — `OllamaLLM.ainvoke()` doesn't support `images` array.
  Fixed with direct `httpx` POST to Ollama `/api/generate` with `"images": [b64]`.
- **Gender-inappropriate diagnoses** (pregnancy for male patient) — `sex` field was never sent to API.
  Fixed: passed through entire chain + added `PATIENT DEMOGRAPHICS RULES` to system prompt.
- **`has-[:checked]` CSS** unreliable on Tailwind CDN — replaced with JS `updateSexToggle()`.

### UX Changes
- Logo: `icon-192.png` → `Gemma_Logo.png` centered across all screens (home + loading)
- Home screen: "BHW Name" → "Barangay Health Worker"; Filipino disclaimer → English
- Intake screen: sex toggle JS-driven; BP split into sys/dia inputs; Take Photo button blue; reduced bottom whitespace
- Result screen: no triage level badge shown here — moved to after follow-up answers
- Summary screen: full redesign — colored full-width verdict panel (RED/YELLOW/GREEN), chips row (age/sex/triage), SOAP card with navy square badges, English disclaimer
- End Shift: BAN grid → SVG donut chart (GREEN/YELLOW/RED segments); coordinator email removed from home screen (moved to End Shift flow)
- Bottom nav: "+ Patient" clears form and shows intake screen

### PDF
- Removed WeasyPrint (macOS `libgobject-2.0-0` dependency, not portable for hackathon judges)
- ReportLab is now the sole PDF generator (`pdf_service.py:_generate_with_reportlab()`)
- PDF served with `Content-Disposition: inline` — opens in browser PDF viewer

### Database Cleanup
Renamed field and added new field — old `gemma.db` deleted (recreates fresh on next startup):

| Before | After |
|---|---|
| `handoff_summary` | `soap_notes` |
| _(missing)_ | `followup_questions` (Text, JSON array) |
| `coordinator_email NOT NULL` | `coordinator_email NULL, default=""` |

**Files updated for this rename:**
- `app/db/models.py` — column definitions
- `models/schemas.py` — PatientCreate, PatientOut
- `app/api/routes/patients.py` — Patient constructor
- `app/api/routes/export.py` — `_patient_to_dict()`
- `app/services/pdf_service.py` — both `_build_html()` and `_generate_with_reportlab()`
- `frontend/static/js/app.js` — `proceedToSummary()` payload
- `tests/test_export.py` — mock patient dicts
- `scripts/seed_db.py` — seed data

---

## Current Status: MVP COMPLETE ✅

All planned features are implemented and wired end-to-end:

| Feature | Status |
|---|---|
| Patient intake (name, age, sex, address, vitals, complaint) | ✅ |
| Photo capture + MedGemma image analysis | ✅ |
| Text triage via Gemma 4 E4B | ✅ |
| Follow-up questions + refined triage | ✅ |
| SOAP note generation | ✅ |
| Patient log table + status update | ✅ |
| PDF handoff document (ReportLab) | ✅ |
| Excel shift report export | ✅ |
| End-of-shift email to coordinator | ✅ |
| PWA manifest + service worker | ✅ |
| SVG donut chart on End Shift screen | ✅ |
| Gender-aware AI prompting | ✅ |

---

## Remaining Before Submission (May 18, 2026)

1. **Push to GitHub** — create public repo, push `main`
   ```bash
   git remote add origin https://github.com/techmum21p/GEMMA.git
   git push -u origin main
   ```
2. **End-to-end test with Ollama running** — pull models if not already:
   ```bash
   ollama pull gemma4:e4b && ollama pull medgemma:4b
   ```
3. **Demo video** — record a full patient triage flow on Android Chrome
4. **Technical write-up** — Kaggle notebook / README

> Email/SMTP dropped — not a submission requirement.

---

## How to Run

```bash
source /Users/aireesm4/Python_Projects/venv_gemma/bin/activate
cd /Users/aireesm4/Python_Projects/GEMMA/backend
uvicorn main:app --reload
# Open http://localhost:8000
```

> Ollama must be running: `ollama serve`
> Models required: `gemma4:e4b` and `medgemma:4b`
