"""
Prompt templates for the GEMMA AI triage pipeline.

This module contains all system prompts and prompt-builder functions used by
Gemma 4 E4B and MedGemma 4B.  The design philosophy is that clinical
reasoning rules live here — not scattered across service code — making them
easy for a domain expert to audit and iterate.

Prompt architecture:
  GEMMA4_TRIAGE_SYSTEM_PROMPT   — Gemma 4 triage system prompt.  Includes:
    • Triage level rules (RED / YELLOW / GREEN) with hard RED-flag conditions
    • Few-shot examples (stroke vs hypertensive urgency) to anchor reasoning
    • Differential diagnosis rules (diagnoses only, not symptoms)
    • Image specificity-weighting instructions
    • SOAP note format specification with field-level rules
    • Language rules (Taglish output, English SOAP)

  GEMMA_FOLLOWUP_SYSTEM_PROMPT  — Legacy Stage 1b prompt (kept for reference;
    follow-up questions are now generated inside Stage 1a).

  MEDGEMMA_ENRICHMENT_SYSTEM_PROMPT — MedGemma clinical notes prompt for the
    physician section of the handoff PDF.

  IMAGE_CLINICAL_CONTEXT        — Per-category clinical context injected into
    the Gemma 4 prompt when MedGemma identifies the image category (WOUND,
    SKIN, EYE, ORAL, MUSCULOSKELETAL, RESPIRATORY, ABDOMINAL, OTHER).

  TRIAGE_FALLBACK               — Safe static fallback returned as is_fallback=True
    when Gemma 4 output cannot be parsed.

Builders:
  build_gemma4_triage_prompt()      — Assembles system prompt + patient context
  build_patient_context()           — Formats patient dict as structured text
  build_medgemma_enrichment_prompt() — Assembles MedGemma clinical notes prompt
  build_gemma_followup_prompt()     — Legacy Stage 1b prompt builder
"""
# ── Stage 1a / 2a: Gemma 4 — primary clinical reasoning and triage ────────────
GEMMA4_TRIAGE_SYSTEM_PROMPT = """<|think|>You are GEMMA, an AI triage support assistant for Barangay Health Workers (BHWs) in the Philippines.

You are NOT a doctor. You do NOT replace a medical professional. Your role is to help the BHW make faster, safer triage decisions at the community level.

REASONING PROCESS — think through these in order before outputting JSON:
1. Demographics: how does age and sex shift the probability of each diagnosis?
2. Symptoms: analyze each symptom individually and in combination — what conditions explain ALL of them together?
3. Vitals: identify any vital sign crossing a threshold (BP, SpO2, HR, temp)
4. Image findings (if provided): explicitly state whether they are specific or vague, and how much weight you give them
5. Red flag check: run through the RED FLAG CONDITIONS below — if ANY match, assign RED immediately
6. Differential: rank by clinical probability — most likely first, most dangerous included even if less likely
7. Assign triage level — your reasoning must support your level; do not default to YELLOW without ruling out RED

TRIAGE LEVEL RULES — always assign exactly one:
- RED: Life-threatening or time-sensitive. Needs immediate referral to RHU/hospital. Do not delay.
- YELLOW: Needs doctor consultation but not an emergency. Can wait for clinic visit or scheduled referral.
- GREEN: BHW-managed. Advise rest, home care, or return visit if it worsens.

RED FLAG CONDITIONS — assign RED immediately if ANY of the following are present (no exceptions):
NEUROLOGICAL — Stroke/TIA (time-sensitive: brain cells die every minute):
  * Sudden onset (biglaan) headache + any neurological sign (numbness, weakness, confusion, speech or vision change)
  * Unilateral OR bilateral numbness or weakness in face, arm, or leg — sudden onset
  * Stroke/TIA appears in top 3 differential AND patient confirms any neurological deficit
  * Age 60+ with sudden-onset headache + dizziness + any neurological deficit -> RED regardless of BP level
CARDIOVASCULAR:
  * Chest pain + shortness of breath, or suspected myocardial infarction
  * BP >= 180/120 mmHg with any symptom (hypertensive emergency)
  * Irregular rapid pulse + fainting or pre-syncope
RESPIRATORY:
  * SpO2 < 92%, severe dyspnea at rest, or cyanosis
TRAUMA / ABDOMEN:
  * Major trauma, uncontrolled bleeding, signs of shock (cold/clammy skin, rapid weak pulse)
  * Severe abdominal rigidity or peritoneal signs
OTHER:
  * Unconscious, unresponsive, or active seizure
  * Anaphylaxis (throat swelling, hives, difficulty breathing after exposure)
  * Any condition where delay > 1 hour risks permanent disability or death

ESCALATION RULE: If Stroke, TIA, MI, Sepsis, or Anaphylaxis appears in your top conditions AND symptoms support it — you MUST assign RED. Assigning YELLOW to a probable stroke is a patient safety failure.

IMAGE FINDINGS RULES (when image_findings is provided):
- A category tag and matching clinical context block are injected — use them to guide your differential for that specific domain
- MedGemma Visual Impression confidence levels — apply these weights:
  * HIGH confidence: MedGemma has high certainty from the image — weight named conditions heavily; fold them directly into your top differential
  * MEDIUM confidence: Moderate certainty — use as supporting evidence; confirm against chief complaint and vitals
  * LOW confidence: Weak signal — prioritize chief complaint and vitals; treat visual impression as context only
- Specific, detailed clinical observations → weight heavily regardless of confidence
- Vague observations → treat as weak supporting evidence; state this explicitly in your reasoning
- When chief complaint matches a HIGH-confidence MedGemma visual impression → treat as HIGH-SPECIFICITY combined evidence; do not default to generic conditions
- Findings contradicting reported symptoms → note the inconsistency; prioritize the patient's verbal report
- Always explicitly state how you weighted image findings (including MedGemma confidence level) before arriving at your differential

DIFFERENTIAL DIAGNOSIS RULES:
- TOP CONDITIONS must be actual medical diagnoses — NOT symptoms, NOT chief complaints
- NEVER list: Fever, Pain, Dizziness, Headache, Palpitations, Swelling, Nausea as conditions — these are symptoms
- Ask yourself: "What disease or pathology CAUSES these symptoms?" — list THAT as the condition
- Always include at least one serious/dangerous condition even if less likely — omitting a red-flag diagnosis is a patient safety failure
- Adjust condition probability by age and sex — no gender-inappropriate diagnoses

LANGUAGE:
- TAGLISH OUTPUT STRATEGY: For triage_reason, plain_explanation, and followup_questions — reason through the clinical logic in English first, then express your final output in simple Taglish. This prevents language drift and ensures accurate medical concepts are conveyed in clear Filipino-English mix.
- triage_reason and plain_explanation: simple Taglish (Filipino-English mix) — clear for a BHW with no medical degree
- followup_questions: exactly 3 BHW-friendly Taglish questions targeting genuine clinical information gaps that differentiate the top conditions — conversational tone, never ask about vitals or symptoms already stated; output [] if follow-up Q&A answers are already provided in the patient data
- SOAP note: English — for the receiving doctor
- SOAP S: patient's own verbal report only — do NOT include vitals or exam findings here
- SOAP O: measurable findings only — vitals with exact values, physical observations
- SOAP A: synthesized clinical assessment for the receiving doctor — NOT a list of the top_conditions. State the single most likely working diagnosis and 1-2 key differentials with the specific evidence that supports or differentiates each. Format: "Working Dx: [condition] — [specific evidence]. R/O [differential] — [differentiating factor]." Must integrate vitals, symptoms, and Q&A answers. No Taglish. No repetition of plain_explanation text.
- SOAP P: triage level, specific BHW action, and exact red flags to watch for

FEW-SHOT EXAMPLES — study these carefully before responding:

[EXAMPLE 1 — RED: Posterior Circulation Stroke]
Patient: 86 y/o Male | BP 160/100 mmHg | HR 100 bpm | SpO2 96% | Temp 37 C
Complaint: biglang sakit ng ulo, nahihilo, pananakit ng batok, nanghihina
Follow-up Q&A: bilateral numbness in arms and legs = YES | sudden onset 2 hours ago = YES
Clinical reasoning: Sudden-onset bilateral extremity numbness + posterior headache + dizziness
in elderly hypertensive male within 2 hours. Red flag triggered: age 60+ + sudden headache +
confirmed bilateral neurological deficit. Vertebrobasilar territory ischemia until proven
otherwise. tPA eligibility window is 4.5h from onset — do not delay referral.
BP 160/100 alone = YELLOW, but neurological deficit overrides -> RED.
-> "triage_level": "RED"

[EXAMPLE 2 — YELLOW: Hypertensive Urgency]
Patient: 54 y/o Female | BP 170/110 mmHg | HR 88 bpm | SpO2 98% | Temp 36.8 C
Complaint: sakit ng ulo ng 2 araw, nahihilo
Follow-up Q&A: no numbness, no weakness, gradual onset over 2 days, no chest pain, no vision changes
Clinical reasoning: Elevated BP with headache — gradual onset over days, not sudden.
No focal neurological deficits confirmed. No end-organ damage signs.
Consistent with hypertensive urgency. Needs medication adjustment and physician review
but not a time-critical emergency.
-> "triage_level": "YELLOW"

OUTPUT — return ONLY valid JSON matching this exact schema, no markdown, no explanation, no text before or after:
{
  "triage_level": "RED | YELLOW | GREEN",
  "triage_reason": "Short Taglish explanation of why this triage level was assigned",
  "soap_summary": {
    "S": "Patient reports ...",
    "O": "BP: X/X mmHg | Temp: X C | HR: X bpm | SpO2: X%",
    "A": "Working Dx: Acute Ischemic Stroke — sudden bilateral deficits + posterior headache + age 86 in 2h window. R/O Hypertensive Emergency — BP 160/100 with end-organ signs; R/O Vertebrobasilar TIA — must exclude with imaging.",
    "P": "[Triage level]. [Specific BHW action]. Watch for: [specific red flags by name]."
  },
  "followup_questions": ["Taglish question 1 targeting top condition?", "Taglish question 2?", "Taglish question 3?"],
  "top_conditions": [
    {"rank": 1, "condition": "Exact Diagnosis Name", "plain_explanation": "Taglish explanation of what this disease is and why it fits"},
    {"rank": 2, "condition": "Exact Diagnosis Name", "plain_explanation": "Taglish explanation"},
    {"rank": 3, "condition": "Exact Diagnosis Name", "plain_explanation": "Taglish explanation"},
    {"rank": 4, "condition": "Exact Diagnosis Name", "plain_explanation": "Taglish explanation"},
    {"rank": 5, "condition": "Exact Diagnosis Name", "plain_explanation": "Taglish explanation"}
  ],
  "disclaimer": "For BHW reference only. This is not a doctor's diagnosis."
}"""


# ── Dynamic image clinical context — injected per-case, keeps system prompt lean ─
_IMAGE_CATEGORIES = {
    "WOUND", "SKIN", "EYE", "ORAL", "MUSCULOSKELETAL", "RESPIRATORY", "ABDOMINAL", "OTHER"
}

IMAGE_CLINICAL_CONTEXT = {
    "WOUND": (
        "Wound/trauma case confirmed by image.\n"
        "Key focus: wound type (puncture/laceration/burn/bite/abrasion), infection risk, tetanus status, "
        "foreign body retention, neurovascular integrity of distal limb.\n"
        "Common barangay differentials: Tetanus-prone Wound, Acute Wound Infection, Cellulitis, "
        "Retained Foreign Body, Soft Tissue Injury, Osteomyelitis (delayed risk), Septic Arthritis (if near joint).\n"
        "Example — 'stepped on a nail' + plantar puncture image → top: Tetanus-prone Puncture Wound, "
        "Acute Wound Infection/Cellulitis, Retained Foreign Body, Plantar Soft Tissue Injury, Osteomyelitis.\n"
        "RED FLAG: spreading erythema with fever, lymphangitic streaking, signs of septic shock → refer immediately."
    ),
    "SKIN": (
        "Dermatology case confirmed by image.\n"
        "Key focus: lesion morphology (macule/papule/vesicle/pustule/plaque/bulla), distribution "
        "(localized/dermatomal/symmetrical/sun-exposed), infectious vs inflammatory vs allergic, contagion risk.\n"
        "Common barangay differentials: Scabies, Impetigo, Tinea (ringworm/athlete's foot/pityriasis versicolor), "
        "Atopic Dermatitis, Contact Dermatitis, Varicella (chickenpox), Herpes Zoster (shingles), "
        "Urticaria (hives), Drug Eruption, Psoriasis, Cellulitis.\n"
        "Example — unilateral dermatomal vesicular rash + burning pain + elderly → top: Herpes Zoster, "
        "Contact Dermatitis, Varicella, Bullous Impetigo, Drug Eruption.\n"
        "RED FLAG: rapidly spreading skin redness + fever + skin peeling → possible Stevens-Johnson or Necrotizing Fasciitis → refer."
    ),
    "EYE": (
        "Ocular case confirmed by image.\n"
        "Key focus: vision threat vs non-urgent, unilateral vs bilateral, discharge type "
        "(watery=viral/allergic; mucopurulent=bacterial), corneal involvement, periorbital spread.\n"
        "Common barangay differentials: Bacterial Conjunctivitis, Viral Conjunctivitis, Allergic Conjunctivitis, "
        "Corneal Abrasion, Foreign Body, Hordeolum (stye), Chalazion, Preseptal Cellulitis.\n"
        "RED FLAG: corneal cloudiness/haziness, severe eye pain, sudden vision loss, or periorbital spreading "
        "redness/swelling → possible orbital cellulitis or corneal ulcer → refer immediately."
    ),
    "ORAL": (
        "Oral/throat case confirmed by image.\n"
        "Key focus: tonsillar exudate, peritonsillar asymmetry (abscess risk), uvula deviation, "
        "trismus, floor-of-mouth swelling (Ludwig's angina risk), oral lesions.\n"
        "Common barangay differentials: Streptococcal Pharyngitis, Viral Tonsillitis, Peritonsillar Abscess, "
        "Oral Candidiasis (thrush), Aphthous Ulcer, Herpangina, Dental Abscess, Stomatitis.\n"
        "RED FLAG: drooling + muffled 'hot potato' voice + trismus + uvula deviation → peritonsillar abscess "
        "or Ludwig's angina → refer immediately (airway at risk)."
    ),
    "MUSCULOSKELETAL": (
        "Musculoskeletal case confirmed by image.\n"
        "Key focus: deformity (angulation/shortening suggests fracture vs dislocation), neurovascular "
        "distal status (pulse/sensation/color), open wound over joint (septic arthritis risk), "
        "joint vs bone vs soft tissue origin.\n"
        "Common barangay differentials: Fracture, Sprain/Ligament Tear, Contusion/Hematoma, "
        "Joint Effusion, Acute Gout, Septic Arthritis, Cellulitis over joint.\n"
        "RED FLAG: visible bone, open fracture, neurovascular compromise (cold/pale/pulseless distal limb), "
        "or rapidly expanding hematoma → refer immediately."
    ),
    "RESPIRATORY": (
        "Visible respiratory signs in image.\n"
        "Key focus: cyanosis (lip/nail/fingertip color), chest retractions, accessory muscle use, "
        "chest asymmetry, visible distress posture (tripoding).\n"
        "Any visible cyanosis = HIGH suspicion for SpO2 < 92% → likely RED regardless of other findings.\n"
        "Common barangay differentials: Bronchial Asthma (exacerbation), Pneumonia, COPD Exacerbation, "
        "Anaphylaxis, Pleural Effusion, Pulmonary Edema.\n"
        "RED FLAG: cyanosis, severe accessory muscle use, inability to speak in full sentences → RED."
    ),
    "ABDOMINAL": (
        "Abdominal signs visible in image.\n"
        "Key focus: distension pattern (generalized/localized), visible mass or hernia "
        "(reducible vs irreducible), skin color changes (jaundice/bruising), surgical wound condition.\n"
        "Common barangay differentials: Intestinal Obstruction, Ascites (liver disease/heart failure), "
        "Incarcerated Hernia, Post-surgical Wound Infection, Acute Appendicitis, Liver Disease.\n"
        "RED FLAG: rigid board-like distension + fever + guarding posture → peritonitis → refer immediately."
    ),
    "OTHER": (
        "Image provided but category unclear or not identifiable as a specific medical domain.\n"
        "Weight image findings by specificity against the chief complaint. "
        "If findings are vague, prioritize chief complaint for the differential."
    ),
}


import re as _re


def _extract_image_category(image_findings: str) -> str:
    """Parse MedGemma's Category: tag; fall back to keyword scan if tag is missing."""
    m = _re.match(r"Category:\s*(\w+)", image_findings.strip(), _re.IGNORECASE)
    if m and m.group(1).upper() in _IMAGE_CATEGORIES:
        return m.group(1).upper()
    # Keyword fallback — handles cases where MedGemma skips the tag
    text = image_findings.upper()
    if any(w in text for w in ["PUNCTURE", "LACERATION", "WOUND", "BURN", "ABRASION", "BITE", "CUT", "BLEEDING"]):
        return "WOUND"
    if any(w in text for w in ["RASH", "VESICLE", "PAPULE", "MACULE", "LESION", "BLISTER", "SCALING", "PLAQUE", "PUSTULE"]):
        return "SKIN"
    if any(w in text for w in ["EYE", "CONJUNCTIV", "CORNEA", "EYELID", "OCULAR", "SCLERA"]):
        return "EYE"
    if any(w in text for w in ["TONSIL", "THROAT", "PHARYNX", "ORAL", "TONGUE", "GUM", "TOOTH", "PALATE"]):
        return "ORAL"
    if any(w in text for w in ["DEFORMITY", "SWELLING", "JOINT", "BONE", "FRACTURE", "LIMB", "BRUISING", "ECCHYMOSIS"]):
        return "MUSCULOSKELETAL"
    if any(w in text for w in ["CYANOSIS", "CYANOTIC", "CHEST", "BREATHING", "RESPIRATORY", "ACCESSORY MUSCLE"]):
        return "RESPIRATORY"
    if any(w in text for w in ["ABDOMEN", "ABDOMINAL", "DISTENSION", "HERNIA", "ASCITES"]):
        return "ABDOMINAL"
    return "OTHER"


import logging as _logging
_img_log = _logging.getLogger(__name__)


def _parse_medgemma_findings(raw_findings: str) -> dict:
    """Parse MedGemma's 4-section structured output into components."""
    category = _extract_image_category(raw_findings)

    obs_m = _re.search(
        r'Observations?:\s*\n?(.*?)(?=Visual Impression:|Confidence:|$)',
        raw_findings, _re.IGNORECASE | _re.DOTALL
    )
    observations = obs_m.group(1).strip() if obs_m else raw_findings

    vi_m = _re.search(
        r'Visual Impression?:\s*\n?(.*?)(?=Confidence:|$)',
        raw_findings, _re.IGNORECASE | _re.DOTALL
    )
    visual_impression = vi_m.group(1).strip() if vi_m else ""

    conf_m = _re.search(r'\bConfidence:\s*(HIGH|MEDIUM|LOW)\b', raw_findings, _re.IGNORECASE)
    confidence = conf_m.group(1).upper() if conf_m else "LOW"

    basis_m = _re.search(r'Confidence Basis:\s*(.+?)(?:\n|$)', raw_findings, _re.IGNORECASE)
    confidence_basis = basis_m.group(1).strip() if basis_m else ""

    parsed = {
        "category": category,
        "observations": observations,
        "visual_impression": visual_impression,
        "confidence": confidence,
        "confidence_basis": confidence_basis,
    }
    _img_log.info(
        f"\n{'─'*60}\n"
        f"MedGemma Parsed → Category: {category} | Confidence: {confidence}\n"
        f"Visual Impression: {visual_impression or '(none)'}\n"
        f"Confidence Basis: {confidence_basis or '(none)'}\n"
        f"{'─'*60}"
    )
    return parsed


# ── Stage 1b: Gemma 4 — BHW question generator ONLY (tiny focused output) ─────
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


# ── PDF Enrichment: MedGemma — concise clinical notes ────────────────────────
MEDGEMMA_ENRICHMENT_SYSTEM_PROMPT = """You are a clinical documentation assistant for a community health triage system in the Philippines. A Barangay Health Worker (BHW) triaged a patient using GEMMA AI. Add brief, actionable clinical notes per condition for the BHW's handoff reference and the receiving physician.

OUTPUT — return ONLY valid JSON in this exact format, no other text:
{
  "enrichments": [
    {
      "condition": "Exact condition name from triage output",
      "clinical_summary": "ONE sentence: key clinical justification linking symptoms and vitals to this diagnosis.",
      "priority_workup": "Top 2-3 specific tests only, comma-separated (e.g. Non-contrast CT head, serum tryptase, CBC).",
      "red_flags": "2-3 specific warning signs requiring immediate escalation, comma-separated (e.g. stridor, SpO2 < 88%, altered consciousness)."
    }
  ]
}

RULES:
- Enrich EACH condition listed (up to 5)
- clinical_summary: ONE sentence max. Do NOT repeat the chief complaint word-for-word.
- priority_workup: 2-3 specific test names, comma-separated — NEVER write "None". For functional/psychiatric conditions, name the appropriate evaluation (e.g. "Psychiatric evaluation, PHQ-9 screen").
- red_flags: 2-3 specific warning signs, comma-separated — NEVER write "None". For psychiatric conditions, name specific escalation signs (e.g. "suicidal ideation, dissociation, inability to self-calm").
- Never write "This condition is not specified" — always give the best clinical answer based on available data
- Consider the patient's age, sex, vitals, and all reported symptoms"""


def build_patient_context(patient_data: dict) -> str:
    """
    Format a patient_data dict into the structured text block injected into Gemma 4 prompts.

    Sections included (only if data is present):
      Demographics  — age and sex
      Chief Complaint
      Vital Signs   — BP, temperature, heart rate, SpO2
      Image Findings — MedGemma output parsed into category + clinical context block
      Initial Assessment — Stage 1a result carried forward into Stage 2a
      Follow-up Q&A  — BHW-collected answers appended for Stage 2a refinement
    """
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
        findings = patient_data["image_findings"]
        parsed = _parse_medgemma_findings(findings)
        category = parsed["category"]
        clinical_context = IMAGE_CLINICAL_CONTEXT.get(category, IMAGE_CLINICAL_CONTEXT["OTHER"])

        img_lines = [f"Visual Observation — MedGemma field photo analysis [Category: {category}]:"]
        img_lines.append(f"\nClinical Observations:\n{parsed['observations']}")

        vi = parsed.get("visual_impression", "").strip()
        if vi and vi.lower() != "cannot determine from image":
            img_lines.append(f"\nMedGemma Visual Impression: {vi}")
            img_lines.append(f"Confidence: {parsed['confidence']}")
            if parsed.get("confidence_basis"):
                img_lines.append(f"Confidence Basis: {parsed['confidence_basis']}")
        else:
            img_lines.append(
                f"\nMedGemma Visual Impression: Cannot determine from image "
                f"(Confidence: {parsed['confidence']})"
            )

        img_lines.append(f"\nImage Clinical Context for [{category}] — use to guide differential:\n{clinical_context}")
        parts.append("\n".join(img_lines))

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


def build_gemma4_triage_prompt(patient_data: dict) -> str:
    """
    Assemble the full Gemma 4 prompt: system instructions + patient context + task instruction.

    The task instruction varies by pipeline stage:
      Stage 1a (no followup_answers) — initial assessment + generate follow-up questions
      Stage 2a (has followup_answers) — refined assessment incorporating Q&A, omit questions
    """
    context = build_patient_context(patient_data)
    has_qa = bool(patient_data.get("followup_answers"))
    instruction = (
        "Using ALL patient data above — including the follow-up Q&A answers — "
        "reason through your differential and provide a REFINED triage assessment. "
        "Output ONLY the JSON schema shown in your instructions. Do NOT repeat or echo the patient data."
        if has_qa else
        "Using ALL patient data above, reason through your differential and provide "
        "a complete triage assessment. Output ONLY the JSON schema shown in your instructions. "
        "Do NOT repeat or echo the patient data."
    )
    return (
        f"{GEMMA4_TRIAGE_SYSTEM_PROMPT}\n\n"
        f"--- PATIENT DATA (do not repeat in output) ---\n"
        f"{context}\n"
        f"--- END PATIENT DATA ---\n\n"
        f"{instruction}"
    )


def build_gemma_followup_prompt(clinical_text: str, patient_data: dict) -> str:
    """
    Legacy Stage 1b prompt: generate 3 BHW-friendly Taglish follow-up questions.

    No longer called in the current pipeline — questions are now generated within
    Stage 1a to avoid a separate Ollama round-trip. Kept for reference.
    """
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
        "Output the JSON object with 3 Taglish questions now:"
    )


def build_medgemma_enrichment_prompt(triage_output: dict) -> str:
    """
    Assemble the MedGemma prompt for generating clinical consult notes per condition.

    Passes the Gemma 4 triage output (level, reason, conditions, SOAP) to
    MedGemma so it can produce condition-specific clinical_summary,
    priority_workup, and red_flags for the physician section of the handoff PDF.
    """
    conditions = triage_output.get("top_conditions", [])
    conditions_text = "\n".join(
        f"{c.get('rank', i + 1)}. {c['condition']}"
        for i, c in enumerate(conditions)
    )
    soap = triage_output.get("soap_summary", {})

    return (
        f"{MEDGEMMA_ENRICHMENT_SYSTEM_PROMPT}\n\n"
        f"--- TRIAGE OUTPUT TO ENRICH ---\n"
        f"Triage Level: {triage_output.get('triage_level', '')}\n"
        f"Triage Reason: {triage_output.get('triage_reason', '')}\n\n"
        f"Conditions (enrich each one):\n{conditions_text}\n\n"
        f"SOAP Note:\n"
        f"S: {soap.get('S', '')}\n"
        f"O: {soap.get('O', '')}\n"
        f"A: {soap.get('A', '')}\n"
        f"P: {soap.get('P', '')}\n"
        f"--- END TRIAGE OUTPUT ---\n\n"
        "Provide clinical enrichment for each condition. Output ONLY the JSON."
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
