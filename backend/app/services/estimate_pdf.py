"""
PDF Estimate Generation for Just Jon Handyman Services
Uses ReportLab, structurally mirroring invoice_pdf.py's layout.
"""
import math
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from ..models import Estimate

# Company info
COMPANY_NAME = "Just Jon Industries INC."
COMPANY_ADDRESS = "867 Brooke Valley Road, Perth, ON"
COMPANY_HST = "HST# 709114680RT0001"
COMPANY_PHONE = "613-200-9362"
COMPANY_EMAIL = "justjonindustries@gmail.com"

# Theme
THEME_COLOR = colors.HexColor("#1a1a2e")
ACCENT_COLOR = colors.HexColor("#2c5f78")
TEXT_COLOR = colors.HexColor("#333333")
LIGHT_BG = colors.HexColor("#f8f9fa")
BORDER_COLOR = colors.HexColor("#dee2e6")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "justjon_logo.png")

PHASE_ORDER = ["preplanning", "build", "finishing"]
PHASE_LABELS = {
    "preplanning": "Preplanning",
    "build": "The Build",
    "finishing": "Finishing",
}


def draw_header_footer(canvas, doc):
    """Draw static header and footer on every page."""
    canvas.saveState()
    page_width, page_height = letter

    # --- HEADER ---
    header_height = 1.4 * inch
    canvas.setFillColor(THEME_COLOR)
    canvas.rect(0, page_height - header_height, page_width, header_height, fill=1, stroke=0)

    left_x = 0.5 * inch
    top_y = page_height - 0.35 * inch

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 24)
    canvas.drawString(left_x, top_y, "ESTIMATE")

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(left_x, top_y - 24, COMPANY_NAME)

    canvas.setFont("Helvetica", 9)
    canvas.drawString(left_x, top_y - 38, COMPANY_ADDRESS)
    canvas.drawString(left_x, top_y - 50, COMPANY_HST)
    canvas.drawString(left_x, top_y - 62, f"{COMPANY_PHONE}  |  {COMPANY_EMAIL}")

    right_x = page_width - 0.5 * inch
    if os.path.exists(LOGO_PATH):
        try:
            canvas.drawImage(
                LOGO_PATH,
                right_x - 1.8 * inch,
                page_height - header_height + 0.2 * inch,
                width=1.8 * inch,
                height=1.0 * inch,
                preserveAspectRatio=True,
                anchor="sw",
                mask="auto",
            )
        except Exception:
            _draw_logo_text(canvas, right_x, top_y)
    else:
        _draw_logo_text(canvas, right_x, top_y)

    # --- FOOTER ---
    footer_top = 0.85 * inch
    canvas.setStrokeColor(BORDER_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(0.5 * inch, footer_top, page_width - 0.5 * inch, footer_top)

    canvas.setFillColor(TEXT_COLOR)
    canvas.setFont("Helvetica", 8)
    y = footer_top - 14
    canvas.drawString(0.5 * inch, y, "This estimate is valid for 30 days from the date above.")
    canvas.drawString(0.5 * inch, y - 12, "Final pricing may be adjusted after an on-site assessment.")

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#999999"))
    canvas.drawRightString(right_x, 0.3 * inch, "Powered by OBATEK")

    canvas.restoreState()


def _draw_logo_text(canvas, right_x, top_y):
    """Fallback: draw company name as styled text instead of logo image."""
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(colors.white)
    canvas.drawRightString(right_x, top_y - 10, "Just Jon")
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(right_x, top_y - 26, "Handyman Services")


def generate_estimate_pdf(estimate: Estimate) -> bytes:
    """Generate a PDF estimate and return it as bytes."""
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.7 * inch,
        bottomMargin=1.1 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
    )

    elements = []
    styles = getSampleStyleSheet()

    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9,
        textColor=TEXT_COLOR, leading=13,
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=TEXT_COLOR, leading=13,
    )
    bill_to_header = ParagraphStyle(
        "BillToHeader", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9,
        alignment=TA_RIGHT, textColor=TEXT_COLOR,
    )
    bill_to_text = ParagraphStyle(
        "BillToText", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9,
        alignment=TA_RIGHT, textColor=TEXT_COLOR, leading=13,
    )
    section_heading = ParagraphStyle(
        "SectionHeading", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=11,
        textColor=THEME_COLOR, spaceAfter=6, spaceBefore=12,
    )
    phase_heading = ParagraphStyle(
        "PhaseHeading", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9.5,
        textColor=ACCENT_COLOR, spaceAfter=4, spaceBefore=8,
    )
    scope_style = ParagraphStyle(
        "ScopeText", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=TEXT_COLOR, leading=14, spaceAfter=12,
    )

    # ==============================
    # 1. ESTIMATE META & BILL TO
    # ==============================
    est_data = [
        [Paragraph("Estimate No.", label_style), Paragraph(str(estimate.estimate_number), value_style)],
        [Paragraph("Date", label_style), Paragraph(estimate.created_date.strftime("%B %d, %Y"), value_style)],
    ]

    t_left = Table(est_data, colWidths=[1.0 * inch, 2.2 * inch])
    t_left.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    if estimate.client:
        name = estimate.client.name
        address = estimate.client.address
    else:
        name = estimate.client_name_override
        address = estimate.address_override

    bill_to_flowables = [Paragraph("<b>For</b>", bill_to_header)]
    if name:
        bill_to_flowables.append(Paragraph(name, bill_to_text))
    if address:
        for part in address.split("\n"):
            bill_to_flowables.append(Paragraph(part, bill_to_text))

    top_table_data = [[t_left, bill_to_flowables]]
    t_top = Table(top_table_data, colWidths=[3.75 * inch, 3.75 * inch])
    t_top.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))

    elements.append(t_top)
    elements.append(Spacer(1, 0.3 * inch))

    # ==============================
    # 2. SCOPE OF WORK
    # ==============================
    if estimate.scope_of_work:
        elements.append(Paragraph("SCOPE OF WORK", section_heading))
        elements.append(Paragraph(estimate.scope_of_work, scope_style))
        elements.append(Spacer(1, 0.1 * inch))

    # ==============================
    # 3. HOUR BREAKDOWN
    # ==============================
    tasks_by_phase: dict = {phase: [] for phase in PHASE_ORDER}
    for task in sorted(estimate.tasks, key=lambda t: (t.phase, t.sort_order)):
        if task.phase in tasks_by_phase:
            tasks_by_phase[task.phase].append(task)

    if any(tasks_by_phase.values()):
        elements.append(Paragraph("HOUR BREAKDOWN", section_heading))

        for phase in PHASE_ORDER:
            phase_tasks = tasks_by_phase[phase]
            if not phase_tasks:
                continue

            elements.append(Paragraph(PHASE_LABELS[phase], phase_heading))

            phase_data = [["Task", "Hours", ""]]
            for task in phase_tasks:
                phase_data.append([
                    task.description,
                    f"{task.hours:g}",
                    "Heavy equipment" if task.uses_heavy_equipment else "",
                ])

            t_phase = Table(phase_data, colWidths=[4.2 * inch, 0.8 * inch, 2.5 * inch])
            t_phase.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_COLOR),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (0, -1), 6),
            ]))
            elements.append(t_phase)
            elements.append(Spacer(1, 0.1 * inch))

        elements.append(Spacer(1, 0.1 * inch))

    # ==============================
    # 4. CHARGES SUMMARY TABLE
    # ==============================
    elements.append(Paragraph("CHARGES SUMMARY", section_heading))

    charges_header = ["Description", "Detail", "Amount"]
    charges_data = [charges_header]

    charges_data.append(["Days", "", f"{estimate.travel_days}"])
    charges_data.append(["Labour", f"{estimate.total_hours:g} hrs x {estimate.crew_size} techs", f"${estimate.labour_amount:,.2f}"])

    if estimate.distance_km is not None:
        km_display = f"{estimate.distance_km:,.0f} km @ ${estimate.km_rate:,.2f}/km x {estimate.travel_days} day(s)"
    else:
        km_display = ""
    charges_data.append(["Km fee", km_display, f"${estimate.travel_amount:,.2f}"])

    charges_data.append(["Materials (before tax)", "", f"${estimate.materials_amount:,.2f}"])

    if estimate.heavy_equipment_amount > 0:
        charges_data.append(["Heavy equipment", "", f"${estimate.heavy_equipment_amount:,.2f}"])

    if estimate.redseal_amount > 0:
        charges_data.append(["Red seal trades", "", f"${estimate.redseal_amount:,.2f}"])

    if estimate.rental_amount > 0:
        charges_data.append(["Rental", "", f"${estimate.rental_amount:,.2f}"])

    if estimate.fuel_amount > 0:
        charges_data.append(["Fuel", "", f"${estimate.fuel_amount:,.2f}"])

    if estimate.dump_fee > 0:
        charges_data.append(["Dump fee", "", f"${estimate.dump_fee:,.2f}"])

    if estimate.include_admin_fee and estimate.admin_amount > 0:
        admin_periods = math.ceil(estimate.travel_days / 7) if estimate.travel_days > 0 else 0
        admin_detail = f"${estimate.admin_fee:,.2f} x {admin_periods}" if admin_periods > 1 else ""
        charges_data.append(["Admin fee", admin_detail, f"${estimate.admin_amount:,.2f}"])

    if estimate.permits_fee > 0:
        charges_data.append(["Permits fee", "", f"${estimate.permits_fee:,.2f}"])

    col_widths = [2.8 * inch, 2.4 * inch, 2.3 * inch]
    t_charges = Table(charges_data, colWidths=col_widths)

    charges_style = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_COLOR),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 1, BORDER_COLOR),
        ("LINEBELOW", (0, -1), (-1, -1), 1, BORDER_COLOR),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
    ]

    for i in range(1, len(charges_data)):
        if i % 2 == 0:
            charges_style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_BG))

    t_charges.setStyle(TableStyle(charges_style))
    elements.append(t_charges)
    elements.append(Spacer(1, 0.2 * inch))

    # ==============================
    # 5. TOTALS
    # ==============================
    totals_data = [
        ["Hours", f"{estimate.total_hours:g}"],
        ["Subtotal", f"${estimate.subtotal:,.2f}"],
    ]
    if estimate.include_hst:
        totals_data.append([f"HST (13%) - {COMPANY_HST}", f"${estimate.hst_amount:,.2f}"])
    totals_data.append(["Total after taxes" if estimate.include_hst else "Total", f"${estimate.total:,.2f}"])

    t_totals = Table(totals_data, colWidths=[2.5 * inch, 1.5 * inch])
    t_totals.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, THEME_COLOR),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), THEME_COLOR),
        ("TOPPADDING", (0, -1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
    ]))

    totals_wrapper = Table([[None, t_totals]], colWidths=[3.5 * inch, 4.0 * inch])
    elements.append(totals_wrapper)
    elements.append(Spacer(1, 0.3 * inch))

    # ==============================
    # 6. NOTES
    # ==============================
    if estimate.notes:
        elements.append(Paragraph("<b>Notes</b>", label_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(estimate.notes, value_style))

    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    buffer.seek(0)
    return buffer.getvalue()
