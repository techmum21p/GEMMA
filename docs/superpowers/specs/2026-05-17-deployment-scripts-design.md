# Deployment Scripts Design — GEMMA Local Installer
**Date:** 2026-05-17
**Status:** Approved

---

## Goal

Provide four scripts at the project root that allow a non-technical user to set up and run GEMMA on a barangay health center laptop (Windows or macOS) without any command-line knowledge beyond double-clicking a file.

---

## Files

All four scripts live at `GEMMA/` (project root):

```
setup.sh      ← macOS first-time setup (run once)
setup.bat     ← Windows first-time setup (run once)
start.sh      ← macOS daily launcher
start.bat     ← Windows daily launcher
```

---

## setup.sh / setup.bat — First-Time Setup

Run once per machine. Safe to re-run (idempotent).

### Steps

1. Print GEMMA ASCII banner
2. **Check Python 3.11+**
   - macOS: `python3 --version`, parse major.minor
   - Windows: `python --version`, parse major.minor
   - On failure: print clear message + `https://www.python.org/downloads/`
   - Exit with code 1
3. **Check Ollama installed**
   - Run `ollama --version`
   - On failure: print clear message + `https://ollama.com/download`
   - Exit with code 1
4. **Create virtual environment** at `backend/.venv`
   - macOS: `python3 -m venv backend/.venv`
   - Windows: `python -m venv backend\.venv`
   - Skip if `.venv` already exists
5. **Install Python dependencies**
   - macOS: `backend/.venv/bin/pip install -r backend/requirements.txt`
   - Windows: `backend\.venv\Scripts\pip install -r backend\requirements.txt`
6. **Copy .env**
   - If `backend/.env` does not exist: copy `backend/.env.example` → `backend/.env`
   - If `backend/.env` already exists: skip (never overwrite)
   - Print: "Edit backend/.env with your SMTP email credentials before first use."
7. **Pull AI models via Ollama**
   - Print warning: models are ~4GB each, download may take 10–20 minutes
   - `ollama pull gemma4:e4b`
   - `ollama pull medgemma:4b`
8. **Create export directories** if missing
   - `backend/exports/pdfs/`
   - `backend/exports/reports/`
9. Print: "Setup complete! Run start.sh (Mac) or start.bat (Windows) to launch GEMMA."

### Error Behavior
- Any failed prerequisite check prints a plain-English message with a URL and exits immediately
- pip install failures print the error and exit — user should re-run setup

---

## start.sh / start.bat — Daily Launcher

Run every day to start the app. Handles Ollama automatically.

### Steps

1. Print GEMMA ASCII banner
2. **Check Ollama is responding**
   - `curl -s http://localhost:11434` (macOS) / `curl -s http://localhost:11434` (Windows, curl available in Win10+)
   - If not responding: start `ollama serve` in background, wait 3 seconds, check again
   - If still not responding: print error + `https://ollama.com/download`, exit
3. **Activate virtual environment**
   - macOS: `source backend/.venv/bin/activate`
   - Windows: `backend\.venv\Scripts\activate.bat`
   - If venv missing: print "Run setup.sh first" and exit
4. **Start uvicorn**
   - `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
   - Print: "GEMMA is running at http://localhost:8000"
5. **Open browser automatically**
   - macOS: `open http://localhost:8000`
   - Windows: `start http://localhost:8000`

### Notes
- On Windows, Ollama often runs as a system tray app already — the curl check handles both cases
- `Ctrl+C` in the terminal stops uvicorn; Ollama continues running in background (expected)
- Port 8000 is hardcoded to match the default in `config.py`

---

## What BHWs See

- Setup: run once by whoever installs GEMMA on the laptop
- Daily: double-click `start.bat` / `start.sh` → browser opens automatically → GEMMA UI
- BHWs never see source code — only the web interface at `http://localhost:8000`

---

## Out of Scope

- Auto-installing Python or Ollama (check + link only)
- Docker containerization
- Remote/cloud deployment
- Multi-user authentication
- Automatic updates

---

## Hackathon Submission Notes

- Scripts live at project root, visible immediately in the GitHub repo
- README should reference these scripts as the installation method
- Safe to include in the public repo — no secrets, no credentials
