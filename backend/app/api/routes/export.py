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
    return {
        "id": patient.id,
        "shift_id": patient.shift_id,
        "timestamp": patient.timestamp,
        "name": patient.name,
        "age": patient.age,
        "sex": patient.sex,
        "chief_complaint": patient.chief_complaint,
        "image_path": patient.image_path,
        "image_findings": patient.image_findings,
        "followup_qa": patient.followup_qa,
        "triage_level": patient.triage_level,
        "top_conditions": patient.top_conditions,
        "handoff_summary": patient.handoff_summary,
        "status": patient.status,
        "pdf_path": patient.pdf_path,
        "triage_reason": "",
        "disclaimer": "Para sa kaalaman ng BHW lamang. Hindi ito pagsusuri ng doktor.",
    }


def _shift_to_dict(shift: Shift) -> dict:
    return {
        "id": shift.id,
        "bhw_name": shift.bhw_name,
        "date": shift.date,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "coordinator_email": shift.coordinator_email,
    }


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
    )


@router.get("/pdf/{patient_id}")
async def export_pdf(patient_id: int, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    shift = await db.get(Shift, patient.shift_id)
    bhw_name = shift.bhw_name if shift else "BHW"

    patient_dict = _patient_to_dict(patient)
    pdf_path = generate_pdf(patient_dict, bhw_name)

    patient.pdf_path = pdf_path
    await db.commit()

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=Path(pdf_path).name,
    )
