"""
BHW Handoff PDF Generator — produces the doctor-facing patient handoff document.

generate_pdf() is the public entry point.  It:
  1. Fetches MedGemma enrichment data from the prefetch cache (or runs it now).
  2. Calls _generate_with_reportlab() to build the PDF using ReportLab.

The PDF contains:
  - GEMMA header (navy) with Barangay Platero branding
  - Triage level badge (colour-coded RED / YELLOW / GREEN) with action label
  - Patient demographics and vitals
  - Chief complaint (bullet-formatted)
  - Top N differential diagnoses
  - Follow-up Q&A if collected
  - SOAP note (doctor-facing, English)
  - Image findings from MedGemma (if image was provided)
  - Additional Clinical Notes per condition (MedGemma enrichment physician section)
  - Filipino-language disclaimer
  - Footer with generation timestamp

ReportLab is used instead of WeasyPrint because WeasyPrint requires system
libraries (libcairo, libpango) that are not reliably available on a Windows
laptop.  ReportLab is pure Python and installs without system dependencies.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

_PLACEHOLDER_COND = re.compile(r'^condition\s*\d+$', re.IGNORECASE)

logger = logging.getLogger(__name__)

PDF_DIR = Path("exports/pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; color: #1a1a1a; font-size: 13px; }}
  .header {{ background: #1B3A6B; color: white; padding: 16px 20px; }}
  .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; }}
  .header .subtitle {{ font-size: 11px; opacity: 0.8; margin-top: 3px; }}
  .content {{ padding: 16px 20px; }}
  .badge-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }}
  .badge {{ display: inline-block; padding: 6px 18px; border-radius: 4px; font-size: 16px; font-weight: bold; color: white; }}
  .RED {{ background: #C0392B; }}
  .YELLOW {{ background: #E67E22; }}
  .GREEN {{ background: #2D6A2D; }}
  .triage-reason {{ font-size: 12px; color: #444; margin: 4px 0 0 0; }}
  .section {{ margin-bottom: 14px; }}
  .section-title {{ font-size: 11px; font-weight: bold; color: #1B3A6B; border-bottom: 2px solid #1B3A6B; padding-bottom: 3px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }}
  .info-item {{ font-size: 12px; }}
  .info-label {{ color: #888; font-size: 10px; text-transform: uppercase; }}
  .vitals-row {{ display: flex; gap: 24px; margin-top: 4px; }}
  .vital-item {{ font-size: 12px; }}
  .condition-item {{ padding: 5px 0; border-bottom: 1px solid #f0f0f0; font-size: 12px; }}
  .condition-item:last-child {{ border-bottom: none; }}
  .condition-rank {{ display: inline-block; background: #1B3A6B; color: white; font-weight: bold; font-size: 10px; width: 18px; height: 18px; border-radius: 50%; text-align: center; line-height: 18px; margin-right: 6px; }}
  .condition-name {{ font-weight: bold; }}
  .condition-explanation {{ color: #555; font-style: italic; }}
  .qa-item {{ padding: 4px 0; font-size: 12px; border-bottom: 1px solid #f5f5f5; }}
  .qa-q {{ color: #333; font-weight: bold; }}
  .qa-a {{ color: #555; margin-left: 8px; }}
  .soap-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .soap-table td {{ padding: 6px 8px; vertical-align: top; border: 1px solid #e8e8e8; }}
  .soap-label {{ background: #f0f4f8; font-weight: bold; color: #1B3A6B; width: 110px; white-space: nowrap; }}
  .image-findings {{ background: #f8f8f8; border-left: 3px solid #1B3A6B; padding: 8px 12px; font-size: 12px; color: #444; }}
  .disclaimer {{ background: #FFF8E1; border: 1px solid #F5C518; padding: 8px 12px; font-size: 11px; color: #7a5c00; margin-top: 14px; border-radius: 4px; }}
  .footer {{ margin-top: 16px; border-top: 1px solid #ddd; padding-top: 8px; font-size: 10px; color: #999; text-align: center; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 14px 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>🏥 GEMMA — Doctor Handoff Summary</h1>
  <div class="subtitle">Guided Emergency &amp; Medical Management Assistant &nbsp;|&nbsp; Barangay Health Center, City of Biñan</div>
</div>

<div class="content">

<!-- Triage Level -->
<div class="section" style="margin-top:12px;">
  <div class="section-title">Triage Assessment</div>
  <div class="badge-row">
    <div class="badge {triage_level}">{triage_level}</div>
  </div>
  <p class="triage-reason">{triage_reason}</p>
</div>

<!-- Patient Information -->
<div class="section">
  <div class="section-title">Patient Information</div>
  <div class="info-grid">
    <div class="info-item"><div class="info-label">Name</div>{name}</div>
    <div class="info-item"><div class="info-label">Age / Sex</div>{age_sex}</div>
    <div class="info-item"><div class="info-label">Address</div>{address}</div>
    <div class="info-item"><div class="info-label">Date &amp; Time</div>{timestamp}</div>
    <div class="info-item"><div class="info-label">Brgy.Health Worker on Duty</div>{bhw_name}</div>
    <div class="info-item"><div class="info-label">Status</div>{status}</div>
  </div>
  {vitals_section}
</div>

<!-- Chief Complaint -->
<div class="section">
  <div class="section-title">Chief Complaint</div>
  <p style="margin:0; font-size:13px;">{chief_complaint}</p>
</div>

<!-- Top N Possible Conditions -->
<div class="section">
  <div class="section-title">Top {conditions_count} Possible Conditions</div>
  {conditions_html}
</div>

<!-- Follow-up Q&A -->
{followup_section}

<!-- SOAP Note -->
<div class="section">
  <div class="section-title">SOAP Note (for Doctor)</div>
  <table class="soap-table">
    <tr><td class="soap-label">S — Subjective</td><td>{soap_s}</td></tr>
    <tr><td class="soap-label">O — Objective</td><td>{soap_o}</td></tr>
    <tr><td class="soap-label">A — Assessment</td><td>{soap_a}</td></tr>
    <tr><td class="soap-label">P — Plan</td><td>{soap_p}</td></tr>
  </table>
</div>

<!-- Image Findings -->
{image_section}

<div class="disclaimer">
  ⚠️ <strong>Para sa kaalaman ng Brgy. Health Worker at Doktor lamang.</strong> Hindi ito opisyal na medikal na rekord.
  Hindi kapalit ng klinikal na pagsusuri ng lisensyadong doktor.
</div>

<div class="footer">
  Generated by GEMMA — Guided Emergency &amp; Medical Management Assistant &nbsp;|&nbsp;
  City of Biñan &nbsp;|&nbsp; {generated_at}
</div>

</div>
</body>
</html>"""


def _build_html(patient: dict, bhw_name: str) -> str:
    """Build the HTML string for a patient handoff document (unused — kept for reference)."""
    name    = patient.get("name") or "Not provided"
    age     = patient.get("age")
    sex_raw = patient.get("sex")
    sex     = {"M": "Male", "F": "Female"}.get(sex_raw, "—") if sex_raw else "—"
    age_sex = f"{age or '—'} y/o / {sex}"
    address = patient.get("address") or "—"
    status  = patient.get("status") or "Pending"

    timestamp = patient.get("timestamp", datetime.utcnow())
    ts_str = timestamp.strftime("%b %d, %Y  %H:%M") if not isinstance(timestamp, str) else timestamp

    # Vitals section
    bp         = patient.get("bp")
    temp       = patient.get("temperature")
    heart_rate = patient.get("heart_rate")
    spo2       = patient.get("spo2")
    if bp or temp or heart_rate or spo2:
        vitals_section = '<div class="vitals-row" style="margin-top:8px;flex-wrap:wrap;gap:12px;">'
        if bp:
            vitals_section += f'<div class="vital-item"><div class="info-label">Blood Pressure</div>{bp} mmHg</div>'
        if temp:
            vitals_section += f'<div class="vital-item"><div class="info-label">Temperature</div>{temp} °C</div>'
        if heart_rate:
            vitals_section += f'<div class="vital-item"><div class="info-label">Heart Rate</div>{heart_rate} bpm</div>'
        if spo2:
            vitals_section += f'<div class="vital-item"><div class="info-label">SpO2</div>{spo2}%</div>'
        vitals_section += '</div>'
    else:
        vitals_section = '<div style="font-size:11px;color:#aaa;margin-top:4px;">No vitals recorded</div>'

    # Chief complaint — bullet-formatted
    complaint_raw = patient.get("chief_complaint", "")
    complaint_lines = [l.strip() for l in complaint_raw.split("\n") if l.strip()]
    if len(complaint_lines) == 1:
        complaint_lines = [l.strip() for l in complaint_lines[0].split(";") if l.strip()]
    chief_complaint_html = "".join(
        f'<div style="margin:2px 0;">• {line}</div>' for line in complaint_lines
    ) or complaint_raw

    # Top conditions — filter out padding placeholders
    top_conditions = patient.get("top_conditions", [])
    if isinstance(top_conditions, str):
        top_conditions = json.loads(top_conditions)
    _SKIP = {"additional assessment needed", "n/a", "na", "unable to assess"}
    top_conditions = [
        c for c in top_conditions
        if c.get("condition", "").lower() not in _SKIP
        and not _PLACEHOLDER_COND.match(c.get("condition", "").strip())
    ]
    conditions_html = ""
    for c in top_conditions:
        conditions_html += (
            f'<div class="condition-item">'
            f'<span class="condition-rank">{c["rank"]}</span>'
            f'<span class="condition-name">{c["condition"]}</span>'
            f' — <span class="condition-explanation">{c["plain_explanation"]}</span>'
            f'</div>'
        )

    # Follow-up Q&A
    followup_raw = patient.get("followup_qa", "{}")
    try:
        followup_qa = json.loads(followup_raw) if isinstance(followup_raw, str) else followup_raw
    except Exception:
        followup_qa = {}
    if followup_qa:
        qa_rows = "".join(
            f'<div class="qa-item"><span class="qa-q">Q: {q}</span><span class="qa-a">→ {a}</span></div>'
            for q, a in followup_qa.items()
        )
        followup_section = f'<div class="section"><div class="section-title">Follow-Up Questions &amp; Answers</div>{qa_rows}</div>'
    else:
        followup_section = ""

    # SOAP
    handoff = patient.get("soap_notes", "{}")
    if isinstance(handoff, str):
        try:
            soap = json.loads(handoff)
        except Exception:
            soap = {"S": handoff, "O": "—", "A": "—", "P": "—"}
    else:
        soap = handoff

    # Image findings
    image_findings = patient.get("image_findings")
    image_section = ""
    if image_findings:
        image_section = (
            f'<div class="section">'
            f'<div class="section-title">Image Findings (MedGemma AI)</div>'
            f'<div class="image-findings">{image_findings}</div>'
            f'</div>'
        )

    return HTML_TEMPLATE.format(
        name=name,
        age_sex=age_sex,
        address=address,
        status=status,
        timestamp=ts_str,
        bhw_name=bhw_name,
        vitals_section=vitals_section,
        chief_complaint=chief_complaint_html,
        triage_level=patient.get("triage_level", "YELLOW"),
        triage_reason=patient.get("triage_reason", ""),
        conditions_count=len(top_conditions),
        conditions_html=conditions_html,
        followup_section=followup_section,
        soap_s=soap.get("S", ""),
        soap_o=soap.get("O", ""),
        soap_a=soap.get("A", ""),
        soap_p=soap.get("P", ""),
        image_section=image_section,
        generated_at=datetime.utcnow().strftime("%b %d, %Y %H:%M UTC"),
    )


async def generate_pdf(patient: dict, bhw_name: str) -> str:
    """
    Generate a ReportLab PDF handoff document for a triaged patient.

    Fetches MedGemma enrichment (clinical notes per condition) from the
    prefetch cache if available, then builds the PDF and returns its path.
    The route handler stores the path in the DB so subsequent requests are
    served directly from disk without regenerating.
    """
    patient_id = patient.get("id", "unknown")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pdf_path = PDF_DIR / f"patient_{patient_id}_{ts}.pdf"

    # Build triage_output dict from patient record for MedGemma enrichment
    triage_output = {
        "triage_level": patient.get("triage_level", ""),
        "triage_reason": patient.get("triage_reason", ""),
        "top_conditions": _parse_conditions(patient.get("top_conditions", "[]")),
        "soap_summary": _parse_soap(patient.get("soap_notes", "{}")),
    }
    from app.services.enrichment_cache import get_or_fetch
    enrichments = await get_or_fetch(triage_output)

    _generate_with_reportlab(patient, bhw_name, str(pdf_path), enrichments)
    logger.info(f"PDF generated: {pdf_path}")

    return str(pdf_path)


def _parse_conditions(raw) -> list:
    """Deserialise top_conditions from a JSON string or pass through a list."""
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


def _parse_soap(raw) -> dict:
    """Deserialise soap_notes from a JSON string or pass through a dict."""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {"S": "", "O": "", "A": "", "P": ""}


def _generate_with_reportlab(patient: dict, bhw_name: str, pdf_path: str, enrichments: list | None = None) -> None:
    """
    Build and write the ReportLab PDF to pdf_path.

    Sections rendered in order:
      1. Navy header with GEMMA branding
      2. Triage badge (RED / YELLOW / GREEN) with action label
      3. Patient information grid + vitals
      4. Chief complaint (bullet-formatted)
      5. Top N differential diagnoses
      6. Follow-up Q&A (if collected)
      7. SOAP note table
      8. Image findings (if provided)
      9. Additional Clinical Notes — MedGemma enrichment per condition
      10. Filipino disclaimer box
      11. Footer with generation timestamp
    """
    import html as _html
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, KeepTogether)
    from reportlab.lib.units import cm

    # ── Page geometry ─────────────────────────────────────────────────────────
    LM = RM = 1.5 * cm
    TM = BM = 1.5 * cm
    W = A4[0] - LM - RM          # usable width ≈ 510 pts / 18 cm

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            topMargin=TM, bottomMargin=BM,
                            leftMargin=LM, rightMargin=RM)

    # ── Colour palette ────────────────────────────────────────────────────────
    NAVY   = colors.HexColor("#1B3A6B")
    WHITE  = colors.white
    LIGHT  = colors.HexColor("#F0F4F8")
    GRID   = colors.HexColor("#E0E8F0")
    MUTED  = colors.HexColor("#777777")
    WBGC   = colors.HexColor("#FFF8E1")
    WBRD   = colors.HexColor("#F5C518")
    WFGC   = colors.HexColor("#7a5c00")
    BADGE  = {
        "RED":    colors.HexColor("#C0392B"),
        "YELLOW": colors.HexColor("#E67E22"),
        "GREEN":  colors.HexColor("#2D6A2D"),
    }
    ACTION = {
        "RED":    "CRITICAL  —  Refer to RHU / Hospital Immediately",
        "YELLOW": "URGENT  —  See Doctor On-Site at BHS",
        "GREEN":  "STABLE  —  Home Care / BHW-Managed",
    }

    # ── Typography ────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()["Normal"]

    def ps(name, **kw):
        return ParagraphStyle(name, parent=base, **kw)

    HDR_TITLE  = ps("HDR_TITLE", fontName="Helvetica-Bold", fontSize=15,
                    textColor=WHITE,  leading=19)
    HDR_SUB    = ps("HDR_SUB",   fontSize=8,
                    textColor=colors.HexColor("#B0C4DE"), leading=11)
    BADGE_LVL  = ps("BADGE_LVL", fontName="Helvetica-Bold", fontSize=22,
                    textColor=WHITE, alignment=1, leading=26)
    BADGE_ACT  = ps("BADGE_ACT", fontSize=10,
                    textColor=WHITE, alignment=1, leading=14)
    REASON_P   = ps("REASON_P",  fontSize=9, textColor=colors.HexColor("#444"),
                    leading=12)
    SEC_HDR    = ps("SEC_HDR",   fontName="Helvetica-Bold", fontSize=9,
                    textColor=NAVY,  leading=12)
    LBL        = ps("LBL",       fontName="Helvetica-Bold", fontSize=8,
                    textColor=NAVY,  leading=11)
    VAL        = ps("VAL",       fontSize=9,  leading=12)
    BODY       = ps("BODY",      fontSize=10, leading=14)
    RANK_PS    = ps("RANK_PS",   fontName="Helvetica-Bold", fontSize=10,
                    textColor=WHITE, alignment=1, leading=13)
    QQ         = ps("QQ",        fontName="Helvetica-Bold", fontSize=9,
                    textColor=colors.HexColor("#333"), leading=12)
    QA_PS      = ps("QA_PS",     fontSize=9,
                    textColor=colors.HexColor("#555"), leading=12, leftIndent=10,
                    spaceAfter=4)
    SOAP_LBL   = ps("SOAP_LBL",  fontName="Helvetica-Bold", fontSize=9,
                    textColor=NAVY, leading=12)
    SOAP_VAL   = ps("SOAP_VAL",  fontSize=9, leading=12)
    DISC       = ps("DISC",      fontSize=8.5, textColor=WFGC, leading=12)
    FOOTER     = ps("FOOTER",    fontSize=7.5, textColor=MUTED,
                    alignment=1, leading=10)

    # ── Helper: full-width section header with navy underline ─────────────────
    def section(title):
        t = Table([[Paragraph(title.upper(), SEC_HDR)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("LINEBELOW",     (0, 0), (-1, -1), 1.5, NAVY),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        return t

    # ── Escape helper (no emojis in Helvetica) ────────────────────────────────
    def e(s):
        return _html.escape(str(s)) if s else ""

    # ── Extract patient data ──────────────────────────────────────────────────
    name    = patient.get("name") or "Not provided"
    age     = patient.get("age")
    sex_raw = patient.get("sex")
    sex     = {"M": "Male", "F": "Female"}.get(sex_raw, "—") if sex_raw else "—"
    address = patient.get("address") or "—"
    status  = patient.get("status") or "Pending"
    bp         = patient.get("bp")
    temp       = patient.get("temperature")
    heart_rate = patient.get("heart_rate")
    spo2       = patient.get("spo2")
    tl      = patient.get("triage_level", "YELLOW")
    reason  = patient.get("triage_reason") or ""

    timestamp = patient.get("timestamp", datetime.utcnow())
    ts_str = timestamp.strftime("%b %d, %Y  %H:%M") if not isinstance(timestamp, str) else timestamp

    top_conds = patient.get("top_conditions", [])
    if isinstance(top_conds, str):
        try:    top_conds = json.loads(top_conds)
        except: top_conds = []
    _SKIP_CONDS = {"additional assessment needed", "n/a", "na", "unable to assess"}
    top_conds = [
        c for c in top_conds
        if c.get("condition", "").lower() not in _SKIP_CONDS
        and not _PLACEHOLDER_COND.match(c.get("condition", "").strip())
    ]

    fq_raw = patient.get("followup_qa", "{}")
    try:    fq = json.loads(fq_raw) if isinstance(fq_raw, str) else fq_raw
    except: fq = {}

    handoff = patient.get("soap_notes", "{}")
    if isinstance(handoff, str):
        try:    soap = json.loads(handoff)
        except: soap = {"S": handoff, "O": "—", "A": "—", "P": "—"}
    else:
        soap = handoff

    badge_color = BADGE.get(tl, BADGE["YELLOW"])

    # ── Build story ───────────────────────────────────────────────────────────
    story = []

    # 1. HEADER — full-width navy bar
    hdr = Table([
        [Paragraph("GEMMA — Doctor Handoff Summary", HDR_TITLE)],
        [Paragraph(
            "Guided Emergency &amp; Medical Management Assistant  |  "
            "Barangay Platero Health Center, City of Biñan", HDR_SUB)],
    ], colWidths=[W])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (0, 0),   12),
        ("BOTTOMPADDING", (0, 0), (0, 0),   3),
        ("TOPPADDING",    (0, 1), (0, 1),   1),
        ("BOTTOMPADDING", (0, 1), (0, 1),   11),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 0.4 * cm))

    # 2. TRIAGE BADGE — full-width, colour-coded
    badge = Table([
        [Paragraph(tl, BADGE_LVL)],
        [Paragraph(ACTION.get(tl, ""), BADGE_ACT)],
    ], colWidths=[W])
    badge.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), badge_color),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (0, 0),   14),
        ("BOTTOMPADDING", (0, 0), (0, 0),   4),
        ("TOPPADDING",    (0, 1), (0, 1),   2),
        ("BOTTOMPADDING", (0, 1), (0, 1),   12),
    ]))
    story.append(KeepTogether([badge]))
    if reason:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(e(reason), REASON_P))
    story.append(Spacer(1, 0.35 * cm))

    # 3. PATIENT INFORMATION — 4-column grid
    story.append(section("Patient Information"))
    story.append(Spacer(1, 0.2 * cm))

    L1 = W * 0.20   # label col
    V1 = W * 0.30   # value col

    info_tbl = Table([
        [Paragraph("Name",         LBL), Paragraph(e(name),  VAL),
         Paragraph("Age / Sex",    LBL), Paragraph(f"{age or '—'} y/o / {sex}", VAL)],
        [Paragraph("Address",      LBL), Paragraph(e(address), VAL),
         Paragraph("Date &amp; Time", LBL), Paragraph(e(ts_str), VAL)],
        [Paragraph("BHW on Duty",  LBL), Paragraph(e(bhw_name), VAL),
         Paragraph("Status",       LBL), Paragraph(e(status),   VAL)],
    ], colWidths=[L1, V1, L1, V1])
    info_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(info_tbl)

    # Vitals — up to 2 highlighted rows (BP+Temp, HR+SpO2)
    if bp or temp or heart_rate or spo2:
        story.append(Spacer(1, 0.15 * cm))
        v_rows = []
        if bp or temp:
            v_rows.append([
                Paragraph("Blood Pressure", LBL),
                Paragraph(f"{bp} mmHg" if bp else "—", VAL),
                Paragraph("Temperature",    LBL),
                Paragraph(f"{temp} °C" if temp else "—", VAL),
            ])
        if heart_rate or spo2:
            v_rows.append([
                Paragraph("Heart Rate",  LBL),
                Paragraph(f"{heart_rate} bpm" if heart_rate else "—", VAL),
                Paragraph("SpO2",        LBL),
                Paragraph(f"{spo2}%" if spo2 else "—", VAL),
            ])
        v_tbl = Table(v_rows, colWidths=[L1, V1, L1, V1])
        v_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("LINEABOVE",     (0, 0), (-1, 0),   0.5, NAVY),
            ("LINEBELOW",     (0, -1), (-1, -1), 0.5, NAVY),
            ("LINEBELOW",     (0, 0), (-1, 0),   0.3, colors.HexColor("#D0DCE8")),
        ]))
        story.append(v_tbl)
    story.append(Spacer(1, 0.3 * cm))

    # 4. CHIEF COMPLAINT — split into bullet lines for readability
    story.append(section("Chief Complaint"))
    story.append(Spacer(1, 0.2 * cm))
    complaint_text = patient.get("chief_complaint", "")
    # Split by newlines; if single line also split by "; " for multi-symptom entries
    complaint_lines = [l.strip() for l in complaint_text.split("\n") if l.strip()]
    if len(complaint_lines) == 1:
        complaint_lines = [l.strip() for l in complaint_lines[0].split(";") if l.strip()]
    bullet_style = ps("BULLET", fontSize=10, leading=14, leftIndent=12, firstLineIndent=-12)
    for line in complaint_lines:
        story.append(Paragraph(f"•  {e(line)}", bullet_style))
    story.append(Spacer(1, 0.3 * cm))

    # 5. TOP N POSSIBLE CONDITIONS
    if top_conds:
        story.append(section(f"Top {len(top_conds)} Possible Conditions"))
        story.append(Spacer(1, 0.2 * cm))
        RANK_W = 0.7 * cm
        COND_W = W - RANK_W
        for c in top_conds:
            cond_markup = f'<b>{e(c.get("condition", ""))}</b>'
            cond_style = ps(f"CN{c.get('rank','')}", leading=13, leftIndent=8)
            row_tbl = Table(
                [[Paragraph(str(c.get("rank", "")), RANK_PS),
                  Paragraph(cond_markup, cond_style)]],
                colWidths=[RANK_W, COND_W],
            )
            row_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (0, 0),   NAVY),
                ("BACKGROUND",    (1, 0), (1, 0),   LIGHT),
                ("ALIGN",         (0, 0), (0, 0),   "CENTER"),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (0, 0),   0),
                ("RIGHTPADDING",  (0, 0), (0, 0),   0),
                ("LEFTPADDING",   (1, 0), (1, 0),   0),
                ("RIGHTPADDING",  (1, 0), (1, 0),   6),
                ("LINEBELOW",     (0, 0), (-1, -1), 0.5, WHITE),
            ]))
            story.append(row_tbl)
        story.append(Spacer(1, 0.3 * cm))

    # 6. FOLLOW-UP Q&A
    if fq:
        story.append(section("Follow-Up Questions &amp; Answers"))
        story.append(Spacer(1, 0.2 * cm))
        for q, a in fq.items():
            story.append(Paragraph(f"Q: {e(q)}", QQ))
            story.append(Paragraph(f"A: {e(a)}", QA_PS))
        story.append(Spacer(1, 0.2 * cm))

    # 7. SOAP NOTE — keep header + table together so they never split across pages
    SOAP_L = 3.5 * cm
    SOAP_V = W - SOAP_L
    soap_tbl = Table([
        [Paragraph("S — Subjective", SOAP_LBL), Paragraph(e(soap.get("S", "")), SOAP_VAL)],
        [Paragraph("O — Objective",  SOAP_LBL), Paragraph(e(soap.get("O", "")), SOAP_VAL)],
        [Paragraph("A — Assessment", SOAP_LBL), Paragraph(e(soap.get("A", "")), SOAP_VAL)],
        [Paragraph("P — Plan",       SOAP_LBL), Paragraph(e(soap.get("P", "")), SOAP_VAL)],
    ], colWidths=[SOAP_L, SOAP_V])
    soap_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), LIGHT),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (0, -1),  7),
        ("LEFTPADDING",   (1, 0), (1, -1),  9),
        ("RIGHTPADDING",  (1, 0), (1, -1),  6),
        ("GRID",          (0, 0), (-1, -1), 0.5, GRID),
    ]))
    story.append(KeepTogether([
        section("SOAP Note (for Doctor)"),
        Spacer(1, 0.2 * cm),
        soap_tbl,
    ]))
    story.append(Spacer(1, 0.35 * cm))

    # 8. IMAGE FINDINGS (optional)
    image_findings = patient.get("image_findings")
    if image_findings:
        story.append(section("Image Findings (MedGemma AI)"))
        story.append(Spacer(1, 0.15 * cm))
        img_tbl = Table(
            [[Paragraph(e(image_findings), SOAP_VAL)]], colWidths=[W]
        )
        img_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBEFORE",    (0, 0), (0, -1),  3, NAVY),
        ]))
        story.append(img_tbl)
        story.append(Spacer(1, 0.3 * cm))

    # 9. ADDITIONAL CLINICAL NOTES (MedGemma — compact, one row per condition)
    valid_enrichments = [
        enr for enr in (enrichments or [])
        if enr.get("condition")
        and not _PLACEHOLDER_COND.match(enr.get("condition", "").strip())
        and enr.get("condition", "").lower() not in _SKIP_CONDS
    ]
    if valid_enrichments:
        ENRICH_LBL = ps("ENRICH_LBL", fontName="Helvetica-Bold", fontSize=7.5,
                        textColor=NAVY, leading=11)
        ENRICH_VAL = ps("ENRICH_VAL", fontSize=8, leading=12)
        ENRICH_HDR = ps("ENRICH_HDR", fontName="Helvetica-Bold", fontSize=9,
                        textColor=WHITE, leading=12)
        DANGER_PS  = ps("DANGER_PS",  fontSize=8, textColor=colors.HexColor("#C0392B"),
                        leading=12)

        story.append(KeepTogether([
            section("Additional Clinical Notes (MedGemma AI)"),
            Spacer(1, 0.15 * cm),
        ]))

        EL = 3.0 * cm
        EV = W - EL

        _NONE_VALS = {'none', 'n/a', 'na', 'not applicable', 'not available', '-', '—', 'nil'}

        def _enrich_val(raw: str) -> str:
            v = e(raw or "").strip()
            return "" if v.lower() in _NONE_VALS else v

        for enr in valid_enrichments:
            cond_name = e(enr.get("condition", ""))
            summary = _enrich_val(enr.get("clinical_summary") or enr.get("clinical_reasoning", ""))
            workup  = _enrich_val(enr.get("priority_workup")  or enr.get("suggested_workup", ""))
            flags   = _enrich_val(enr.get("red_flags", ""))

            hdr_tbl = Table([[Paragraph(cond_name, ENRICH_HDR)]], colWidths=[W])
            hdr_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))

            detail_rows = []
            if summary:
                detail_rows.append([Paragraph("Summary", ENRICH_LBL), Paragraph(summary, ENRICH_VAL)])
            if workup:
                detail_rows.append([Paragraph("Key Tests", ENRICH_LBL), Paragraph(workup, ENRICH_VAL)])
            if flags:
                detail_rows.append([Paragraph("Watch For", ENRICH_LBL), Paragraph(flags, DANGER_PS)])

            if detail_rows:
                detail_tbl = Table(detail_rows, colWidths=[EL, EV])
                detail_tbl.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (0, -1), LIGHT),
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING",   (0, 0), (0, -1),  7),
                    ("LEFTPADDING",   (1, 0), (1, -1),  8),
                    ("RIGHTPADDING",  (1, 0), (1, -1),  6),
                    ("GRID",          (0, 0), (-1, -1), 0.5, GRID),
                ]))
                story.append(KeepTogether([hdr_tbl, detail_tbl]))
                story.append(Spacer(1, 0.1 * cm))

        story.append(Spacer(1, 0.2 * cm))

    # 10. DISCLAIMER — full-width, yellow box, text wraps properly
    disc_tbl = Table([[Paragraph(
        "[!]  Para sa kaalaman ng BHW at doktor lamang. "
        "Hindi ito opisyal na medikal na rekord. "
        "Hindi kapalit ng klinikal na pagsusuri ng lisensyadong doktor.",
        DISC,
    )]], colWidths=[W])
    disc_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), WBGC),
        ("BOX",           (0, 0), (-1, -1), 0.75, WBRD),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(disc_tbl)
    story.append(Spacer(1, 0.3 * cm))

    # 10. FOOTER
    gen_time = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")
    story.append(Paragraph(
        f"Generated by GEMMA — Guided Emergency &amp; Medical Management Assistant  |  "
        f"Barangay Platero, City of Biñan  |  {gen_time}",
        FOOTER,
    ))

    doc.build(story)
