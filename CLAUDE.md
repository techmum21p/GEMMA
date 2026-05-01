# CLAUDE.md — GEMMA Project Instructions
> Read this file first before doing anything. This is your source of truth.

---

## What is GEMMA?

**GEMMA** = Guided Emergency & Medical Management Assistant
A triage decision-support PWA for Barangay Health Workers (BHWs) in the Philippines.
Built for the **Kaggle × Google DeepMind Gemma 4 Good Hackathon 2026**.

Full spec is in `GEMMA_PRD.md`. Read it. Don't skip it.

---

## Your Role

You are a senior Python/FastAPI engineer building a working MVP.
- Follow the PRD strictly — do not invent features not listed there
- If something is marked ❌ Out of Scope in the PRD, do not build it
- When in doubt, ask. Don't assume.
- Prefer simple and working over clever and broken
- This must run on a laptop AND be installable as a PWA on Android Chrome

---

## Tech Stack — Do Not Deviate

| Layer | Technology |
|---|---|
| Backend | **FastAPI** (Python 3.11+) |
| AI — Text | **Gemma 4 E4B** via **Ollama** (`gemma4:e4b`) |
| AI — Image | **MedGemma 4B** via **Ollama** (`medgemma:4b`) |
| AI Orchestration | **LangChain** + `langchain-ollama` |
| Database | **SQLite** via SQLAlchemy async (`aiosqlite`) |
| Frontend | **HTML + Tailwind CSS** (CDN) — single-page PWA |
| PDF | **WeasyPrint** (fallback: ReportLab) |
| Excel Export | **Pandas + openpyxl** |
| Email | **smtplib** (default) or SendGrid |
| Runtime | **Ollama** running locally |

**Never use:**
- ❌ Django, Flask, or any other web framework
- ❌ React, Vue, Next.js — plain HTML + Tailwind only
- ❌ Any cloud AI API (OpenAI, Gemini API, Anthropic) — Ollama only
- ❌ PostgreSQL, MySQL, MongoDB — SQLite only
- ❌ Docker (unless explicitly asked)

---

## Project Structure

Maintain this exact structure:

```
GEMMA/
├── CLAUDE.md                  ← you are here
├── GEMMA_PRD.md               ← product spec, read this
├── docs/
│   └── api.md
│
├── backend/                   ← FastAPI app (run uvicorn from here)
│   ├── .env                   ← secrets (never commit)
│   ├── .env.example           ← template
│   ├── requirements.txt
│   ├── main.py                ← FastAPI app entry point
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── triage.py      ← POST /triage, POST /triage/image
│   │   │       ├── patients.py    ← GET/POST/PATCH /patients
│   │   │       ├── shifts.py      ← POST /shifts/start, POST /shifts/end
│   │   │       ├── export.py      ← GET /export/excel, GET /export/pdf/{id}
│   │   │       └── email.py       ← POST /email/shift-report
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py          ← pydantic-settings, env vars
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py        ← async engine, session factory
│   │   │   └── models.py          ← SQLAlchemy ORM models
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── triage_service.py  ← core AI triage logic
│   │   │   ├── image_service.py   ← MedGemma image analysis
│   │   │   ├── pdf_service.py     ← WeasyPrint PDF generation
│   │   │   ├── export_service.py  ← Excel shift report
│   │   │   └── email_service.py   ← smtplib / SendGrid
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── triage_prompt.py   ← system + user prompt templates
│   │       └── image_prompt.py    ← MedGemma prompt templates
│   │
│   ├── exports/
│   │   ├── pdfs/                  ← generated handoff PDFs
│   │   └── reports/               ← generated Excel shift reports
│   │
│   ├── models/                    ← Pydantic request/response schemas
│   │   └── schemas.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_triage.py
│   │   └── test_export.py
│   │
├── scripts/
│   └── seed_db.py             ← optional: seed test patients
│
└── docs/
    └── api.md                 ← API endpoint documentation
```

---

## Database Models

### `shifts` table
```python
id: str (UUID, PK)
bhw_name: str
date: date
start_time: datetime
end_time: datetime (nullable)
coordinator_email: str
```

### `patients` table
```python
id: int (PK, autoincrement)
shift_id: str (FK → shifts.id)
timestamp: datetime
name: str (nullable)
age: int (nullable)
sex: str (nullable)  # "M" or "F"
address: str (nullable)  # barangay address for household profiling
bp: str (nullable)  # manually entered, e.g. "120/80"
temperature: str (nullable)  # manually entered, e.g. "38.2°C"
chief_complaint: str
image_path: str (nullable)
image_findings: str (nullable)
followup_qa: str  # JSON string
triage_level: str  # "RED", "YELLOW", "GREEN"
top_conditions: str  # JSON string, list of 5
handoff_summary: str  # SOAP-lite note
status: str  # "Pending", "Seen", "Referred", "Sent Home"
pdf_path: str (nullable)
```

---

## API Routes

### Triage
- `POST /api/triage` — text-only triage
- `POST /api/triage/image` — multipart: image + complaint → MedGemma + Gemma4

### Patients
- `POST /api/patients` — save triaged patient to DB
- `GET /api/patients?shift_id=xxx` — get all patients for a shift
- `PATCH /api/patients/{id}/status` — update patient status

### Shifts
- `POST /api/shifts/start` — start a new shift, returns shift_id
- `POST /api/shifts/end` — close shift, trigger export + email

### Export
- `GET /api/export/excel/{shift_id}` — download shift Excel report
- `GET /api/export/pdf/{patient_id}` — generate + download handoff PDF

### Email
- `POST /api/email/shift-report` — send shift report email to coordinator

---

## AI Pipeline Rules

### Gemma 4 E4B (Text Triage)
- Model: `gemma4:e4b` via Ollama
- Use `langchain_ollama.OllamaLLM`
- System prompt must include:
  - Role: triage support assistant, NOT a doctor
  - Output language: Filipino / plain English (no jargon)
  - Output format: strict JSON (see below)
  - Disclaimer enforcement on conditions list

### MedGemma 4B (Image Analysis)
- Model: `medgemma:4b` via Ollama
- Use `langchain_ollama.OllamaLLM` with base64 image input
- Only called when image is provided
- Output: plain text description of visual findings
- Visual findings are then injected into the Gemma 4 triage prompt

### Required Triage JSON Output Format
```json
{
  "triage_level": "RED | YELLOW | GREEN",
  "triage_reason": "short explanation in Filipino",
  "top_conditions": [
    {"rank": 1, "condition": "...", "plain_explanation": "..."},
    {"rank": 2, "condition": "...", "plain_explanation": "..."},
    {"rank": 3, "condition": "...", "plain_explanation": "..."},
    {"rank": 4, "condition": "...", "plain_explanation": "..."},
    {"rank": 5, "condition": "...", "plain_explanation": "..."}
  ],
  "followup_questions": [
    "Question 1 in Filipino?",
    "Question 2 in Filipino?",
    "Question 3 in Filipino?"
  ],
  "soap_summary": {
    "S": "...",
    "O": "...",
    "A": "...",
    "P": "..."
  },
  "disclaimer": "Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."
}
```

**Always validate this JSON before saving.** If Gemma returns malformed JSON, retry once, then return a safe fallback with triage_level = "YELLOW".

---

## Frontend Rules

### Framework
- Tailwind CSS via CDN — no build step needed
- Single `index.html` file — all screens in one page, shown/hidden via JS
- No React, no Vue, no npm frontend build tools

### PWA Requirements
- `manifest.json` in `/frontend/static/`
- Service worker at `/frontend/static/js/sw.js`
- App must be installable on Android Chrome ("Add to Home Screen")
- Cache static assets for offline use

### Color Palette (Tailwind custom config)
```javascript
// In index.html <script> before Tailwind CDN
tailwind.config = {
  theme: {
    extend: {
      colors: {
        navy:  '#1B3A6B',
        forest:'#2D6A2D',
        gold:  '#F5C518',
        danger:'#C0392B',
        amber: '#E67E22',
        light: '#F0F4F8',
      }
    }
  }
}
```

### Language Rules
- **Default to English** for all UI labels, buttons, and instructions — English is self-explanatory and reduces confusion
- Use Filipino/Taglish **only** where it adds clarity or avoids ambiguity (e.g., medical terms, local context like "Barangay", AI disclaimer)
- The AI disclaimer stays in Filipino: *"Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."*
- Chief complaint placeholder text may use Taglish to guide BHW input
- Do NOT translate self-explanatory English labels (Name, Age, Sex, Status, Save, etc.) into Filipino

### UI Rules
- Minimum tap target: 48px height for all buttons
- Font size minimum: 16px for body, 20px+ for key labels
- Triage color badges must be full-width, high contrast
- **Intuitive, minimal manual entry** — use smart defaults, auto-fill where possible, toggles/selects over free text
- Camera button must use `getUserMedia` API (works in Chrome Android)
- Triage status badges: use only RED / YELLOW / GREEN — no invented sub-categories

### Screens (show/hide via `data-screen` attribute + JS)
1. `screen-home` — BHW name input only (no coordinator email here), Start Shift button
2. `screen-intake` — patient profiling + vital signs (optional) + chief complaint + optional photo capture
3. `screen-result` — triage badge, top 5, follow-up questions
4. `screen-summary` — SOAP note, Generate PDF button
5. `screen-log` — patient table for current shift
6. `screen-endshift` — stats summary, End Shift + email confirm

---

## PDF Handoff Document

Generated by `pdf_service.py` using WeasyPrint.

Must include:
- GEMMA logo / header with Barangay Platero branding
- Patient info (name, age, sex, timestamp)
- Triage level badge (color-coded)
- Top 5 possible conditions
- Full SOAP note
- BHW name who triaged
- Disclaimer: *"Hindi ito opisyal na medikal na rekord. Para sa gabay ng doktor lamang."*
- Footer: *"Generated by GEMMA — Guided Emergency & Medical Management Assistant"*

---

## Excel Shift Report

Generated by `export_service.py` using Pandas + openpyxl.

### Sheet 1: Patient Log
Columns: `#`, `Time`, `Name`, `Age`, `Sex`, `Chief Complaint`, `Triage Level`, `Top Condition`, `Status`

### Sheet 2: Shift Summary
- Total patients triaged
- RED / YELLOW / GREEN breakdown + percentages
- BHW name, shift date, start/end time
- Top 3 most common conditions across the shift

---

## Email

Sent by `email_service.py` via smtplib (default).

- **To:** coordinator_email from shift record
- **Subject:** `[GEMMA] Shift Report — {bhw_name} — {date}`
- **Body:** Plain text shift summary stats
- **Attachment:** Excel shift report `.xlsx`

---

## Environment Variables

Always load from `.env` via `app/core/config.py` (pydantic-settings).
Never hardcode secrets. Never commit `.env`.

Required variables:
```
OLLAMA_BASE_URL=http://localhost:11434
GEMMA_MODEL=gemma4:e4b
MEDGEMMA_MODEL=medgemma:4b
DATABASE_URL=sqlite+aiosqlite:///./gemma.db
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
```

---

## Build Order

Follow this sequence. Do not skip steps.

```
1. backend/app/core/config.py          ← settings first
2. backend/app/db/models.py            ← ORM models
3. backend/app/db/database.py          ← async engine + session
4. backend/models/schemas.py           ← Pydantic schemas
5. backend/app/prompts/                ← prompt templates
6. backend/app/services/triage_service.py   ← core AI logic
7. backend/app/services/image_service.py    ← MedGemma
8. backend/app/api/routes/triage.py         ← triage endpoints
9. backend/app/api/routes/patients.py       ← patient CRUD
10. backend/app/api/routes/shifts.py        ← shift management
11. backend/app/services/pdf_service.py     ← PDF generation
12. backend/app/services/export_service.py  ← Excel export
13. backend/app/services/email_service.py   ← email send
14. backend/app/api/routes/export.py        ← export endpoints
15. backend/app/api/routes/email.py         ← email endpoint
16. backend/main.py                         ← wire everything together
17. frontend/templates/index.html           ← all screens
18. frontend/static/js/app.js               ← screen logic + API calls
19. frontend/static/js/camera.js            ← camera capture
20. frontend/static/js/sw.js                ← service worker
21. frontend/static/manifest.json           ← PWA manifest
```

---

## Testing Checklist

Before declaring anything "done", verify:

- [ ] `cd backend && uvicorn main:app --reload` starts without errors
- [ ] SQLite DB is created automatically on first run
- [ ] `/api/triage` returns valid JSON with all required fields
- [ ] `/api/triage/image` accepts image upload and returns analysis
- [ ] Patient is saved to DB after triage
- [ ] Patient log table shows all shift patients
- [ ] PDF generates without error and includes all required sections
- [ ] Excel export has both sheets with correct data
- [ ] Email sends successfully (test with a real Gmail SMTP)
- [ ] PWA installs on Android Chrome (manifest + service worker)
- [ ] App works offline after first load (service worker caching)

---

## Key Constraints — Always Respect These

1. **GEMMA is not a doctor.** Every AI output must include the disclaimer.
2. **Offline-first.** No feature should require internet to function (except email send).
3. **Filipino language.** All patient-facing and BHW-facing text in Filipino/Taglish.
4. **No auth.** Simple shift-based session — BHW name is the only identity.
5. **Privacy.** Patient names are optional. No data leaves the device except the shift email.
6. **Deterministic triage.** Always return RED, YELLOW, or GREEN. Never "uncertain" or "unknown".
7. **Graceful fallback.** If Ollama is unreachable, show a clear error — don't crash silently.

---

## Hackathon Context

- Competition: Kaggle × Google DeepMind — Gemma 4 Good Hackathon 2026
- Deadline: **May 18, 2026**
- Required deliverables: working demo, public GitHub repo, technical write-up, demo video
- Judging: Social Impact + Technical Innovation + Constrained Environment support
- Demo scenario: BHW triaging patients at **Barangay Platero Health Center, City of Biñan**

---

*GEMMA — Guided Emergency & Medical Management Assistant*
*Hindi kapalit ng doktor o BHW — gabay lamang para sa mas mabilis na serbisyo.* 🏥
