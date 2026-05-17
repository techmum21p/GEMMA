"""
Patient CRUD API routes.

Endpoints:
  POST   /api/patients               — Save a triaged patient record to SQLite.
  GET    /api/patients?shift_id=xxx  — List all patients for a given shift.
  GET    /api/patients/{id}          — Retrieve a single patient by ID.
  PATCH  /api/patients/{id}/status  — Update the patient's workflow status
                                       (Pending → Seen / Referred / Sent Home).

Patient records are created after the BHW completes triage and taps "Save".
The AI-generated fields (triage_level, top_conditions, soap_notes, etc.) are
passed in from the frontend state and persisted as-is.
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Patient
from models.schemas import PatientCreate, PatientOut, PatientStatusUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/patients", tags=["patients"])

VALID_STATUSES = {"Pending", "Seen", "Referred", "Sent Home"}


@router.post("", response_model=PatientOut)
async def create_patient(payload: PatientCreate, db: AsyncSession = Depends(get_db)):
    """Persist a triaged patient to the database; initial status is Pending."""
    patient = Patient(
        shift_id=payload.shift_id,
        timestamp=datetime.utcnow(),
        name=payload.name,
        age=payload.age,
        sex=payload.sex,
        address=payload.address,
        bp=payload.bp,
        temperature=payload.temperature,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        chief_complaint=payload.chief_complaint,
        image_path=payload.image_path,
        image_findings=payload.image_findings,
        followup_questions=json.dumps(payload.followup_questions or []),
        followup_qa=json.dumps(payload.followup_qa or {}),
        triage_level=payload.triage_level,
        triage_reason=payload.triage_reason,
        top_conditions=json.dumps(payload.top_conditions),
        soap_notes=payload.soap_notes,
        status="Pending",
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientOut])
async def get_patients(shift_id: str, db: AsyncSession = Depends(get_db)):
    """Return all patients for a shift, ordered by triage timestamp."""
    result = await db.execute(
        select(Patient).where(Patient.shift_id == shift_id).order_by(Patient.timestamp)
    )
    return result.scalars().all()


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(patient_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve a single patient record by primary key."""
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}/status", response_model=PatientOut)
async def update_patient_status(
    patient_id: int,
    payload: PatientStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update the BHW-managed workflow status for a patient (Seen / Referred / Sent Home)."""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")

    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient.status = payload.status
    await db.commit()
    await db.refresh(patient)
    return patient
