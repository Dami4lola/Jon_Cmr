"""
Invoice API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
from decimal import Decimal

from ..models import Invoice, Job, Client
from ..schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceStatusUpdate
from ..schemas.job import JobBrief
from ..schemas.client import ClientBrief
from ..services.invoice_pdf import generate_invoice_pdf
from .deps import DBSession, ManagerUser

router = APIRouter()


def invoice_to_response(invoice: Invoice, job: Job, client: Client) -> InvoiceResponse:
    """Convert Invoice model to response schema"""
    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        created_date=invoice.created_date,
        due_date=invoice.due_date,
        subtotal=invoice.subtotal,
        hst_amount=invoice.hst_amount,
        total=invoice.total,
        status=invoice.status,
        notes=invoice.notes,
        job=JobBrief(
            id=job.id,
            description=job.description,
            client_name=client.name,
            start_date=job.start_date,
            end_date=job.end_date,
        ),
        client=ClientBrief(
            id=client.id,
            name=client.name,
            phone_number=client.phone_number,
            address=client.address,
        ),
    )


def generate_invoice_number(session) -> str:
    """Generate unique invoice number: INV-YYYY-NNNN"""
    year = date.today().year
    prefix = f"INV-{year}-"

    # Find last invoice number for this year
    statement = (
        select(Invoice)
        .where(Invoice.invoice_number.startswith(prefix))
        .order_by(Invoice.invoice_number.desc())
    )
    last_invoice = session.exec(statement).first()

    if last_invoice:
        last_num = int(last_invoice.invoice_number.split("-")[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f"{prefix}{new_num:04d}"


@router.get("/", response_model=list[InvoiceResponse])
def list_invoices(
    session: DBSession,
    current_user: ManagerUser,
    status_filter: str | None = None,
):
    """List all invoices (manager only)"""
    statement = (
        select(Invoice)
        .options(selectinload(Invoice.job).selectinload(Job.client))
    )

    if status_filter:
        statement = statement.where(Invoice.status == status_filter)

    statement = statement.order_by(Invoice.created_date.desc())
    invoices = session.exec(statement).all()

    return [
        invoice_to_response(inv, inv.job, inv.job.client)
        for inv in invoices
    ]


@router.post("/job/{job_id}", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
    data: InvoiceCreate | None = None,
):
    """Create an invoice for a job (manager only)"""
    # Get job with client
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client), selectinload(Job.invoice))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Check if invoice already exists
    if job.invoice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice {job.invoice.invoice_number} already exists for this job",
        )

    # Calculate amounts
    subtotal = job.estimate_amount or Decimal("0.00")
    hst_amount = subtotal * Decimal("0.13")
    total = subtotal + hst_amount

    # Create invoice
    invoice = Invoice(
        job_id=job_id,
        invoice_number=generate_invoice_number(session),
        subtotal=subtotal,
        hst_amount=hst_amount,
        total=total,
        due_date=date.today() + timedelta(days=30),
        notes=data.notes if data else "Payment due within 30 days.",
    )

    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    return invoice_to_response(invoice, job, job.client)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Get a specific invoice (manager only)"""
    statement = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.job).selectinload(Job.client))
    )
    invoice = session.exec(statement).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    return invoice_to_response(invoice, invoice.job, invoice.job.client)


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    session: DBSession,
    current_user: ManagerUser,
    inline: bool = False,
):
    """Download invoice as PDF (manager only)"""
    statement = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.job).selectinload(Job.client))
    )
    invoice = session.exec(statement).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Generate PDF
    pdf_content = generate_invoice_pdf(invoice, invoice.job, invoice.job.client)

    # Set disposition (inline for browser view, attachment for download)
    disposition = "inline" if inline else "attachment"
    filename = f"Invoice_{invoice.invoice_number}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"'
        },
    )


@router.put("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(
    invoice_id: int,
    data: InvoiceStatusUpdate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Update invoice status (manager only)"""
    statement = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.job).selectinload(Job.client))
    )
    invoice = session.exec(statement).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Validate status
    valid_statuses = ["draft", "sent", "paid", "overdue"]
    if data.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )

    invoice.status = data.status
    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    return invoice_to_response(invoice, invoice.job, invoice.job.client)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Delete an invoice (manager only)"""
    invoice = session.get(Invoice, invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    session.delete(invoice)
    session.commit()
