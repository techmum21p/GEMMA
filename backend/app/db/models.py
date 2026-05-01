import uuid
from datetime import datetime, date

from sqlalchemy import String, Integer, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    bhw_name: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    coordinator_email: Mapped[str] = mapped_column(String, nullable=False)

    patients: Mapped[list["Patient"]] = relationship("Patient", back_populates="shift", lazy="select")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shift_id: Mapped[str] = mapped_column(String, ForeignKey("shifts.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    image_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_qa: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    triage_level: Mapped[str] = mapped_column(String(10), nullable=False)
    top_conditions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    handoff_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Pending", nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    shift: Mapped["Shift"] = relationship("Shift", back_populates="patients")
