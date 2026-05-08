"""
Job schemas
"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date, time, datetime
from typing import List


from .client import ClientBrief
from .worker import WorkerBrief


class WorkerScheduleEntry(BaseModel):
    """Single day assignment for a worker"""
    worker_id: int
    date: date


class JobPhotoResponse(BaseModel):
    """Job photo response"""
    id: int
    public_url: str
    caption: str | None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    """Create job"""
    client_id: int
    title: str = Field(..., min_length=1, max_length=100)
    details: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    scheduled_time: time | None = None
    estimated_duration: Decimal | None = Field(default=None, ge=0, le=99.99)
    estimate_amount: Decimal | None = Field(default=None, ge=0)
    address_override: str | None = None
    is_redseal_trade: bool = False
    assigned_worker_ids: List[int] = []
    worker_schedule: List[WorkerScheduleEntry] = []


class JobUpdate(BaseModel):
    """Update job"""
    client_id: int | None = None
    title: str | None = None
    details: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    scheduled_time: time | None = None
    estimated_duration: Decimal | None = None
    is_completed: bool | None = None
    estimate_amount: Decimal | None = None
    address_override: str | None = None
    is_redseal_trade: bool | None = None
    assigned_worker_ids: List[int] | None = None
    worker_schedule: List[WorkerScheduleEntry] | None = None


class JobResponse(BaseModel):
    """Job response"""
    id: int
    title: str
    details: str | None
    start_date: date | None
    end_date: date | None
    scheduled_time: time | None
    estimated_duration: Decimal | None
    is_completed: bool
    is_redseal_trade: bool
    estimate_amount: Decimal | None
    calculated_distance_km: Decimal | None
    address_override: str | None
    job_address: str  # Resolved address

    # Nested objects
    client: ClientBrief
    assigned_workers: List[WorkerBrief]
    worker_schedule: List[WorkerScheduleEntry] = []
    my_scheduled_dates: List[date] = []
    photos: List[JobPhotoResponse] = []

    class Config:
        from_attributes = True


class JobBrief(BaseModel):
    """Brief job info for nested responses"""
    id: int
    title: str
    client_name: str
    start_date: date | None
    end_date: date | None

    class Config:
        from_attributes = True


class CalendarEvent(BaseModel):
    """Calendar event for job scheduling"""
    id: int
    title: str
    start: date
    end: date | None = None
    time: str | None = None
    duration: str | None = None
    client: str
    address: str
    description: str
    phone_number: str | None = None
    email: str | None = None
    coworkers: list[str] = []
