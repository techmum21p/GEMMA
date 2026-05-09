# JSON Stress Test & Safe Manual Fallback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Gemma 4 returns malformed JSON, surface the failure visibly in the UI, auto-populate a SOAP note from entered data, and let the BHW manually assign RED/YELLOW/GREEN — with a one-click demo trigger that exercises the real parser fallback chain.

**Architecture:** Backend adds `_build_fallback_with_patient_data()` which replaces the bare `TRIAGE_FALLBACK` return and injects `is_fallback: true` into the response. A new `POST /api/triage/test-fallback` route feeds broken JSON through the real `_parse_triage_json()` chain and returns the fallback result. The frontend detects `is_fallback`, hides AI content, shows an amber banner and RED/YELLOW/GREEN selector, and uses the manually chosen level when saving the patient.

**Tech Stack:** FastAPI, Pydantic, Python `re`/`json`, Vanilla JS, Tailwind CSS

---

## File Map

| File | Change |
|---|---|
| `backend/app/services/triage_service.py` | Add `_build_fallback_with_patient_data()`, `run_fallback_stress_test()`; update call sites in `_run_initial_triage` and `_run_refined_triage` |
| `backend/models/schemas.py` | Add `is_fallback: bool = False` to `TriageResponse` |
| `backend/app/api/routes/triage.py` | Add `POST /api/triage/test-fallback` route |
| `backend/tests/test_triage.py` | Add tests for new functions |
| `frontend/templates/index.html` | Add fallback banner + selector in `screen-result`; add "Simulate AI Failure" button in `screen-intake` |
| `frontend/static/js/app.js` | Add `simulateAIFailure()`, update `renderTriageResult()` and `proceedToSummary()` |

---

## Task 1: Add `_build_fallback_with_patient_data()` to triage_service

**Files:**
- Modify: `backend/app/services/triage_service.py`
- Modify: `backend/tests/test_triage.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_triage.py`:

```python
from app.services.triage_service import _build_fallback_with_patient_data

SAMPLE_PATIENT_DATA = {
    "chief_complaint": "Masakit ang ulo at may lagnat.",
    "age": 35,
    "sex": "F",
    "bp": "130/85",
    "temperature": "38.5",
    "heart_rate": "92",
    "spo2": None,
    "followup_answers": None,
    "initial_assessment": None,
    "image_findings": None,
}

def test_build_fallback_includes_is_fallback_flag():
    result = _build_fallback_with_patient_data(SAMPLE_PATIENT_DATA)
    assert result["is_fallback"] is True

def test_build_fallback_triage_level_is_yellow():
    result = _build_fallback_with_patient_data(SAMPLE_PATIENT_DATA)
    assert result["triage_level"] == "YELLOW"

def test_build_fallback_soap_contains_chief_complaint():
    result = _build_fallback_with_patient_data(SAMPLE_PATIENT_DATA)
    assert "Masakit ang ulo at may lagnat." in result["soap_summary"]["S"]

def test_build_fallback_soap_o_contains_vitals():
    result = _build_fallback_with_patient_data(SAMPLE_PATIENT_DATA)
    assert "130/85" in result["soap_summary"]["O"]
    assert "38.5" in result["soap_summary"]["O"]

def test_build_fallback_soap_a_mentions_manual():
    result = _build_fallback_with_patient_data(SAMPLE_PATIENT_DATA)
    assert "manually" in result["soap_summary"]["A"].lower()

def test_build_fallback_with_no_vitals():
    sparse = {"chief_complaint": "Nahihilo.", "age": None, "sex": None,
              "bp": None, "temperature": None, "heart_rate": None, "spo2": None,
              "followup_answers": None, "initial_assessment": None, "image_findings": None}
    result = _build_fallback_with_patient_data(sparse)
    assert result["is_fallback"] is True
    assert "Nahihilo." in result["soap_summary"]["S"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_triage.py::test_build_fallback_includes_is_fallback_flag -v
```

Expected: `ImportError` or `AttributeError` — `_build_fallback_with_patient_data` not defined yet.

- [ ] **Step 3: Implement `_build_fallback_with_patient_data()` in `triage_service.py`**

Add after the `_DEFAULT_DISCLAIMER` constant (around line 22), before `_call_gemma`:

```python
def _build_fallback_with_patient_data(patient_data: dict) -> dict:
    """Return TRIAGE_FALLBACK enriched with available patient data and is_fallback flag."""
    complaint = patient_data.get("chief_complaint") or "Not recorded."
    answers = patient_data.get("followup_answers") or {}

    s_parts = [f"Chief complaint: {complaint}"]
    if answers:
        for q, a in answers.items():
            s_parts.append(f"Q: {q} — A: {a}")
    soap_s = " | ".join(s_parts)

    vitals = []
    if patient_data.get("bp"):
        vitals.append(f"BP: {patient_data['bp']}")
    if patient_data.get("temperature"):
        vitals.append(f"Temp: {patient_data['temperature']}°C")
    if patient_data.get("heart_rate"):
        vitals.append(f"HR: {patient_data['heart_rate']} bpm")
    if patient_data.get("spo2"):
        vitals.append(f"SpO2: {patient_data['spo2']}%")
    if patient_data.get("age"):
        vitals.append(f"Age: {patient_data['age']}")
    if patient_data.get("sex"):
        vitals.append(f"Sex: {patient_data['sex']}")
    soap_o = ", ".join(vitals) if vitals else "No vitals recorded."

    return {
        "triage_level": "YELLOW",
        "triage_reason": "Hindi ma-process ang AI assessment. Kailangan ng manu-manong pagtukoy ng triage level.",
        "is_fallback": True,
        "top_conditions": TRIAGE_FALLBACK["top_conditions"],
        "followup_questions": TRIAGE_FALLBACK["followup_questions"],
        "soap_summary": {
            "S": soap_s,
            "O": soap_o,
            "A": "AI assessment failed — triage level assigned manually by BHW.",
            "P": "Refer to physician for evaluation. Manual triage level pending BHW selection.",
        },
        "disclaimer": _DEFAULT_DISCLAIMER,
    }
```

- [ ] **Step 4: Update call sites in `_run_initial_triage` and `_run_refined_triage`**

In `_run_initial_triage` (line 188), change:
```python
        return TRIAGE_FALLBACK
```
to:
```python
        return _build_fallback_with_patient_data(patient_data)
```

In `_run_refined_triage` (line 218), change:
```python
        return TRIAGE_FALLBACK
```
to:
```python
        return _build_fallback_with_patient_data(patient_data)
```

- [ ] **Step 5: Run all new tests**

```bash
cd backend && python -m pytest tests/test_triage.py::test_build_fallback_includes_is_fallback_flag tests/test_triage.py::test_build_fallback_triage_level_is_yellow tests/test_triage.py::test_build_fallback_soap_contains_chief_complaint tests/test_triage.py::test_build_fallback_soap_o_contains_vitals tests/test_triage.py::test_build_fallback_soap_a_mentions_manual tests/test_triage.py::test_build_fallback_with_no_vitals -v
```

Expected: All 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/triage_service.py backend/tests/test_triage.py
git commit -m "feat: add _build_fallback_with_patient_data — enriched fallback with SOAP auto-population and is_fallback flag"
```

---

## Task 2: Add `run_fallback_stress_test()` and update `TriageResponse` schema

**Files:**
- Modify: `backend/app/services/triage_service.py`
- Modify: `backend/models/schemas.py`
- Modify: `backend/tests/test_triage.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_triage.py`:

```python
from app.services.triage_service import run_fallback_stress_test

@pytest.mark.asyncio
async def test_stress_test_returns_fallback_shape():
    result = await run_fallback_stress_test(SAMPLE_PATIENT_DATA)
    assert result["is_fallback"] is True
    assert result["triage_level"] == "YELLOW"
    assert "soap_summary" in result
    assert "Masakit ang ulo at may lagnat." in result["soap_summary"]["S"]

@pytest.mark.asyncio
async def test_stress_test_parser_chain_fires():
    """Verify the broken string actually exercises _parse_triage_json before fallback."""
    from app.services import triage_service
    import unittest.mock as mock

    original = triage_service._parse_triage_json
    called_with = []

    def spy(raw):
        called_with.append(raw)
        return original(raw)

    with mock.patch.object(triage_service, '_parse_triage_json', side_effect=spy):
        result = await run_fallback_stress_test(SAMPLE_PATIENT_DATA)

    assert len(called_with) == 1
    assert "BANANA" in called_with[0]
    assert result["is_fallback"] is True
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && python -m pytest tests/test_triage.py::test_stress_test_returns_fallback_shape -v
```

Expected: `ImportError` — `run_fallback_stress_test` not defined yet.

- [ ] **Step 3: Add `run_fallback_stress_test()` to `triage_service.py`**

Add at the end of the file (after `run_triage`):

```python
async def run_fallback_stress_test(patient_data: dict) -> dict:
    """
    Feeds deliberately broken JSON through the real _parse_triage_json chain,
    then returns _build_fallback_with_patient_data. Used by POST /api/triage/test-fallback
    to demonstrate the fallback safety net in demos and writeups.
    """
    broken = '{ triage_level: BANANA, top_conditions: [[[}'
    try:
        _parse_triage_json(broken)
    except Exception as e:
        logger.warning(f"[stress-test] Parser correctly rejected broken input: {e}")
    return _build_fallback_with_patient_data(patient_data)
```

- [ ] **Step 4: Add `is_fallback` to `TriageResponse` in `schemas.py`**

In `backend/models/schemas.py`, update `TriageResponse`:

```python
class TriageResponse(BaseModel):
    triage_level: str
    triage_reason: str
    top_conditions: list[Condition]
    followup_questions: list[str]
    soap_summary: SoapNote
    disclaimer: str
    is_fallback: bool = False
```

- [ ] **Step 5: Run new tests**

```bash
cd backend && python -m pytest tests/test_triage.py::test_stress_test_returns_fallback_shape tests/test_triage.py::test_stress_test_parser_chain_fires -v
```

Expected: Both PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/triage_service.py backend/models/schemas.py backend/tests/test_triage.py
git commit -m "feat: add run_fallback_stress_test and is_fallback field to TriageResponse schema"
```

---

## Task 3: Add `POST /api/triage/test-fallback` route

**Files:**
- Modify: `backend/app/api/routes/triage.py`
- Modify: `backend/tests/test_triage.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_triage.py`:

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_test_fallback_endpoint_returns_is_fallback():
    res = client.post("/api/triage/test-fallback", json={
        "chief_complaint": "Nahihilo.",
        "age": 40,
        "sex": "M",
        "bp": "140/90",
        "temperature": "37.2",
        "heart_rate": None,
        "spo2": None,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_fallback"] is True
    assert data["triage_level"] == "YELLOW"
    assert "Nahihilo." in data["soap_summary"]["S"]

def test_test_fallback_endpoint_empty_body():
    res = client.post("/api/triage/test-fallback", json={
        "chief_complaint": "Walang nabanggit."
    })
    assert res.status_code == 200
    assert res.json()["is_fallback"] is True
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_triage.py::test_test_fallback_endpoint_returns_is_fallback -v
```

Expected: `404` or route not found.

- [ ] **Step 3: Add the route to `triage.py`**

Add the import at the top of `backend/app/api/routes/triage.py`:

```python
from app.services.triage_service import run_triage, run_fallback_stress_test
```

Then add the new route after the existing `/image` route:

```python
class FallbackTestRequest(BaseModel):
    chief_complaint: str = "No complaint recorded."
    age: int | None = None
    sex: str | None = None
    bp: str | None = None
    temperature: str | None = None
    heart_rate: str | None = None
    spo2: str | None = None


from pydantic import BaseModel as _BaseModel

class FallbackTestRequest(_BaseModel):
    chief_complaint: str = "No complaint recorded."
    age: int | None = None
    sex: str | None = None
    bp: str | None = None
    temperature: str | None = None
    heart_rate: str | None = None
    spo2: str | None = None


@router.post("/test-fallback", response_model=TriageResponse)
async def test_fallback(body: FallbackTestRequest = None):
    """
    Demo endpoint: feeds broken JSON through _parse_triage_json, returns is_fallback result.
    No DB writes. Safe to call repeatedly.
    """
    patient_data = {
        "chief_complaint": body.chief_complaint if body else "No complaint recorded.",
        "age": body.age if body else None,
        "sex": body.sex if body else None,
        "bp": body.bp if body else None,
        "temperature": body.temperature if body else None,
        "heart_rate": body.heart_rate if body else None,
        "spo2": body.spo2 if body else None,
        "followup_answers": None,
        "initial_assessment": None,
        "image_findings": None,
    }
    return await run_fallback_stress_test(patient_data)
```

**Note:** The `FallbackTestRequest` class should be defined once at module level (remove the duplicate). The correct version to keep:

```python
from pydantic import BaseModel as PydanticModel

class FallbackTestRequest(PydanticModel):
    chief_complaint: str = "No complaint recorded."
    age: int | None = None
    sex: str | None = None
    bp: str | None = None
    temperature: str | None = None
    heart_rate: str | None = None
    spo2: str | None = None


@router.post("/test-fallback", response_model=TriageResponse)
async def test_fallback(body: FallbackTestRequest | None = None):
    patient_data = {
        "chief_complaint": body.chief_complaint if body else "No complaint recorded.",
        "age": body.age if body else None,
        "sex": body.sex if body else None,
        "bp": body.bp if body else None,
        "temperature": body.temperature if body else None,
        "heart_rate": body.heart_rate if body else None,
        "spo2": body.spo2 if body else None,
        "followup_answers": None,
        "initial_assessment": None,
        "image_findings": None,
    }
    return await run_fallback_stress_test(patient_data)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_triage.py::test_test_fallback_endpoint_returns_is_fallback tests/test_triage.py::test_test_fallback_endpoint_empty_body -v
```

Expected: Both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/triage.py backend/tests/test_triage.py
git commit -m "feat: add POST /api/triage/test-fallback route for demo stress testing"
```

---

## Task 4: Frontend — fallback UI in `screen-result`

**Files:**
- Modify: `frontend/templates/index.html`
- Modify: `frontend/static/js/app.js`

- [ ] **Step 1: Add fallback banner and selector markup to `screen-result` in `index.html`**

Inside `<div id="screen-result" ...>`, immediately after the opening `<div class="px-4 py-5 flex flex-col gap-4">`, add:

```html
<!-- Fallback banner — shown only when is_fallback=true -->
<div id="fallback-banner" class="hidden flex-col gap-4">
  <div class="bg-amber-50 rounded-2xl shadow-sm px-5 py-4 border-l-4 border-amber-500 flex items-start gap-4">
    <span class="text-3xl leading-none mt-0.5">⚠️</span>
    <div>
      <div class="font-display font-bold text-amber-900 text-base leading-tight">AI Assessment Failed</div>
      <div class="text-sm text-amber-800 mt-1 leading-snug">
        Please assign the triage level manually before saving.
      </div>
    </div>
  </div>
  <div class="flex flex-col gap-3">
    <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Select Triage Level</p>
    <button onclick="selectManualLevel('RED')" id="manual-btn-red"
      class="w-full bg-danger text-white font-display font-black text-xl py-4 rounded-2xl active:scale-95 transition-transform opacity-60">
      🔴 RED — Critical, Refer Now
    </button>
    <button onclick="selectManualLevel('YELLOW')" id="manual-btn-yellow"
      class="w-full bg-yellow-400 text-white font-display font-black text-xl py-4 rounded-2xl active:scale-95 transition-transform opacity-60">
      🟡 YELLOW — See Doctor Today
    </button>
    <button onclick="selectManualLevel('GREEN')" id="manual-btn-green"
      class="w-full bg-forest text-white font-display font-black text-xl py-4 rounded-2xl active:scale-95 transition-transform opacity-60">
      🟢 GREEN — Home Care
    </button>
  </div>
</div>
```

Then wrap the existing AI content (the Preliminary Assessment notice, conditions list, and follow-up questions section) in a `<div id="ai-result-content">`:

```html
<!-- AI result content — hidden when is_fallback=true -->
<div id="ai-result-content">
  <!-- ... existing preliminary notice, conditions, follow-up questions ... -->
</div>
```

Update the existing action buttons at the bottom of `screen-result`. Change the "Skip & Save Patient" button to also work as the save trigger in fallback mode:

```html
<div class="flex flex-col gap-3">
  <button onclick="refineWithFollowup()" id="btn-refine-followup"
    class="w-full bg-navy text-white font-semibold py-4 rounded-2xl text-base active:scale-95 transition-transform">
    🔄 Submit Answers & Save
  </button>
  <button onclick="proceedToSummary()" id="btn-proceed-summary"
    class="w-full bg-forest text-white font-display font-bold py-4 rounded-2xl text-base active:scale-95 transition-transform">
    ✅ Skip & Save Patient
  </button>
</div>
```

- [ ] **Step 2: Add `simulateAIFailure()` and manual level state to `app.js`**

In the `state` object (near the top of `app.js`), add:

```javascript
manualTriageLevel: null,
```

Add the new functions after `renderTriageResult`:

```javascript
function selectManualLevel(level) {
  state.manualTriageLevel = level;
  const colors = { RED: 'bg-danger', YELLOW: 'bg-yellow-400', GREEN: 'bg-forest' };
  ['RED', 'YELLOW', 'GREEN'].forEach(l => {
    const btn = document.getElementById(`manual-btn-${l.toLowerCase()}`);
    if (btn) {
      btn.classList.toggle('opacity-60', l !== level);
      btn.classList.toggle('ring-4', l === level);
      btn.classList.toggle('ring-white', l === level);
      btn.classList.toggle('ring-offset-2', l === level);
    }
  });
  document.getElementById('btn-proceed-summary').disabled = false;
}

async function simulateAIFailure() {
  const complaint = readComplaint() || 'Simulated patient complaint.';
  const sexEl = document.querySelector('input[name="sex"]:checked');
  const bpSys = document.getElementById('input-bp-sys')?.value.trim() || '';
  const bpDia = document.getElementById('input-bp-dia')?.value.trim() || '';
  const bp = bpSys && bpDia ? `${bpSys}/${bpDia}` : '';

  showScreen('screen-loading', true);
  startLoadingAnimation(false);

  try {
    const res = await fetch('/api/triage/test-fallback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chief_complaint: complaint,
        age: parseInt(document.getElementById('input-age')?.value) || null,
        sex: sexEl ? sexEl.value : null,
        bp: bp || null,
        temperature: document.getElementById('input-temp')?.value.trim() || null,
        heart_rate: document.getElementById('input-hr')?.value.trim() || null,
        spo2: document.getElementById('input-spo2')?.value.trim() || null,
      }),
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const result = await res.json();
    state.currentTriageResult = result;
    state.manualTriageLevel = null;
    stopLoadingAnimation();
    renderTriageResult(result);
    showScreen('screen-result');
  } catch (err) {
    stopLoadingAnimation();
    showScreen('screen-intake');
    showError(`Stress test failed: ${err.message}`);
  }
}
```

- [ ] **Step 3: Update `renderTriageResult()` to handle `is_fallback`**

At the **start** of `renderTriageResult(result)` in `app.js`, add:

```javascript
function renderTriageResult(result) {
  const isFallback = result.is_fallback === true;

  // Show/hide fallback vs AI content
  const fallbackBanner = document.getElementById('fallback-banner');
  const aiContent = document.getElementById('ai-result-content');
  const btnRefine = document.getElementById('btn-refine-followup');
  const btnSave = document.getElementById('btn-proceed-summary');

  if (fallbackBanner) fallbackBanner.classList.toggle('hidden', !isFallback);
  if (fallbackBanner) fallbackBanner.classList.toggle('flex', isFallback);
  if (aiContent) aiContent.classList.toggle('hidden', isFallback);
  if (btnRefine) btnRefine.classList.toggle('hidden', isFallback);
  if (btnSave) btnSave.disabled = isFallback; // disabled until manual level chosen

  if (isFallback) return; // no AI content to render

  // ... rest of existing renderTriageResult code unchanged ...
```

- [ ] **Step 4: Update `proceedToSummary()` to use `manualTriageLevel` when fallback**

In `proceedToSummary()`, after `const result = state.currentTriageResult;`, add:

```javascript
  // Use manually selected level when AI failed
  if (result.is_fallback && state.manualTriageLevel) {
    result.triage_level = state.manualTriageLevel;
    result.soap_summary.P = `Refer to physician for evaluation. Manual triage level: ${state.manualTriageLevel}.`;
  }
```

And in the patient save payload (where `triage_level: result.triage_level` is set), no change needed — `result.triage_level` is already updated by the line above.

- [ ] **Step 5: Add "Simulate AI Failure" button to `screen-intake`**

In `frontend/templates/index.html`, immediately before the closing `</div>` of `screen-intake` (after the `camera-input` hidden input, around line 250), add:

```html
<!-- Demo stress-test trigger -->
<div class="px-4 pb-3 text-center">
  <button onclick="simulateAIFailure()"
    class="text-xs text-gray-400 underline underline-offset-2 active:text-gray-600">
    Simulate AI Failure
  </button>
</div>
```

- [ ] **Step 6: Manual smoke test**

Start the server:
```bash
cd backend && uvicorn main:app --reload
```

Open `http://localhost:8000` in the browser. Run through this checklist:

1. Fill in a chief complaint and vitals on the intake screen
2. Tap **"Simulate AI Failure"** — loading screen should appear, then `screen-result` should show
3. Verify amber banner "AI Assessment Failed" is visible
4. Verify AI conditions list and follow-up questions are hidden
5. Tap **YELLOW** — button should highlight (ring), others dim
6. Tap **Skip & Save Patient** — summary screen should show YELLOW verdict panel
7. Verify SOAP S contains the complaint you typed, O contains vitals
8. Tap **Generate PDF** — verify PDF generates without error
9. Normal triage path: fill complaint, tap **ASSESS WITH GEMMA** (requires Ollama running) — verify banner does NOT appear

- [ ] **Step 7: Commit**

```bash
git add frontend/templates/index.html frontend/static/js/app.js
git commit -m "feat: fallback UI — amber banner, manual RED/YELLOW/GREEN selector, Simulate AI Failure button"
```

---

## Self-Review

**Spec coverage:**
- ✅ `is_fallback: true` flag in API response — Task 2 (schema) + Task 1 (service)
- ✅ SOAP auto-populated from patient data — Task 1 (`_build_fallback_with_patient_data`)
- ✅ Call sites updated — Task 1 Step 4
- ✅ `POST /api/triage/test-fallback` — Task 3
- ✅ Amber banner in `screen-result` — Task 4 Step 1
- ✅ RED/YELLOW/GREEN selector — Task 4 Step 1
- ✅ Save disabled until level chosen — Task 4 Steps 2–3
- ✅ Manual level used in save payload — Task 4 Step 4
- ✅ "Simulate AI Failure" button in `screen-intake` — Task 4 Step 5
- ✅ `simulateAIFailure()` function — Task 4 Step 2
- ✅ Backend 422 guard — already enforced by existing Pydantic `PatientCreate.triage_level: str` + route validation; `proceedToSummary` sets a valid level from the three buttons only

**Type consistency:**
- `_build_fallback_with_patient_data` defined in Task 1, imported by `run_fallback_stress_test` in Task 2 — ✅
- `run_fallback_stress_test` defined in Task 2, imported by route in Task 3 — ✅
- `selectManualLevel(level)` defined in Task 4 Step 2, called from HTML buttons in Task 4 Step 1 — ✅
- `simulateAIFailure()` defined in Task 4 Step 2, called from HTML button in Task 4 Step 5 — ✅
- `state.manualTriageLevel` initialized in Task 4 Step 2, read in `proceedToSummary` in Task 4 Step 4 — ✅

**Note on existing tests:** `test_triage.py` imports `_parse_triage_response` and mocks `_get_gemma_llm` — both are stale names from a prior pipeline version. Those tests will fail on import. The new tests added in Tasks 1–3 use the correct current names (`_parse_triage_json`, `_call_gemma`, `_build_fallback_with_patient_data`). Fixing the stale tests is out of scope for this feature.
