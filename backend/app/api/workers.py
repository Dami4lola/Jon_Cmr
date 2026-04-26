"""
Worker API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..models import Worker
from ..schemas.worker import WorkerCreate, WorkerUpdate, WorkerResponse
from .deps import DBSession, CurrentUser, ManagerUser

router = APIRouter()


@router.get("/", response_model=list[WorkerResponse])
def list_workers(
    session: DBSession,
    current_user: ManagerUser,  # Only managers can list all workers
    skip: int = 0,
    limit: int = 50,
):
    """List all workers (manager only)"""
    statement = select(Worker).offset(skip).limit(limit)
    workers = session.exec(statement).all()
    return workers


@router.get("/me", response_model=WorkerResponse)
def get_my_worker_profile(
    session: DBSession,
    current_user: CurrentUser,
):
    """Get current user's worker profile"""
    statement = select(Worker).where(Worker.user_id == current_user.id)
    worker = session.exec(statement).first()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    return worker


@router.get("/{worker_id}", response_model=WorkerResponse)
def get_worker(
    worker_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Get a specific worker (manager only)"""
    worker = session.get(Worker, worker_id)

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    return worker


@router.put("/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: int,
    data: WorkerUpdate,
    session: DBSession,
    current_user: ManagerUser,
):
    """Update a worker (manager only)"""
    worker = session.get(Worker, worker_id)

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(worker, key, value)

    session.add(worker)
    session.commit()
    session.refresh(worker)

    return worker
