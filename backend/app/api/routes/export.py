"""
Export API routes — PDF handoff documents and Excel shift reports.

Endpoints:
  GET /api/export/enrichment-status/{patient_id}
      Lightweight poll — returns {"ready": bool} so the frontend can show a
      spinner while MedGemma enrichment runs in the background.

  GET /api/export/excel/{shift_id}
      Generate (or re-generate) the shift Excel report (two sheets: Patient
      Log and Shift Summary) and stream it as a download.

  GET /api/export/pdf/{patient_id}
      Generate the BHW handoff PDF for a patient using ReportLab.  If a PDF
      already exists on disk for this patient it is served directly (cached).
      MedGemma enrichment is fetched from the prefetch cache if available.
"""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Patient, Shift
from app.services.export_service import generate_excel_report
from app.services.pdf_service import generate_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])


def _patient_to_dict(patient: Patient) -> dict:
    """Convert a Patient ORM instance to a plain dict for service layer consumption."""
    return {
        "id": patient.id,
        "shift_id": patient.shift_id,
        "timestamp": patient.timestamp,
        "name": patient.name,
        "age": patient.age,
        "sex": patient.sex,
        "address": getattr(patient, "address", None),
        "bp": getattr(patient, "bp", None),
        "temperature": getattr(patient, "temperature", None),
        "heart_rate": getattr(patient, "heart_rate", None),
        "spo2": getattr(patient, "spo2", None),
        "chief_complaint": patient.chief_complaint,
        "image_path": patient.image_path,
        "image_findings": patient.image_findings,
        "followup_qa": patient.followup_qa,
        "triage_level": patient.triage_level,
        "triage_reason": getattr(patient, "triage_reason", "") or "",
        "top_conditions": patient.top_conditions,
        "soap_notes": patient.soap_notes,
        "status": patient.status,
        "pdf_path": patient.pdf_path,
        "disclaimer": "Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor.",
    }


def _shift_to_dict(shift: Shift) -> dict:
    """Convert a Shift ORM instance to a plain dict for service layer consumption."""
    return {
        "id": shift.id,
        "bhw_name": shift.bhw_name,
        "date": shift.date,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "coordinator_email": shift.coordinator_email,
    }


@router.get("/enrichment-status/{patient_id}")
async def enrichment_status(patient_id: int, db: AsyncSession = Depends(get_db)):
    """Lightweight poll endpoint — tells the frontend when MedGemma enrichment is ready."""
    from app.services.enrichment_cache import is_done
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    raw = patient.top_conditions
    if isinstance(raw, str):
        try:
            top_conditions = json.loads(raw)
        except Exception:
            top_conditions = []
    else:
        top_conditions = raw or []
    triage_output = {"top_conditions": top_conditions}
    return {"ready": is_done(triage_output), "patient_id": patient_id}


@router.get("/excel/{shift_id}")
async def export_excel(shift_id: str, db: AsyncSession = Depends(get_db)):
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    result = await db.execute(
        select(Patient).where(Patient.shift_id == shift_id).order_by(Patient.timestamp)
    )
    patients = result.scalars().all()

    shift_dict = _shift_to_dict(shift)
    patients_list = [_patient_to_dict(p) for p in patients]

    excel_path = generate_excel_report(shift_dict, patients_list)

    return FileResponse(
        path=excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(excel_path).name,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/pdf/{patient_id}")
async def export_pdf(patient_id: int, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Serve existing PDF if it was already generated
    if patient.pdf_path and Path(patient.pdf_path).exists():
        return FileResponse(
            path=patient.pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{Path(patient.pdf_path).name}"'},
        )

    shift = await db.get(Shift, patient.shift_id)
    bhw_name = shift.bhw_name if shift else "BHW"

    patient_dict = _patient_to_dict(patient)
    pdf_path = await generate_pdf(patient_dict, bhw_name)

    patient.pdf_path = pdf_path
    await db.commit()

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{Path(pdf_path).name}"'},
    )
