"""
Shift report email sender.

send_shift_report() emails the Excel shift report to the barangay health
coordinator using smtplib over STARTTLS.  Credentials are read from .env
(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD).

If SMTP credentials are not configured the function returns False and the
route handler returns 503 — the BHW is informed with a clear error message
rather than a silent failure.  This keeps email optional: GEMMA works fully
offline and only phones home when the BHW explicitly triggers the send.
"""
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_body(shift: dict, patients: list[dict]) -> str:
    """Build the plain-text email body with shift summary statistics in Filipino."""
    total = len(patients)
    red = sum(1 for p in patients if p.get("triage_level") == "RED")
    yellow = sum(1 for p in patients if p.get("triage_level") == "YELLOW")
    green = sum(1 for p in patients if p.get("triage_level") == "GREEN")

    start_time = shift.get("start_time", "")
    end_time = shift.get("end_time", "N/A")

    return f"""Magandang araw!

Narito ang shift report mula sa GEMMA — Guided Emergency & Medical Management Assistant.

=== SHIFT SUMMARY ===
BHW: {shift.get('bhw_name', '')}
Petsa: {shift.get('date', '')}
Simula ng Shift: {start_time}
Katapusan ng Shift: {end_time}

=== BILANG NG PASYENTE ===
Kabuuan: {total}
🔴 RED   : {red} ({red/total*100:.0f}% ng kabuuan)
🟡 YELLOW: {yellow} ({yellow/total*100:.0f}% ng kabuuan)
🟢 GREEN : {green} ({green/total*100:.0f}% ng kabuuan)

Nakalakip ang kumpletong Excel report ng shift.

---
Ang mensaheng ito ay awtomatikong nabuo ng GEMMA.
Hindi ito opisyal na medikal na rekord.
Para sa katanungan, makipag-ugnayan sa BHW na naka-nakalagay sa report.

GEMMA — Guided Emergency & Medical Management Assistant
Barangay Platero Health Center, City of Biñan
""" if total > 0 else f"""Magandang araw!

Walang pasyente na na-triage sa shift na ito.

BHW: {shift.get('bhw_name', '')}
Petsa: {shift.get('date', '')}

GEMMA — Guided Emergency & Medical Management Assistant
"""


def send_shift_report(shift: dict, patients: list[dict], excel_path: str) -> bool:
    """
    Email the Excel shift report to the coordinator and return True on success.

    Attaches the .xlsx file, sends via smtplib STARTTLS.
    Returns False (no exception raised) if credentials are missing or SMTP fails —
    the route handler converts this to a 503 response with a Filipino error message.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping email.")
        return False

    to_email = shift.get("coordinator_email", "")
    if not to_email:
        logger.warning("No coordinator email in shift record. Skipping email.")
        return False

    bhw_name = shift.get("bhw_name", "BHW")
    shift_date = shift.get("date", "")
    subject = f"[GEMMA] Shift Report — {bhw_name} — {shift_date}"

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    body = _build_body(shift, patients)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    excel_file = Path(excel_path)
    if excel_file.exists():
        with open(excel_file, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="xlsx")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=excel_file.name,
            )
            msg.attach(attachment)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        logger.info(f"Shift report emailed to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
