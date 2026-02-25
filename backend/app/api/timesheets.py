"""
Timesheet API endpoints
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)

from ..config import settings
from ..models import Timesheet, Worker, Job, Receipt
from ..schemas.timesheet import (
    TimesheetCreate,
    TimesheetUpdate,
    TimesheetResponse,
    ReceiptResponse,
    PayoutPreview,
)
from ..schemas.worker import WorkerBrief
from ..schemas.job import JobBrief
from ..services.payout import calculate_payout, calculate_payout_breakdown
from ..services.s3 import upload_file_to_s3, delete_file_from_s3
from .deps import DBSession, CurrentUser, CurrentWorker, ManagerUser

router = APIRouter()


def timesheet_to_response(timesheet: Timesheet) -> TimesheetResponse:
    """Convert Timesheet model to response schema"""
    return TimesheetResponse(
        id=timesheet.id,
        date=timesheet.date,
        hours_worked=timesheet.hours_worked,
        break_duration=timesheet.break_duration,
        used_company_truck=timesheet.used_company_truck,
        worked_at_hq=timesheet.worked_at_hq,
        company_materials=timesheet.company_materials,
        personal_materials=timesheet.personal_materials,
        calculated_pay=timesheet.calculated_pay,
        receipt_count=len(timesheet.receipts) if timesheet.receipts else 0,
        created_at=timesheet.created_at,
        worker=WorkerBrief(id=timesheet.worker.id, name=timesheet.worker.name),
        job=JobBrief(
            id=timesheet.job.id,
            description=timesheet.job.description,
            client_name=timesheet.job.client.name if timesheet.job.client else "",
            start_date=timesheet.job.start_date,
            end_date=timesheet.job.end_date,
        ),
    )


@router.get("/", response_model=list[TimesheetResponse])
def list_timesheets(
    session: DBSession,
    current_user: CurrentUser,
    worker_id: int | None = None,
):
    """
    List timesheets.
    - Workers: see only their own timesheets
    - Managers: see all timesheets (or filter by worker_id)
    """
    statement = (
        select(Timesheet)
        .options(
            selectinload(Timesheet.worker),
            selectinload(Timesheet.job).selectinload(Job.client),
            selectinload(Timesheet.receipts),
        )
    )

    if current_user.is_manager:
        if worker_id:
            statement = statement.where(Timesheet.worker_id == worker_id)
    else:
        # Workers only see their own
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if worker:
            statement = statement.where(Timesheet.worker_id == worker.id)
        else:
            return []

    statement = statement.order_by(Timesheet.date.desc())
    timesheets = session.exec(statement).all()

    return [timesheet_to_response(ts) for ts in timesheets]


@router.get("/summary")
def get_timesheet_summary(
    session: DBSession,
    current_user: ManagerUser,
):
    """Get payroll summary (manager only)"""
    statement = select(Timesheet)
    timesheets = session.exec(statement).all()

    total_pay = sum(ts.calculated_pay or Decimal("0") for ts in timesheets)
    total_hours = sum(ts.hours_worked for ts in timesheets)

    return {
        "total_pay": float(total_pay),
        "timesheet_count": len(timesheets),
        "total_hours": float(total_hours),
    }


@router.post("/", response_model=TimesheetResponse, status_code=status.HTTP_201_CREATED)
def create_timesheet(
    data: TimesheetCreate,
    session: DBSession,
    current_user: CurrentUser,
):
    """Submit a new timesheet"""
    # Get worker profile
    worker = session.exec(
        select(Worker).where(Worker.user_id == current_user.id)
    ).first()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    # Verify job exists and worker is assigned
    job = session.exec(
        select(Job)
        .where(Job.id == data.job_id)
        .options(selectinload(Job.assigned_workers), selectinload(Job.client))
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Check if worker is assigned (managers can submit for any job)
    if not current_user.is_manager:
        is_assigned = any(w.id == worker.id for w in job.assigned_workers)
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this job",
            )

    # Create timesheet
    timesheet = Timesheet(
        worker_id=worker.id,
        job_id=data.job_id,
        date=data.date,
        hours_worked=data.hours_worked,
        break_duration=data.break_duration,
        used_company_truck=data.used_company_truck,
        worked_at_hq=data.worked_at_hq,
        company_materials=data.company_materials,
        personal_materials=data.personal_materials,
    )

    # Calculate pay
    timesheet.calculated_pay = calculate_payout(timesheet, worker)

    session.add(timesheet)
    session.commit()
    session.refresh(timesheet)

    # Reload with relationships
    statement = (
        select(Timesheet)
        .where(Timesheet.id == timesheet.id)
        .options(
            selectinload(Timesheet.worker),
            selectinload(Timesheet.job).selectinload(Job.client),
        )
    )
    timesheet = session.exec(statement).first()

    return timesheet_to_response(timesheet)


@router.get("/{timesheet_id}", response_model=TimesheetResponse)
def get_timesheet(
    timesheet_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Get a specific timesheet"""
    statement = (
        select(Timesheet)
        .where(Timesheet.id == timesheet_id)
        .options(
            selectinload(Timesheet.worker),
            selectinload(Timesheet.job).selectinload(Job.client),
            selectinload(Timesheet.receipts),
        )
    )
    timesheet = session.exec(statement).first()

    if not timesheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timesheet not found",
        )

    # Authorization: own timesheet or manager
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or timesheet.worker_id != worker.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    return timesheet_to_response(timesheet)


@router.put("/{timesheet_id}", response_model=TimesheetResponse)
def update_timesheet(
    timesheet_id: int,
    data: TimesheetUpdate,
    session: DBSession,
    current_user: CurrentUser,
):
    """Update a timesheet"""
    statement = (
        select(Timesheet)
        .where(Timesheet.id == timesheet_id)
        .options(selectinload(Timesheet.worker))
    )
    timesheet = session.exec(statement).first()

    if not timesheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timesheet not found",
        )

    # Authorization: own timesheet or manager
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or timesheet.worker_id != worker.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(timesheet, key, value)

    timesheet.updated_at = datetime.utcnow()

    # Recalculate pay
    timesheet.calculated_pay = calculate_payout(timesheet, timesheet.worker)

    session.add(timesheet)
    session.commit()

    # Reload with relationships
    statement = (
        select(Timesheet)
        .where(Timesheet.id == timesheet_id)
        .options(
            selectinload(Timesheet.worker),
            selectinload(Timesheet.job).selectinload(Job.client),
        )
    )
    timesheet = session.exec(statement).first()

    return timesheet_to_response(timesheet)


@router.delete("/{timesheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timesheet(
    timesheet_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Delete a timesheet"""
    timesheet = session.get(Timesheet, timesheet_id)

    if not timesheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timesheet not found",
        )

    # Authorization: own timesheet or manager
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or timesheet.worker_id != worker.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    session.delete(timesheet)
    session.commit()


@router.post("/{timesheet_id}/receipts")
def upload_receipts(
    timesheet_id: int,
    session: DBSession,
    current_user: CurrentUser,
    files: list[UploadFile] = File(...),
):
    """Upload receipt images for a timesheet — stores in AWS S3"""
    timesheet = session.get(Timesheet, timesheet_id)

    if not timesheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timesheet not found",
        )

    # Authorization
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or timesheet.worker_id != worker.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    uploaded = []
    logger.info(f"Receipt upload: timesheet_id={timesheet_id}, file_count={len(files)}")

    for file in files:
        content = file.file.read()
        content_type = file.content_type or "image/jpeg"
        filename = file.filename or f"{uuid.uuid4()}.jpg"

        logger.info(f"Processing file: {filename}, type={content_type}, size={len(content)} bytes")

        public_url = upload_file_to_s3(content, filename, content_type)

        receipt = Receipt(
            timesheet_id=timesheet_id,
            public_url=public_url,
            content_type=content_type,
        )
        session.add(receipt)
        uploaded.append({"filename": filename, "url": public_url})

    session.commit()
    logger.info(f"Receipt upload complete: {len(uploaded)} files saved")

    return {"uploaded": len(uploaded), "files": uploaded}


@router.get("/{timesheet_id}/receipts", response_model=list[ReceiptResponse])
def get_timesheet_receipts(
    timesheet_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Get all receipts for a timesheet"""
    timesheet = session.get(Timesheet, timesheet_id)

    if not timesheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timesheet not found",
        )

    # Authorization
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or timesheet.worker_id != worker.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    statement = select(Receipt).where(Receipt.timesheet_id == timesheet_id)
    receipts = session.exec(statement).all()

    return [
        ReceiptResponse(
            id=r.id,
            timesheet_id=r.timesheet_id,
            image_url=r.public_url,
            description=r.description,
            amount=r.amount,
            uploaded_at=r.uploaded_at,
        )
        for r in receipts
    ]


@router.delete("/receipts/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
    receipt_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Delete a receipt — removes from S3 and database"""
    receipt = session.get(Receipt, receipt_id)

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )

    # Get timesheet for authorization
    timesheet = session.get(Timesheet, receipt.timesheet_id)

    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or timesheet.worker_id != worker.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    # Delete from S3
    if receipt.public_url:
        try:
            delete_file_from_s3(receipt.public_url)
        except Exception:
            pass  # Don't fail the delete if S3 cleanup fails

    session.delete(receipt)
    session.commit()


@router.post("/calculate", response_model=PayoutPreview)
def calculate_payout_preview(
    data: TimesheetCreate,
    session: DBSession,
    current_user: CurrentUser,
):
    """Preview payout calculation without creating a timesheet"""
    # Get worker profile
    worker = session.exec(
        select(Worker).where(Worker.user_id == current_user.id)
    ).first()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    # Create temporary timesheet object for calculation
    temp_timesheet = Timesheet(
        worker_id=worker.id,
        job_id=data.job_id,
        date=data.date,
        hours_worked=data.hours_worked,
        break_duration=data.break_duration,
        used_company_truck=data.used_company_truck,
        worked_at_hq=data.worked_at_hq,
        company_materials=data.company_materials,
        personal_materials=data.personal_materials,
    )

    # Get detailed breakdown
    breakdown = calculate_payout_breakdown(temp_timesheet, worker)

    return PayoutPreview(**breakdown)
