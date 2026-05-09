import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.triage_service import _parse_triage_response, run_triage
from app.prompts.triage_prompt import TRIAGE_FALLBACK


VALID_RESPONSE = json.dumps({
    "triage_level": "YELLOW",
    "triage_reason": "Malamang na ordinaryong sakit na kailangan ng konsultasyon.",
    "top_conditions": [
        {"rank": 1, "condition": "Flu", "plain_explanation": "Karaniwang lagnat at sipon."},
        {"rank": 2, "condition": "Dengue", "plain_explanation": "Maaaring may dengue kung may pantal."},
        {"rank": 3, "condition": "COVID-19", "plain_explanation": "Posibleng COVID kung may ubo."},
        {"rank": 4, "condition": "Tonsilitis", "plain_explanation": "Masakit na lalamunan."},
        {"rank": 5, "condition": "UTI", "plain_explanation": "Masakit sa pag-ihi."},
    ],
    "followup_questions": [
        "Gaano katagal na ang lagnat?",
        "Mayroon bang pantal sa katawan?",
        "May close contact ka ba sa COVID positive?",
    ],
    "soap_summary": {
        "S": "Lagnat at sipon mula kahapon.",
        "O": "Walang larawan.",
        "A": "Posibleng flu o viral infection.",
        "P": "Konsultahin ang doktor. Magpahinga at uminom ng tubig.",
    },
    "disclaimer": "Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor.",
})

SAMPLE_PATIENT = {
    "chief_complaint": "Masakit ang ulo at may lagnat.",
    "age": 35,
    "sex": "F",
    "bp": "120/80",
    "temperature": "38.5",
    "heart_rate": None,
    "spo2": None,
    "image_findings": None,
    "followup_answers": None,
    "initial_assessment": None,
}

CLINICAL_TEXT = """TRIAGE LEVEL: YELLOW
TRIAGE REASON: Kailangan ng konsultasyon ng doktor.

TOP CONDITIONS:
1. Flu | Karaniwang lagnat at sipon.
2. Dengue | Maaaring may dengue kung may pantal.
3. COVID-19 | Posibleng COVID kung may ubo.
4. Tonsilitis | Masakit na lalamunan.
5. UTI | Masakit sa pag-ihi.

FOLLOW-UP QUESTIONS:
1. Gaano katagal na ang lagnat?
2. Mayroon bang pantal sa katawan?
3. May close contact ka ba sa COVID positive?

SOAP NOTE:
S: Lagnat at sipon mula kahapon.
O: BP: 120/80. Temp: 38.5°C.
A: Flu most likely. Consider Dengue and COVID-19.
P: Triage level YELLOW. Refer to clinic for consultation."""


def test_parse_valid_response():
    result = _parse_triage_response(VALID_RESPONSE)
    assert result["triage_level"] == "YELLOW"
    assert len(result["top_conditions"]) == 5
    assert "soap_summary" in result


def test_parse_invalid_triage_level():
    bad = json.loads(VALID_RESPONSE)
    bad["triage_level"] = "PURPLE"
    result = _parse_triage_response(json.dumps(bad))
    assert result["triage_level"] == "YELLOW"


def test_parse_missing_keys():
    with pytest.raises((ValueError, KeyError)):
        _parse_triage_response('{"triage_level": "RED"}')


def test_parse_markdown_wrapped():
    wrapped = f"```json\n{VALID_RESPONSE}\n```"
    result = _parse_triage_response(wrapped)
    assert result["triage_level"] == "YELLOW"


@pytest.mark.asyncio
async def test_run_triage_success():
    with (
        patch("app.services.triage_service._get_medgemma_llm") as mock_medgemma,
        patch("app.services.triage_service._get_gemma_llm") as mock_gemma,
    ):
        mock_medgemma_llm = AsyncMock()
        mock_medgemma_llm.ainvoke = AsyncMock(return_value=CLINICAL_TEXT)
        mock_medgemma.return_value = mock_medgemma_llm

        mock_gemma_llm = AsyncMock()
        mock_gemma_llm.ainvoke = AsyncMock(return_value=VALID_RESPONSE)
        mock_gemma.return_value = mock_gemma_llm

        result = await run_triage(SAMPLE_PATIENT)
        assert result["triage_level"] in {"RED", "YELLOW", "GREEN"}
        assert len(result["top_conditions"]) == 5


@pytest.mark.asyncio
async def test_run_triage_fallback_on_error():
    with (
        patch("app.services.triage_service._get_medgemma_llm") as mock_medgemma,
        patch("app.services.triage_service._get_gemma_llm") as mock_gemma,
    ):
        mock_medgemma_llm = AsyncMock()
        mock_medgemma_llm.ainvoke = AsyncMock(side_effect=Exception("Ollama unreachable"))
        mock_medgemma.return_value = mock_medgemma_llm

        mock_gemma_llm = AsyncMock()
        mock_gemma_llm.ainvoke = AsyncMock(side_effect=Exception("Ollama unreachable"))
        mock_gemma.return_value = mock_gemma_llm

        result = await run_triage(SAMPLE_PATIENT)
        assert result["triage_level"] == "YELLOW"
        assert result == TRIAGE_FALLBACK


# ── New tests for _build_fallback_with_patient_data ──
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
    sparse = {
        "chief_complaint": "Nahihilo.",
        "age": None,
        "sex": None,
        "bp": None,
        "temperature": None,
        "heart_rate": None,
        "spo2": None,
        "followup_answers": None,
        "initial_assessment": None,
        "image_findings": None,
    }
    result = _build_fallback_with_patient_data(sparse)
    assert result["is_fallback"] is True
    assert "Nahihilo." in result["soap_summary"]["S"]
