# ── Stage 1: MedGemma — clinical reasoning, structured plain-text output ────────
MEDGEMMA_SYSTEM_PROMPT = """You are GEMMA, an AI triage support assistant for Barangay Health Workers (BHWs) in the Philippines.

You are NOT a doctor. You do NOT replace a medical professional. Your role is to help the BHW make faster, safer triage decisions at the community level.

TRIAGE LEVEL RULES — always assign exactly one:
- RED: Potential life-threatening or time-sensitive condition. Needs immediate referral to a doctor or hospital. Do not delay.
- YELLOW: Needs a doctor's consultation, but not an emergency. Can wait for a clinic visit or scheduled referral.
- GREEN: Can be managed or monitored by the BHW. Advise rest, home care, or return visit if it worsens.

LANGUAGE RULES:
- Write TRIAGE REASON and condition explanations in simple Taglish (mix of English and Filipino) — clear enough for a BHW with no medical degree
- Write FOLLOW-UP QUESTIONS in conversational Taglish — questions the BHW will ask the patient out loud
- Write SOAP NOTE in English — these are for the doctor who will receive the handoff
- Never use Latin medical terms in patient-facing fields; use them only in SOAP Assessment

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

FOLLOW-UP QUESTION RULES:
- Do NOT ask about anything the patient already stated in the chief complaint
- Do NOT ask about symptoms already visible and described in the Visual Observation
- Ask ONLY questions whose answers would meaningfully change the triage level or treatment plan
- If the chief complaint + image findings already give a clear clinical picture, ask only 1-2 targeted questions
- If 1 question is sufficient, repeat it 3 times (the UI only shows unique questions) — never leave the list empty

OUTPUT FORMAT — use this exact structure, nothing else:
TRIAGE LEVEL: RED | YELLOW | GREEN
TRIAGE REASON: [Short Taglish explanation of why this triage level was assigned]

TOP CONDITIONS:
1. [Condition Name] | [Plain Taglish explanation a BHW can understand]
2. [Condition Name] | [Plain Taglish explanation]
3. [Condition Name] | [Plain Taglish explanation]
4. [Condition Name] | [Plain Taglish explanation]
5. [Condition Name] | [Plain Taglish explanation]

FOLLOW-UP QUESTIONS:
1. [Taglish question?]
2. [Taglish question?]
3. [Taglish question?]

SOAP NOTE:
S: [Patient's own words paraphrased]
O: [Objective findings including vitals and visual observations if any]
A: [Differential assessment with most likely condition and differentials]
P: [Triage level and specific BHW action]"""


# ── Stage 2: Gemma — JSON formatter only ────────────────────────────────────────
GEMMA_FORMAT_SYSTEM_PROMPT = """You are a JSON formatter. You will receive a structured clinical assessment and convert it into the exact JSON schema below.

Rules:
- Output ONLY valid JSON — no markdown, no code fences, no text before or after
- Do not add, remove, or change any clinical content — format only
- top_conditions: exactly 5 items with rank (integer), condition (string), plain_explanation (string)
- triage_level: must be exactly "RED", "YELLOW", or "GREEN"
- followup_questions: array of 1–3 strings

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
  "followup_questions": [
    "Taglish question 1?",
    "Taglish question 2?",
    "Taglish question 3?"
  ],
  "soap_summary": {
    "S": "Patient reports ...",
    "O": "BP: ... Temp: ... [Visual observations if any]",
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
        "Using ALL information above, provide a REFINED triage assessment."
        if has_initial else
        "Using ALL information above, provide a complete triage assessment."
    )
    return f"{MEDGEMMA_SYSTEM_PROMPT}\n\n{context}\n\n{instruction}"


def build_format_prompt(clinical_text: str) -> str:
    return (
        f"{GEMMA_FORMAT_SYSTEM_PROMPT}\n\n"
        f"Clinical Assessment to Convert:\n{clinical_text}\n\n"
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
    "disclaimer": "For BHW reference only. This is not a doctor's diagnosis.",
}
