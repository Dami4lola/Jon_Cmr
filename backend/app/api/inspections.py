"""
Job Inspection API endpoints
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import datetime
import os
import uuid

from ..config import settings
from ..models import JobInspection, InspectionPhoto, Job, Worker
from ..models.inspection import InspectionStatus
from ..schemas.inspection import (
    InspectionCreate,
    InspectionUpdate,
    InspectionResponse,
    InspectionPhotoResponse,
)
from ..schemas.job import JobBrief
from ..schemas.worker import WorkerBrief
from .deps import DBSession, CurrentUser, CurrentWorker

router = APIRouter()


def inspection_to_response(inspection: JobInspection) -> InspectionResponse:
    """Convert JobInspection model to response schema"""
    return InspectionResponse(
        id=inspection.id,
        inspection_type=inspection.inspection_type,
        inspection_date=inspection.inspection_date,
        inspection_time=inspection.inspection_time,
        status=inspection.status,
        site_conditions=inspection.site_conditions,
        safety_hazards=inspection.safety_hazards,
        notes=inspection.notes,
        client_present=inspection.client_present,
        access_issues=inspection.access_issues,
        existing_damage=inspection.existing_damage,
        work_completed=inspection.work_completed,
        quality_check_passed=inspection.quality_check_passed,
        client_satisfied=inspection.client_satisfied,
        followup_required=inspection.followup_required,
        followup_notes=inspection.followup_notes,
        client_name_signed=inspection.client_name_signed,
        client_signature=inspection.client_signature,
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
        completed_at=inspection.completed_at,
        job=JobBrief(
            id=inspection.job.id,
            description=inspection.job.description,
            client_name=inspection.job.client.name if inspection.job.client else "",
            scheduled_date=inspection.job.scheduled_date,
        ),
        inspector=WorkerBrief(
            id=inspection.inspector.id,
            name=inspection.inspector.name,
        ) if inspection.inspector else None,
        photos=[
            InspectionPhotoResponse(
                id=photo.id,
                image_path=photo.image_path,
                image_url=f"/uploads/{photo.image_path}",
                caption=photo.caption,
                uploaded_at=photo.uploaded_at,
            )
            for photo in inspection.photos
        ],
    )


@router.get("/job/{job_id}", response_model=list[InspectionResponse])
def list_job_inspections(
    job_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """List inspections for a specific job"""
    # Verify job exists
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Authorization check for workers
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()

        if worker:
            # Check if worker is assigned to job
            statement = (
                select(Job)
                .where(Job.id == job_id)
                .options(selectinload(Job.assigned_workers))
            )
            job_with_workers = session.exec(statement).first()
            is_assigned = any(w.id == worker.id for w in job_with_workers.assigned_workers)

            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this job",
                )

    statement = (
        select(JobInspection)
        .where(JobInspection.job_id == job_id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.client),
            selectinload(JobInspection.inspector),
            selectinload(JobInspection.photos),
        )
        .order_by(JobInspection.inspection_date.desc())
    )
    inspections = session.exec(statement).all()

    return [inspection_to_response(insp) for insp in inspections]


@router.post("/job/{job_id}/{inspection_type}", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
def create_inspection(
    job_id: int,
    inspection_type: str,
    data: InspectionCreate,
    session: DBSession,
    current_user: CurrentUser,
):
    """Create a new inspection for a job"""
    # Validate inspection type
    if inspection_type not in ["pre", "post"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inspection type must be 'pre' or 'post'",
        )

    # Get worker profile
    worker = session.exec(
        select(Worker).where(Worker.user_id == current_user.id)
    ).first()

    if not worker and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    # Verify job exists and worker is assigned
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.assigned_workers), selectinload(Job.client))
    )
    job = session.exec(statement).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Check authorization
    if not current_user.is_manager and worker:
        is_assigned = any(w.id == worker.id for w in job.assigned_workers)
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this job",
            )

    # Check if inspection of this type already exists
    existing = session.exec(
        select(JobInspection)
        .where(JobInspection.job_id == job_id)
        .where(JobInspection.inspection_type == inspection_type)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{inspection_type.title()}-inspection already exists for this job",
        )

    # Create inspection
    inspection = JobInspection(
        job_id=job_id,
        inspection_type=inspection_type,
        inspector_id=worker.id if worker else None,
        inspection_date=data.inspection_date,
        inspection_time=data.inspection_time,
        status=data.status,
        site_conditions=data.site_conditions,
        safety_hazards=data.safety_hazards,
        notes=data.notes,
        client_present=data.client_present,
        access_issues=data.access_issues,
        existing_damage=data.existing_damage,
        work_completed=data.work_completed,
        quality_check_passed=data.quality_check_passed,
        client_satisfied=data.client_satisfied,
        followup_required=data.followup_required,
        followup_notes=data.followup_notes,
        client_name_signed=data.client_name_signed,
        client_signature=data.client_signature,
    )

    if inspection.status == InspectionStatus.COMPLETED.value:
        inspection.completed_at = datetime.utcnow()

    session.add(inspection)
    session.commit()
    session.refresh(inspection)

    # Reload with relationships
    statement = (
        select(JobInspection)
        .where(JobInspection.id == inspection.id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.client),
            selectinload(JobInspection.inspector),
            selectinload(JobInspection.photos),
        )
    )
    inspection = session.exec(statement).first()

    return inspection_to_response(inspection)


@router.get("/{inspection_id}", response_model=InspectionResponse)
def get_inspection(
    inspection_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Get a specific inspection"""
    statement = (
        select(JobInspection)
        .where(JobInspection.id == inspection_id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.client),
            selectinload(JobInspection.job).selectinload(Job.assigned_workers),
            selectinload(JobInspection.inspector),
            selectinload(JobInspection.photos),
        )
    )
    inspection = session.exec(statement).first()

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Authorization check
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()

        if worker:
            is_assigned = any(w.id == worker.id for w in inspection.job.assigned_workers)
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this job",
                )

    return inspection_to_response(inspection)


@router.put("/{inspection_id}", response_model=InspectionResponse)
def update_inspection(
    inspection_id: int,
    data: InspectionUpdate,
    session: DBSession,
    current_user: CurrentUser,
):
    """Update an inspection"""
    statement = (
        select(JobInspection)
        .where(JobInspection.id == inspection_id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.assigned_workers),
        )
    )
    inspection = session.exec(statement).first()

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    # Authorization check
    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()

        if worker:
            is_assigned = any(w.id == worker.id for w in inspection.job.assigned_workers)
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this job",
                )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(inspection, key, value)

    inspection.updated_at = datetime.utcnow()

    # Set completed_at if status changed to completed
    if data.status == InspectionStatus.COMPLETED.value and not inspection.completed_at:
        inspection.completed_at = datetime.utcnow()

    session.add(inspection)
    session.commit()

    # Reload with relationships
    statement = (
        select(JobInspection)
        .where(JobInspection.id == inspection_id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.client),
            selectinload(JobInspection.inspector),
            selectinload(JobInspection.photos),
        )
    )
    inspection = session.exec(statement).first()

    return inspection_to_response(inspection)


@router.post("/{inspection_id}/photos")
def upload_inspection_photos(
    inspection_id: int,
    session: DBSession,
    current_user: CurrentUser,
    files: list[UploadFile] = File(...),
):
    """Upload photos to an inspection"""
    inspection = session.get(JobInspection, inspection_id)

    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    uploaded = []
    for file in files:
        # Generate unique filename
        ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        filename = f"{uuid.uuid4()}{ext}"

        # Create directory
        upload_dir = os.path.join(
            settings.UPLOAD_DIR,
            "inspections",
            str(inspection.job_id),
            inspection.inspection_type,
        )
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            content = file.file.read()
            f.write(content)

        # Create photo record (store relative path)
        relative_path = os.path.join(
            "inspections",
            str(inspection.job_id),
            inspection.inspection_type,
            filename,
        )
        photo = InspectionPhoto(
            inspection_id=inspection_id,
            image_path=relative_path,
        )
        session.add(photo)
        uploaded.append({"filename": filename, "path": relative_path})

    session.commit()

    return {"uploaded": len(uploaded), "files": uploaded}


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspection_photo(
    photo_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    """Delete an inspection photo"""
    photo = session.get(InspectionPhoto, photo_id)

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    # Delete file from disk
    full_path = os.path.join(settings.UPLOAD_DIR, photo.image_path)
    if os.path.exists(full_path):
        os.remove(full_path)

    session.delete(photo)
    session.commit()
