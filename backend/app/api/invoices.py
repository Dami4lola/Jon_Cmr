"""
Invoice API endpoints
"""
import io
import logging
import zipfile
import requests as http_requests
from collections import defaultdict
from dataclasses import replace
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)
from fastapi.responses import Response
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from ..models import Invoice, Job, Client, Timesheet, Receipt, Worker
from ..schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoicePreview,
    InvoiceStatusUpdate,
    InvoiceUpdate,
)
from ..schemas.job import JobBrief
from ..schemas.client import ClientBrief
from ..services.invoice_pdf import generate_invoice_pdf
from ..services.job_cost import (  # noqa: F401
    BillingRates,
    compute_job_billing,
    date_in_period,
    invoice_amounts,
    resolve_billing_rates,
    LABOUR_RATE,
    REDSEAL_RATE,
    HST_RATE,
)
from ..services.job_cost import BILLABLE_KM_RATE as DEFAULT_KM_RATE  # noqa: F401
from .deps import DBSession, ManagerUser, AdminUser

router = APIRouter()

# Deliberately NOT job_cost.MINIMUM_HOURS, which is Decimal("4"). The two are equal,
# but the quick quote returns max(rounded_hours, MINIMUM_HOURS) as estimated_hours and
# the public /quote page renders it raw, so "4.0 hrs" would silently become "4 hrs".
MINIMUM_HOURS = Decimal("4.0")


def _round_hours(hours_worked: Decimal, break_duration: Decimal = Decimal("0"), minimum_hours: Decimal = MINIMUM_HOURS) -> Decimal:
    """
    Round raw hours worked to the nearest quarter-hour, subtract break time,
    and enforce a minimum billable floor.

    Rounding uses float round() at 0.25-hour granularity (scale × 4, round, ÷ 4).
    Break is subtracted after rounding. Result is floored at minimum_hours.

    Args:
        hours_worked: Raw hours from the timesheet entry.
        break_duration: Unpaid break time in hours to subtract after rounding.
        minimum_hours: Minimum billable floor (default 4.0 hours).

    Returns:
        Billable hours as a Decimal, >= 0 and >= minimum_hours.
    """
    hours_float = float(hours_worked)
    break_float = float(break_duration)
    rounded = (round(hours_float * 4) / 4) - break_float
    billable = Decimal(str(max(rounded, 0)))
    return max(billable, minimum_hours)


def _timesheets_in_period(
    session,
    job_id: int,
    period_start: date | None = None,
    period_end: date | None = None,
    with_receipts: bool = False,
) -> list[Timesheet]:
    """
    The job's timesheets whose date falls in the billing period, both ends inclusive.

    A null bound is unbounded, so a null/null period is the whole job - the shape every
    invoice issued before progress billing existed still carries.

    This is what makes progress billing safe against double-billing: a timesheet has a
    single date, so it lands in at most one period, and the 4-hour minimum that
    compute_job_billing applies per timesheet can never be applied to the same work
    twice. Travel and materials follow the same partition, because both are derived from
    the timesheets handed to the billing engine.
    """
    statement = select(Timesheet).where(Timesheet.job_id == job_id)
    if period_start is not None:
        statement = statement.where(Timesheet.date >= period_start)
    if period_end is not None:
        statement = statement.where(Timesheet.date <= period_end)

    loads = [selectinload(Timesheet.worker)]
    if with_receipts:
        loads.append(selectinload(Timesheet.receipts))

    return session.exec(statement.options(*loads).order_by(Timesheet.date)).all()


def _resolve_invoice_rates(job: Job, data: InvoiceCreate | None) -> BillingRates:
    """The job's billable rates, with any per-invoice override laid over the top."""
    rates = resolve_billing_rates(job)
    if data is None:
        return rates

    return replace(
        rates,
        labour_rate=data.labour_rate if data.labour_rate is not None else rates.labour_rate,
        redseal_rate=data.redseal_rate if data.redseal_rate is not None else rates.redseal_rate,
        km_rate=data.km_rate if data.km_rate is not None else rates.km_rate,
    )


def _calculate_invoice_amounts(
    session,
    job: Job,
    data: InvoiceCreate | None,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
):
    """
    Auto-calculate all invoice line items from the job's timesheets in the billing period.
    - Labour hours: sum of hours_worked from timesheets (rounded, 4hr min per timesheet)
    - Labour amount: billable hours x the job's billable labour rate, or its Red Seal
      rate when the worker ticked Red Seal. NOT the worker's hourly rate - that is a
      payout figure.
    - Travel: one round trip per non-HQ timesheet x the job's distance
    - Materials: sum of personal_materials from timesheets
    - Inventory materials: sum of company_materials from timesheets

    The arithmetic lives in services/job_cost.py so the invoice, the payout run and the
    Job Financials page cannot drift apart. The query stays here.
    """
    timesheets = _timesheets_in_period(session, job.id, period_start, period_end)

    billing = compute_job_billing(
        job,
        timesheets,
        rates=_resolve_invoice_rates(job, data),
        dump_fee=data.dump_fee if data else Decimal("0"),
        admin_fee=data.admin_fee if data else Decimal("0"),
        include_hst=data.include_hst if data else True,
        # Passed explicitly: invoices' Decimal("4.0") and job_cost's Decimal("4") are
        # equal but serialize differently, and this value reaches the public quote page.
        minimum_hours=MINIMUM_HOURS,
    )
    return invoice_amounts(billing)


def _overlapping_invoices(
    job: Job,
    period_start: date | None,
    period_end: date | None,
) -> list[Invoice]:
    """
    Existing invoices whose billing period intersects this one, a null bound being
    unbounded in that direction.

    A whole-job invoice therefore overlaps everything, which is the point: with the
    one-invoice-per-job rule gone, a second whole-job invoice would bill every timesheet
    a second time and nothing else in the system would notice.
    """
    def intersects(invoice: Invoice) -> bool:
        starts_after_their_end = (
            period_start is not None
            and invoice.period_end is not None
            and period_start > invoice.period_end
        )
        ends_before_their_start = (
            period_end is not None
            and invoice.period_start is not None
            and period_end < invoice.period_start
        )
        return not (starts_after_their_end or ends_before_their_start)

    return [invoice for invoice in job.invoices if intersects(invoice)]


def _reject_double_billing(
    session,
    job: Job,
    period_start: date | None,
    period_end: date | None,
) -> None:
    """
    Refuse a period whose timesheets another invoice has already billed.

    Only an overlap that actually contains timesheets is a double-bill - re-billing a
    gap where nobody worked is harmless, and blocking it would be a false alarm.
    """
    overlapping = _overlapping_invoices(job, period_start, period_end)
    if not overlapping:
        return

    already_billed = {
        timesheet.date
        for invoice in overlapping
        for timesheet in _timesheets_in_period(
            session, job.id, invoice.period_start, invoice.period_end
        )
        if date_in_period(timesheet.date, period_start, period_end)
    }
    if not already_billed:
        return

    numbers = ", ".join(invoice.invoice_number for invoice in overlapping)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Timesheets on {len(already_billed)} day(s) in this period are already "
            f"billed on invoice {numbers}. Adjust the period, or resend with "
            f"allow_overlap to bill them again."
        ),
    )


def invoice_to_response(invoice: Invoice, job: Job, client: Client) -> InvoiceResponse:
    """Convert Invoice model to response schema"""
    return InvoiceResponse(
        id=invoice.id,
        job_id=invoice.job_id,
        invoice_number=invoice.invoice_number,
        created_date=invoice.created_date,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
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
        km_rate=invoice.km_rate,
        labour_rate=invoice.labour_rate,
        redseal_rate=invoice.redseal_rate,
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
    """
    Create an invoice for a job. Auto-calculates from timesheets/receipts, manager can override.

    A job is billed as many times as it takes, at any point in its life - completing the
    job is a scheduling decision and has nothing to do with invoicing. Each invoice
    covers a billing period, and the periods must not overlap unless the manager says so
    outright.
    """
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.client),
            selectinload(Job.invoices),
            selectinload(Job.estimate),
        )
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    period_start = data.period_start if data else None
    period_end = data.period_end if data else None

    if not (data and data.allow_overlap):
        _reject_double_billing(session, job, period_start, period_end)

    amounts = _calculate_invoice_amounts(
        session, job, data, period_start=period_start, period_end=period_end
    )

    # Apply manager overrides if provided
    if data:
        if data.labour_amount is not None:
            amounts["labour_amount"] = data.labour_amount
        if data.travel_amount is not None:
            amounts["travel_amount"] = data.travel_amount
        if data.materials_amount is not None:
            amounts["materials_amount"] = data.materials_amount
        if data.inventory_materials is not None:
            amounts["inventory_materials"] = data.inventory_materials
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
        period_start=period_start,
        period_end=period_end,
        notes=data.notes if data else "Payment due within 30 days.",
        **amounts,
    )

    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    return invoice_to_response(invoice, job, job.client)


@router.get("/job/{job_id}", response_model=list[InvoiceResponse])
def list_job_invoices(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Every invoice raised against one job, in billing-period order (manager only)"""
    invoices = session.exec(
        select(Invoice)
        .where(Invoice.job_id == job_id)
        .options(selectinload(Invoice.job).selectinload(Job.client))
    ).all()

    ordered = sorted(
        invoices,
        key=lambda inv: (
            inv.period_start is not None,
            inv.period_start or date.min,
            inv.created_date,
            inv.id,
        ),
    )
    return [invoice_to_response(inv, inv.job, inv.job.client) for inv in ordered]


@router.get("/preview/job/{job_id}", response_model=InvoicePreview)
def preview_invoice(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
    period_start: date | None = None,
    period_end: date | None = None,
):
    """Preview auto-calculated invoice amounts for a job's billing period before creation"""
    job = session.exec(
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.client),
            selectinload(Job.invoices),
            selectinload(Job.estimate),
        )
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    amounts = _calculate_invoice_amounts(
        session, job, None, period_start=period_start, period_end=period_end
    )
    rates = resolve_billing_rates(job)
    timesheets = _timesheets_in_period(session, job.id, period_start, period_end)

    return InvoicePreview(
        invoice_number=generate_invoice_number(session),
        period_start=period_start,
        period_end=period_end,
        timesheet_count=len(timesheets),
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
        labour_rate=rates.labour_rate,
        redseal_rate=rates.redseal_rate,
        km_rate=rates.km_rate,
        rate_source=rates.source,
        overlapping_invoice_numbers=[
            inv.invoice_number
            for inv in _overlapping_invoices(job, period_start, period_end)
        ],
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

    pdf_content = generate_invoice_pdf(invoice, invoice.job.client)

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


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Update invoice financial fields and recalculate totals (manager only)"""
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

    update_fields = data.model_dump(exclude_none=True, exclude={"include_hst"})
    for field, value in update_fields.items():
        setattr(invoice, field, value)

    invoice.subtotal = (
        invoice.labour_amount
        + invoice.travel_amount
        + invoice.materials_amount
        + invoice.inventory_materials
        + invoice.dump_fee
        + invoice.admin_fee
    )

    apply_hst = data.include_hst if data.include_hst is not None else (invoice.hst_amount > 0)
    invoice.hst_amount = (
        (invoice.subtotal * HST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if apply_hst else Decimal("0")
    )
    invoice.total = invoice.subtotal + invoice.hst_amount

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


@router.get("/{invoice_id}/receipts/download")
def download_invoice_receipts(
    invoice_id: int,
    session: DBSession,
    current_user: AdminUser,
):
    """
    Download the receipts this invoice billed as a ZIP file (admin only).

    Scoped to the invoice's own billing period, so each progress invoice hands back the
    expenses it charged for rather than every receipt on the job.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    timesheets = _timesheets_in_period(
        session,
        invoice.job_id,
        invoice.period_start,
        invoice.period_end,
        with_receipts=True,
    )

    all_receipts = [
        (receipt, ts.worker)
        for ts in timesheets
        for receipt in ts.receipts
    ]
    if not all_receipts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No receipts found for this invoice",
        )

    zip_buffer = io.BytesIO()
    downloaded_count = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for receipt, worker in all_receipts:
            try:
                resp = http_requests.get(receipt.public_url, timeout=10)
                resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to download receipt {receipt.id}: {e}")
                continue

            # Strip the UUID prefix added during S3 upload ("uuid_originalname.jpg" → "originalname.jpg")
            raw_filename = receipt.public_url.split("/")[-1]
            original_name = raw_filename.split("_", 1)[-1] if "_" in raw_filename else raw_filename
            worker_slug = (worker.name if worker else "unknown").replace(" ", "_")
            zip_filename = f"{receipt.id}_{worker_slug}_{original_name}"

            zf.writestr(zip_filename, resp.content)
            downloaded_count += 1

    if downloaded_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download any receipts",
        )

    zip_buffer.seek(0)
    filename = f"invoice_{invoice.invoice_number}_receipts.zip"
    return Response(
        content=zip_buffer.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
