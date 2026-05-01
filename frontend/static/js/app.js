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
    'screen-intake': 'Bagong Pasyente',
    'screen-result': 'Resulta ng Triage',
    'screen-summary': 'Handoff Summary',
    'screen-log': 'Patient Log',
    'screen-endshift': 'Tapusin ang Shift',
    'screen-loading': 'Sinusuri...',
  };

  if (screenId === 'screen-home') {
    header.classList.add('hidden');
    bottomNav.classList.add('hidden');
  } else {
    header.classList.remove('hidden');
    subtitle.textContent = subtitles[screenId] || 'GEMMA';

    if (state.shiftId) {
      bottomNav.classList.remove('hidden');
      document.getElementById('shift-info-header').classList.remove('hidden');
      document.getElementById('header-bhw-name').textContent = state.bhwName || '';
      document.getElementById('header-patient-count').textContent = `${state.patients.length} pasyente`;
    }
  }

  window.scrollTo(0, 0);
}

function goBack() {
  state.screenHistory.pop();
  const prev = state.screenHistory[state.screenHistory.length - 1] || 'screen-home';
  showScreen(prev, false);
}

// ── Toast ──────────────────────────────────────────────────────────────────
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

// ── Shift ──────────────────────────────────────────────────────────────────
async function startShift() {
  const bhwName = document.getElementById('input-bhw-name').value.trim();
  const email = document.getElementById('input-coordinator-email').value.trim();

  if (!bhwName) { showError('Mangyaring ilagay ang pangalan ng BHW.'); return; }
  if (!email || !email.includes('@')) { showError('Mangyaring maglagay ng valid na email ng coordinator.'); return; }

  try {
    const fd = new FormData();
    const res = await fetch('/api/shifts/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bhw_name: bhwName, coordinator_email: email }),
    });

    if (!res.ok) throw new Error(await res.text());
    const shift = await res.json();

    state.shiftId = shift.id;
    state.bhwName = shift.bhw_name;
    state.coordinatorEmail = shift.coordinator_email;
    state.screenHistory = ['screen-home'];

    showToast(`Shift nagsimula! Maligayang pagdating, ${bhwName}!`);
    showScreen('screen-intake');
  } catch (err) {
    showError(`Hindi ma-simulan ang shift: ${err.message}`);
  }
}

// ── Triage Submission ──────────────────────────────────────────────────────
async function submitTriage() {
  const complaint = document.getElementById('input-complaint').value.trim();
  if (!complaint) { showError('Mangyaring ilarawan ang sintomas ng pasyente.'); return; }

  showScreen('screen-loading', true);
  document.getElementById('loading-message').textContent = 'Hinihintay ang sagot ng GEMMA AI...';

  try {
    const fd = new FormData();
    fd.append('chief_complaint', complaint);
    fd.append('followup_answers', '{}');
    fd.append('image_findings', '');

    let endpoint = '/api/triage';

    if (state.capturedImageFile) {
      endpoint = '/api/triage/image';
      fd.append('image', state.capturedImageFile, state.capturedImageFile.name || 'photo.jpg');
      document.getElementById('loading-message').textContent = 'Sinusuri ang larawan at sintomas...';
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

    renderTriageResult(result);
    showScreen('screen-result');
  } catch (err) {
    showScreen('screen-intake');
    showError(`May problema sa triage: ${err.message}\n\nSiguraduhin na tumatakbo ang Ollama.`);
  }
}

function renderTriageResult(result) {
  const level = result.triage_level || 'YELLOW';
  const badge = document.getElementById('triage-badge-container');
  const levelText = document.getElementById('triage-level-text');
  const reasonText = document.getElementById('triage-reason-text');

  badge.className = badge.className.replace(/bg-\w+/g, '');
  const colors = { RED: 'bg-danger', YELLOW: 'bg-amber', GREEN: 'bg-forest' };
  badge.classList.add(colors[level] || 'bg-amber', 'rounded-2xl', 'shadow', 'p-5', 'text-center', 'text-white');

  const labels = { RED: '🔴 RED — Agarang Atensyon', YELLOW: '🟡 YELLOW — Konsultasyon', GREEN: '🟢 GREEN — Monitoring' };
  levelText.textContent = labels[level] || level;
  reasonText.textContent = result.triage_reason || '';

  const condList = document.getElementById('conditions-list');
  condList.innerHTML = '';
  (result.top_conditions || []).forEach(c => {
    const el = document.createElement('div');
    el.className = 'flex gap-3 items-start p-3 bg-light rounded-xl';
    el.innerHTML = `
      <div class="bg-navy text-white text-xs font-bold rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0">${c.rank}</div>
      <div>
        <div class="font-semibold text-sm text-navy">${c.condition}</div>
        <div class="text-xs text-gray-500 mt-0.5">${c.plain_explanation}</div>
      </div>`;
    condList.appendChild(el);
  });

  const fqList = document.getElementById('followup-questions-list');
  fqList.innerHTML = '';
  (result.followup_questions || []).forEach((q, i) => {
    const el = document.createElement('div');
    el.className = 'flex flex-col gap-1';
    el.innerHTML = `
      <label class="text-sm font-semibold text-gray-700">${i + 1}. ${q}</label>
      <textarea id="fq-answer-${i}" rows="2" placeholder="Sagot ng pasyente..."
        class="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:border-navy focus:outline-none resize-none"></textarea>`;
    fqList.appendChild(el);
  });
}

async function refineWithFollowup() {
  const complaint = document.getElementById('input-complaint').value.trim();
  const questions = state.currentTriageResult?.followup_questions || [];
  const answers = {};

  questions.forEach((q, i) => {
    const ansEl = document.getElementById(`fq-answer-${i}`);
    if (ansEl && ansEl.value.trim()) answers[q] = ansEl.value.trim();
  });

  if (Object.keys(answers).length === 0) {
    showToast('Mangyaring sagutin ang kahit isang tanong bago mag-refine.');
    return;
  }

  showScreen('screen-loading', true);
  document.getElementById('loading-message').textContent = 'Nirerepormasyon ang assessment...';

  try {
    const fd = new FormData();
    fd.append('chief_complaint', complaint);
    fd.append('followup_answers', JSON.stringify(answers));
    if (state.currentTriageResult?.image_findings) {
      fd.append('image_findings', state.currentTriageResult.image_findings);
    }

    const res = await fetch('/api/triage', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);

    const result = await res.json();
    state.currentTriageResult = result;
    renderTriageResult(result);
    showScreen('screen-result');
  } catch (err) {
    showScreen('screen-result');
    showError(`Hindi ma-refine: ${err.message}`);
  }
}

async function proceedToSummary() {
  const result = state.currentTriageResult;
  if (!result) return;

  const soap = result.soap_summary || {};
  document.getElementById('soap-s').textContent = soap.S || '';
  document.getElementById('soap-o').textContent = soap.O || '';
  document.getElementById('soap-a').textContent = soap.A || '';
  document.getElementById('soap-p').textContent = soap.P || '';

  const complaint = document.getElementById('input-complaint').value.trim();
  const name = document.getElementById('input-name').value.trim() || null;
  const age = parseInt(document.getElementById('input-age').value) || null;
  const sexEl = document.querySelector('input[name="sex"]:checked');
  const sex = sexEl ? sexEl.value : null;

  const questions = result.followup_questions || [];
  const followup_qa = {};
  questions.forEach((q, i) => {
    const el = document.getElementById(`fq-answer-${i}`);
    if (el && el.value.trim()) followup_qa[q] = el.value.trim();
  });

  try {
    const payload = {
      shift_id: state.shiftId,
      name, age, sex,
      chief_complaint: complaint,
      image_path: state.capturedImagePath || null,
      image_findings: result.image_findings || null,
      followup_qa,
      triage_level: result.triage_level,
      top_conditions: result.top_conditions,
      handoff_summary: JSON.stringify(result.soap_summary),
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

    document.getElementById('header-patient-count').textContent = `${state.patients.length} pasyente`;
    showScreen('screen-summary');
  } catch (err) {
    showError(`Hindi ma-save ang pasyente: ${err.message}`);
  }
}

async function generatePDF() {
  if (!state.currentPatientId) { showError('Walang pasyente na naka-save.'); return; }

  const btn = document.getElementById('btn-generate-pdf');
  btn.textContent = '⏳ Ginagawa ang PDF...';
  btn.disabled = true;

  try {
    const url = `/api/export/pdf/${state.currentPatientId}`;
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.download = `patient_${state.currentPatientId}_handoff.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('PDF na-generate! Binubuksan...');
  } catch (err) {
    showError(`Hindi ma-generate ang PDF: ${err.message}`);
  } finally {
    btn.textContent = '📄 I-Generate ang PDF';
    btn.disabled = false;
  }
}

function saveAndNewPatient() {
  clearIntakeForm();
  showScreen('screen-intake');
}

function clearIntakeForm() {
  document.getElementById('input-name').value = '';
  document.getElementById('input-age').value = '';
  document.getElementById('input-complaint').value = '';
  document.querySelectorAll('input[name="sex"]').forEach(el => el.checked = false);
  clearPhoto();
  state.capturedImageFile = null;
  state.capturedImagePath = null;
  state.currentTriageResult = null;
  state.currentPatientId = null;
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
  } catch (err) {
    showToast('Hindi ma-load ang patient log.');
  }
}

function renderPatientLog() {
  const list = document.getElementById('patient-log-list');
  const empty = document.getElementById('log-empty');
  list.innerHTML = '';

  const red = state.patients.filter(p => p.triage_level === 'RED').length;
  const yellow = state.patients.filter(p => p.triage_level === 'YELLOW').length;
  const green = state.patients.filter(p => p.triage_level === 'GREEN').length;

  document.getElementById('stat-red').textContent = red;
  document.getElementById('stat-yellow').textContent = yellow;
  document.getElementById('stat-green').textContent = green;
  document.getElementById('header-patient-count').textContent = `${state.patients.length} pasyente`;

  if (state.patients.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  const badgeColors = { RED: 'bg-danger', YELLOW: 'bg-amber', GREEN: 'bg-forest' };
  const statuses = ['Pending', 'Seen', 'Referred', 'Sent Home'];

  state.patients.slice().reverse().forEach(p => {
    let conditions = [];
    try { conditions = JSON.parse(p.top_conditions || '[]'); } catch {}
    const topCond = conditions[0]?.condition || '—';

    const ts = new Date(p.timestamp);
    const timeStr = ts.toLocaleTimeString('fil-PH', { hour: '2-digit', minute: '2-digit' });

    const card = document.createElement('div');
    card.className = 'bg-white rounded-xl shadow p-4 flex flex-col gap-2';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-gray-400">${timeStr}</span>
          <span class="font-semibold text-sm">${p.name || 'Walang Pangalan'}</span>
          ${p.age ? `<span class="text-xs text-gray-400">${p.age}${p.sex || ''}</span>` : ''}
        </div>
        <span class="text-white text-xs font-bold px-3 py-1 rounded-full ${badgeColors[p.triage_level] || 'bg-amber'}">${p.triage_level}</span>
      </div>
      <div class="text-sm text-gray-600 line-clamp-1">${p.chief_complaint}</div>
      <div class="text-xs text-gray-400">Posible: ${topCond}</div>
      <div class="flex items-center gap-2 mt-1">
        <span class="text-xs text-gray-500">Status:</span>
        <select onchange="updateStatus(${p.id}, this.value)" class="text-xs border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:border-navy">
          ${statuses.map(s => `<option value="${s}" ${p.status === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
        <button onclick="downloadPatientPDF(${p.id})" class="text-xs text-navy underline ml-auto">PDF</button>
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
    showToast(`Status na-update: ${status}`);
  } catch (err) {
    showError('Hindi ma-update ang status.');
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
  const red = state.patients.filter(p => p.triage_level === 'RED').length;
  const yellow = state.patients.filter(p => p.triage_level === 'YELLOW').length;
  const green = state.patients.filter(p => p.triage_level === 'GREEN').length;

  document.getElementById('endshift-bhw').textContent = state.bhwName || '';
  document.getElementById('endshift-total').textContent = state.patients.length;
  document.getElementById('endshift-red').textContent = red;
  document.getElementById('endshift-yellow').textContent = yellow;
  document.getElementById('endshift-green').textContent = green;
  document.getElementById('endshift-email').textContent = state.coordinatorEmail || '';

  if (state.shiftId) {
    document.getElementById('btn-download-excel').href = `/api/export/excel/${state.shiftId}`;
  }
}

async function sendShiftEmail() {
  if (!state.shiftId) return;

  const btn = document.getElementById('btn-send-email');
  btn.textContent = '⏳ Nagpapadala...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/email/shift-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shift_id: state.shiftId }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Email send failed');
    }

    showToast('Email naipadala na sa coordinator!', 4000);
    btn.textContent = '✅ Naipadala na!';
  } catch (err) {
    showError(`Hindi ma-send ang email: ${err.message}`);
    btn.textContent = '📧 Ipadala ang Report sa Email';
    btn.disabled = false;
  }
}

async function confirmEndShift() {
  if (!confirm('Sigurado ka bang tapusin ang shift?')) return;

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
    document.getElementById('input-coordinator-email').value = '';

    showToast('Shift natapos na. Salamat!', 3000);
    setTimeout(() => showScreen('screen-home'), 500);
  } catch (err) {
    showError(`Hindi ma-tapusin ang shift: ${err.message}`);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
showScreen('screen-home', false);
