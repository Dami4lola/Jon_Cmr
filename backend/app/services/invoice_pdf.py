"""
PDF Invoice Generation for OBATEK - Ported from Django
Uses ReportLab to generate professional invoices
"""
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from ..models import Invoice, Job, Client

# Theme Configuration (Matches the blue theme)
THEME_COLOR = colors.HexColor("#2c5f78")  # Muted Teal/Blue
TEXT_COLOR = colors.HexColor("#333333")
ALT_ROW_COLOR = colors.HexColor("#f2f2f2")  # Light Gray for banding


def draw_header_footer(canvas, doc):
    """
    Draws the static background elements (Blue Header/Footer bars)
    that stay consistent on every page.
    """
    canvas.saveState()

    # --- Header Blue Bar ---
    header_height = 1.2 * inch
    canvas.setFillColor(THEME_COLOR)
    canvas.rect(0, letter[1] - header_height, letter[0], header_height, fill=1, stroke=0)

    # --- Header Text (White) ---
    canvas.setFillColor(colors.white)

    # "INVOICE" Title (Left)
    canvas.setFont("Helvetica", 32)
    canvas.drawString(0.5 * inch, letter[1] - 0.8 * inch, "INVOICE")

    # Company Info (Right)
    canvas.setFont("Helvetica-Bold", 12)
    right_margin = letter[0] - 0.5 * inch
    top_text_y = letter[1] - 0.4 * inch

    canvas.drawRightString(right_margin, top_text_y, "OBATEK")

    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(right_margin, top_text_y - 14, "Professional Services")
    canvas.drawRightString(right_margin, top_text_y - 28, "Ottawa, Ontario")
    canvas.drawRightString(right_margin, top_text_y - 42, "contact@obatek.com")

    # --- Footer Blue Bar ---
    footer_height = 0.6 * inch
    canvas.setFillColor(THEME_COLOR)
    canvas.rect(0, 0, letter[0], footer_height, fill=1, stroke=0)

    # Footer Text
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawCentredString(letter[0] / 2, 0.25 * inch, "Thank you for your business!")

    canvas.restoreState()


def generate_invoice_pdf(invoice: Invoice, job: Job, client: Client) -> bytes:
    """
    Generate a PDF invoice and return it as bytes
    """
    buffer = BytesIO()

    # Increase top margin to avoid overlapping with our custom header
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

    # --- Styles ---
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=TEXT_COLOR,
        leading=14,
    )

    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=TEXT_COLOR,
        leading=14,
    )

    bill_to_header_style = ParagraphStyle(
        "BillToHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=TEXT_COLOR,
    )

    bill_to_text_style = ParagraphStyle(
        "BillToText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=TEXT_COLOR,
        leading=14,
    )

    # ==============================
    # 1. TOP SECTION (Invoice Meta & Bill To)
    # ==============================

    # Left Side: Invoice Details
    inv_data = [
        [
            Paragraph("Invoice No.", label_style),
            Paragraph(str(invoice.invoice_number), value_style),
        ],
        [
            Paragraph("Date of Issue", label_style),
            Paragraph(invoice.created_date.strftime("%B %d, %Y"), value_style),
        ],
        [
            Paragraph("Due Date", label_style),
            Paragraph(
                invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "Upon Receipt",
                value_style,
            ),
        ],
    ]

    t_left = Table(inv_data, colWidths=[1.2 * inch, 2 * inch])
    t_left.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    # Right Side: Bill To
    address_parts = [client.name]
    if client.address:
        address_parts.extend(client.address.split("\n"))

    bill_to_flowables = [Paragraph("<b>Bill To</b>", bill_to_header_style)]
    for part in address_parts:
        bill_to_flowables.append(Paragraph(part, bill_to_text_style))

    # Master Table to hold Left and Right side by side
    top_table_data = [[t_left, bill_to_flowables]]
    t_top = Table(top_table_data, colWidths=[3.75 * inch, 3.75 * inch])
    t_top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )

    elements.append(t_top)
    elements.append(Spacer(1, 0.5 * inch))

    # ==============================
    # 2. PRICING TABLE
    # ==============================

    headers = ["Item", "Description", "Hours", "Rate", "Amount"]
    data = [headers]

    # Row 1 (The Job)
    data.append(
        [
            "1",
            job.description[:80] + "..." if len(job.description) > 80 else job.description,
            "-",
            "-",
            f"${invoice.subtotal:,.2f}",
        ]
    )

    col_widths = [0.6 * inch, 3.4 * inch, 0.8 * inch, 1.0 * inch, 1.7 * inch]
    t_pricing = Table(data, colWidths=col_widths)

    pricing_style = [
        # Header Row Styling
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_COLOR),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEXT_COLOR),
        ("LINEABOVE", (0, 0), (-1, 0), 1, TEXT_COLOR),
        # General Alignment
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        # Row Padding
        ("TOPPADDING", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
    ]

    # Zebra Striping
    for i in range(1, len(data)):
        bg_color = colors.white if i % 2 == 0 else ALT_ROW_COLOR
        pricing_style.append(("BACKGROUND", (0, i), (-1, i), bg_color))

    t_pricing.setStyle(TableStyle(pricing_style))
    elements.append(t_pricing)

    elements.append(Spacer(1, 0.2 * inch))

    # ==============================
    # 3. TOTALS SECTION
    # ==============================

    totals_data = [
        ["Subtotal", f"${invoice.subtotal:,.2f}"],
        ["Discount", "$0.00"],
        ["HST (13%)", f"${invoice.hst_amount:,.2f}"],
        ["Total", f"${invoice.total:,.2f}"],
    ]

    t_totals = Table(totals_data, colWidths=[1.5 * inch, 1.7 * inch])
    t_totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT_COLOR),
                # Bold and Highlight the Final Total
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (1, -1), (1, -1), colors.HexColor("#d9edf7")),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )

    # Align totals to the far right
    totals_wrapper = Table([[None, t_totals]], colWidths=[4.3 * inch, 3.2 * inch])
    elements.append(totals_wrapper)

    elements.append(Spacer(1, 0.5 * inch))

    # ==============================
    # 4. NOTES (Optional)
    # ==============================
    if invoice.notes:
        elements.append(Paragraph("<b>Notes:</b>", styles["Normal"]))
        elements.append(Paragraph(invoice.notes, styles["Normal"]))

    # Build PDF with the custom header/footer callback
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    buffer.seek(0)
    return buffer.getvalue()
