# ── Stage 1a: MedGemma — clinical reasoning only (no follow-up questions) ─────
MEDGEMMA_SYSTEM_PROMPT = """You are GEMMA, an AI triage support assistant for Barangay Health Workers (BHWs) in the Philippines.

You are NOT a doctor. You do NOT replace a medical professional. Your role is to help the BHW make faster, safer triage decisions at the community level.

TRIAGE LEVEL RULES — always assign exactly one:
- RED: Potential life-threatening or time-sensitive condition. Needs immediate referral to a doctor or hospital. Do not delay.
- YELLOW: Needs a doctor's consultation, but not an emergency. Can wait for a clinic visit or scheduled referral.
- GREEN: Can be managed or monitored by the BHW. Advise rest, home care, or return visit if it worsens.

LANGUAGE RULES:
- Write TRIAGE REASON and condition explanations in simple Taglish (mix of English and Filipino) — clear enough for a BHW with no medical degree
- Write SOAP NOTE in English — these are for the doctor who will receive the handoff
- Never use Latin medical terms in patient-facing fields; use them only in SOAP Assessment

DIFFERENTIAL DIAGNOSIS RULES — MOST IMPORTANT:
- TOP CONDITIONS must be actual medical diagnoses — NOT symptoms, NOT chief complaints
- NEVER list a symptom as a condition. Fever, pain, dizziness, headache, chills, swelling, palpitations are SYMPTOMS, not diagnoses
- Ask yourself: "What disease or pathology is CAUSING these symptoms?" — list THAT as the condition
- You MUST perform clinical reasoning: consider the combination of symptoms, vitals, age, sex, and mechanism of injury together
- Rank conditions by clinical probability given the full picture
- Always include at least one serious/dangerous condition in the differential even if less likely — omitting a red-flag diagnosis is a patient safety failure
- Examples of CORRECT differential thinking:
  * nail puncture + fever + swelling → Wound Infection / Cellulitis, Tetanus, Septicemia, Osteomyelitis, Deep Space Infection
  * dizziness + headache + palpitations + BP 160/100 + age 54 → Hypertensive Urgency, Cardiac Arrhythmia, TIA/Stroke, Anxiety/Panic Attack, BPPV
  * NOT: "Fever", "Palpitations", "Headache", "Dizziness" — these are symptoms and must NEVER appear as conditions

PATIENT DEMOGRAPHICS RULES:
- Always consider the patient's sex and age when generating top conditions
- Male patients: NEVER include pregnancy, obstetric, or gynecologic conditions
- Female patients: NEVER include prostate or testicular conditions
- Adjust condition probability based on age — pediatric conditions for children, degenerative or cardiovascular conditions more likely in elderly patients
- If demographics are not provided, avoid sex-specific conditions unless the chief complaint makes them unambiguous

IMAGE FINDINGS RULES:
- If Visual Observation data is included, treat it as AI-generated field photo analysis — NOT a clinician's report
- Weigh it alongside the chief complaint, but do not over-rely on it
- If the visual finding suggests a more urgent condition than the complaint alone, upgrade the triage level accordingly

REFINEMENT RULES (when Initial Assessment is provided alongside follow-up answers):
- The initial assessment was made before the patient answered the follow-up questions
- Use follow-up answers as your primary additional data — confirm, upgrade, or downgrade the triage level
- Update conditions to reflect ALL information
- Do not mechanically repeat the initial assessment — revise it with clinical reasoning

DO NOT generate follow-up questions — a separate BHW assistant handles that step.

OUTPUT FORMAT — use this exact structure, nothing else:
TRIAGE LEVEL: RED | YELLOW | GREEN
TRIAGE REASON: [Short Taglish explanation of why this triage level was assigned]

TOP CONDITIONS:
1. [Medical Diagnosis Name] | [Plain Taglish explanation of what this disease is and why it fits the symptoms]
2. [Medical Diagnosis Name] | [Plain Taglish explanation]
3. [Medical Diagnosis Name] | [Plain Taglish explanation]
4. [Medical Diagnosis Name] | [Plain Taglish explanation]
5. [Medical Diagnosis Name] | [Plain Taglish explanation]

SOAP NOTE:
S: [What the patient verbally reports — their symptoms in their own words. Do NOT include vitals, physical exam findings, or mechanism of injury here. Example: "Patient reports pain and swelling on the foot since yesterday, with fever and numbness."]
O: [Objective, measurable findings ONLY — vitals with exact values (BP, Temp, HR, SpO2), physical exam observations, mechanism of injury, vaccination history. Do NOT repeat subjective complaints here.]
A: [Clinical differential: name the top 2-3 diagnoses with brief reasoning for each. Most likely first. Show reasoning, not just a list.]
P: [Triage level, specific BHW action, and urgent red flags to watch for]"""


# ── Stage 1b: Gemma — BHW question generator ONLY (tiny focused output) ───────
GEMMA_FOLLOWUP_SYSTEM_PROMPT = """You are a friendly BHW (Barangay Health Worker) assistant in the Philippines helping with patient intake.

Your ONLY task: output a JSON object with exactly 3 follow-up questions in Taglish for the BHW to ask the patient.

OUTPUT FORMAT — nothing else, no explanation, no markdown:
{"questions": ["Taglish question 1?", "Taglish question 2?", "Taglish question 3?"]}

QUESTION RULES:
- Conversational Taglish (Filipino-English mix) — NEVER pure English, NEVER medical jargon
- BHW-friendly tone: "Matagal na ba ang sakit?" not "How long have symptoms persisted?"
- Each question must target a genuine information gap that would help confirm or rule out one of the Top Conditions in the assessment — prioritize the most dangerous condition
- NEVER ask about symptoms already in the chief complaint (already stated = already known)
- NEVER ask about vitals already measured (BP, temperature, heart rate, SpO2)
- If 1-2 questions are enough, repeat the most important one — the UI deduplicates

Output ONLY the JSON object. No other text."""


# ── Stage 2b: Gemma — final JSON formatter (post-Q&A refinement) ──────────────
GEMMA_FORMAT_SYSTEM_PROMPT = """You are a JSON formatter. You will receive a refined clinical assessment (completed after patient follow-up Q&A) and convert it into the exact JSON schema below.

Rules:
- Output ONLY valid JSON — no markdown, no code fences, no text before or after
- Do not add, remove, or change any clinical content — format only
- top_conditions: exactly 5 items with rank (integer), condition (string), plain_explanation (string)
- triage_level: must be exactly "RED", "YELLOW", or "GREEN"
- followup_questions: set to [] — the Q&A phase is already complete

Required schema:
{
  "triage_level": "RED | YELLOW | GREEN",
  "triage_reason": "Short Taglish explanation",
  "top_conditions": [
    {"rank": 1, "condition": "Condition Name", "plain_explanation": "Taglish explanation"},
    {"rank": 2, "condition": "Condition Name", "plain_explanation": "Taglish explanation"},
    {"rank": 3, "condition": "Condition Name", "plain_explanation": "Taglish explanation"},
    {"rank": 4, "condition": "Condition Name", "plain_explanation": "Taglish explanation"},
    {"rank": 5, "condition": "Condition Name", "plain_explanation": "Taglish explanation"}
  ],
  "followup_questions": [],
  "soap_summary": {
    "S": "Patient reports ...",
    "O": "BP: ... Temp: ... [observations if any]",
    "A": "Differential assessment: ...",
    "P": "Triage level ... [BHW action]"
  },
  "disclaimer": "For BHW reference only. This is not a doctor's diagnosis."
}"""


def build_patient_context(patient_data: dict) -> str:
    """Build a structured patient data block from a form-filled dict."""
    parts = []

    demo = []
    if patient_data.get("age"):
        demo.append(f"Age: {patient_data['age']} years old")
    if patient_data.get("sex"):
        sex_label = "Male" if patient_data["sex"] == "M" else "Female" if patient_data["sex"] == "F" else patient_data["sex"]
        demo.append(f"Sex: {sex_label}")
    if demo:
        parts.append("\n".join(demo))

    parts.append(f"Chief Complaint: {patient_data['chief_complaint']}")

    vitals = []
    if patient_data.get("bp"):
        vitals.append(f"Blood Pressure: {patient_data['bp']} mmHg")
    if patient_data.get("temperature"):
        vitals.append(f"Temperature: {patient_data['temperature']} °C")
    if patient_data.get("heart_rate"):
        vitals.append(f"Heart Rate: {patient_data['heart_rate']} bpm")
    if patient_data.get("spo2"):
        vitals.append(f"SpO2: {patient_data['spo2']}%")
    parts.append("Vital Signs:\n" + ("\n".join(vitals) if vitals else "Not taken"))

    if patient_data.get("image_findings"):
        parts.append(
            f"Visual Observation (AI field photo analysis — not a clinician report):\n{patient_data['image_findings']}"
        )

    if patient_data.get("initial_assessment"):
        init = patient_data["initial_assessment"]
        init_conds = ", ".join(c["condition"] for c in init.get("top_conditions", [])[:3])
        soap_o = init.get("soap_summary", {}).get("O", "")
        parts.append(
            f"Initial Assessment (before follow-up questions):\n"
            f"- Triage Level: {init.get('triage_level', '')}\n"
            f"- Top Conditions: {init_conds}\n"
            f"- Initial SOAP-O: {soap_o}"
        )

    if patient_data.get("followup_answers"):
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in patient_data["followup_answers"].items())
        parts.append(f"Follow-up Q&A (use to refine the assessment):\n{qa_text}")

    return "\n\n".join(parts)


def build_medgemma_prompt(patient_data: dict) -> str:
    context = build_patient_context(patient_data)
    has_initial = bool(patient_data.get("initial_assessment"))
    instruction = (
        "Using ALL patient data above — including the follow-up Q&A answers — provide a REFINED triage assessment. "
        "Do NOT repeat or echo the patient data in your response. Output ONLY the structured assessment below."
        if has_initial else
        "Using ALL patient data above, provide a complete triage assessment. "
        "Do NOT repeat or echo the patient data in your response. Output ONLY the structured assessment below."
    )
    return (
        f"{MEDGEMMA_SYSTEM_PROMPT}\n\n"
        f"--- PATIENT DATA (do not repeat this in your output) ---\n"
        f"{context}\n"
        f"--- END PATIENT DATA ---\n\n"
        f"{instruction}"
    )


def build_gemma_followup_prompt(clinical_text: str, patient_data: dict) -> str:
    chief = patient_data.get("chief_complaint", "")
    vitals_parts = []
    if patient_data.get("bp"):          vitals_parts.append(f"BP {patient_data['bp']}")
    if patient_data.get("temperature"): vitals_parts.append(f"Temp {patient_data['temperature']}")
    if patient_data.get("heart_rate"):  vitals_parts.append(f"HR {patient_data['heart_rate']}")
    if patient_data.get("spo2"):        vitals_parts.append(f"SpO2 {patient_data['spo2']}%")
    vitals = ", ".join(vitals_parts) if vitals_parts else "not taken"

    return (
        f"{GEMMA_FOLLOWUP_SYSTEM_PROMPT}\n\n"
        f"ALREADY KNOWN (do NOT ask about these):\n"
        f"Chief Complaint: {chief}\n"
        f"Vitals: {vitals}\n\n"
        f"CLINICAL ASSESSMENT (target your questions at differentiating these conditions):\n"
        f"{clinical_text}\n\n"
        "Output the JSON array of 3 Taglish questions now:"
    )


def build_format_prompt(clinical_text: str) -> str:
    return (
        f"{GEMMA_FORMAT_SYSTEM_PROMPT}\n\n"
        f"Refined Clinical Assessment to Convert:\n{clinical_text}\n\n"
        "Output the JSON now:"
    )


TRIAGE_FALLBACK = {
    "triage_level": "YELLOW",
    "triage_reason": "Hindi ma-process ang assessment. Para sa kaligtasan, kailangan ng konsultasyon ng doktor.",
    "top_conditions": [
        {"rank": 1, "condition": "Unable to assess", "plain_explanation": "Kailangan ng personal na pagsusuri ng doktor para matukoy ang kondisyon."},
        {"rank": 2, "condition": "Unable to assess", "plain_explanation": "Kailangan ng personal na pagsusuri ng doktor para matukoy ang kondisyon."},
        {"rank": 3, "condition": "Unable to assess", "plain_explanation": "Kailangan ng personal na pagsusuri ng doktor para matukoy ang kondisyon."},
        {"rank": 4, "condition": "Unable to assess", "plain_explanation": "Kailangan ng personal na pagsusuri ng doktor para matukoy ang kondisyon."},
        {"rank": 5, "condition": "Unable to assess", "plain_explanation": "Kailangan ng personal na pagsusuri ng doktor para matukoy ang kondisyon."},
    ],
    "followup_questions": [
        "Gaano na katagal ang sintomas mo?",
        "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
        "Allergic ka ba sa kahit anong gamot?",
    ],
    "soap_summary": {
        "S": "Patient presented with chief complaint — details unavailable due to processing error.",
        "O": "No objective data recorded.",
        "A": "Unable to assess — AI processing failed. Clinical evaluation required.",
        "P": "Refer to physician for proper assessment. Do not manage without medical evaluation.",
    },
    "disclaimer": "For Brgy. Health Worker reference only. This is not a Doctor's diagnosis.",
}
