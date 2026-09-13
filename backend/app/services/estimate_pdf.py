"""
PDF Estimate Generation for Just Jon Handyman Services
Uses ReportLab. Layout mirrors the business's own "Work Estimate" template
(plain white header, simple 2-column charges table, disclaimer/signature
block at the bottom) rather than a generic invoice-style design.
"""
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

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
LIGHT_BG = colors.HexColor("#f0f0f0")
BORDER_COLOR = colors.HexColor("#999999")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "justjon_logo.png")

PHASE_ORDER = ["preplanning", "build", "finishing"]
PHASE_LABELS = {
    "preplanning": "Preplanning",
    "build": "The Build",
    "finishing": "Finishing",
}

SCAFFOLDING_LABELS = {
    "frame": "Frames (incl. crossers)",
    "crosser": "Crossers",
    "jack": "Jacks",
    "plank": "Planks",
}


def draw_header_footer(canvas, doc):
    """Draw the static company header and footer credit line on every page."""
    canvas.saveState()
    page_width, page_height = letter

    left_x = 0.5 * inch
    top_y = page_height - 0.6 * inch

    canvas.setFillColor(TEXT_COLOR)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(left_x, top_y, COMPANY_NAME)

    canvas.setFont("Helvetica", 9)
    canvas.drawString(left_x, top_y - 14, COMPANY_ADDRESS)
    canvas.drawString(left_x, top_y - 26, COMPANY_HST)
    canvas.drawString(left_x, top_y - 38, COMPANY_PHONE)
    canvas.drawString(left_x, top_y - 50, COMPANY_EMAIL)

    right_x = page_width - 0.5 * inch
    if os.path.exists(LOGO_PATH):
        try:
            canvas.drawImage(
                LOGO_PATH,
                right_x - 1.6 * inch,
                page_height - 1.5 * inch,
                width=1.6 * inch,
                height=1.15 * inch,
                preserveAspectRatio=True,
                anchor="n",
                mask="auto",
            )
        except Exception:
            _draw_logo_text(canvas, right_x, top_y)
    else:
        _draw_logo_text(canvas, right_x, top_y)

    # --- FOOTER: just the branding credit line, page by page ---
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#999999"))
    canvas.drawRightString(right_x, 0.35 * inch, "Powered by OBATEK")

    canvas.restoreState()


def _draw_logo_text(canvas, right_x, top_y):
    """Fallback: draw company name as styled text instead of logo image."""
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(ACCENT_COLOR)
    canvas.drawRightString(right_x, top_y - 10, "Just Jon")
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(right_x, top_y - 26, "Handyman Services")


def _amount_or_slash(value) -> str:
    """Charges table cells show '/' for an unused line instead of $0.00,
    matching the business's own template - every row is always listed."""
    return f"${value:,.2f}" if value and value > 0 else "/"


def generate_estimate_pdf(estimate: Estimate, customer_copy: bool = False) -> bytes:
    """Generate a PDF estimate and return it as bytes.

    customer_copy=True omits the internal Preplanning/Build/Finishing hour
    breakdown - that's the version meant to actually be sent to the client;
    the full version (customer_copy=False) is for internal use.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.5 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "EstimateTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=22,
        textColor=colors.black, spaceAfter=10,
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5,
        textColor=TEXT_COLOR, leading=15,
    )
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
    section_heading = ParagraphStyle(
        "SectionHeading", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10.5,
        textColor=colors.black, spaceAfter=4, spaceBefore=10,
    )
    phase_heading = ParagraphStyle(
        "PhaseHeading", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9.5,
        textColor=ACCENT_COLOR, spaceAfter=4, spaceBefore=8,
    )
    scope_style = ParagraphStyle(
        "ScopeText", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=TEXT_COLOR, leading=14, spaceAfter=8,
    )
    duration_style = ParagraphStyle(
        "Duration", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5,
        textColor=TEXT_COLOR, leading=13, spaceBefore=4, spaceAfter=4,
    )
    footer_note_style = ParagraphStyle(
        "FooterNote", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8.5,
        textColor=TEXT_COLOR, leading=13, alignment=TA_LEFT,
    )
    change_order_style = ParagraphStyle(
        "ChangeOrder", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8.5,
        textColor=TEXT_COLOR, leading=13, spaceBefore=10,
    )
    signature_style = ParagraphStyle(
        "Signature", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5,
        textColor=TEXT_COLOR, leading=20, spaceBefore=6,
    )

    # ==============================
    # 1. TITLE + ESTIMATE META
    # ==============================
    elements.append(Paragraph("Work Estimate", title_style))

    if estimate.client:
        name = estimate.client.name
        address = estimate.client.address
        phone = estimate.client.phone_number
    else:
        name = estimate.client_name_override
        address = estimate.address_override
        phone = None

    meta_lines = [
        f"Estimate No: {estimate.estimate_number}",
        f"Estimate Date: {estimate.created_date.strftime('%B %d, %Y')}",
    ]
    if name:
        meta_lines.append(f"Client: {name}")
    if address:
        meta_lines.append(f"Address: {address.replace(chr(10), ', ')}")
    if phone:
        meta_lines.append(f"Phone: {phone}")

    elements.append(Paragraph("<br/>".join(meta_lines), meta_style))
    elements.append(Spacer(1, 0.2 * inch))

    # ==============================
    # 2. SCOPE OF WORK
    # ==============================
    if estimate.scope_of_work:
        elements.append(Paragraph("Scope of Work", section_heading))
        elements.append(Paragraph(estimate.scope_of_work, scope_style))

    # ==============================
    # 3. ESTIMATED DURATION
    # ==============================
    if estimate.travel_days > 0:
        day_word = "Day" if estimate.travel_days == 1 else "Days"
        elements.append(Paragraph(
            f"<b>Estimated Duration to Complete:</b> {estimate.travel_days} {day_word}",
            duration_style,
        ))

    # ==============================
    # 4. HOUR BREAKDOWN (internal copy only)
    # ==============================
    tasks_by_phase: dict = {phase: [] for phase in PHASE_ORDER}
    for task in sorted(estimate.tasks, key=lambda t: (t.phase, t.sort_order)):
        if task.phase in tasks_by_phase:
            tasks_by_phase[task.phase].append(task)

    if not customer_copy and any(tasks_by_phase.values()):
        elements.append(Paragraph("Hour Breakdown", section_heading))

        for phase in PHASE_ORDER:
            phase_tasks = tasks_by_phase[phase]
            if not phase_tasks:
                continue

            elements.append(Paragraph(PHASE_LABELS[phase], phase_heading))

            phase_data = [["Task", "Hours", ""]]
            for task in phase_tasks:
                tags = []
                if task.uses_heavy_equipment:
                    tags.append("Heavy equipment")
                if task.uses_redseal:
                    tags.append("Red Seal")
                phase_data.append([task.description, f"{task.hours:g}", ", ".join(tags)])

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
    # 5. CHARGES TABLE
    # ==============================
    scaffolding_total = sum(
        (row.rate_per_day * row.quantity for row in estimate.scaffolding_rows), 0
    ) * estimate.travel_days

    charges_rows = [
        ("Labour", estimate.labour_amount),
        ("Kms", estimate.travel_amount),
        ("Materials (before tax)", estimate.materials_amount),
        ("Scaffolding", scaffolding_total),
        ("Tooling / Supplies", estimate.tooling_amount),
        ("Heavy Equipment", estimate.heavy_equipment_amount),
        ("Red Seal Trades", estimate.redseal_amount),
        ("Rental", estimate.rental_amount),
        ("Fuel", estimate.fuel_amount),
        ("Dump Fee", estimate.dump_fee),
        ("Admin Fee", estimate.admin_amount),
        ("Permit Fee", estimate.permits_fee),
        ("Engineering Fee", estimate.engineering_fee),
    ]

    charges_data = [["Description", "Amount ($)"]]
    for label, value in charges_rows:
        charges_data.append([label, _amount_or_slash(value)])

    charges_data.append(["Subtotal", f"${estimate.subtotal:,.2f}"])
    if estimate.include_hst:
        charges_data.append(["Total with HST (13%)", f"${estimate.total:,.2f}"])
    else:
        charges_data.append(["Total", f"${estimate.total:,.2f}"])

    t_charges = Table(charges_data, colWidths=[5.0 * inch, 2.0 * inch])
    t_charges.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_COLOR),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
    ]))
    elements.append(t_charges)
    elements.append(Spacer(1, 0.25 * inch))

    # ==============================
    # 6. NOTES
    # ==============================
    if estimate.notes:
        elements.append(Paragraph("<b>Notes</b>", label_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(estimate.notes, value_style))
        elements.append(Spacer(1, 0.15 * inch))

    # ==============================
    # 7. DISCLAIMER + CHANGE ORDER + SIGNATURES
    # ==============================
    elements.append(Paragraph(
        "This estimate is an approximation and is not guaranteed.<br/>"
        "The estimate is based on information provided from the client regarding project requirements.<br/>"
        "Actual cost may change once all project elements are finalized or negotiated.<br/>"
        "Billable hours are invoiced at end of working week. Estimate valid for 30 days.",
        footer_note_style,
    ))
    elements.append(Paragraph(
        "Work requested beyond the Scope of Work will be treated as a change order at the "
        "listed labour rate + materials + travel.",
        change_order_style,
    ))
    elements.append(Paragraph(
        "Customer Approval: _________________________ &nbsp;&nbsp;&nbsp;Date: ____________",
        signature_style,
    ))
    elements.append(Paragraph(
        "Authorized Signature: _________________________ &nbsp;&nbsp;&nbsp;Date: ____________",
        signature_style,
    ))

    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    buffer.seek(0)
    return buffer.getvalue()
