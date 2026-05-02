import json
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.image_service import analyze_image
from app.services.triage_service import run_triage
from models.schemas import TriageResponse, ImageAnalysisResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/triage", tags=["triage"])

UPLOAD_DIR = Path("exports/images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
