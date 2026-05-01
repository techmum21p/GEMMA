"""Seed the database with test shift and patients for development."""
import asyncio
import json
import uuid
from datetime import datetime, date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import Shift, Patient


async def seed():
    await init_db()

    async with AsyncSessionLocal() as db:
        shift_id = str(uuid.uuid4())
        shift = Shift(
            id=shift_id,
            bhw_name="Maria Santos (Test BHW)",
            date=date.today(),
            start_time=datetime.utcnow(),
            coordinator_email="coordinator@health.gov.ph",
        )
        db.add(shift)

        patients = [
            Patient(
                shift_id=shift_id,
                timestamp=datetime.utcnow(),
                name="Juan dela Cruz",
                age=35,
                sex="M",
                chief_complaint="Masakit ang ulo at may lagnat mula kahapon ng gabi.",
                triage_level="YELLOW",
                top_conditions=json.dumps([
                    {"rank": 1, "condition": "Flu", "plain_explanation": "Karaniwang viral infection."},
                    {"rank": 2, "condition": "Dengue", "plain_explanation": "Posible kung may pantal."},
                    {"rank": 3, "condition": "COVID-19", "plain_explanation": "Kailangan ng test."},
                    {"rank": 4, "condition": "Tonsilitis", "plain_explanation": "Masakit ang lalamunan."},
                    {"rank": 5, "condition": "Heatstroke", "plain_explanation": "Kung mainit ang panahon."},
                ]),
                handoff_summary=json.dumps({
                    "S": "Lagnat at sakit ng ulo mula kahapon.",
                    "O": "Walang larawan.",
                    "A": "Posibleng flu o viral infection.",
                    "P": "Konsultahin ang doktor. Magpahinga at uminom ng tubig.",
                }),
                followup_qa=json.dumps({"Gaano katagal na ang lagnat?": "Mula kahapon ng gabi."}),
                status="Pending",
            ),
            Patient(
                shift_id=shift_id,
                timestamp=datetime.utcnow(),
                name=None,
                age=60,
                sex="F",
                chief_complaint="Nanghihina, nahihirapan huminga, masakit ang dibdib.",
                triage_level="RED",
                top_conditions=json.dumps([
                    {"rank": 1, "condition": "Heart attack", "plain_explanation": "Posibleng atake sa puso."},
                    {"rank": 2, "condition": "Angina", "plain_explanation": "Sakit ng dibdib mula sa puso."},
                    {"rank": 3, "condition": "Pulmonary embolism", "plain_explanation": "Posibleng pamumuo ng dugo sa baga."},
                    {"rank": 4, "condition": "GERD", "plain_explanation": "Acidity ng tiyan."},
                    {"rank": 5, "condition": "Anxiety attack", "plain_explanation": "Pag-aalala na nagdudulot ng sakit."},
                ]),
                handoff_summary=json.dumps({
                    "S": "Nanghihina at nahihirapan huminga. Masakit ang dibdib.",
                    "O": "Walang larawan.",
                    "A": "Posibleng cardiac emergency.",
                    "P": "I-refer agad sa ospital. Huwag hayaang lumakad nang malayo.",
                }),
                followup_qa="{}",
                status="Referred",
            ),
            Patient(
                shift_id=shift_id,
                timestamp=datetime.utcnow(),
                name="Pedro Reyes",
                age=12,
                sex="M",
                chief_complaint="Pantal sa braso at binti. Medyo mautak.",
                triage_level="GREEN",
                top_conditions=json.dumps([
                    {"rank": 1, "condition": "Allergic reaction", "plain_explanation": "Posibleng allergy sa pagkain o halaman."},
                    {"rank": 2, "condition": "Insect bite", "plain_explanation": "Kagat ng insekto."},
                    {"rank": 3, "condition": "Heat rash", "plain_explanation": "Pantal mula sa init."},
                    {"rank": 4, "condition": "Eczema", "plain_explanation": "Sakit sa balat."},
                    {"rank": 5, "condition": "Chickenpox", "plain_explanation": "Bulutong tubig."},
                ]),
                handoff_summary=json.dumps({
                    "S": "Pantal sa braso at binti, mautak.",
                    "O": "Walang larawan.",
                    "A": "Posibleng allergic reaction.",
                    "P": "Mag-apply ng antihistamine cream. Kung lumala, pumunta sa doktor.",
                }),
                followup_qa="{}",
                status="Seen",
            ),
        ]

        for p in patients:
            db.add(p)

        await db.commit()
        print(f"Seed complete. Shift ID: {shift_id}")
        print(f"Created {len(patients)} test patients.")


if __name__ == "__main__":
    asyncio.run(seed())
