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
