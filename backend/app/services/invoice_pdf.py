"""
PDF Invoice Generation for Just Jon Handyman Services
Uses ReportLab to generate professional invoices
"""
import os
from io import BytesIO
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from ..models import Invoice, Job, Client

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


def draw_header_footer(canvas, doc):
    """Draw static header and footer on every page."""
    canvas.saveState()
    page_width, page_height = letter

    # --- HEADER ---
    header_height = 1.4 * inch
    canvas.setFillColor(THEME_COLOR)
    canvas.rect(0, page_height - header_height, page_width, header_height, fill=1, stroke=0)

    # Left side: Company info
    canvas.setFillColor(colors.white)
    left_x = 0.5 * inch
    top_y = page_height - 0.35 * inch

    canvas.setFont("Helvetica-Bold", 24)
    canvas.drawString(left_x, top_y, "INVOICE")

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(left_x, top_y - 24, COMPANY_NAME)

    canvas.setFont("Helvetica", 9)
    canvas.drawString(left_x, top_y - 38, COMPANY_ADDRESS)
    canvas.drawString(left_x, top_y - 50, COMPANY_HST)
    canvas.drawString(left_x, top_y - 62, f"{COMPANY_PHONE}  |  {COMPANY_EMAIL}")

    # Right side: Logo or text fallback
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
    canvas.drawString(0.5 * inch, y, f"E-transfer to {COMPANY_EMAIL} or cheque payable to {COMPANY_NAME}")
    canvas.drawString(0.5 * inch, y - 12, "Total payable upon receipt. Overdue accounts subject to 2% monthly interest.")

    # Powered by OBATEK (bottom right)
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


def generate_invoice_pdf(invoice: Invoice, job: Job, client: Client, timesheets: list | None = None) -> bytes:
    """Generate a PDF invoice and return it as bytes."""
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
    scope_style = ParagraphStyle(
        "ScopeText", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=TEXT_COLOR, leading=14, spaceAfter=12,
    )

    # ==============================
    # 1. INVOICE META & BILL TO
    # ==============================
    inv_data = [
        [Paragraph("Invoice No.", label_style), Paragraph(str(invoice.invoice_number), value_style)],
        [Paragraph("Date", label_style), Paragraph(invoice.created_date.strftime("%B %d, %Y"), value_style)],
    ]

    t_left = Table(inv_data, colWidths=[1.0 * inch, 2.2 * inch])
    t_left.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    address_parts = [client.name]
    if client.address:
        address_parts.extend(client.address.split("\n"))

    bill_to_flowables = [Paragraph("<b>Bill To</b>", bill_to_header)]
    for part in address_parts:
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
    if invoice.scope_of_work:
        elements.append(Paragraph("SCOPE OF WORK", section_heading))
        elements.append(Paragraph(invoice.scope_of_work, scope_style))
        elements.append(Spacer(1, 0.1 * inch))

    # ==============================
    # 3. CHARGES SUMMARY TABLE
    # ==============================
    elements.append(Paragraph("CHARGES SUMMARY", section_heading))

    charges_header = ["Description", "Detail", "Amount"]
    charges_data = [charges_header]

    charges_data.append(["Labour", "", f"${invoice.labour_amount:,.2f}"])

    km_display = f"{invoice.total_distance_km:,.0f} km @ $2.00/km"
    charges_data.append(["Travel", km_display, f"${invoice.travel_amount:,.2f}"])

    charges_data.append(["Materials (before tax)", "", f"${invoice.materials_amount:,.2f}"])

    if invoice.inventory_materials > 0:
        charges_data.append(["Inventory Materials Used", "", f"${invoice.inventory_materials:,.2f}"])

    if invoice.dump_fee > 0:
        charges_data.append(["Dump Fee", "", f"${invoice.dump_fee:,.2f}"])

    if invoice.admin_fee > 0:
        charges_data.append(["Admin Fee", "", f"${invoice.admin_fee:,.2f}"])

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
    # 4. RECEIPTS SECTION
    # ==============================
    if timesheets:
        all_receipts = [
            (receipt, ts)
            for ts in timesheets
            for receipt in (ts.receipts or [])
        ]
        if all_receipts:
            elements.append(Paragraph("RECEIPTS", section_heading))

            receipt_header = ["Worker", "Date", "Description", "Amount"]
            receipt_data = [receipt_header]
            receipt_subtotal = Decimal("0")

            for receipt, ts in all_receipts:
                worker_name = ts.worker.name if ts.worker else "Unknown"
                date_str = ts.date.strftime("%b %d, %Y") if ts.date else ""
                description = receipt.description or ""
                amount_str = f"${receipt.amount:,.2f}" if receipt.amount is not None else "—"
                if receipt.amount is not None:
                    receipt_subtotal += receipt.amount
                receipt_data.append([worker_name, date_str, description, amount_str])

            receipt_data.append(["", "", "Receipt Subtotal", f"${receipt_subtotal:,.2f}"])

            r_col_widths = [1.8 * inch, 1.2 * inch, 2.7 * inch, 1.8 * inch]
            t_receipts = Table(receipt_data, colWidths=r_col_widths)

            receipt_style = [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_COLOR),
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("LINEBELOW", (0, 0), (-1, 0), 1, BORDER_COLOR),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (0, -1), 6),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, BORDER_COLOR),
            ]
            for i in range(1, len(receipt_data) - 1):
                if i % 2 == 0:
                    receipt_style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_BG))

            t_receipts.setStyle(TableStyle(receipt_style))
            elements.append(t_receipts)
            elements.append(Spacer(1, 0.2 * inch))

    # ==============================
    # 5. TOTALS
    # ==============================
    totals_data = [
        ["Subtotal", f"${invoice.subtotal:,.2f}"],
        [f"HST (13%) - {COMPANY_HST}", f"${invoice.hst_amount:,.2f}"],
        ["Total Due", f"${invoice.total:,.2f}"],
    ]

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
    # 5. NOTES
    # ==============================
    if invoice.notes:
        elements.append(Paragraph("<b>Notes</b>", label_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(invoice.notes, value_style))

    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    buffer.seek(0)
    return buffer.getvalue()
