"""
SQLAlchemy ORM models for the GEMMA triage application.

Two tables:
  shifts   — one record per BHW shift (start/end time, BHW name)
  patients — one record per triaged patient, linked to a shift

JSON data (top_conditions, followup_questions, followup_qa, soap_notes) is
stored as serialised JSON strings in TEXT columns.  SQLite does not have a
native JSON column type, and keeping the data as strings avoids any
ORM-level deserialisation surprises when reading back from the DB.
"""
import uuid
from datetime import datetime, date

from sqlalchemy import String, Integer, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Shift(Base):
    """
    Represents a single BHW duty shift.

    A shift groups all patients triaged by one BHW during one session.
    coordinator_email is optional at shift start and can be collected later
    at the End Shift screen before the email report is sent.
    """
    __tablename__ = "shifts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    bhw_name: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    coordinator_email: Mapped[str] = mapped_column(String, nullable=True, default="")

    patients: Mapped[list["Patient"]] = relationship("Patient", back_populates="shift", lazy="select")


class Patient(Base):
    """
    Represents one triaged patient within a shift.

    All AI-generated content (top_conditions, soap_notes, followup_questions,
    followup_qa) is stored as JSON strings.  image_path points to the uploaded
    photo on the local filesystem; image_findings stores MedGemma's plain-text
    assessment. pdf_path is set after the first PDF generation and reused on
    subsequent downloads.
    """
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shift_id: Mapped[str] = mapped_column(String, ForeignKey("shifts.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    bp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(10), nullable=True)
    heart_rate: Mapped[str | None] = mapped_column(String(10), nullable=True)
    spo2: Mapped[str | None] = mapped_column(String(10), nullable=True)
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    image_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_questions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    followup_qa: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    triage_level: Mapped[str] = mapped_column(String(10), nullable=False)
    triage_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_conditions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    soap_notes: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Pending", nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    shift: Mapped["Shift"] = relationship("Shift", back_populates="patients")
