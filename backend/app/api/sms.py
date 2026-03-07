"""
SMS API endpoints
"""
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from pydantic import BaseModel
from datetime import datetime

from ..models import SmsLog
from .deps import DBSession, ManagerUser

router = APIRouter()


class SmsLogResponse(BaseModel):
    id: int
    job_id: int
    client_id: int
    phone_number: str
    message_body: str
    status: str
    twilio_sid: str | None
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/log", response_model=list[SmsLogResponse])
def list_sms_logs(
    session: DBSession,
    current_user: ManagerUser,
):
    """List all SMS logs (manager only)"""
    logs = session.exec(
        select(SmsLog).order_by(SmsLog.created_at.desc()).limit(100)
    ).all()
    return logs


@router.get("/jobs/{job_id}/log", response_model=list[SmsLogResponse])
def get_job_sms_log(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Get SMS log for a specific job (manager only)"""
    logs = session.exec(
        select(SmsLog)
        .where(SmsLog.job_id == job_id)
        .order_by(SmsLog.created_at.desc())
    ).all()
    return logs
