"""
Invoice API endpoints
"""
import logging
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)
from fastapi.responses import Response
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ..models import Invoice, Job, Client, Timesheet
from ..schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoicePreview,
    InvoiceStatusUpdate,
)
from ..schemas.job import JobBrief
from ..schemas.client import ClientBrief
from ..services.invoice_pdf import generate_invoice_pdf
from .deps import DBSession, ManagerUser

router = APIRouter()

MILEAGE_RATE = Decimal("1.00")
MINIMUM_HOURS = Decimal("4.0")
LABOUR_RATE = Decimal("80.00")  # $80/hr per tech for invoicing
REDSEAL_RATE = Decimal("100.00")  # $100/hr for Red Seal trades (plumbing, etc.)
HST_RATE = Decimal("0.13")


def _round_hours(hours_worked: Decimal, break_duration: Decimal = Decimal("0"), minimum_hours: Decimal = MINIMUM_HOURS) -> Decimal:
    hours_float = float(hours_worked)
    break_float = float(break_duration)
    rounded = (round(hours_float * 4) / 4) - break_float
    billable = Decimal(str(max(rounded, 0)))
    return max(billable, minimum_hours)


def _calculate_invoice_amounts(session, job: Job, data: InvoiceCreate | None):
    """
    Auto-calculate all invoice line items from job timesheet data.
    - Labour hours: sum of hours_worked from timesheets (rounded, 4hr min per timesheet)
    - Labour amount: billable hours × worker hourly rate
    - Materials: sum of personal_materials from timesheets
    - Inventory materials: sum of company_materials from timesheets
    """
    timesheets = session.exec(
        select(Timesheet)
        .where(Timesheet.job_id == job.id)
        .options(selectinload(Timesheet.worker))
    ).all()

    logger.info(f"Invoice calc for job {job.id}: found {len(timesheets)} timesheets")
    for ts in timesheets:
        logger.info(
            f"  Timesheet {ts.id}: worker={ts.worker.name if ts.worker else 'None'}, "
            f"hours={ts.hours_worked}, rate={ts.worker.hourly_rate if ts.worker else 'N/A'}, "
            f"personal_materials={ts.personal_materials}, company_materials={ts.company_materials}"
        )

    total_labour_hours = Decimal("0")
    labour_amount = Decimal("0")
    materials_amount = Decimal("0")
    inventory_materials = Decimal("0")
    for ts in timesheets:
        effective_min = ts.minimum_hours_override if ts.minimum_hours_override is not None else MINIMUM_HOURS
        billable = _round_hours(ts.hours_worked, ts.break_duration, effective_min)
        total_labour_hours += billable
        rate = REDSEAL_RATE if job.is_redseal_trade else LABOUR_RATE
        labour_amount += billable * rate
        materials_amount += ts.personal_materials or Decimal("0")
        inventory_materials += ts.company_materials or Decimal("0")

    labour_amount = labour_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    materials_amount = materials_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    inventory_materials = inventory_materials.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    distance_km = job.calculated_distance_km or Decimal("0")
    travel_amount = (distance_km * MILEAGE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    dump_fee = data.dump_fee if data else Decimal("0")
    admin_fee = data.admin_fee if data else Decimal("0")

    subtotal = labour_amount + travel_amount + materials_amount + inventory_materials + dump_fee + admin_fee
    include_hst = data.include_hst if data else True
    hst_amount = (subtotal * HST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if include_hst else Decimal("0")
    total = subtotal + hst_amount

    return {
        "total_labour_hours": total_labour_hours,
        "labour_amount": labour_amount,
        "total_distance_km": distance_km,
        "travel_amount": travel_amount,
        "materials_amount": materials_amount,
        "inventory_materials": inventory_materials,
        "dump_fee": dump_fee,
        "admin_fee": admin_fee,
        "subtotal": subtotal,
        "hst_amount": hst_amount,
        "total": total,
    }


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
        scope_of_work=invoice.scope_of_work,
        labour_amount=invoice.labour_amount,
        travel_amount=invoice.travel_amount,
        materials_amount=invoice.materials_amount,
        inventory_materials=invoice.inventory_materials,
        dump_fee=invoice.dump_fee,
        admin_fee=invoice.admin_fee,
        total_labour_hours=invoice.total_labour_hours,
        total_distance_km=invoice.total_distance_km,
        job=JobBrief(
            id=job.id,
            title=job.title,
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
    from ..models.settings import AppSettings

    year = date.today().year
    prefix = f"INV-{year}-"

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

    # Apply floor from settings
    setting = session.get(AppSettings, "invoice_start_number")
    if setting:
        floor_num = int(setting.value)
        new_num = max(new_num, floor_num)

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
    """Create an invoice for a job. Auto-calculates from timesheets/receipts, manager can override."""
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

    if job.invoice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice {job.invoice.invoice_number} already exists for this job",
        )

    amounts = _calculate_invoice_amounts(session, job, data)

    # Apply manager overrides if provided
    if data:
        if data.labour_amount is not None:
            amounts["labour_amount"] = data.labour_amount
        if data.travel_amount is not None:
            amounts["travel_amount"] = data.travel_amount
        if data.materials_amount is not None:
            amounts["materials_amount"] = data.materials_amount
        if data.total_labour_hours is not None:
            amounts["total_labour_hours"] = data.total_labour_hours
        if data.total_distance_km is not None:
            amounts["total_distance_km"] = data.total_distance_km

        # Recalculate totals after overrides
        amounts["subtotal"] = (
            amounts["labour_amount"]
            + amounts["travel_amount"]
            + amounts["materials_amount"]
            + amounts["inventory_materials"]
            + amounts["dump_fee"]
            + amounts["admin_fee"]
        )
        if data.include_hst:
            amounts["hst_amount"] = (amounts["subtotal"] * HST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            amounts["hst_amount"] = Decimal("0")
        amounts["total"] = amounts["subtotal"] + amounts["hst_amount"]

    inv_number = (data.invoice_number.strip() if data and data.invoice_number else "") or generate_invoice_number(session)
    existing = session.exec(select(Invoice).where(Invoice.invoice_number == inv_number)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice number {inv_number} is already in use",
        )

    invoice = Invoice(
        job_id=job_id,
        invoice_number=inv_number,
        scope_of_work=data.scope_of_work if data else None,
        due_date=date.today() + timedelta(days=30),
        notes=data.notes if data else "Payment due within 30 days.",
        **amounts,
    )

    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    return invoice_to_response(invoice, job, job.client)


@router.get("/preview/job/{job_id}", response_model=InvoicePreview)
def preview_invoice(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Preview auto-calculated invoice amounts for a job before creation"""
    job = session.exec(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client))
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    amounts = _calculate_invoice_amounts(session, job, None)

    return InvoicePreview(
        invoice_number=generate_invoice_number(session),
        labour_hours=amounts["total_labour_hours"],
        labour_amount=amounts["labour_amount"],
        travel_km=amounts["total_distance_km"],
        travel_amount=amounts["travel_amount"],
        materials_amount=amounts["materials_amount"],
        inventory_materials=amounts["inventory_materials"],
        admin_fee=amounts["admin_fee"],
        subtotal=amounts["subtotal"],
        hst_amount=amounts["hst_amount"],
        total=amounts["total"],
    )


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

    pdf_content = generate_invoice_pdf(invoice, invoice.job, invoice.job.client)

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
