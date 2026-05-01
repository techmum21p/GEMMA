import json
import logging

from langchain_ollama import OllamaLLM

from app.core.config import settings
from app.prompts.triage_prompt import TRIAGE_SYSTEM_PROMPT, build_triage_prompt, TRIAGE_FALLBACK

logger = logging.getLogger(__name__)

_llm: OllamaLLM | None = None

_DEFAULT_FOLLOWUP = [
    "Gaano na katagal ang mga sintomas mo?",
    "Mayroon ka bang ibang nararamdaman bukod sa nabanggit?",
    "Allergic ka ba sa kahit anong gamot?",
]
_DEFAULT_DISCLAIMER = "For BHW reference only. This is not a doctor's diagnosis."


def _get_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=settings.GEMMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
            format="json",
            num_ctx=8192,
            num_predict=8192,  # generous ceiling — model stops at end of JSON anyway
        )
    return _llm


def _repair_truncated_json(raw: str) -> dict:
    """
    Handle the common truncation pattern where the model runs out of tokens
    mid-string on the last field (usually 'disclaimer').
    Strategy: find the last clean comma at depth 1 and close the object there.
    """
    depth = 0
    in_string = False
    last_comma_at_depth_1 = -1
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == '"' and (i == 0 or raw[i - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if c in ("{", "["):
                depth += 1
            elif c in ("}", "]"):
                depth -= 1
            elif c == "," and depth == 1:
                last_comma_at_depth_1 = i
        i += 1

    if last_comma_at_depth_1 > 0:
        candidate = raw[:last_comma_at_depth_1].rstrip() + "\n}"
        return json.loads(candidate)
    raise ValueError("JSON repair found no recovery point")


def _parse_triage_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # Try clean parse first; fall back to truncation repair
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed ({e}), attempting truncation repair…")
        data = _repair_truncated_json(raw)

    # Only hard-fail on fields we can't fabricate
    critical = {"triage_level", "top_conditions", "soap_summary"}
    missing_critical = critical - data.keys()
    if missing_critical:
        raise ValueError(f"Missing critical keys: {missing_critical}")

    # Fill optional fields with safe defaults so we never return the "Unable to assess" fallback
    # just because the model ran out of tokens on the last field
    data.setdefault("triage_reason", "Assessment based on available information.")
    data.setdefault("followup_questions", _DEFAULT_FOLLOWUP)
    data.setdefault("disclaimer", _DEFAULT_DISCLAIMER)

    if data["triage_level"] not in {"RED", "YELLOW", "GREEN"}:
        data["triage_level"] = "YELLOW"

    # Normalize top_conditions — Gemma sometimes puts condition name in "rank"
    # and omits "condition" entirely, e.g. {"rank": "Anemia", "plain_explanation": "..."}
    raw_conditions = data.get("top_conditions", [])
    conditions = []
    for i, item in enumerate(raw_conditions):
        rank_val = item.get("rank")
        condition_val = item.get("condition")
        if isinstance(rank_val, str) and not condition_val:
            # rank field contains condition name — repair it
            conditions.append({
                "rank": i + 1,
                "condition": rank_val,
                "plain_explanation": item.get("plain_explanation", "Kailangan ng karagdagang pagsusuri ng doktor."),
            })
        else:
            try:
                rank_int = int(rank_val)
            except (TypeError, ValueError):
                rank_int = i + 1
            conditions.append({
                "rank": rank_int,
                "condition": condition_val or "Additional assessment needed",
                "plain_explanation": item.get("plain_explanation", "Kailangan ng karagdagang pagsusuri ng doktor."),
            })

    # Pad top_conditions to 5 if truncated mid-list
    while len(conditions) < 5:
        rank = len(conditions) + 1
        conditions.append({
            "rank": rank,
            "condition": "Additional assessment needed",
            "plain_explanation": "Kailangan ng karagdagang pagsusuri ng doktor.",
        })
    data["top_conditions"] = conditions[:5]

    return data


async def run_triage(
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
) -> dict:
    llm = _get_llm()
    user_prompt = build_triage_prompt(
        chief_complaint, image_findings, followup_answers,
        bp, temperature, heart_rate, spo2, initial_assessment,
        age=age, sex=sex,
    )

    full_prompt = f"{TRIAGE_SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        raw = await llm.ainvoke(full_prompt)
        result = _parse_triage_response(raw)
        logger.info(f"Triage succeeded: level={result['triage_level']}, "
                    f"conditions={len(result.get('top_conditions', []))}")
        return result
    except Exception as e:
        logger.warning(f"Triage attempt 1 failed: {e}. Retrying with explicit JSON reminder…")

    try:
        raw = await llm.ainvoke(
            full_prompt + "\n\nCRITICAL: Output ONLY the JSON object. "
            "Do not add any text before or after. Close all brackets and braces properly."
        )
        result = _parse_triage_response(raw)
        logger.info(f"Triage retry succeeded: level={result['triage_level']}")
        return result
    except Exception as e:
        logger.error(f"Triage retry also failed: {e}. Returning fallback.")
        return TRIAGE_FALLBACK
