"""
Triage API routes — the primary entry point into the GEMMA AI pipeline.

Endpoints:
  POST /api/triage         — Text-only triage.  Accepts patient demographic
                             data, vitals, chief complaint, and optional
                             follow-up Q&A answers as form fields.  Routes to
                             Stage 1a (initial) or Stage 2a (refined) based on
                             whether followup_answers is present.

  POST /api/triage/image   — Multimodal triage.  Same as above but also
                             accepts an image upload.  The image is saved to
                             disk and sent to MedGemma (Stage 0) before the
                             Gemma 4 triage call.

  POST /api/triage/test-fallback — Demo endpoint that feeds deliberately
                             broken JSON through the parser chain and returns
                             the is_fallback=True response.  Used to showcase
                             the graceful degradation UI during demos.
"""
import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.image_service import analyze_image
from app.services.triage_service import run_triage, run_fallback_stress_test
from models.schemas import TriageResponse, ImageAnalysisResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/triage", tags=["triage"])

UPLOAD_DIR = Path("exports/images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class FallbackTestRequest(BaseModel):
    """Request body for /test-fallback endpoint."""
    chief_complaint: str = "No complaint recorded."
    age: int | None = None
    sex: str | None = None
    bp: str | None = None
    temperature: str | None = None
    heart_rate: str | None = None
    spo2: str | None = None


def _build_patient_data(
    chief_complaint: str,
    age: str = "",
    sex: str = "",
    bp: str = "",
    temperature: str = "",
    heart_rate: str = "",
    spo2: str = "",
    image_findings: str = "",
    followup_answers: str = "{}",
    initial_assessment: str = "",
) -> dict:
    """
    Coerce raw form strings into a typed patient_data dict for the triage pipeline.

    Empty strings become None (not passed to Gemma 4 to keep prompts lean).
    followup_answers and initial_assessment are JSON strings deserialised here.
    """
    age_int = None
    try:
        age_int = int(age) if age else None
    except ValueError:
        pass

    try:
        followup_dict = json.loads(followup_answers) if followup_answers else {}
    except Exception:
        followup_dict = {}

    try:
        initial_dict = json.loads(initial_assessment) if initial_assessment else None
    except Exception:
        initial_dict = None

    return {
        "chief_complaint": chief_complaint,
        "age": age_int,
        "sex": sex or None,
        "bp": bp or None,
        "temperature": temperature or None,
        "heart_rate": heart_rate or None,
        "spo2": spo2 or None,
        "image_findings": image_findings or None,
        "followup_answers": followup_dict or None,
        "initial_assessment": initial_dict,
    }


@router.post("", response_model=TriageResponse)
async def triage_text(
    chief_complaint: str = Form(...),
    age: str = Form(default=""),
    sex: str = Form(default=""),
    bp: str = Form(default=""),
    temperature: str = Form(default=""),
    heart_rate: str = Form(default=""),
    spo2: str = Form(default=""),
    image_findings: str = Form(default=""),
    followup_answers: str = Form(default="{}"),
    initial_assessment: str = Form(default=""),
):
    """
    Run text-only triage via Gemma 4.

    Routes to Stage 1a (initial assessment) when followup_answers is empty,
    or Stage 2a (refined assessment) when follow-up Q&A answers are provided.
    Returns is_fallback=True if Gemma 4 output cannot be parsed.
    """
    patient_data = _build_patient_data(
        chief_complaint=chief_complaint,
        age=age, sex=sex, bp=bp, temperature=temperature,
        heart_rate=heart_rate, spo2=spo2,
        image_findings=image_findings,
        followup_answers=followup_answers,
        initial_assessment=initial_assessment,
    )
    return await run_triage(patient_data)


@router.post("/image", response_model=TriageResponse)
async def triage_with_image(
    chief_complaint: str = Form(...),
    image: UploadFile = File(...),
    age: str = Form(default=""),
    sex: str = Form(default=""),
    bp: str = Form(default=""),
    temperature: str = Form(default=""),
    heart_rate: str = Form(default=""),
    spo2: str = Form(default=""),
    followup_answers: str = Form(default="{}"),
):
    """
    Multimodal triage: image upload → MedGemma Stage 0 → Gemma 4 Stage 1a/2a.

    The uploaded file is saved to exports/images/ and passed to analyze_image().
    MedGemma's findings string is injected into patient_data before the Gemma 4
    triage call.  The response includes image_path and image_findings fields.
    """
    ext = Path(image.filename).suffix if image.filename else ".jpg"
    img_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    with open(img_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    image_findings = await analyze_image(str(img_path), chief_complaint)

    patient_data = _build_patient_data(
        chief_complaint=chief_complaint,
        age=age, sex=sex, bp=bp, temperature=temperature,
        heart_rate=heart_rate, spo2=spo2,
        image_findings=image_findings,
        followup_answers=followup_answers,
    )

    result = await run_triage(patient_data)
    result["image_path"] = str(img_path)
    result["image_findings"] = image_findings
    return result


@router.post("/test-fallback", response_model=TriageResponse)
async def test_fallback(body: FallbackTestRequest | None = None):
    """
    Demo endpoint: feeds deliberately broken JSON through _parse_triage_json, returns is_fallback result.
    No DB writes. Safe to call repeatedly during demos.
    """
    if body is None:
        body = FallbackTestRequest()

    patient_data = {
        "chief_complaint": body.chief_complaint,
        "age": body.age,
        "sex": body.sex,
        "bp": body.bp,
        "temperature": body.temperature,
        "heart_rate": body.heart_rate,
        "spo2": body.spo2,
        "followup_answers": None,
        "initial_assessment": None,
        "image_findings": None,
    }
    return await run_fallback_stress_test(patient_data)
