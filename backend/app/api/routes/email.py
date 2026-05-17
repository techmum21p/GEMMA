"""
Email API route — send the shift report to the barangay health coordinator.

Endpoint:
  POST /api/email/shift-report
      Generates the Excel shift report and emails it to the coordinator.
      Recipient email can be overridden in the request body (collected at the
      End Shift screen) or falls back to the email stored on the shift record.
      Returns 503 if SMTP is not configured in .env.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Patient, Shift
from app.services.email_service import send_shift_report
from app.services.export_service import generate_excel_report
from models.schemas import EmailRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/shift-report")
async def send_email_report(payload: EmailRequest, db: AsyncSession = Depends(get_db)):
    shift = await db.get(Shift, payload.shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    result = await db.execute(
        select(Patient).where(Patient.shift_id == payload.shift_id).order_by(Patient.timestamp)
    )
    patients = result.scalars().all()

    # Use email override from request if provided (collected on end-shift screen)
    recipient_email = payload.coordinator_email or shift.coordinator_email
    if not recipient_email:
        raise HTTPException(status_code=400, detail="No coordinator email provided.")

    shift_dict = {
        "id": shift.id,
        "bhw_name": shift.bhw_name,
        "date": shift.date,
        "start_time": shift.start_time,
        "end_time": shift.end_time,
        "coordinator_email": recipient_email,
    }
    patients_list = [
        {
            "id": p.id,
            "timestamp": p.timestamp,
            "name": p.name,
            "age": p.age,
            "sex": p.sex,
            "chief_complaint": p.chief_complaint,
            "triage_level": p.triage_level,
            "top_conditions": p.top_conditions,
            "status": p.status,
        }
        for p in patients
    ]

    excel_path = generate_excel_report(shift_dict, patients_list)
    success = send_shift_report(shift_dict, patients_list, excel_path)

    if not success:
        raise HTTPException(
            status_code=503,
            detail="Hindi ma-send ang email. Suriin ang SMTP settings sa .env file.",
        )

    return {"message": f"Shift report sent to {recipient_email}", "excel_path": excel_path}
