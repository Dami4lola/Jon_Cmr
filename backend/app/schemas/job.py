"""
Job schemas
"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date, time
from typing import List

from .client import ClientBrief
from .worker import WorkerBrief


class JobCreate(BaseModel):
    """Create job"""
    client_id: int
    description: str = Field(..., min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    scheduled_time: time | None = None
    estimated_duration: Decimal | None = Field(default=None, ge=0, le=99.99)
    estimate_amount: Decimal | None = Field(default=None, ge=0)
    address_override: str | None = None
    is_redseal_trade: bool = False
    assigned_worker_ids: List[int] = []


class JobUpdate(BaseModel):
    """Update job"""
    client_id: int | None = None
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    scheduled_time: time | None = None
    estimated_duration: Decimal | None = None
    is_completed: bool | None = None
    estimate_amount: Decimal | None = None
    address_override: str | None = None
    is_redseal_trade: bool | None = None
    assigned_worker_ids: List[int] | None = None


class JobResponse(BaseModel):
    """Job response"""
    id: int
    description: str
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

    class Config:
        from_attributes = True


class JobBrief(BaseModel):
    """Brief job info for nested responses"""
    id: int
    description: str
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
