TRIAGE_SYSTEM_PROMPT = """Ikaw ay isang AI triage support assistant para sa Barangay Health Worker (BHW).
HINDI ka doktor at HINDI ka kapalit ng medikal na propesyonal.
Ang iyong papel ay tulungan ang BHW na mas mabilis na ma-assess ang pasyente.

Mga panuntunan:
1. Laging gumamit ng simpleng Filipino o Taglish — walang komplikadong medikal na terminolohiya para sa BHW.
2. Ang triage_level ay LAGING isa sa: RED, YELLOW, o GREEN — walang iba.
   - RED: Kailangan ng agarang atensyon ng doktor / referral
   - YELLOW: Kailangan ng konsultasyon ng doktor, hindi agarang emergency
   - GREEN: Maaaring hawakan ng BHW / monitoring lamang
3. Laging mag-isulat ng disclaimer sa output.
4. Ang lahat ng followup_questions ay sa Filipino / simpleng English.
5. LAGING mag-output ng valid JSON — walang markdown code blocks, plain JSON lamang.
6. Ang top_conditions ay listahan ng 5 posibleng kondisyon — mula pinaka-posible hanggang pinaka-hindi posible.

Output format (strict JSON, no markdown):
{
  "triage_level": "RED | YELLOW | GREEN",
  "triage_reason": "maikling paliwanag sa Filipino",
  "top_conditions": [
    {"rank": 1, "condition": "...", "plain_explanation": "..."},
    {"rank": 2, "condition": "...", "plain_explanation": "..."},
    {"rank": 3, "condition": "...", "plain_explanation": "..."},
    {"rank": 4, "condition": "...", "plain_explanation": "..."},
    {"rank": 5, "condition": "...", "plain_explanation": "..."}
  ],
  "followup_questions": [
    "Tanong 1 sa Filipino?",
    "Tanong 2 sa Filipino?",
    "Tanong 3 sa Filipino?"
  ],
  "soap_summary": {
    "S": "...",
    "O": "...",
    "A": "...",
    "P": "..."
  },
  "disclaimer": "Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor."
}"""


def build_triage_prompt(
    chief_complaint: str,
    image_findings: str | None = None,
    followup_answers: dict | None = None,
) -> str:
    parts = [f"Chief Complaint ng Pasyente: {chief_complaint}"]

    if image_findings:
        parts.append(f"\nNakita sa larawan (MedGemma analysis):\n{image_findings}")

    if followup_answers:
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in followup_answers.items())
        parts.append(f"\nMga sagot sa follow-up questions:\n{qa_text}")

    parts.append("\nBigyan ng triage assessment ang pasyenteng ito. Output ay strict JSON lamang.")
    return "\n".join(parts)


TRIAGE_FALLBACK = {
    "triage_level": "YELLOW",
    "triage_reason": "Hindi ma-proseso ang assessment. Kailangan ng konsultasyon ng doktor para sa kaligtasan.",
    "top_conditions": [
        {"rank": 1, "condition": "Hindi matukoy", "plain_explanation": "Kailangan ng mas detalyadong pagsusuri ng doktor."},
        {"rank": 2, "condition": "Hindi matukoy", "plain_explanation": "Kailangan ng mas detalyadong pagsusuri ng doktor."},
        {"rank": 3, "condition": "Hindi matukoy", "plain_explanation": "Kailangan ng mas detalyadong pagsusuri ng doktor."},
        {"rank": 4, "condition": "Hindi matukoy", "plain_explanation": "Kailangan ng mas detalyadong pagsusuri ng doktor."},
        {"rank": 5, "condition": "Hindi matukoy", "plain_explanation": "Kailangan ng mas detalyadong pagsusuri ng doktor."},
    ],
    "followup_questions": [
        "Gaano katagal na ang sintomas?",
        "Mayroon bang ibang sintomas bukod sa nabanggit?",
        "Mayroon bang allergy sa gamot?",
    ],
    "soap_summary": {
        "S": "Hindi ma-proseso ang chief complaint.",
        "O": "Walang available na objective data.",
        "A": "Hindi matukoy — kailangan ng pagsusuri ng doktor.",
        "P": "I-refer sa doktor para sa proper assessment.",
    },
    "disclaimer": "Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor.",
}
