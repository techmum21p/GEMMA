import json
import logging
import re

from langchain_ollama import OllamaLLM

from app.core.config import settings
from app.prompts.triage_prompt import (
    TRIAGE_FALLBACK,
    build_gemma_followup_prompt,
    build_medgemma_prompt,
)

logger = logging.getLogger(__name__)

_medgemma_llm: OllamaLLM | None = None
_gemma_llm: OllamaLLM | None = None

_DEFAULT_FOLLOWUP = [
    "Gaano na katagal ang mga sintomas mo?",
    "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
    "Allergic ka ba sa kahit anong gamot?",
]
_DEFAULT_DISCLAIMER = "For BHW reference only. This is not a doctor's diagnosis."


def _get_medgemma_llm() -> OllamaLLM:
    global _medgemma_llm
    if _medgemma_llm is None:
        _medgemma_llm = OllamaLLM(
            model=settings.MEDGEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.2,
            num_ctx=4096,
            num_predict=2048,
        )
    return _medgemma_llm


def _get_gemma_llm() -> OllamaLLM:
    global _gemma_llm
    if _gemma_llm is None:
        _gemma_llm = OllamaLLM(
            model=settings.GEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.3,
            format="json",   # forces valid JSON object output — bare arrays are unreliable
            num_ctx=4096,
            num_predict=512,  # enough for a small JSON object with 3 Taglish questions
        )
    return _gemma_llm


def _parse_medgemma_text(clinical_text: str) -> dict:
    """
    Parse MedGemma's structured plain text output deterministically.
    This replaces the Gemma JSON-format call for structured data extraction,
    eliminating truncation failures on complex JSON generation.
    """
    result: dict = {}

    # Triage level
    m = re.search(r'TRIAGE LEVEL:\s*(RED|YELLOW|GREEN)', clinical_text, re.IGNORECASE)
    result['triage_level'] = m.group(1).upper() if m else 'YELLOW'

    # Triage reason (text between TRIAGE REASON and TOP CONDITIONS)
    m = re.search(r'TRIAGE REASON:\s*(.+?)(?=\n\s*\nTOP|\nTOP)', clinical_text, re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r'TRIAGE REASON:\s*(.+?)$', clinical_text, re.MULTILINE | re.IGNORECASE)
    result['triage_reason'] = m.group(1).strip() if m else 'Assessment based on available information.'

    # Top conditions — format: "1. Condition Name | Plain explanation"
    conditions: list[dict] = []
    m = re.search(r'TOP CONDITIONS:\s*\n(.*?)(?=\n\s*\nSOAP|\nSOAP)', clinical_text, re.DOTALL | re.IGNORECASE)
    if m:
        for line in m.group(1).strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            line = re.sub(r'^\d+[\.\)]\s*', '', line)  # strip leading "1. "
            if '|' in line:
                cond, expl = line.split('|', 1)
                cond, expl = cond.strip(), expl.strip()
                if cond and cond.upper() not in ('N/A', 'NA'):
                    conditions.append({
                        'rank': len(conditions) + 1,
                        'condition': cond,
                        'plain_explanation': expl,
                    })
            elif line and line.upper() not in ('N/A', 'NA'):
                conditions.append({
                    'rank': len(conditions) + 1,
                    'condition': line,
                    'plain_explanation': 'Kailangan ng karagdagang pagsusuri ng doktor.',
                })

    result['top_conditions'] = conditions[:5]  # cap at 5, show only what MedGemma provided

    # SOAP note
    soap: dict = {'S': '', 'O': '', 'A': '', 'P': ''}
    m = re.search(r'SOAP NOTE:\s*\n(.*)', clinical_text, re.DOTALL | re.IGNORECASE)
    if m:
        soap_text = m.group(1)
        s = re.search(r'\bS:\s*(.+?)(?=\nO:|\Z)', soap_text, re.DOTALL)
        o = re.search(r'\bO:\s*(.+?)(?=\nA:|\Z)', soap_text, re.DOTALL)
        a = re.search(r'\bA:\s*(.+?)(?=\nP:|\Z)', soap_text, re.DOTALL)
        # P: stop at echoed context markers (MedGemma sometimes echoes patient data after the plan)
        _ECHO_MARKERS = r'Age:|Sex:|Chief Complaint:|Vital Signs:|Follow-up Q&A|Initial Assessment|Blood Pressure:|Temperature:|Heart Rate:|SpO2:'
        p = re.search(rf'\bP:\s*(.+?)(?=\n\n|\n(?:{_ECHO_MARKERS})|\Z)', soap_text, re.DOTALL)
        if s: soap['S'] = s.group(1).strip()
        if o: soap['O'] = o.group(1).strip()
        if a: soap['A'] = a.group(1).strip()
        if p: soap['P'] = p.group(1).strip()
    result['soap_summary'] = soap
    result['disclaimer'] = _DEFAULT_DISCLAIMER

    return result


async def _run_initial_triage(patient_data: dict) -> dict:
    """
    Stage 1a: MedGemma → clinical plain text (differential Dx, triage level, SOAP)
    Local parser: extract all structured fields deterministically — no JSON truncation risk
    Stage 1b: Gemma → ONLY 3 Taglish follow-up questions (JSON array of strings, tiny output)
    """
    medgemma = _get_medgemma_llm()
    gemma = _get_gemma_llm()
    medgemma_prompt = build_medgemma_prompt(patient_data)

    try:
        clinical_text = await medgemma.ainvoke(medgemma_prompt)
        logger.info(f"[Stage 1a] MedGemma assessment ({len(clinical_text)} chars)")
        logger.debug(f"[Stage 1a] MedGemma output:\n{clinical_text}")

        result = _parse_medgemma_text(clinical_text)
        if result['triage_level'] not in {'RED', 'YELLOW', 'GREEN'}:
            raise ValueError(f"Invalid triage level parsed: {result['triage_level']}")

        # Stage 1b: Gemma generates ONLY a tiny JSON array of 3 questions
        followup_prompt = build_gemma_followup_prompt(clinical_text, patient_data)
        raw_qs = await gemma.ainvoke(followup_prompt)
        logger.info(f"[Stage 1b] Gemma questions raw: {raw_qs[:300]}")

        try:
            clean = raw_qs.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1].lstrip("json").strip()
            data = json.loads(clean)
            # Gemma outputs {"questions": [...]} — also handle bare list as fallback
            if isinstance(data, dict):
                raw_list = data.get("questions") or data.get("followup_questions") or []
            elif isinstance(data, list):
                raw_list = data
            else:
                raise ValueError(f"Unexpected type: {type(data)}")
            questions = [str(q).strip() for q in raw_list if str(q).strip()][:3]
            if not questions:
                raise ValueError("Empty after filtering")
        except Exception as qe:
            logger.warning(f"[Stage 1b] Question parse failed ({qe}), using defaults")
            questions = _DEFAULT_FOLLOWUP

        result['followup_questions'] = questions if questions else _DEFAULT_FOLLOWUP
        logger.info(f"Initial triage done: level={result['triage_level']}, qs={len(result['followup_questions'])}")
        return result

    except Exception as e:
        logger.error(f"Initial triage failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK


async def _run_refined_triage(patient_data: dict) -> dict:
    """
    Stage 2a: MedGemma → refined clinical plain text (uses Q&A answers)
    Local parser: extract refined assessment — no Gemma call needed
    """
    medgemma = _get_medgemma_llm()
    medgemma_prompt = build_medgemma_prompt(patient_data)

    try:
        clinical_text = await medgemma.ainvoke(medgemma_prompt)
        logger.info(f"[Stage 2a] MedGemma refined assessment ({len(clinical_text)} chars)")
        logger.debug(f"[Stage 2a] MedGemma output:\n{clinical_text}")

        result = _parse_medgemma_text(clinical_text)
        if result['triage_level'] not in {'RED', 'YELLOW', 'GREEN'}:
            raise ValueError(f"Invalid triage level parsed: {result['triage_level']}")

        result['followup_questions'] = []  # Q&A phase is complete
        logger.info(f"Refined triage done: level={result['triage_level']}")
        return result

    except Exception as e:
        logger.error(f"Refined triage failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK


async def run_triage(patient_data: dict) -> dict:
    """
    Routes to the correct pipeline stage based on whether follow-up answers exist.

    Initial triage  (no followup_answers): Stage 1a MedGemma → local parse → Stage 1b Gemma Qs
    Refined triage  (has followup_answers): Stage 2a MedGemma → local parse (no Gemma needed)
    """
    if patient_data.get("followup_answers"):
        return await _run_refined_triage(patient_data)
    return await _run_initial_triage(patient_data)
