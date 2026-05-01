# GEMMA — Product Requirements Document
**Guided Emergency & Medical Management Assistant**
*Powered by Gemma 4 (E4B) + MedGemma 4B*

> Barangay Platero, City of Biñan | Kaggle × Google DeepMind — Gemma 4 Good Hackathon 2026

---

## 1. Problem Statement

Barangay health centers across the Philippines face a daily reality: long queues, overwhelmed Barangay Health Workers (BHWs), and doctors burdened with patients who could have been pre-assessed. BHWs — the first human touchpoint in public healthcare — often lack structured tools to guide their assessments, leading to inconsistent triage and slower patient throughput.

**GEMMA** is an AI-powered triage decision-support assistant that empowers BHWs to conduct faster, more structured patient intake — reducing waiting time, unburdening doctors, and improving the overall quality of care at the barangay level.

> ⚠️ **GEMMA does not replace BHWs or doctors.** It is a decision-support layer — a co-pilot that makes BHWs more confident and doctors less overwhelmed.

---

## 1a. BHS Triage Context — How It Actually Works

Understanding the real-world BHS workflow is critical to designing GEMMA correctly. The standard 4-step process at Philippine Barangay Health Centers:

### Step 1 — Initial Reception
BHWs greet patients and collect basic personal details: name, address, and family information. This data is recorded in forms and household profiles for community tracking. GEMMA must support this profiling step before any clinical assessment begins.

### Step 2 — Symptom Assessment
Staff quickly note the chief complaint (colds, cough, diarrhea, wounds, dengue symptoms, etc.) and check for emergency signs. Vital signs (blood pressure, temperature) are measured manually by the BHW — particularly for priority cases. GEMMA captures this data as structured input to the AI pipeline.

### Step 3 — Categorization & Disposition
Patients are sorted into one of three disposition paths — which map directly to GEMMA's triage levels:

| BHS Disposition | GEMMA Level | Meaning |
|---|---|---|
| Refer to RHU / hospital | 🔴 RED | Urgent — requires higher-level facility |
| Doctor consultation at BHS | 🟡 YELLOW | Non-urgent — needs on-site doctor |
| Home treatment / BHW management | 🟢 GREEN | Mild — BHW handles, home care instructions |

### Step 4 — Common Services Post-Triage
After categorization, patients queue for: general consultations, minor treatments (first aid, wound care), immunizations, prenatal check-ups, and health monitoring. During outbreaks (e.g., dengue), quick home-care instructions are given to GREEN patients. GEMMA's patient log and shift report capture this full service picture.

> **Design implication:** GEMMA's intake flow must mirror this 4-step sequence — reception first, symptoms second, AI assessment third, status tracking fourth. Do not skip the reception/profiling step.

---

## 2. Goals & Success Metrics

| Goal | Metric |
|---|---|
| Faster patient intake | Triage time per patient < 3 minutes |
| Structured doctor handoff | 100% of patients have a generated summary |
| Shift record keeping | Full patient log exportable per shift |
| Multimodal assessment | Image analysis available for visible conditions |
| Offline capability | App functional without internet connection |
| Hackathon alignment | Uses Gemma 4 + MedGemma multimodal features |

---

## 3. Target Users

### Primary — Barangay Health Worker (BHW)
- Non-clinical background, trained in basic health protocols
- Communicates in Filipino / Taglish
- Uses a basic Android smartphone
- Low to moderate digital literacy — needs simple, big-button UI
- Works in shifts at the barangay health center

### Secondary — Municipal Health Officer / Doctor
- Receives structured patient summaries from BHW
- Gets end-of-shift patient log report via email
- Does not interact with the app directly

### Tertiary — Central Coordinator / Health Records Officer
- Receives exported shift reports
- Monitors patient volume and triage trends across barangays

---

## 4. Core Features (MVP Scope)

### F01 — Patient Reception + Symptom Intake ✅
- **Step 1 — Basic Profiling:** BHW enters patient name (optional), age, sex, barangay address (optional), and family contact — mirrors the BHS household profiling form
- **Step 2 — Vital Signs (optional manual entry):** BHW can enter BP (e.g., "120/80") and temperature if already measured — feeds into the AI assessment as objective data
- **Step 3 — Chief Complaint:** BHW types patient's main symptom in Taglish / Filipino / English
- Simple large-font fields, mobile-optimized — minimum 48px tap targets
- All fields except chief complaint are optional to keep intake fast

### F02 — Photo Capture + MedGemma Image Analysis ✅
- BHW takes a photo of visible condition (wound, rash, swelling, etc.)
- MedGemma 4B analyzes the image
- Visual findings merged with symptom text for holistic assessment
- Triggered only when complaint is visible/external

### F03 — Triage Priority Output (Red / Yellow / Green) ✅
- **🔴 RED** — Refer to RHU or higher-level facility immediately
- **🟡 YELLOW** — Needs on-site doctor consultation (non-urgent, wait for BHS doctor)
- **🟢 GREEN** — BHW-managed; home treatment + care instructions sufficient
- Color-coded full-width badge — readable at a glance even outdoors / under fluorescent light
- Displayed alongside the recommended **disposition action** in plain Filipino (e.g., "I-refer sa RHU", "Puntahan ang doktor dito", "Maaaring umuwi na")

### F04 — Top 5 Possible Conditions ✅
- Gemma 4 generates a ranked list of possible conditions based on symptoms + image
- Displayed as plain language (not medical jargon) for BHW context
- Always accompanied by disclaimer: *"Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."*

### F05 — Guided Follow-Up Questions ✅
- After initial triage, GEMMA generates 3–5 follow-up questions
- Helps BHW gather more structured information
- Questions are in Filipino / simple English
- BHW inputs answers; GEMMA refines triage output if needed

### F06 — Doctor Handoff Summary + PDF Export ✅
- Auto-generated SOAP-lite note per patient:
  - **S** — Subjective (chief complaint, symptoms reported)
  - **O** — Objective (visible findings from image, vitals if entered)
  - **A** — Assessment (top conditions, triage level)
  - **P** — Plan (recommended next step)
- Displayed on screen for BHW to hand to doctor
- **On-demand PDF generation** — BHW taps "Generate PDF" to produce a formatted handoff document
- PDF includes: patient info, triage level badge, top 5 conditions, SOAP note, timestamp, BHW name, GEMMA disclaimer
- PDF can be printed at the health center OR shared digitally (via messaging app, email) to the doctor
- Generated locally using `reportlab` — no cloud dependency (WeasyPrint removed; requires system libs not portable across judges' machines)

> 📌 **Future scope:** Direct send to doctor's device / EMR system integration

### F07 — Patient Log Table ✅
- Running table of all patients triaged in the current shift
- Columns: `#`, `Time`, `Name` (optional), `Chief Complaint`, `Triage Level`, `Top Condition`, `Status`
- BHW can mark patient as `Seen by Doctor` / `Referred` / `Sent Home`
- Stored locally in SQLite — no cloud dependency

### F08 — End-of-Shift Export + Email ✅
- BHW taps "End Shift" button
- Patient log exported as `.xlsx` file
- Summary stats generated: total patients, breakdown by triage level
- Email sent automatically to designated coordinator
- Email includes: shift date, BHW name, patient log attachment, summary stats

---

## 5. Out of Scope (MVP)

> These are intentionally excluded to keep the weekend build focused.

- ❌ Electronic Medical Records (EMR) integration
- ❌ Real-time sync across multiple devices
- ❌ Voice input / speech-to-text
- ❌ Vital signs hardware integration (BP, SpO2)
- ❌ User authentication / login system
- ❌ Multi-barangay dashboard
- ❌ iOS support
- ❌ Cloud storage / database
- ❌ Prescription generation

---

## 6. User Flow

```
[Patient arrives at health center]
         ↓
[BHW opens GEMMA on Android / laptop]
         ↓
[BHW taps "Bagong Pasyente" (New Patient)]
         ↓
── STEP 1: RECEPTION / PROFILING ──────────────────
[BHW enters: name (opt), age, sex, address (opt)]
[Vital signs if already measured: BP, temp (opt)]
         ↓
── STEP 2: SYMPTOM INTAKE ─────────────────────────
[BHW types chief complaint in Taglish / Filipino]
         ↓
[Is condition visible? YES → Take photo → MedGemma analyzes]
                         NO  → Skip photo
         ↓
── STEP 3: AI ASSESSMENT ──────────────────────────
[GEMMA outputs:]
  • 🔴/🟡/🟢 Triage Level + Disposition Action
  • Top 5 Possible Conditions (plain Filipino)
  • 3–5 Follow-up Questions
         ↓
[BHW asks follow-up Qs, inputs answers]
[GEMMA refines assessment if needed]
         ↓
── STEP 4: STATUS TRACKING ────────────────────────
[Doctor Handoff Summary / SOAP note generated]
[Patient added to shift log table]
[BHW routes patient: Referral / Doctor queue / Home]
         ↓
[Doctor sees patient → BHW marks status]
         ↓
        ...repeat for next patient...
         ↓
[BHW taps "Tapusin ang Shift" (End Shift)]
         ↓
[Excel export generated + emailed to coordinator]
```

---

## 7. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Text AI | Gemma 4 E4B (via Ollama) | Lightweight, offline, Taglish-capable |
| Image AI | MedGemma 4B (via Ollama) | Medical image understanding |
| Orchestration | LangChain (Python) | Familiar stack, prompt chaining |
| Backend | FastAPI (Python) | Async, lightweight, REST API |
| Frontend | HTML + Tailwind CSS (PWA) | Mobile-first, installable on Android |
| Storage | SQLite | Offline-first, zero infra |
| Export | Pandas + openpyxl | Excel shift reports |
| PDF Generation | WeasyPrint / ReportLab | On-demand doctor handoff PDF |
| Email | smtplib / SendGrid | End-of-shift coordinator notification |
| Runtime | Ollama (local) | No cloud dependency, privacy-safe |

---

## 8. AI Pipeline Design

```
User Input (text + optional image)
         ↓
┌────────────────────────────────────────┐
│           GEMMA AI Pipeline            │
│                                        │
│  [MedGemma 4B] ← image (if provided)  │
│       ↓ visual findings                │
│  [Prompt Builder]                      │
│    + chief complaint                   │
│    + visual findings                   │
│    + follow-up answers (if any)        │
│       ↓                                │
│  [Gemma 4 E4B]                         │
│    → Triage Level (R/Y/G)             │
│    → Top 5 Conditions                  │
│    → Follow-up Questions               │
│    → SOAP Handoff Summary              │
└────────────────────────────────────────┘
         ↓
   SQLite Patient Log
         ↓
   Display to BHW
```

### Key Prompt Design Principles
- Always output in Filipino-friendly plain language
- Never use complex medical jargon in BHW-facing output
- Always include disclaimer on conditions list
- Triage output must be deterministic (R/Y/G) — no ambiguous responses
- System prompt enforces: *"You are a triage support assistant. You do not replace a doctor."*

---

## 9. Data Model (SQLite)

### Table: `patients`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `shift_id` | TEXT | UUID per shift |
| `timestamp` | DATETIME | Time of intake |
| `name` | TEXT | Optional patient name |
| `age` | INTEGER | Optional |
| `sex` | TEXT | Optional (M/F) |
| `address` | TEXT | Optional barangay address (household profile) |
| `bp` | TEXT | Optional manually-entered blood pressure (e.g., "120/80") |
| `temperature` | TEXT | Optional manually-entered temperature (e.g., "38.2°C") |
| `chief_complaint` | TEXT | Raw symptom input |
| `image_path` | TEXT | Local path to photo (if taken) |
| `image_findings` | TEXT | MedGemma output |
| `followup_qa` | TEXT | JSON of Q&A pairs |
| `triage_level` | TEXT | RED / YELLOW / GREEN |
| `top_conditions` | TEXT | JSON list of top 5 |
| `handoff_summary` | TEXT | SOAP-lite note |
| `status` | TEXT | Pending / Seen / Referred / Sent Home |
| `pdf_path` | TEXT | Local path to generated handoff PDF (if created) |

### Table: `shifts`

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | UUID |
| `bhw_name` | TEXT | Name of BHW on duty |
| `date` | DATE | Shift date |
| `start_time` | DATETIME | Shift start |
| `end_time` | DATETIME | Shift end (on export) |
| `coordinator_email` | TEXT | Recipient for shift report |

---

## 10. UI/UX Guidelines

### Design Principles
- **Mobile-first** — designed for 390px viewport (standard Android)
- **Large touch targets** — minimum 48px tap areas for BHW usability
- **High contrast** — readable in outdoor / fluorescent lighting
- **Minimal text** — icons + color + short labels wherever possible
- **Intuitive, minimal manual entry** — smart defaults, auto-fill, toggles/selects over free text wherever possible
- **English-first UI** — use English for all standard labels and buttons; Filipino only where it adds clarity or avoids ambiguity (e.g., AI disclaimer, culturally specific terms)
- **AI disclaimer stays in Filipino:** *"Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."*

### Color Palette (Barangay Platero)

| Token | Hex | Usage |
|---|---|---|
| `--navy` | `#1B3A6B` | Primary headers, buttons |
| `--green` | `#2D6A2D` | Success, Green triage, accents |
| `--gold` | `#F5C518` | Highlights, stars, warnings |
| `--red` | `#C0392B` | Red triage, urgent alerts |
| `--amber` | `#E67E22` | Yellow triage |
| `--light` | `#F0F4F8` | Background, cards |
| `--white` | `#FFFFFF` | Surface |

### Key Screens
1. **Home / Shift Start** — BHW name input only (coordinator email collected separately at end-shift, not on login)
2. **New Patient Intake** — patient profiling + optional vital signs + chief complaint + optional photo
3. **Triage Result** — large color badge, top 5, follow-up Qs
4. **Handoff Summary** — SOAP note, "Generate PDF" button, shareable/printable output
5. **Patient Log** — table of current shift patients
6. **End Shift** — summary stats, export + email confirmation

---

## 11. Hackathon Submission Checklist

- [ ] Working demo (PWA, runs on Android + laptop)
- [ ] Public GitHub repository (clean README, setup instructions)
- [ ] Technical write-up (how Gemma 4 + MedGemma are used)
- [ ] Demo video (real-world scenario: BHW triaging a patient at Brgy. Platero)
- [ ] Kaggle notebook (optional: model inference walkthrough)

### Judging Criteria Alignment

| Criterion | How GEMMA Addresses It |
|---|---|
| **Social Impact** | Real Philippine public health problem, underserved BHWs |
| **Technical Innovation** | Multimodal (text + image), Taglish prompting, offline-first |
| **Constrained Environments** | Runs fully on Ollama locally, SQLite, no cloud needed |
| **Gemma 4 Usage** | E4B for edge deployment + MedGemma 4B for medical imaging |
| **Working Prototype** | Full PWA with all features functional |
| **Clear Use Case** | BHW triage at barangay health centers |

---

## 12. Build Timeline

| Week | Focus | Deliverables |
|---|---|---|
| **Week 1** (May 1–7) | Core AI Pipeline | Ollama setup, symptom→triage prompt, MedGemma image pipeline, SQLite schema |
| **Week 2** (May 8–14) | Full Feature Build | FastAPI backend, Tailwind PWA frontend, all 8 features working |
| **Week 3** (May 15–18) | Polish + Submit | UI cleanup, demo video, GitHub repo, write-up, Kaggle submission |

---

## 13. Project Tagline

> *"Hindi kapalit ng doktor o BHW — gabay lamang para sa mas mabilis na serbisyo."*
> *(Not a replacement for doctors or BHWs — just a guide for faster service.)*

---

*GEMMA — Guided Emergency & Medical Management Assistant*
*Built for the Kaggle × Google DeepMind Gemma 4 Good Hackathon 2026*
*Barangay Platero, City of Biñan 🏡⭐*
