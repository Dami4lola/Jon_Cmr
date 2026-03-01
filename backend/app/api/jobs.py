"""
Job API endpoints
"""
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, status, Body
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ..models import Job, Worker, Client, JobWorkerLink, JobWorkerSchedule, JobPhoto
from ..schemas.job import JobCreate, JobUpdate, JobResponse, JobPhotoResponse, CalendarEvent, WorkerScheduleEntry
from ..schemas.client import ClientBrief
from ..schemas.worker import WorkerBrief
from ..services.distance import calculate_distance, get_distance_info
from ..services.s3 import upload_file_to_s3, delete_file_from_s3
from .deps import DBSession, CurrentUser, CurrentWorker, ManagerUser

logger = logging.getLogger(__name__)

router = APIRouter()


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to response schema"""
    return JobResponse(
        id=job.id,
        title=job.title,
        details=job.details,
        start_date=job.start_date,
        end_date=job.end_date,
        scheduled_time=job.scheduled_time,
        estimated_duration=job.estimated_duration,
        is_completed=job.is_completed,
        is_redseal_trade=job.is_redseal_trade,
        estimate_amount=job.estimate_amount,
        calculated_distance_km=job.calculated_distance_km,
        address_override=job.address_override,
        job_address=job.get_job_address(),
        client=ClientBrief(
            id=job.client.id,
            name=job.client.name,
            phone_number=job.client.phone_number,
            address=job.client.address,
        ),
        assigned_workers=[
            WorkerBrief(id=w.id, name=w.name)
            for w in job.assigned_workers
        ],
        worker_schedule=[
            WorkerScheduleEntry(worker_id=ws.worker_id, date=ws.date)
            for ws in (job.worker_schedule or [])
        ],
        photos=[
            JobPhotoResponse(
                id=p.id,
                public_url=p.public_url,
                caption=p.caption,
                uploaded_at=p.uploaded_at,
            )
            for p in (job.photos or [])
        ],
    )


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    session: DBSession,
    current_user: CurrentUser,
    completed: bool | None = None,
):
    """
    List jobs.
    - Workers: see only assigned jobs
    - Managers: see all jobs
    """
    statement = (
        select(Job)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )

    # Filter by completion status if specified
    if completed is not None:
        statement = statement.where(Job.is_completed == completed)

    # Workers only see assigned jobs
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker:
            return []
        statement = statement.join(JobWorkerLink).where(
            JobWorkerLink.worker_id == worker.id
        )

    statement = statement.order_by(Job.start_date.desc())
    jobs = session.exec(statement).all()

    return [job_to_response(job) for job in jobs]


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    data: JobCreate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Create a new job (manager only)"""
    # Verify client exists
    client = session.get(Client, data.client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # Create job
    job = Job(
        client_id=data.client_id,
        title=data.title,
        details=data.details,
        start_date=data.start_date,
        end_date=data.end_date,
        scheduled_time=data.scheduled_time,
        estimated_duration=data.estimated_duration,
        estimate_amount=data.estimate_amount,
        address_override=data.address_override,
        is_redseal_trade=data.is_redseal_trade,
    )

    # Calculate distance
    job_address = data.address_override or client.address
    distance = calculate_distance(job_address)
    if distance:
        job.calculated_distance_km = distance

    session.add(job)
    session.commit()

    # Save worker schedule entries
    if data.worker_schedule:
        for entry in data.worker_schedule:
            schedule = JobWorkerSchedule(job_id=job.id, worker_id=entry.worker_id, date=entry.date)
            session.add(schedule)
        # Derive assigned_worker_ids from schedule
        schedule_worker_ids = set(e.worker_id for e in data.worker_schedule)
        all_worker_ids = schedule_worker_ids | set(data.assigned_worker_ids or [])
    else:
        all_worker_ids = set(data.assigned_worker_ids or [])

    # Assign workers
    if all_worker_ids:
        for worker_id in all_worker_ids:
            worker = session.get(Worker, worker_id)
            if worker:
                link = JobWorkerLink(job_id=job.id, worker_id=worker_id)
                session.add(link)
        session.commit()

    # Refresh with relationships
    session.refresh(job)
    statement = (
        select(Job)
        .where(Job.id == job.id)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )
    job = session.exec(statement).first()

    return job_to_response(job)


@router.get("/calendar", response_model=list[CalendarEvent])
def get_calendar_events(
    session: DBSession,
    current_user: CurrentUser,
):
    """Get jobs as calendar events for the current worker"""
    # Get worker profile
    worker = session.exec(
        select(Worker).where(Worker.user_id == current_user.id)
    ).first()

    if not worker and not current_user.is_manager:
        return []

    statement = (
        select(Job)
        .options(selectinload(Job.client))
        .where(Job.start_date.isnot(None))
        .where(Job.is_completed == False)
    )

    # Workers only see assigned jobs
    if not current_user.is_manager and worker:
        statement = statement.join(JobWorkerLink).where(
            JobWorkerLink.worker_id == worker.id
        )

    jobs = session.exec(statement).all()

    events = []
    for job in jobs:
        event = CalendarEvent(
            id=job.id,
            title=f"{job.client.name} - {job.title}",
            start=job.start_date,
            end=job.end_date,
            time=job.scheduled_time.strftime("%H:%M") if job.scheduled_time else None,
            duration=str(job.estimated_duration) if job.estimated_duration else None,
            client=job.client.name,
            address=job.get_job_address(),
            description=job.details or job.title,
        )
        events.append(event)

    return events


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Get a specific job"""
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Workers can only view assigned jobs
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if worker:
            is_assigned = any(w.id == worker.id for w in job.assigned_workers)
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this job",
                )

    return job_to_response(job)


@router.get("/{job_id}/distance")
def get_job_distance(
    job_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Get calculated distance for a job"""
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    job_address = job.get_job_address()

    # If distance not calculated, try to calculate
    if job.calculated_distance_km is None:
        distance = calculate_distance(job_address)
        if distance:
            job.calculated_distance_km = distance
            session.add(job)
            session.commit()

    return {
        "job_id": job.id,
        "distance_km": float(job.calculated_distance_km) if job.calculated_distance_km else None,
        "job_address": job_address,
    }


@router.post("/recalculate-distances")
def recalculate_all_distances(
    session: DBSession,
    current_user: ManagerUser,
):
    """Recalculate distances for all jobs missing distance data (manager only)"""
    statement = (
        select(Job)
        .where(Job.calculated_distance_km.is_(None))
        .options(selectinload(Job.client))
    )
    jobs = session.exec(statement).all()

    updated = []
    failed = []
    for job in jobs:
        job_address = job.get_job_address()
        if not job_address:
            failed.append({"job_id": job.id, "reason": "No address"})
            continue
        distance = calculate_distance(job_address)
        if distance:
            job.calculated_distance_km = distance
            session.add(job)
            updated.append({"job_id": job.id, "distance_km": float(distance), "address": job_address})
        else:
            failed.append({"job_id": job.id, "reason": "API returned no result", "address": job_address})

    session.commit()

    return {
        "updated": len(updated),
        "failed": len(failed),
        "details": updated,
        "errors": failed,
    }


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    data: JobUpdate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Update a job (manager only)"""
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True, exclude={"assigned_worker_ids", "worker_schedule"})
    for key, value in update_data.items():
        setattr(job, key, value)

    # Handle worker schedule
    if data.worker_schedule is not None:
        # Remove existing schedule entries
        for sched in session.exec(select(JobWorkerSchedule).where(JobWorkerSchedule.job_id == job_id)).all():
            session.delete(sched)
        # Add new schedule entries
        for entry in data.worker_schedule:
            schedule = JobWorkerSchedule(job_id=job_id, worker_id=entry.worker_id, date=entry.date)
            session.add(schedule)
        # Merge worker IDs from schedule and explicit assignments
        schedule_worker_ids = set(e.worker_id for e in data.worker_schedule)
        explicit_ids = set(data.assigned_worker_ids) if data.assigned_worker_ids is not None else set()
        merged_ids = schedule_worker_ids | explicit_ids
        # Replace assigned_worker_ids with merged set
        data.assigned_worker_ids = list(merged_ids) if merged_ids else []

    # Handle worker assignments
    if data.assigned_worker_ids is not None:
        # Remove existing assignments
        session.exec(
            select(JobWorkerLink).where(JobWorkerLink.job_id == job_id)
        )
        for link in session.exec(select(JobWorkerLink).where(JobWorkerLink.job_id == job_id)).all():
            session.delete(link)

        # Add new assignments
        for worker_id in data.assigned_worker_ids:
            link = JobWorkerLink(job_id=job_id, worker_id=worker_id)
            session.add(link)

    # Recalculate distance if address changed
    if data.address_override is not None or data.client_id is not None:
        client = session.get(Client, job.client_id)
        job_address = job.address_override or (client.address if client else "")
        distance = calculate_distance(job_address)
        if distance:
            job.calculated_distance_km = distance

    session.add(job)
    session.commit()
    session.refresh(job)

    # Refresh with relationships
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )
    job = session.exec(statement).first()

    return job_to_response(job)


@router.post("/{job_id}/assign", response_model=JobResponse)
def assign_workers_to_job(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
    worker_ids: list[int] = Body(..., embed=True),
):
    """Assign workers to a job (manager only)"""
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Remove existing assignments
    for link in session.exec(select(JobWorkerLink).where(JobWorkerLink.job_id == job_id)).all():
        session.delete(link)

    # Add new assignments
    for worker_id in worker_ids:
        worker = session.get(Worker, worker_id)
        if worker:
            link = JobWorkerLink(job_id=job_id, worker_id=worker_id)
            session.add(link)

    session.commit()

    # Refresh with relationships
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.client), selectinload(Job.assigned_workers), selectinload(Job.photos), selectinload(Job.worker_schedule))
    )
    job = session.exec(statement).first()

    return job_to_response(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Delete a job (manager only)"""
    job = session.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    session.delete(job)
    session.commit()


@router.post("/{job_id}/photos", response_model=list[JobPhotoResponse], status_code=status.HTTP_201_CREATED)
def upload_job_photos(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
    files: list[UploadFile] = File(...),
):
    """Upload photos to a job (manager only)"""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    uploaded = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' is not an image",
            )

        contents = file.file.read()
        public_url = upload_file_to_s3(
            file_bytes=contents,
            filename=file.filename or "photo.jpg",
            content_type=file.content_type,
            prefix=f"jobs/{job_id}",
        )

        photo = JobPhoto(
            job_id=job_id,
            public_url=public_url,
            content_type=file.content_type,
        )
        session.add(photo)
        session.commit()
        session.refresh(photo)
        uploaded.append(
            JobPhotoResponse(
                id=photo.id,
                public_url=photo.public_url,
                caption=photo.caption,
                uploaded_at=photo.uploaded_at,
            )
        )

    return uploaded


@router.delete("/{job_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_photo(
    job_id: int,
    photo_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Delete a job photo (manager only)"""
    photo = session.exec(
        select(JobPhoto).where(JobPhoto.id == photo_id, JobPhoto.job_id == job_id)
    ).first()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    # Delete from S3
    try:
        delete_file_from_s3(photo.public_url)
    except Exception as e:
        logger.warning(f"Failed to delete S3 object for photo {photo_id}: {e}")

    session.delete(photo)
    session.commit()
