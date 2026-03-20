"""
Time-off request API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from sqlalchemy.orm import selectinload
import datetime as dt

from ..models import TimeOffRequest, Worker
from ..schemas.time_off_request import (
    TimeOffRequestCreate,
    TimeOffRequestReview,
    TimeOffRequestResponse,
)
from ..schemas.worker import WorkerBrief
from .deps import DBSession, CurrentUser, ManagerUser

router = APIRouter()


def request_to_response(req: TimeOffRequest) -> TimeOffRequestResponse:
    return TimeOffRequestResponse(
        id=req.id,
        worker_id=req.worker_id,
        dates=req.dates,
        reason=req.reason,
        status=req.status,
        manager_note=req.manager_note,
        reviewed_by_id=req.reviewed_by_id,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
        worker=WorkerBrief(id=req.worker.id, name=req.worker.name),
    )


@router.get("/", response_model=list[TimeOffRequestResponse])
def list_time_off_requests(
    session: DBSession,
    current_user: CurrentUser,
    status_filter: str | None = None,
    worker_id: int | None = None,
):
    statement = (
        select(TimeOffRequest)
        .options(selectinload(TimeOffRequest.worker))
    )

    if current_user.is_manager:
        if worker_id:
            statement = statement.where(TimeOffRequest.worker_id == worker_id)
    else:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if worker:
            statement = statement.where(TimeOffRequest.worker_id == worker.id)
        else:
            return []

    if status_filter:
        statement = statement.where(TimeOffRequest.status == status_filter)

    statement = statement.order_by(TimeOffRequest.created_at.desc())
    requests = session.exec(statement).all()
    return [request_to_response(r) for r in requests]


@router.post("/", response_model=TimeOffRequestResponse, status_code=status.HTTP_201_CREATED)
def create_time_off_request(
    data: TimeOffRequestCreate,
    session: DBSession,
    current_user: CurrentUser,
):
    worker = session.exec(
        select(Worker).where(Worker.user_id == current_user.id)
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker profile not found")

    req = TimeOffRequest(
        worker_id=worker.id,
        dates=[d.isoformat() for d in data.dates],
        reason=data.reason,
    )
    session.add(req)
    session.commit()
    session.refresh(req)

    statement = (
        select(TimeOffRequest)
        .where(TimeOffRequest.id == req.id)
        .options(selectinload(TimeOffRequest.worker))
    )
    req = session.exec(statement).one()
    return request_to_response(req)


@router.post("/{request_id}/review", response_model=TimeOffRequestResponse)
def review_time_off_request(
    request_id: int,
    data: TimeOffRequestReview,
    session: DBSession,
    current_user: ManagerUser,
):
    statement = (
        select(TimeOffRequest)
        .where(TimeOffRequest.id == request_id)
        .options(selectinload(TimeOffRequest.worker))
    )
    req = session.exec(statement).first()
    if not req:
        raise HTTPException(status_code=404, detail="Time-off request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request has already been reviewed")

    req.status = data.status
    req.manager_note = data.manager_note
    req.reviewed_by_id = current_user.id
    req.reviewed_at = dt.datetime.utcnow()
    req.updated_at = dt.datetime.utcnow()

    session.add(req)
    session.commit()
    session.refresh(req)
    return request_to_response(req)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_off_request(
    request_id: int,
    session: DBSession,
    current_user: CurrentUser,
):
    req = session.get(TimeOffRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Time-off request not found")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")

    if not current_user.is_manager:
        worker = session.exec(
            select(Worker).where(Worker.user_id == current_user.id)
        ).first()
        if not worker or worker.id != req.worker_id:
            raise HTTPException(status_code=403, detail="Not authorized")

    session.delete(req)
    session.commit()
