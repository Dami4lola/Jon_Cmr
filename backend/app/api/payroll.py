"""
Payroll processing API endpoints
"""
import logging
import zipfile
from collections import defaultdict
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ..models import Timesheet, Job
from ..schemas.payroll import (
    PayrollProcessRequest,
    PayrollEntryDetail,
    PayrollWorkerSummary,
)
from ..services.payroll_pdf import generate_payroll_pdf
from .deps import DBSession, ManagerUser

logger = logging.getLogger(__name__)

router = APIRouter()

# Constants
KM_RATE = Decimal("0.50")
MINIMUM_HOURS = Decimal("4.0")
HST_RATE = Decimal("0.13")


def _round_hours(hours_worked: Decimal) -> Decimal:
    """Round hours to nearest 0.25 and apply 4-hour minimum."""
    hours_float = float(hours_worked)
    rounded = Decimal(str(round(hours_float * 4) / 4))
    return max(rounded, MINIMUM_HOURS)


@router.post("/process-period")
def process_payroll_period(
    data: PayrollProcessRequest,
    session: DBSession,
    current_user: ManagerUser,
):
    """
    Process payroll for a date range.
    Generates per-worker PDF summaries, archives timesheets, returns ZIP.
    """
    if data.end_date < data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    # 1. Query unpaid timesheets in date range
    statement = (
        select(Timesheet)
        .where(
            Timesheet.date >= data.start_date,
            Timesheet.date <= data.end_date,
            Timesheet.is_paid == False,
        )
        .options(
            selectinload(Timesheet.worker),
            selectinload(Timesheet.job).selectinload(Job.client),
        )
        .order_by(Timesheet.date)
    )
    timesheets = session.exec(statement).all()

    if not timesheets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No unpaid timesheets found in the selected date range",
        )

    # 2. Group by worker
    grouped: dict[int, list[Timesheet]] = defaultdict(list)
    for ts in timesheets:
        grouped[ts.worker_id].append(ts)

    # 3. Build summaries and generate PDFs
    worker_pdfs: list[tuple[str, bytes]] = []  # (filename, pdf_bytes)
    worker_summaries: list[PayrollWorkerSummary] = []

    for worker_id, worker_timesheets in grouped.items():
        worker = worker_timesheets[0].worker
        entries: list[PayrollEntryDetail] = []

        total_hours = Decimal("0")
        total_labour = Decimal("0")
        total_km = Decimal("0")
        total_km_cost = Decimal("0")
        total_personal_materials = Decimal("0")

        for ts in worker_timesheets:
            billable_hours = _round_hours(ts.hours_worked)
            labour_cost = (billable_hours * worker.hourly_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            km_distance = ts.job.calculated_distance_km or Decimal("0")
            km_cost = (km_distance * KM_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            client_name = ts.job.client.name if ts.job and ts.job.client else "Unknown"

            entry = PayrollEntryDetail(
                date=ts.date,
                customer_name=client_name,
                job_description=ts.job.title if ts.job else "",
                hours_worked=ts.hours_worked,
                billable_hours=billable_hours,
                labour_rate=worker.hourly_rate,
                labour_cost=labour_cost,
                km_distance=km_distance,
                km_rate=KM_RATE,
                km_cost=km_cost,
                personal_materials=ts.personal_materials,
            )
            entries.append(entry)

            total_hours += billable_hours
            total_labour += labour_cost
            total_km += km_distance
            total_km_cost += km_cost
            total_personal_materials += ts.personal_materials

        # HST calculations
        if worker.charges_hst:
            labour_hst = (total_labour * HST_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            km_hst = (total_km_cost * HST_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            materials_hst = (total_personal_materials * HST_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            labour_hst = Decimal("0")
            km_hst = Decimal("0")
            materials_hst = Decimal("0")

        grand_total = (
            total_labour + total_km_cost + total_personal_materials
            + labour_hst + km_hst + materials_hst
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        summary = PayrollWorkerSummary(
            worker_id=worker_id,
            worker_name=worker.name,
            entries=entries,
            total_hours=total_hours,
            total_labour=total_labour,
            total_km=total_km,
            total_km_cost=total_km_cost,
            total_personal_materials=total_personal_materials,
            labour_hst=labour_hst,
            km_hst=km_hst,
            materials_hst=materials_hst,
            grand_total=grand_total,
            charges_hst=worker.charges_hst,
        )
        worker_summaries.append(summary)

        # Generate PDF (before marking as paid — atomic safety)
        pdf_bytes = generate_payroll_pdf(summary, data.start_date, data.end_date)
        safe_name = worker.name.replace(" ", "_").replace("/", "_")
        filename = f"Payroll_{safe_name}_{data.start_date}_{data.end_date}.pdf"
        worker_pdfs.append((filename, pdf_bytes))

    # 4. All PDFs generated successfully — now mark timesheets as paid (atomic)
    for ts in timesheets:
        ts.is_paid = True
        session.add(ts)
    session.commit()

    logger.info(
        f"Payroll processed: {len(worker_summaries)} workers, "
        f"{len(timesheets)} timesheets archived "
        f"({data.start_date} to {data.end_date})"
    )

    # 5. Create ZIP in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, pdf_bytes in worker_pdfs:
            zf.writestr(filename, pdf_bytes)
    zip_buffer.seek(0)

    # 6. Return ZIP response
    zip_filename = f"Payroll_{data.start_date}_{data.end_date}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )
