# GEMMA — Guided Emergency & Medical Management Assistant

> *"Hindi kapalit ng doktor o BHW — gabay lamang para sa mas mabilis na serbisyo."*
> *(Not a replacement for doctors or BHWs — just a guide for faster service.)*

GEMMA is an AI-powered triage decision-support PWA built for **Barangay Health Workers (BHWs)** in the Philippines. It runs fully offline on a laptop and is installable as a Progressive Web App on Android Chrome — no internet, no cloud, no subscription required.

Built for the **Kaggle × Google DeepMind — Gemma 4 Good Hackathon 2026**.

# Videos Demos
https://www.youtube.com/@GenXAI-21

---

## What It Does

A BHW opens GEMMA on their phone or laptop. They enter a patient's chief complaint, optionally take a photo of a visible condition, and within seconds GEMMA outputs:

- **Triage level** — RED (refer immediately), YELLOW (needs doctor), or GREEN (BHW can manage)
- **Top 5 possible conditions** in plain Filipino/Taglish — not medical jargon
- **3 guided follow-up questions** to refine the assessment
- **SOAP-lite handoff note** for the doctor
- **Printable PDF handoff document** — generated locally, no cloud upload
- **End-of-shift Excel report** — downloaded directly from the End Shift screen

All data stays on the device. No account needed. Works without internet after first load.

---

## AI Models

| Model | Role |
|---|---|
| **Gemma 4 E4B** (`gemma4:e4b`) | Primary clinical reasoning — triage level, SOAP note, differential diagnosis, follow-up questions |
| **MedGemma 4B** (`medgemma:4b`) | Medical image analysis (wounds, rashes, lesions) + physician-facing PDF clinical notes |

Both models run locally via **Ollama** — zero cloud dependency.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| AI runtime | Ollama (local) |
| AI orchestration | Direct `httpx` to Ollama API |
| Database | SQLite via SQLAlchemy + aiosqlite |
| Frontend | HTML + Tailwind CSS (CDN) — single-page PWA |
| PDF generation | ReportLab |
| Excel export | Pandas + openpyxl |

---

## Requirements

| Dependency | Minimum Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.12 recommended |
| Ollama | Latest | Must be running before starting GEMMA |
| RAM | 16 GB | 24 GB recommended — both models must fit in memory alongside the OS |
| Storage | ~8 GB free | ~3 GB for `gemma4:e4b`, ~4 GB for `medgemma:4b` |
| OS | Windows 10/11 or macOS 12+ | Linux also works |

---

## Installation — macOS

### 1. Install Python 3.11+

```bash
# Check if you already have it
python3 --version

# Install via Homebrew if needed
brew install python@3.12
```

### 2. Install Ollama

Download from [ollama.com](https://ollama.com) and run the installer, or via Homebrew:

```bash
brew install ollama
```

### 3. Pull the AI models

This is a one-time download (~7 GB total). Make sure you're on WiFi.

```bash
ollama pull gemma4:e4b
ollama pull medgemma:4b
```

Verify both are ready:

```bash
ollama list
```

### 4. Clone the repository

```bash
git clone https://github.com/techmum21p/GEMMA.git
cd GEMMA
```

### 5. Create and activate a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 6. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 7. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
OLLAMA_BASE_URL=http://localhost:11434
GEMMA_MODEL=gemma4:e4b
MEDGEMMA_MODEL=medgemma:4b
DATABASE_URL=sqlite+aiosqlite:///./gemma.db

APP_HOST=0.0.0.0
APP_PORT=8000
```

### 8. Start Ollama

```bash
ollama serve
```

Leave this terminal open. Open a new terminal for the next step.

### 9. Run GEMMA

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Installation — Windows

### 1. Install Python 3.11+

Download from [python.org](https://www.python.org/downloads/). During installation:
- Check **"Add Python to PATH"**
- Check **"Install pip"**

Verify in Command Prompt or PowerShell:

```powershell
python --version
```

### 2. Install Ollama

Download the Windows installer from [ollama.com](https://ollama.com) and run it. Ollama installs as a background service and starts automatically.

### 3. Pull the AI models

Open **Command Prompt** or **PowerShell**:

```powershell
ollama pull gemma4:e4b
ollama pull medgemma:4b
```

Verify both are ready:

```powershell
ollama list
```

### 4. Clone the repository

```powershell
git clone https://github.com/techmum21p/GEMMA.git
cd GEMMA
```

> If you don't have Git, download it from [git-scm.com](https://git-scm.com) or download the repo ZIP from GitHub.

### 5. Create and activate a virtual environment

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
```

Your prompt should now show `(venv)`.

### 6. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 7. Configure environment variables

Copy the example file:

```powershell
copy .env.example .env
```

Open `.env` in Notepad or any editor and fill in your values:

```env
OLLAMA_BASE_URL=http://localhost:11434
GEMMA_MODEL=gemma4:e4b
MEDGEMMA_MODEL=medgemma:4b
DATABASE_URL=sqlite+aiosqlite:///./gemma.db

APP_HOST=0.0.0.0
APP_PORT=8000
```

### 8. Run GEMMA

Ollama on Windows starts automatically as a service, so no separate `ollama serve` command is needed.

```powershell
cd backend
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Connecting a Mobile Phone (Android Chrome)

GEMMA is a Progressive Web App (PWA) designed to be used on-site by BHWs on their phones. You can connect any Android device on the same network as the laptop running GEMMA.

### Option A — Same WiFi Network

1. Make sure your laptop and phone are connected to the **same WiFi router**.

2. Find your laptop's local IP address:

   **macOS:**
   ```bash
   ipconfig getifaddr en0
   # or: ifconfig | grep "inet " | grep -v 127
   ```

   **Windows (PowerShell):**
   ```powershell
   ipconfig
   # Look for "IPv4 Address" under your WiFi adapter — e.g. 192.168.1.105
   ```

3. On your phone's **Chrome browser**, open:
   ```
   http://<your-laptop-ip>:8000
   ```
   Example: `http://192.168.1.105:8000`

4. GEMMA loads. To install it as a PWA (home screen app), see the section below.

### Option B — Mobile Hotspot (no router needed)

This is the recommended setup for field use — the laptop creates a hotspot and the phone connects to it directly. No router, no ISP required.

**macOS (Internet Sharing):**

1. System Settings → General → Sharing → **Internet Sharing**
2. Share from: **Wi-Fi** (or Ethernet if laptop has a cable)
3. To devices using: **Wi-Fi**
4. Turn on **Internet Sharing**
5. Find your Mac's hotspot IP — open **Terminal** and run:
   ```bash
   ipconfig getifaddr bridge100
   # or: ifconfig bridge100 | grep "inet "
   ```
   The IP shown is what your phone will use to reach the server.
6. On your phone's Chrome, open: `http://<that-ip>:8000`

**Windows (Mobile Hotspot):**

1. Settings → Network & Internet → **Mobile hotspot**
2. Toggle **Share my Internet connection** ON
3. Note the hotspot **name and password** shown on screen
4. On your phone, connect to that hotspot via Wi-Fi settings
5. Find your laptop's hotspot IP — open **PowerShell** and run:
   ```powershell
   ipconfig
   ```
   Look for the adapter named **"Local Area Connection\* x"** (the hotspot adapter) and note its **IPv4 Address**.
6. On your phone's Chrome, open: `http://<that-ip>:8000`

> **Tip:** If the page doesn't load, check that Windows Firewall allows inbound connections on port 8000. See the Troubleshooting section below.

---

## Installing as a PWA on Android Chrome

Once GEMMA is open in Chrome on your Android phone:

1. Tap the **three-dot menu** (⋮) in the top-right corner of Chrome
2. Tap **"Add to Home screen"** or **"Install app"**
3. Confirm — GEMMA will appear on your home screen like a native app
4. Open it from the home screen — it runs in fullscreen, no browser chrome

The service worker caches all static assets on first load, so GEMMA works offline after installation. AI inference still requires the laptop (Ollama) to be reachable on the same network.

---

## Running GEMMA

Start these in order each session:

```
1. Start Ollama      →  ollama serve           (macOS/Linux; Windows: starts automatically)
2. Activate venv     →  source venv/bin/activate   (macOS) | venv\Scripts\activate  (Windows)
3. Start server      →  cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
4. Open browser      →  http://localhost:8000   (laptop) | http://<ip>:8000  (phone)
```

You should see the GEMMA banner in the terminal:

```
╔══════════════════════════════════════════════════════════════╗
║       GEMMA — Guided Emergency & Medical Management          ║
║         Barangay Platero Health Center, City of Biñan        ║
║         Kaggle × Google DeepMind Gemma 4 Good 2026           ║
╚══════════════════════════════════════════════════════════════╝
```

---

## App Workflow

```
BHW opens GEMMA → enters name → starts shift
        ↓
New Patient → enters name (optional), age, sex, address (optional)
           → enters vital signs if measured (BP, temp, HR, SpO2)
           → types chief complaint
           → optionally takes photo (camera) or uploads from gallery
        ↓
GEMMA runs AI triage (Gemma 4 + MedGemma if photo present)
        ↓
Result screen → triage badge (RED/YELLOW/GREEN)
             → top 5 possible conditions in Taglish
             → 3 follow-up questions → BHW asks patient → enters answers
             → GEMMA refines assessment
        ↓
SOAP summary screen → handoff note → Generate PDF (optional)
        ↓
Patient saved to shift log → BHW marks status (Seen / Referred / Sent Home)
        ↓
End Shift → tap "Download Excel Report" → close shift
```

---

## API Reference

The backend exposes a REST API at `http://localhost:8000/api/`. Interactive docs are available at:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/shifts/start` | Start a new BHW shift |
| `POST` | `/api/shifts/end` | Close the shift (records end_time) |
| `POST` | `/api/triage` | Text-only triage (Gemma 4) |
| `POST` | `/api/triage/image` | Multipart: image + complaint → MedGemma + Gemma 4 |
| `POST` | `/api/triage/test-fallback` | Demo the AI fallback safety net (no Ollama call) |
| `POST` | `/api/patients` | Save a triaged patient to the database |
| `GET` | `/api/patients?shift_id=xxx` | Get all patients for a shift |
| `PATCH` | `/api/patients/{id}/status` | Update patient status |
| `GET` | `/api/export/excel/{shift_id}` | Download shift Excel report |
| `GET` | `/api/export/pdf/{patient_id}` | Generate and download handoff PDF |
| `GET` | `/health` | Health check |

---

## Generated Files

All generated files are saved locally and excluded from version control:

| Path | Contents |
|---|---|
| `backend/gemma.db` | SQLite database (shifts + patients) |
| `backend/exports/pdfs/` | Generated patient handoff PDFs |
| `backend/exports/reports/` | Generated Excel shift reports |
| `backend/exports/images/` | Uploaded patient images |

---

## Configuration

All settings are in `backend/.env`. See `backend/.env.example` for the full template.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `GEMMA_MODEL` | `gemma4:e4b` | Primary reasoning model |
| `MEDGEMMA_MODEL` | `medgemma:4b` | Image analysis + PDF enrichment model |
| `DATABASE_URL` | `sqlite+aiosqlite:///./gemma.db` | SQLite database path |
| `APP_HOST` | `0.0.0.0` | Server bind host (`0.0.0.0` allows LAN/hotspot access) |
| `APP_PORT` | `8000` | Server port |

---

## Troubleshooting

**Ollama model not found**
```
Error: model 'gemma4:e4b' not found
```
Run `ollama pull gemma4:e4b` and wait for the download to complete.

**Port 8000 already in use**
```bash
# macOS/Linux — find and kill the process
lsof -i :8000
kill -9 <PID>

# Windows PowerShell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Phone can't reach the server**
- Confirm laptop and phone are on the same network (WiFi or hotspot)
- Make sure you used `--host 0.0.0.0` when starting uvicorn (not `127.0.0.1`)
- Check your laptop's firewall: allow inbound connections on port 8000
  - **macOS:** System Settings → Network → Firewall → allow Python/uvicorn
  - **Windows:** Windows Defender Firewall → Allow an app → add Python

**Slow inference / model loading**
- First inference after startup loads the model into RAM — expect 30–60 seconds
- Subsequent calls are faster (model stays loaded in Ollama)
- 24 GB RAM is recommended — on 16 GB machines, both models competing for memory alongside the OS will cause significant slowdowns or swap. Close all other applications.

**PDF opens blank on mobile**
- Tap the **"↗ All Pages"** button in the PDF viewer header to open it in a new tab
- Or long-press the PDF viewer and select "Open in new tab"

---

## Project Structure

```
GEMMA/
├── backend/
│   ├── main.py                         ← FastAPI app entry point
│   ├── requirements.txt
│   ├── .env.example                    ← copy to .env and fill in
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── triage.py               ← POST /triage, /triage/image
│   │   │   ├── patients.py             ← patient CRUD
│   │   │   ├── shifts.py               ← shift start/end
│   │   │   ├── export.py               ← PDF + Excel download
│   │   │   └── email.py                ← shift report email
│   │   ├── core/config.py              ← pydantic-settings, env vars
│   │   ├── db/
│   │   │   ├── database.py             ← async engine + session
│   │   │   └── models.py               ← SQLAlchemy ORM models
│   │   ├── services/
│   │   │   ├── triage_service.py       ← Gemma 4 pipeline (Stages 1a, 2a)
│   │   │   ├── image_service.py        ← MedGemma Stage 0 image analysis
│   │   │   ├── medgemma_enrichment_service.py  ← MedGemma PDF enrichment
│   │   │   ├── enrichment_cache.py     ← background prefetch + cache
│   │   │   ├── ollama_lock.py          ← asyncio semaphore for Ollama
│   │   │   ├── pdf_service.py          ← ReportLab PDF generation
│   │   │   ├── export_service.py       ← Excel shift report
│   │   │   └── email_service.py        ← smtplib email send
│   │   └── prompts/
│   │       ├── triage_prompt.py        ← Gemma 4 system + user prompts
│   │       └── image_prompt.py         ← MedGemma image prompt
│   ├── models/schemas.py               ← Pydantic request/response schemas
│   └── exports/                        ← generated PDFs, Excel, images (gitignored)
├── frontend/
│   ├── templates/index.html            ← single-page PWA (all screens)
│   └── static/
│       ├── js/
│       │   ├── app.js                  ← screen logic + API calls
│       │   ├── camera.js               ← camera capture + gallery upload
│       │   └── sw.js                   ← service worker (offline caching)
│       ├── css/app.css
│       ├── manifest.json               ← PWA manifest
│       └── icons/                      ← app icons (192px, 512px)
└── docs/
    ├── kaggle_writeup.md               ← hackathon technical write-up
    └── ai_pipeline.md                  ← detailed AI pipeline documentation
```

---

## Disclaimer

> **GEMMA is not a diagnostic tool and does not replace medical professionals.**
> All AI outputs are decision-support references for Barangay Health Workers only.
> Final clinical decisions must always be made by a licensed healthcare provider.
>
> *"Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."*

---

## Hackathon

**Competition:** Kaggle × Google DeepMind — Gemma 4 Good Hackathon 2026

**Demo scenario:** Barangay Platero Health Center, City of Biñan, Laguna, Philippines

**Track:** Health & Sciences

---

*GEMMA — Guided Emergency & Medical Management Assistant*
*Built with Gemma 4 E4B + MedGemma 4B via Ollama*
