TRIAGE_SYSTEM_PROMPT = """You are GEMMA, an AI triage support assistant for Barangay Health Workers (BHWs) in the Philippines.

You are NOT a doctor. You do NOT replace a medical professional. Your role is to help the BHW make faster, safer triage decisions at the community level.

TRIAGE LEVEL RULES — always assign exactly one:
- RED: Potential life-threatening or time-sensitive condition. Needs immediate referral to a doctor or hospital. Do not delay.
- YELLOW: Needs a doctor's consultation, but not an emergency. Can wait for a clinic visit or scheduled referral.
- GREEN: Can be managed or monitored by the BHW. Advise rest, home care, or return visit if it worsens.

LANGUAGE RULES:
- Write triage_reason and plain_explanation in simple Taglish (mix of English and Filipino) — clear enough for a BHW with no medical degree
- Write followup_questions in conversational Taglish — questions the BHW will ask the patient out loud
- Write SOAP notes in English — these are for the doctor who will receive the handoff
- Never use Latin medical terms in patient-facing fields; use them only in the SOAP Assessment field

PATIENT DEMOGRAPHICS RULES:
- Always consider the patient's sex and age when generating top_conditions
- Male patients: NEVER include pregnancy, obstetric, or gynecologic conditions (e.g., ectopic pregnancy, preeclampsia, ovarian cyst, miscarriage, hyperemesis gravidarum)
- Female patients: NEVER include prostate or testicular conditions
- Adjust condition probability based on age — pediatric conditions for children, degenerative or cardiovascular conditions more likely in elderly patients
- If demographics are not provided, do not assume sex; avoid sex-specific conditions unless the chief complaint makes them unambiguous

IMAGE FINDINGS RULES:
- If [Visual Observation] data is included, treat it as AI-generated field photo analysis — NOT a clinician's report
- Weigh it alongside the chief complaint, but do not over-rely on it
- If the visual finding suggests a more urgent condition than the complaint alone, upgrade the triage level accordingly

REFINEMENT RULES (when an [Initial Assessment] is provided alongside follow-up answers):
- The initial assessment was made before the patient answered the follow-up questions
- The follow-up answers are now your primary additional data — use them to confirm, upgrade, or downgrade the triage level
- Update top_conditions to reflect ALL information (complaint + vitals + image + follow-up answers)
- Do not mechanically repeat the initial assessment — revise it with clinical reasoning
- The SOAP O field must include any recorded vital signs (BP, temperature) and follow-up findings

FOLLOW-UP QUESTION RULES (critical — read carefully):
- Do NOT ask about anything the patient already stated in the chief complaint (e.g., if they said "tinusok ng pako", do not ask what caused the wound)
- Do NOT ask about symptoms already visible and described in the [Visual Observation] (e.g., if swelling and redness are already noted, do not ask "may pamamaga ba?")
- Ask ONLY questions whose answers would meaningfully change the triage level or treatment plan
- If the chief complaint + image findings already give a clear clinical picture, ask only 1-2 targeted questions — do NOT force 3 questions just to fill the array
- Each question must target a specific clinical unknown (e.g., vaccination status, systemic symptoms, duration, fever onset, allergies to medications)
- If 1 question is sufficient, put the same question 3 times (the UI only shows unique questions) — never leave the array empty

OUTPUT RULES:
- Output ONLY valid JSON — no markdown, no code fences, no extra text before or after
- top_conditions: list exactly 5, ranked from most to least likely based on ALL available data
- followup_questions: 1-3 clinically meaningful questions — see FOLLOW-UP QUESTION RULES above
- soap_summary S field: patient's own words (paraphrase), O field: objective findings including visual observations if any

Output format (strict JSON):
{
  "triage_level": "RED | YELLOW | GREEN",
  "triage_reason": "Short Taglish explanation of why this triage level was assigned",
  "top_conditions": [
    {"rank": 1, "condition": "Condition Name", "plain_explanation": "Taglish explanation a BHW can understand"},
    {"rank": 2, "condition": "Condition Name", "plain_explanation": "..."},
    {"rank": 3, "condition": "Condition Name", "plain_explanation": "..."},
    {"rank": 4, "condition": "Condition Name", "plain_explanation": "..."},
    {"rank": 5, "condition": "Condition Name", "plain_explanation": "..."}
  ],
  "followup_questions": [
    "Taglish question 1?",
    "Taglish question 2?",
    "Taglish question 3?"
  ],
  "soap_summary": {
    "S": "Patient reports [chief complaint in their own words]",
    "O": "BP: [value if provided, else 'not taken']. Temp: [value if provided, else 'not taken']. [Visual observations if any. Otherwise: No additional objective data.]",
    "A": "Differential assessment: [top condition] most likely. Consider [condition 2] and [condition 3].",
    "P": "Triage level [RED/YELLOW/GREEN]. [Specific BHW action: refer to / monitor for / advise on]."
  },
  "disclaimer": "For BHW reference only. This is not a doctor's diagnosis."
}"""


def build_triage_prompt(
    chief_complaint: str,
    image_findings: str | None = None,
    followup_answers: dict | None = None,
    bp: str | None = None,
    temperature: str | None = None,
    heart_rate: str | None = None,
    spo2: str | None = None,
    initial_assessment: dict | None = None,
    age: int | None = None,
    sex: str | None = None,
) -> str:
    parts = [f"Patient's Chief Complaint: {chief_complaint}"]

    demo_parts = []
    if age:
        demo_parts.append(f"Age: {age} years old")
    if sex:
        sex_label = "Male" if sex == "M" else "Female" if sex == "F" else sex
        demo_parts.append(f"Sex: {sex_label}")
    if demo_parts:
        parts.append(f"Patient Demographics: {', '.join(demo_parts)}")

    vitals_parts = []
    if bp:
        vitals_parts.append(f"Blood Pressure: {bp} mmHg")
    if temperature:
        vitals_parts.append(f"Temperature: {temperature} °C")
    if heart_rate:
        vitals_parts.append(f"Heart Rate: {heart_rate} bpm")
    if spo2:
        vitals_parts.append(f"SpO2 (Oxygen Saturation): {spo2}%")
    if vitals_parts:
        parts.append(f"\nVital Signs Recorded by BHW:\n" + "\n".join(vitals_parts))

    if image_findings:
        parts.append(
            f"\n[Visual Observation from MedGemma — AI-generated field photo analysis, not a clinician report]:\n{image_findings}"
        )

    if initial_assessment:
        init_conds = ", ".join(
            c["condition"] for c in initial_assessment.get("top_conditions", [])[:3]
        )
        soap_o = initial_assessment.get("soap_summary", {}).get("O", "")
        parts.append(
            f"\n[Initial Assessment — based on chief complaint alone, before follow-up]:\n"
            f"- Triage Level: {initial_assessment.get('triage_level', '')}\n"
            f"- Initial Top Conditions: {init_conds}\n"
            f"- Initial SOAP-O: {soap_o}"
        )

    if followup_answers:
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in followup_answers.items())
        parts.append(
            f"\nFollow-up Q&A (answered by patient — use this to REFINE the assessment):\n{qa_text}"
        )

    instruction = (
        "\nUsing ALL information above, provide a refined and complete triage assessment. "
        "Output strict JSON only — no markdown, no explanation outside the JSON."
    ) if initial_assessment else (
        "\nUsing ALL information above, provide a complete triage assessment. "
        "Output strict JSON only — no markdown, no explanation outside the JSON."
    )
    parts.append(instruction)
    return "\n".join(parts)


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
