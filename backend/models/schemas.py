from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any

from pydantic import BaseModel, field_validator


# ── Triage ────────────────────────────────────────────────────────────────────

class TriageRequest(BaseModel):
    chief_complaint: str
    followup_answers: dict[str, str] | None = None
    image_findings: str | None = None


class Condition(BaseModel):
    rank: int
    condition: str
    plain_explanation: str


class SoapNote(BaseModel):
    S: str
    O: str
    A: str
    P: str


class TriageResponse(BaseModel):
    triage_level: str
    triage_reason: str
    top_conditions: list[Condition]
    followup_questions: list[str]
    soap_summary: SoapNote
    disclaimer: str
    is_fallback: bool = False


# ── Image ─────────────────────────────────────────────────────────────────────

class ImageAnalysisResponse(BaseModel):
    findings: str


# ── Patients ──────────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    shift_id: str
    name: str | None = None
    age: int | None = None
    sex: str | None = None
    address: str | None = None
    bp: str | None = None
    temperature: str | None = None
    heart_rate: str | None = None
    spo2: str | None = None
    chief_complaint: str
    image_path: str | None = None
    image_findings: str | None = None
    followup_questions: list[str] | None = None
    followup_qa: dict[str, Any] | None = None
    triage_level: str
    triage_reason: str | None = None
    top_conditions: list[dict[str, Any]]
    soap_notes: str


class PatientStatusUpdate(BaseModel):
    status: str


class PatientOut(BaseModel):
    id: int
    shift_id: str
    timestamp: datetime
    name: str | None
    age: int | None
    sex: str | None
    address: str | None = None
    bp: str | None = None
    temperature: str | None = None
    heart_rate: str | None = None
    spo2: str | None = None
    chief_complaint: str
    image_path: str | None
    image_findings: str | None
    followup_questions: str
    followup_qa: str
    triage_level: str
    triage_reason: str | None = None
    top_conditions: str
    soap_notes: str
    status: str
    pdf_path: str | None

    model_config = {"from_attributes": True}


# ── Shifts ────────────────────────────────────────────────────────────────────

class ShiftStart(BaseModel):
    bhw_name: str
    coordinator_email: str = ""


class ShiftOut(BaseModel):
    id: str
    bhw_name: str
    date: date
    start_time: datetime
    end_time: datetime | None
    coordinator_email: str

    model_config = {"from_attributes": True}


# ── Email ─────────────────────────────────────────────────────────────────────

class EmailRequest(BaseModel):
    shift_id: str
    coordinator_email: str | None = None
