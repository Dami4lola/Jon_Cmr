"""
Job API endpoints
"""
from fastapi import APIRouter, HTTPException, status, Body
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ..models import Job, Worker, Client, JobWorkerLink
from ..schemas.job import JobCreate, JobUpdate, JobResponse, CalendarEvent
from ..schemas.client import ClientBrief
from ..schemas.worker import WorkerBrief
from ..services.distance import calculate_distance, get_distance_info
from .deps import DBSession, CurrentUser, CurrentWorker, ManagerUser

router = APIRouter()


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to response schema"""
    return JobResponse(
        id=job.id,
        description=job.description,
        start_date=job.start_date,
        end_date=job.end_date,
        scheduled_time=job.scheduled_time,
        estimated_duration=job.estimated_duration,
        is_completed=job.is_completed,
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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
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
        description=data.description,
        start_date=data.start_date,
        end_date=data.end_date,
        scheduled_time=data.scheduled_time,
        estimated_duration=data.estimated_duration,
        estimate_amount=data.estimate_amount,
        address_override=data.address_override,
    )

    # Calculate distance
    job_address = data.address_override or client.address
    distance = calculate_distance(job_address)
    if distance:
        job.calculated_distance_km = distance

    session.add(job)
    session.commit()

    # Assign workers
    if data.assigned_worker_ids:
        for worker_id in data.assigned_worker_ids:
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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
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
            title=f"{job.client.name} - {job.description[:30]}",
            start=job.start_date,
            end=job.end_date,
            time=job.scheduled_time.strftime("%H:%M") if job.scheduled_time else None,
            duration=str(job.estimated_duration) if job.estimated_duration else None,
            client=job.client.name,
            address=job.get_job_address(),
            description=job.description,
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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True, exclude={"assigned_worker_ids"})
    for key, value in update_data.items():
        setattr(job, key, value)

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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
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
        .options(selectinload(Job.client), selectinload(Job.assigned_workers))
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
