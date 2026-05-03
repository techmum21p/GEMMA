// ── State ──────────────────────────────────────────────────────────────────
const state = {
  shiftId: null,
  bhwName: null,
  coordinatorEmail: null,
  currentPatientId: null,
  currentTriageResult: null,
  capturedImageFile: null,
  capturedImagePath: null,
  screenHistory: [],
  patients: [],
  logFilter: 'ALL',
};

// ── Screen Management ──────────────────────────────────────────────────────
function showScreen(screenId, addToHistory = true) {
  if (addToHistory && state.screenHistory[state.screenHistory.length - 1] !== screenId) {
    state.screenHistory.push(screenId);
  }

  document.querySelectorAll('[data-screen]').forEach(el => {
    el.classList.add('hidden');
    el.classList.remove('screen-active');
  });

  const target = document.getElementById(screenId);
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('screen-active');
  }

  const header = document.getElementById('app-header');
  const bottomNav = document.getElementById('bottom-nav');
  const subtitle = document.getElementById('header-subtitle');

  const subtitles = {
    'screen-intake':      'New Patient',
    'screen-result':      'Triage Result',
    'screen-summary':     'Handoff Summary',
    'screen-log':         'Patient Log',
    'screen-endshift':    'End Shift',
    'screen-loading':     'Analyzing...',
    'screen-pdf-viewer':  'Patient PDF',
  };

  if (screenId === 'screen-home' || screenId === 'screen-pdf-viewer') {
    header.classList.add('hidden');
    bottomNav.classList.add('hidden');
  } else {
    header.classList.remove('hidden');
    subtitle.textContent = subtitles[screenId] || 'GEMMA';

    if (state.shiftId) {
      bottomNav.classList.remove('hidden');
      document.getElementById('shift-info-header').classList.remove('hidden');
      document.getElementById('header-bhw-name').textContent = state.bhwName || '';
      updatePatientCountBadge();
    }
  }

  window.scrollTo(0, 0);
}

function goBack() {
  state.screenHistory.pop();
  const prev = state.screenHistory[state.screenHistory.length - 1] || 'screen-home';
  showScreen(prev, false);
}

function updatePatientCountBadge() {
  const count = state.patients.length;
  document.getElementById('header-patient-count').textContent = `${count} patient${count !== 1 ? 's' : ''}`;

  const badge = document.getElementById('nav-patient-count');
  if (count > 0) {
    badge.textContent = count;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

// ── Loading Animation ──────────────────────────────────────────────────────
let _loadingInterval = null;

function startLoadingAnimation(hasImage = false) {
  const messages = hasImage ? [
    'Reading chief complaint...',
    'Analyzing the photo with MedGemma...',
    'Combining image and symptom data...',
    'Running differential diagnosis...',
    'Assigning triage level...',
    'Writing follow-up questions...',
    'Generating SOAP note...',
    'Almost done...',
  ] : [
    'Reading chief complaint...',
    'Running differential diagnosis...',
    'Assigning triage level...',
    'Ranking possible conditions...',
    'Writing follow-up questions...',
    'Generating SOAP note...',
    'Almost done...',
  ];

  let elapsed = 0;
  let msgIndex = 0;
  const bar = document.getElementById('loading-bar');
  const timer = document.getElementById('loading-timer');
  const msg = document.getElementById('loading-message');

  msg.textContent = messages[0];
  bar.style.width = '5%';

  _loadingInterval = setInterval(() => {
    elapsed++;
    timer.textContent = `${elapsed}s elapsed`;

    // Advance message every ~5 seconds
    const nextMsg = Math.min(Math.floor(elapsed / 5), messages.length - 1);
    if (nextMsg !== msgIndex) {
      msgIndex = nextMsg;
      msg.textContent = messages[msgIndex];
    }

    // Progress bar: grows to 90% over 45 seconds, then stalls
    const pct = Math.min(5 + (elapsed / 45) * 85, 90);
    bar.style.width = `${pct}%`;
  }, 1000);
}

function stopLoadingAnimation() {
  if (_loadingInterval) {
    clearInterval(_loadingInterval);
    _loadingInterval = null;
  }
  const bar = document.getElementById('loading-bar');
  if (bar) bar.style.width = '100%';
}

// ── Toast & Error ──────────────────────────────────────────────────────────
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.remove('opacity-0');
  toast.classList.add('opacity-100');
  setTimeout(() => {
    toast.classList.remove('opacity-100');
    toast.classList.add('opacity-0');
  }, duration);
}

function showError(message) {
  document.getElementById('error-message').textContent = message;
  document.getElementById('error-modal').classList.remove('hidden');
}

function closeErrorModal() {
  document.getElementById('error-modal').classList.add('hidden');
}

// ── Chief Complaint — auto-bullet textarea ─────────────────────────────────
(function initComplaintBullet() {
  // Wait for DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    const ta = document.getElementById('input-complaint');
    if (!ta) return;

    ta.addEventListener('focus', () => {
      if (!ta.value.trim()) ta.value = '• ';
    });

    ta.addEventListener('keydown', e => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const pos   = ta.selectionStart;
      const val   = ta.value;
      const insert = '\n• ';
      ta.value = val.slice(0, pos) + insert + val.slice(ta.selectionEnd);
      ta.selectionStart = ta.selectionEnd = pos + insert.length;
    });

    // Backspace on an empty bullet line removes it
    ta.addEventListener('keydown', e => {
      if (e.key !== 'Backspace') return;
      const pos = ta.selectionStart;
      const val = ta.value;
      if (pos >= 2 && val.slice(pos - 2, pos) === '• ') {
        e.preventDefault();
        ta.value = val.slice(0, pos - 2) + val.slice(pos);
        ta.selectionStart = ta.selectionEnd = pos - 2;
      }
    });
  });
})();

// Helper: read complaint textarea, strip bullet markers, return plain newline-separated text
function readComplaint() {
  const raw = document.getElementById('input-complaint').value;
  return raw
    .split('\n')
    .map(l => l.replace(/^[•·\-]\s*/, '').trim())
    .filter(Boolean)
    .join('\n');
}

// Helper: render complaint text as bullet items into a container element
function renderComplaintBullets(text, container) {
  const lines = text.split('\n').filter(l => l.trim());
  container.innerHTML = lines.map(l =>
    `<div class="flex items-start gap-2">
       <span class="text-navy font-bold leading-tight mt-0.5 select-none">•</span>
       <span class="leading-snug">${l.trim()}</span>
     </div>`
  ).join('');
}

// ── Shift ──────────────────────────────────────────────────────────────────
async function startShift() {
  const bhwName = document.getElementById('input-bhw-name').value.trim();
  if (!bhwName) { showError('Please enter your BHW name to start the shift.'); return; }

  try {
    const res = await fetch('/api/shifts/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bhw_name: bhwName, coordinator_email: '' }),
    });

    if (!res.ok) throw new Error(await res.text());
    const shift = await res.json();

    state.shiftId = shift.id;
    state.bhwName = shift.bhw_name;
    state.coordinatorEmail = '';
    state.screenHistory = ['screen-home'];

    clearIntakeForm();
    showToast(`Shift started. Welcome, ${bhwName}!`);
    showScreen('screen-intake');
  } catch (err) {
    showError(`Could not start shift: ${err.message}`);
  }
}

// ── Triage Submission ──────────────────────────────────────────────────────
async function submitTriage() {
  const complaint = readComplaint();
  if (!complaint) { showError('Please describe the patient\'s chief complaint.'); return; }

  const hasImage = !!state.capturedImageFile;
  showScreen('screen-loading', true);
  startLoadingAnimation(hasImage);

  try {
    const sexEl = document.querySelector('input[name="sex"]:checked');
    const bpSys = document.getElementById('input-bp-sys')?.value.trim() || '';
    const bpDia = document.getElementById('input-bp-dia')?.value.trim() || '';
    const bp = bpSys && bpDia ? `${bpSys}/${bpDia}` : (bpSys || bpDia || '');

    const fd = new FormData();
    fd.append('chief_complaint', complaint);
    fd.append('followup_answers', '{}');
    fd.append('image_findings', '');
    fd.append('bp',          bp);
    fd.append('temperature', document.getElementById('input-temp')?.value.trim() || '');
    fd.append('heart_rate',  document.getElementById('input-hr')?.value.trim()   || '');
    fd.append('spo2',        document.getElementById('input-spo2')?.value.trim() || '');
    fd.append('age',         document.getElementById('input-age')?.value.trim()  || '');
    fd.append('sex',         sexEl ? sexEl.value : '');

    let endpoint = '/api/triage';
    if (hasImage) {
      endpoint = '/api/triage/image';
      fd.append('image', state.capturedImageFile, state.capturedImageFile.name || 'photo.jpg');
    }

    const res = await fetch(endpoint, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);

    const result = await res.json();
    state.currentTriageResult = result;

    if (result.image_path) state.capturedImagePath = result.image_path;
    if (result.image_findings) {
      document.getElementById('image-findings-text').textContent = result.image_findings;
      document.getElementById('image-findings-card').classList.remove('hidden');
    }

    stopLoadingAnimation();
    renderTriageResult(result);
    showScreen('screen-result');
  } catch (err) {
    stopLoadingAnimation();
    showScreen('screen-intake');
    showError(`Triage failed: ${err.message}\n\nMake sure Ollama is running.`);
  }
}

function renderTriageResult(result) {
  // Render chief complaint as bullet list
  const complaintEl = document.getElementById('result-complaint-list');
  if (complaintEl) renderComplaintBullets(readComplaint(), complaintEl);

  const condList = document.getElementById('conditions-list');
  condList.innerHTML = '';
  const _COND_SKIP = new Set(['additional assessment needed', 'n/a', 'na', 'unable to assess']);
  const _COND_FALLBACK = /^condition\s*\d+$/i;
  const realConditions = (result.top_conditions || []).filter(c => {
    const name = (c.condition || '').trim();
    return name && !_COND_SKIP.has(name.toLowerCase()) && !_COND_FALLBACK.test(name);
  });
  const heading = document.getElementById('conditions-heading');
  if (heading) heading.textContent = `Top ${realConditions.length} Possible Condition${realConditions.length !== 1 ? 's' : ''}`;
  realConditions.forEach((c, i) => {
    const el = document.createElement('div');
    el.className = 'flex gap-3 items-start p-3 bg-light rounded-xl';
    el.innerHTML = `
      <div class="bg-navy text-white text-xs font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 mt-0.5">${i + 1}</div>
      <div>
        <div class="font-semibold text-sm text-navy">${c.condition}</div>
        <div class="text-xs text-gray-500 mt-0.5 leading-snug">${c.plain_explanation}</div>
      </div>`;
    condList.appendChild(el);
  });

  const fqList = document.getElementById('followup-questions-list');
  fqList.innerHTML = '';
  (result.followup_questions || []).forEach((q, i) => {
    const el = document.createElement('div');
    el.className = 'flex flex-col gap-1.5';
    el.innerHTML = `
      <label class="text-sm font-semibold text-gray-700">${i + 1}. ${q}</label>
      <textarea id="fq-answer-${i}" rows="2" placeholder="Patient's answer..."
        class="w-full border-2 border-gray-200 rounded-xl px-3 py-2 text-sm focus:border-navy focus:outline-none resize-none"></textarea>`;
    fqList.appendChild(el);
  });
}

async function refineWithFollowup() {
  const complaint = readComplaint();
  const questions = state.currentTriageResult?.followup_questions || [];
  const answers = {};

  questions.forEach((q, i) => {
    const el = document.getElementById(`fq-answer-${i}`);
    if (el && el.value.trim()) answers[q] = el.value.trim();
  });

  if (Object.keys(answers).length === 0) {
    showToast('Please answer at least one question before updating.');
    return;
  }

  showScreen('screen-loading', true);
  startLoadingAnimation(false);

  try {
    const sexElR = document.querySelector('input[name="sex"]:checked');
    const bpSysR = document.getElementById('input-bp-sys')?.value.trim() || '';
    const bpDiaR = document.getElementById('input-bp-dia')?.value.trim() || '';
    const bpR = bpSysR && bpDiaR ? `${bpSysR}/${bpDiaR}` : (bpSysR || bpDiaR || '');

    const fd = new FormData();
    fd.append('chief_complaint', complaint);
    fd.append('followup_answers', JSON.stringify(answers));
    if (state.currentTriageResult?.image_findings) {
      fd.append('image_findings', state.currentTriageResult.image_findings);
    }
    fd.append('bp',          bpR);
    fd.append('temperature', document.getElementById('input-temp')?.value.trim() || '');
    fd.append('heart_rate',  document.getElementById('input-hr')?.value.trim()   || '');
    fd.append('spo2',        document.getElementById('input-spo2')?.value.trim() || '');
    fd.append('age',         document.getElementById('input-age')?.value.trim()  || '');
    fd.append('sex',         sexElR ? sexElR.value : '');

    // Pass initial assessment as context so Gemma can refine — not restart — the analysis
    if (state.currentTriageResult) {
      fd.append('initial_assessment', JSON.stringify({
        triage_level:   state.currentTriageResult.triage_level,
        triage_reason:  state.currentTriageResult.triage_reason,
        top_conditions: state.currentTriageResult.top_conditions,
        soap_summary:   state.currentTriageResult.soap_summary,
      }));
    }

    const res = await fetch('/api/triage', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);

    const result = await res.json();
    state.followupQA = answers;  // save Q&A before currentTriageResult is replaced (refined result has followup_questions: [])
    state.currentTriageResult = result;
    stopLoadingAnimation();
    // Go straight to summary — answers have been incorporated, no need to loop
    await proceedToSummary();
  } catch (err) {
    stopLoadingAnimation();
    showScreen('screen-result');
    showError(`Could not update: ${err.message}`);
  }
}

async function proceedToSummary() {
  const result = state.currentTriageResult;
  if (!result) return;

  const soap = result.soap_summary || {};
  document.getElementById('soap-s').textContent = soap.S || '';
  document.getElementById('soap-o').textContent = soap.O || '';
  document.getElementById('soap-p').textContent = soap.P || '';

  // Assessment — conditions as bullets + SOAP A as optional clinical note
  const _SUMMARY_SKIP = new Set(['additional assessment needed', 'n/a', 'na', 'unable to assess']);
  const _SUMMARY_FALLBACK = /^condition\s*\d+$/i;
  const realConds = (result.top_conditions || []).filter(c => {
    const name = (c.condition || '').trim();
    return name && !_SUMMARY_SKIP.has(name.toLowerCase()) && !_SUMMARY_FALLBACK.test(name);
  });
  document.getElementById('soap-a-conditions').innerHTML = realConds.map(c =>
    `<div class="flex gap-2 items-start text-sm">
      <span class="text-navy font-bold flex-shrink-0 mt-0.5">•</span>
      <span><span class="font-semibold text-gray-800">${c.condition}</span><span class="text-gray-500"> — ${c.plain_explanation}</span></span>
    </div>`
  ).join('');
  const noteEl = document.getElementById('soap-a-note');
  if (soap.A) { noteEl.textContent = `Note: ${soap.A}`; noteEl.classList.remove('hidden'); }
  else noteEl.classList.add('hidden');

  const complaint = readComplaint();
  const name      = document.getElementById('input-name').value.trim() || null;
  const age       = parseInt(document.getElementById('input-age').value) || null;
  const address   = document.getElementById('input-address').value.trim() || null;
  const bpSysP = document.getElementById('input-bp-sys')?.value.trim() || '';
  const bpDiaP = document.getElementById('input-bp-dia')?.value.trim() || '';
  const bp     = bpSysP && bpDiaP ? `${bpSysP}/${bpDiaP}` : (bpSysP || bpDiaP || null);
  const temp       = document.getElementById('input-temp').value.trim() || null;
  const heart_rate = document.getElementById('input-hr').value.trim()   || null;
  const spo2       = document.getElementById('input-spo2').value.trim() || null;
  const sexEl     = document.querySelector('input[name="sex"]:checked');
  const sex       = sexEl ? sexEl.value : null;

  // Use Q&A saved before refined result replaced followup_questions with []
  const followup_qa = state.followupQA || {};

  // Age chip
  const chipAge = document.getElementById('chip-age');
  if (age) { chipAge.textContent = `${age}y`; chipAge.classList.remove('hidden'); }
  else chipAge.classList.add('hidden');

  // Sex chip
  const chipSex = document.getElementById('chip-sex');
  if (sex) { chipSex.textContent = sex === 'M' ? 'Male' : 'Female'; chipSex.classList.remove('hidden'); }
  else chipSex.classList.add('hidden');

  // Triage level chip (small pill in chips row)
  const triageChipCfg = {
    RED:    { bg: 'bg-danger',  label: '✱ RED TRIAGE' },
    YELLOW: { bg: 'bg-amber',   label: '⚡ YELLOW TRIAGE' },
    GREEN:  { bg: 'bg-forest',  label: '● GREEN TRIAGE' },
  };
  const tc = triageChipCfg[result.triage_level] || triageChipCfg.YELLOW;
  const chipTriage = document.getElementById('chip-triage');
  chipTriage.textContent = tc.label;
  chipTriage.className = `text-white text-sm font-bold px-4 py-1.5 rounded-full flex items-center gap-1.5 ${tc.bg}`;

  // Full-width verdict panel
  const verdictCfg = {
    RED:    { bg: 'bg-danger',  level: 'RED',    action: 'CRITICAL — Refer to RHU / Hospital Immediately' },
    YELLOW: { bg: 'bg-amber',   level: 'YELLOW', action: 'URGENT — See Doctor On-Site at BHS' },
    GREEN:  { bg: 'bg-forest',  level: 'GREEN',  action: 'STABLE — Home Care / BHW-Managed' },
  };
  const vc = verdictCfg[result.triage_level] || verdictCfg.YELLOW;
  document.getElementById('verdict-panel').className = `rounded-2xl py-6 px-5 text-white text-center shadow-md ${vc.bg}`;
  document.getElementById('verdict-level').textContent = vc.level;
  document.getElementById('verdict-action').textContent = vc.action;

  try {
    const payload = {
      shift_id: state.shiftId,
      name, age, sex, address,
      bp: bp || null,
      temperature: temp || null,
      heart_rate: heart_rate || null,
      spo2: spo2 || null,
      chief_complaint: complaint,
      image_path: state.capturedImagePath || null,
      image_findings: result.image_findings || null,
      followup_qa,
      triage_level: result.triage_level,
      triage_reason: result.triage_reason || null,
      top_conditions: result.top_conditions,
      followup_questions: result.followup_questions || [],
      soap_notes: JSON.stringify(result.soap_summary),
    };

    const res = await fetch('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(await res.text());
    const patient = await res.json();
    state.currentPatientId = patient.id;
    state.patients.push(patient);
    updatePatientCountBadge();

    document.getElementById('summary-encounter-id').textContent =
      `Encounter ID: #GEM-${String(patient.id).padStart(4, '0')}`;

    showScreen('screen-summary');
    startEnrichmentPolling(patient.id);
  } catch (err) {
    showError(`Could not save patient: ${err.message}`);
  }
}

function startEnrichmentPolling(patientId) {
  const badge = document.getElementById('enrichment-status');
  if (!badge) return;

  badge.className = 'text-xs text-center px-2 py-1 rounded-lg bg-amber-50 text-amber-700';
  badge.textContent = 'Preparing clinical notes for PDF...';
  badge.classList.remove('hidden');

  let attempts = 0;
  const MAX_ATTEMPTS = 40; // 40 × 3s = 2 min max

  const poll = setInterval(async () => {
    attempts++;
    try {
      const res = await fetch(`/api/export/enrichment-status/${patientId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.ready) {
          clearInterval(poll);
          badge.className = 'text-xs text-center px-2 py-1 rounded-lg bg-green-50 text-green-700';
          badge.textContent = 'Clinical notes ready — PDF will generate instantly';
          setTimeout(() => badge.classList.add('hidden'), 4000);
        }
      }
    } catch (_) { /* network blip — keep polling */ }

    if (attempts >= MAX_ATTEMPTS) {
      clearInterval(poll);
      badge.classList.add('hidden');
    }
  }, 3000);
}

let _pdfBlobUrl = null;

async function generatePDF() {
  if (!state.currentPatientId) { showError('No patient saved yet.'); return; }

  const btn = document.getElementById('btn-generate-pdf');
  btn.textContent = '⏳ Generating...';
  btn.disabled = true;

  try {
    const res = await fetch(`/api/export/pdf/${state.currentPatientId}`);
    if (!res.ok) throw new Error(await res.text());

    const blob = await res.blob();
    if (_pdfBlobUrl) URL.revokeObjectURL(_pdfBlobUrl);
    _pdfBlobUrl = URL.createObjectURL(blob);

    _openPDFViewer(_pdfBlobUrl);
  } catch (err) {
    showError(`Could not generate PDF: ${err.message}`);
  } finally {
    btn.textContent = '↓ Generate PDF Handoff';
    btn.disabled = false;
  }
}

function _openPDFViewer(blobUrl) {
  const encounterId = document.getElementById('summary-encounter-id')?.textContent || '';
  document.getElementById('pdf-viewer-title').textContent = encounterId;

  // Reset viewer state
  const iframe  = document.getElementById('pdf-iframe');
  const loading = document.getElementById('pdf-viewer-loading');
  const fallback = document.getElementById('pdf-viewer-fallback');
  iframe.classList.add('hidden');
  loading.classList.remove('hidden');
  fallback.classList.add('hidden');
  iframe.src = '';

  showScreen('screen-pdf-viewer');

  // Load PDF — give the iframe 5 seconds to show content before showing fallback
  let loaded = false;
  iframe.onload = () => {
    if (loaded) return;
    loaded = true;
    loading.classList.add('hidden');
    iframe.classList.remove('hidden');
  };
  setTimeout(() => {
    if (loaded) return;
    loading.classList.add('hidden');
    fallback.classList.remove('hidden');
  }, 5000);

  iframe.src = blobUrl;
}

function closePDFViewer() {
  // Go back to summary; don't add pdf-viewer to history again
  showScreen('screen-summary', false);
}

function saveAndNewPatient() {
  clearIntakeForm();
  showScreen('screen-intake');
}

function clearIntakeForm() {
  ['input-name', 'input-age', 'input-address', 'input-bp-sys', 'input-bp-dia', 'input-temp', 'input-hr', 'input-spo2', 'input-complaint'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.querySelectorAll('input[name="sex"]').forEach(el => el.checked = false);
  updateSexToggle();
  clearPhoto();
  state.capturedImageFile = null;
  state.capturedImagePath = null;
  state.currentTriageResult = null;
  state.currentPatientId = null;
  state.followupQA = null;
  document.getElementById('image-findings-card').classList.add('hidden');
}

// ── Patient Log ────────────────────────────────────────────────────────────
async function refreshPatientLog() {
  if (!state.shiftId) return;

  try {
    const res = await fetch(`/api/patients?shift_id=${state.shiftId}`);
    if (!res.ok) throw new Error('Failed to fetch patients');
    state.patients = await res.json();
    renderPatientLog();
  } catch {
    showToast('Could not load patient log.');
  }
}

function filterLog(level) {
  state.logFilter = level;
  document.querySelectorAll('.log-filter').forEach(btn => {
    const active = btn.id === `filter-${level}`;
    btn.className = `log-filter px-4 py-1.5 rounded-full text-sm font-semibold ${
      active ? 'bg-navy text-white' : 'bg-white text-gray-600 border border-gray-200'
    }`;
  });
  renderPatientLog();
}

function renderPatientLog() {
  const list = document.getElementById('patient-log-list');
  const empty = document.getElementById('log-empty');
  list.innerHTML = '';

  const red    = state.patients.filter(p => p.triage_level === 'RED').length;
  const yellow = state.patients.filter(p => p.triage_level === 'YELLOW').length;
  const green  = state.patients.filter(p => p.triage_level === 'GREEN').length;

  document.getElementById('stat-red').textContent    = red;
  document.getElementById('stat-yellow').textContent = yellow;
  document.getElementById('stat-green').textContent  = green;
  updatePatientCountBadge();

  const filtered = state.logFilter === 'ALL'
    ? state.patients
    : state.patients.filter(p => p.triage_level === state.logFilter);

  if (filtered.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  const dotColors  = { RED: 'bg-danger', YELLOW: 'bg-amber', GREEN: 'bg-forest' };
  const statuses   = ['Pending', 'Seen', 'Referred', 'Sent Home'];

  filtered.slice().reverse().forEach(p => {
    let conditions = [];
    try { conditions = JSON.parse(p.top_conditions || '[]'); } catch {}
    const topCond = conditions[0]?.condition || '—';
    const timeStr = new Date(p.timestamp).toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' });

    const card = document.createElement('div');
    card.className = 'bg-white rounded-xl shadow-sm p-4 flex flex-col gap-2';
    card.innerHTML = `
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <div class="w-3 h-3 rounded-full flex-shrink-0 ${dotColors[p.triage_level] || 'bg-amber'}"></div>
          <span class="font-semibold text-sm truncate">${p.name || 'Anonymous'}</span>
          ${p.age ? `<span class="text-xs text-gray-400 flex-shrink-0">${p.age}${p.sex || ''}</span>` : ''}
        </div>
        <span class="text-xs text-gray-400 flex-shrink-0">${timeStr}</span>
      </div>
      <div class="text-sm text-gray-600 line-clamp-2">${p.chief_complaint}</div>
      <div class="text-xs text-gray-400">Top: ${topCond}</div>
      <div class="flex items-center gap-2 mt-1">
        <select onchange="updateStatus(${p.id}, this.value)"
          class="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-navy flex-1">
          ${statuses.map(s => `<option value="${s}" ${p.status === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
        <button onclick="downloadPatientPDF(${p.id})"
          class="text-xs text-navy underline px-2">PDF</button>
      </div>`;
    list.appendChild(card);
  });
}

async function updateStatus(patientId, status) {
  try {
    const res = await fetch(`/api/patients/${patientId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error('Update failed');
    const idx = state.patients.findIndex(p => p.id === patientId);
    if (idx !== -1) state.patients[idx].status = status;
    showToast(`Status updated: ${status}`);
  } catch {
    showError('Could not update status.');
  }
}

function downloadPatientPDF(patientId) {
  const a = document.createElement('a');
  a.href = `/api/export/pdf/${patientId}`;
  a.target = '_blank';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ── End Shift ──────────────────────────────────────────────────────────────
function prepareEndShift() {
  const red    = state.patients.filter(p => p.triage_level === 'RED').length;
  const yellow = state.patients.filter(p => p.triage_level === 'YELLOW').length;
  const green  = state.patients.filter(p => p.triage_level === 'GREEN').length;

  document.getElementById('endshift-bhw').textContent  = state.bhwName || '';
  document.getElementById('endshift-date').textContent = new Date().toLocaleDateString('en-PH', { dateStyle: 'long' });

  renderDonutChart(red, yellow, green);

  if (state.shiftId) {
    document.getElementById('btn-download-excel').href = `/api/export/excel/${state.shiftId}`;
  }

  // Top conditions (color-coded)
  const condCounts = {};
  state.patients.forEach(p => {
    try {
      const conds = JSON.parse(p.top_conditions || '[]');
      if (conds[0]?.condition) {
        condCounts[conds[0].condition] = (condCounts[conds[0].condition] || 0) + 1;
      }
    } catch {}
  });
  const topConds = Object.entries(condCounts).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const tcCard = document.getElementById('top-conditions-card');
  const tcList = document.getElementById('endshift-top-conditions');
  const rankColors = ['text-danger bg-danger/10', 'text-amber bg-amber/10', 'text-navy bg-navy/10'];
  if (topConds.length > 0) {
    tcCard.classList.remove('hidden');
    tcList.innerHTML = topConds.map(([name, count], i) => `
      <div class="flex items-center justify-between py-2.5 last:pb-0">
        <div class="flex items-center gap-2.5">
          <span class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-black flex-shrink-0 ${rankColors[i]}">${i + 1}</span>
          <span class="text-sm font-semibold text-gray-700">${name}</span>
        </div>
        <span class="text-xs font-semibold text-gray-500 ml-2 flex-shrink-0">${count} case${count !== 1 ? 's' : ''}</span>
      </div>`).join('');
  }
}

function renderDonutChart(red, yellow, green) {
  const total = red + yellow + green;
  const C = 2 * Math.PI * 52; // circumference for r=52

  document.getElementById('donut-total').textContent       = total;
  document.getElementById('donut-red-count').textContent   = red;
  document.getElementById('donut-yellow-count').textContent = yellow;
  document.getElementById('donut-green-count').textContent  = green;

  const gSeg = document.getElementById('donut-seg-green');
  const ySeg = document.getElementById('donut-seg-yellow');
  const rSeg = document.getElementById('donut-seg-red');

  if (total === 0) {
    [gSeg, ySeg, rSeg].forEach(s => { s.setAttribute('stroke-dasharray', `0 ${C}`); s.setAttribute('stroke-dashoffset', '0'); });
    return;
  }

  const gLen = (green  / total) * C;
  const yLen = (yellow / total) * C;
  const rLen = (red    / total) * C;

  // Negative dashoffset pushes each segment to start after the previous one
  gSeg.setAttribute('stroke-dasharray', `${gLen} ${C}`);
  gSeg.setAttribute('stroke-dashoffset', '0');

  ySeg.setAttribute('stroke-dasharray', `${yLen} ${C}`);
  ySeg.setAttribute('stroke-dashoffset', String(-gLen));

  rSeg.setAttribute('stroke-dasharray', `${rLen} ${C}`);
  rSeg.setAttribute('stroke-dashoffset', String(-(gLen + yLen)));
}

async function sendShiftEmail() {
  const emailInput = document.getElementById('input-coordinator-email');
  const email = emailInput.value.trim();

  if (!email || !email.includes('@')) {
    showError('Please enter a valid coordinator email address.');
    emailInput.focus();
    return;
  }

  state.coordinatorEmail = email;

  const btn = document.getElementById('btn-send-email');
  btn.textContent = '⏳ Sending...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/email/shift-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shift_id: state.shiftId, coordinator_email: email }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Email send failed');
    }

    showToast('Report sent to coordinator!', 4000);
    btn.textContent = '✅ Sent!';
  } catch (err) {
    showError(`Could not send email: ${err.message}`);
    btn.textContent = '📧 Send Report via Email';
    btn.disabled = false;
  }
}

async function confirmEndShift() {
  if (!confirm('End this shift? This will close the patient log.')) return;

  try {
    const res = await fetch(`/api/shifts/end?shift_id=${state.shiftId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to end shift');

    state.shiftId = null;
    state.bhwName = null;
    state.coordinatorEmail = null;
    state.patients = [];
    state.screenHistory = [];

    document.getElementById('bottom-nav').classList.add('hidden');
    document.getElementById('shift-info-header').classList.add('hidden');
    document.getElementById('input-bhw-name').value = '';

    showToast('Shift closed. Thank you!', 3000);
    setTimeout(() => showScreen('screen-home'), 500);
  } catch (err) {
    showError(`Could not close shift: ${err.message}`);
  }
}

// ── Sex Toggle ─────────────────────────────────────────────────────────────
function updateSexToggle() {
  const checked = document.querySelector('input[name="sex"]:checked')?.value;
  const mLabel = document.getElementById('sex-label-m');
  const fLabel = document.getElementById('sex-label-f');
  const baseClass = 'flex-1 flex items-center justify-center cursor-pointer transition-colors text-sm font-semibold';
  if (mLabel) mLabel.className = `${baseClass} ${checked === 'M' ? 'bg-navy text-white' : 'text-gray-600'}`;
  if (fLabel) fLabel.className = `${baseClass} ${checked === 'F' ? 'bg-navy text-white' : 'text-gray-600'}`;
}

// ── Init ───────────────────────────────────────────────────────────────────
showScreen('screen-home', false);
