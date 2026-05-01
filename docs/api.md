# GEMMA API Documentation

Base URL: `http://localhost:8000`

---

## Triage

### POST /api/triage
Text-only triage via Gemma 4 E4B.

**Form fields:**
- `chief_complaint` (required) — patient symptom description
- `followup_answers` (optional) — JSON string of Q&A pairs
- `image_findings` (optional) — pre-analyzed image text

**Response:** TriageResponse JSON

---

### POST /api/triage/image
Multipart triage with image analysis via MedGemma 4B.

**Form fields:**
- `chief_complaint` (required)
- `image` (required) — image file upload
- `followup_answers` (optional)

**Response:** TriageResponse JSON + `image_path`, `image_findings` fields

---

## Patients

### POST /api/patients
Save a triaged patient to the database.

### GET /api/patients?shift_id=xxx
Get all patients for a shift.

### GET /api/patients/{id}
Get a single patient by ID.

### PATCH /api/patients/{id}/status
Update patient status. Body: `{"status": "Seen|Referred|Sent Home|Pending"}`

---

## Shifts

### POST /api/shifts/start
Start a new shift. Body: `{"bhw_name": "...", "coordinator_email": "..."}`
Returns: ShiftOut with `id` (use as `shift_id` throughout)

### POST /api/shifts/end?shift_id=xxx
Close a shift and record end time.

### GET /api/shifts/{shift_id}
Get shift details.

---

## Export

### GET /api/export/excel/{shift_id}
Download the Excel shift report (.xlsx).

### GET /api/export/pdf/{patient_id}
Generate and download the patient handoff PDF.

---

## Email

### POST /api/email/shift-report
Send shift report email to coordinator. Body: `{"shift_id": "..."}`

---

## Health

### GET /health
Returns `{"status": "ok"}`.
