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

IMAGE FINDINGS RULES:
- If [Visual Observation] data is included, treat it as AI-generated field photo analysis — NOT a clinician's report
- Weigh it alongside the chief complaint, but do not over-rely on it
- If the visual finding suggests a more urgent condition than the complaint alone, upgrade the triage level accordingly

OUTPUT RULES:
- Output ONLY valid JSON — no markdown, no code fences, no extra text before or after
- top_conditions: list exactly 5, ranked from most to least likely based on ALL available data
- followup_questions: ask 3 questions that would most change the triage level if answered
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
    "O": "Vital signs not available. [Visual observations if any. Otherwise: No objective data recorded.]",
    "A": "Differential assessment: [top condition] most likely. Consider [condition 2] and [condition 3].",
    "P": "Triage level [RED/YELLOW/GREEN]. [Specific BHW action: refer to / monitor for / advise on]."
  },
  "disclaimer": "For BHW reference only. This is not a doctor's diagnosis."
}"""


def build_triage_prompt(
    chief_complaint: str,
    image_findings: str | None = None,
    followup_answers: dict | None = None,
) -> str:
    parts = [f"Patient's Chief Complaint: {chief_complaint}"]

    if image_findings:
        parts.append(
            f"\n[Visual Observation from MedGemma — AI-generated field photo analysis, not a clinician report]:\n{image_findings}"
        )

    if followup_answers:
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in followup_answers.items())
        parts.append(f"\nFollow-up Q&A (answered by patient via BHW):\n{qa_text}")

    parts.append(
        "\nUsing ALL information above, provide a complete triage assessment. "
        "Output strict JSON only — no markdown, no explanation outside the JSON."
    )
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
