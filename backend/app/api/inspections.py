"""
Job Inspection API endpoints
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Body
from sqlmodel import select
from sqlalchemy.orm import selectinload
from datetime import datetime
import os
import uuid

from ..config import settings
from ..models import JobInspection, InspectionPhoto, Job, Worker
from ..schemas.inspection import (
    InspectionCreate,
    InspectionUpdate,
    InspectionResponse,
    InspectionPhotoResponse,
)
from ..schemas.job import JobBrief
from .deps import DBSession, CurrentUser, CurrentWorker

router = APIRouter()


def inspection_to_response(inspection: JobInspection) -> InspectionResponse:
    """Convert JobInspection model to response schema"""
    return InspectionResponse(
        id=inspection.id,
        type=inspection.type,
        date=inspection.date,
        customer_name=inspection.customer_name,
        is_company_truck_required=inspection.is_company_truck_required,
        materials_needed=inspection.materials_needed,
        special_tools_needed=inspection.special_tools_needed,
        existing_damage_notes=inspection.existing_damage_notes,
        flooring_protection_needed=inspection.flooring_protection_needed,
        dump_run_required=inspection.dump_run_required,
        customer_keeping_materials=inspection.customer_keeping_materials,
        materials_to_return=inspection.materials_to_return,
        inventory_used=inspection.inventory_used,
        pickup_required=inspection.pickup_required,
        damages_or_quality_concerns=inspection.damages_or_quality_concerns,
        scope_change_notes=inspection.scope_change_notes,
        job=JobBrief(
            id=inspection.job.id,
            title=inspection.job.title,
            client_name=inspection.job.client.name if inspection.job.client else "",
            start_date=inspection.job.start_date,
            end_date=inspection.job.end_date,
        ),
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
            selectinload(JobInspection.photos),
        )
        .order_by(JobInspection.date.desc())
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
        .where(JobInspection.type == inspection_type)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{inspection_type.title()}-inspection already exists for this job",
        )

    # Create inspection
    inspection = JobInspection(
        job_id=job_id,
        type=inspection_type,
        date=data.date,
        customer_name=data.customer_name,
        is_company_truck_required=data.is_company_truck_required,
        materials_needed=data.materials_needed,
        special_tools_needed=data.special_tools_needed,
        existing_damage_notes=data.existing_damage_notes,
        flooring_protection_needed=data.flooring_protection_needed,
        dump_run_required=data.dump_run_required,
        customer_keeping_materials=data.customer_keeping_materials,
        materials_to_return=data.materials_to_return,
        inventory_used=data.inventory_used,
        pickup_required=data.pickup_required,
        damages_or_quality_concerns=data.damages_or_quality_concerns,
        scope_change_notes=data.scope_change_notes,
    )

    session.add(inspection)
    session.commit()
    session.refresh(inspection)

    # Reload with relationships
    statement = (
        select(JobInspection)
        .where(JobInspection.id == inspection.id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.client),
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

    session.add(inspection)
    session.commit()

    # Reload with relationships
    statement = (
        select(JobInspection)
        .where(JobInspection.id == inspection_id)
        .options(
            selectinload(JobInspection.job).selectinload(Job.client),
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
            inspection.type,
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
            inspection.type,
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


@router.put("/photos/{photo_id}", response_model=InspectionPhotoResponse)
def update_inspection_photo(
    photo_id: int,
    session: DBSession,
    current_user: CurrentUser,
    caption: str = Body(None, embed=True),
):
    """Update an inspection photo caption"""
    photo = session.get(InspectionPhoto, photo_id)

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    if caption is not None:
        photo.caption = caption

    session.add(photo)
    session.commit()
    session.refresh(photo)

    return InspectionPhotoResponse(
        id=photo.id,
        inspection_id=photo.inspection_id,
        image_path=photo.image_path,
        caption=photo.caption,
        uploaded_at=photo.uploaded_at,
    )


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
