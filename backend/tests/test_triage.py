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
    with patch("app.services.triage_service._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=VALID_RESPONSE)
        mock_get_llm.return_value = mock_llm

        result = await run_triage(chief_complaint="Masakit ang ulo at may lagnat.")
        assert result["triage_level"] in {"RED", "YELLOW", "GREEN"}


@pytest.mark.asyncio
async def test_run_triage_fallback_on_error():
    with patch("app.services.triage_service._get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("Ollama unreachable"))
        mock_get_llm.return_value = mock_llm

        result = await run_triage(chief_complaint="Test")
        assert result["triage_level"] == "YELLOW"
        assert result == TRIAGE_FALLBACK
