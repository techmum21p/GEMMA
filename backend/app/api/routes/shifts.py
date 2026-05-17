"""
Shift management API routes.

A shift represents one BHW duty session.  All patients triaged during a
session are linked to the same shift_id so they can be exported together.

Endpoints:
  POST /api/shifts/start         — Open a new shift; returns shift_id used
                                    by all subsequent patient and export calls.
  POST /api/shifts/end?shift_id= — Close the shift (sets end_time).
  GET  /api/shifts/{shift_id}    — Retrieve shift metadata.
"""
import logging
import uuid
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Shift, Patient
from models.schemas import ShiftStart, ShiftOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shifts", tags=["shifts"])


@router.post("/start", response_model=ShiftOut)
async def start_shift(payload: ShiftStart, db: AsyncSession = Depends(get_db)):
    """Create a new shift record.  shift_id is a UUID used as the session key."""
    shift = Shift(
        id=str(uuid.uuid4()),
        bhw_name=payload.bhw_name,
        date=date.today(),
        start_time=datetime.utcnow(),
        coordinator_email=payload.coordinator_email,
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    return shift


@router.post("/end", response_model=ShiftOut)
async def end_shift(shift_id: str, db: AsyncSession = Depends(get_db)):
    """Close the shift by recording end_time.  Prerequisite for the Excel and email export."""
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    shift.end_time = datetime.utcnow()
    await db.commit()
    await db.refresh(shift)
    return shift


@router.get("/{shift_id}", response_model=ShiftOut)
async def get_shift(shift_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch shift metadata by UUID."""
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift
