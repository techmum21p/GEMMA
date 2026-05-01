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


@router.post("", response_model=TriageResponse)
async def triage_text(
    chief_complaint: str = Form(...),
    followup_answers: str = Form(default="{}"),
    image_findings: str = Form(default=""),
    bp: str = Form(default=""),
    temperature: str = Form(default=""),
    heart_rate: str = Form(default=""),
    spo2: str = Form(default=""),
    initial_assessment: str = Form(default=""),
    age: str = Form(default=""),
    sex: str = Form(default=""),
):
    import json
    try:
        followup_dict = json.loads(followup_answers) if followup_answers else {}
    except Exception:
        followup_dict = {}

    try:
        initial_dict = json.loads(initial_assessment) if initial_assessment else None
    except Exception:
        initial_dict = None

    age_int = None
    try:
        age_int = int(age) if age else None
    except ValueError:
        pass

    result = await run_triage(
        chief_complaint=chief_complaint,
        image_findings=image_findings or None,
        followup_answers=followup_dict or None,
        bp=bp or None,
        temperature=temperature or None,
        heart_rate=heart_rate or None,
        spo2=spo2 or None,
        initial_assessment=initial_dict,
        age=age_int,
        sex=sex or None,
    )
    return result


@router.post("/image", response_model=TriageResponse)
async def triage_with_image(
    chief_complaint: str = Form(...),
    image: UploadFile = File(...),
    followup_answers: str = Form(default="{}"),
    bp: str = Form(default=""),
    temperature: str = Form(default=""),
    heart_rate: str = Form(default=""),
    spo2: str = Form(default=""),
    age: str = Form(default=""),
    sex: str = Form(default=""),
):
    import json

    ext = Path(image.filename).suffix if image.filename else ".jpg"
    img_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    with open(img_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    image_findings = await analyze_image(str(img_path), chief_complaint)

    try:
        followup_dict = json.loads(followup_answers) if followup_answers else {}
    except Exception:
        followup_dict = {}

    age_int = None
    try:
        age_int = int(age) if age else None
    except ValueError:
        pass

    result = await run_triage(
        chief_complaint=chief_complaint,
        image_findings=image_findings,
        followup_answers=followup_dict or None,
        bp=bp or None,
        temperature=temperature or None,
        heart_rate=heart_rate or None,
        spo2=spo2 or None,
        age=age_int,
        sex=sex or None,
    )
    result["image_path"] = str(img_path)
    result["image_findings"] = image_findings
    return result
