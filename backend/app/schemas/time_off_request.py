"""
Time-off request schemas
"""
from pydantic import BaseModel, Field, field_validator
import datetime as dt

from .worker import WorkerBrief


class TimeOffRequestCreate(BaseModel):
    dates: list[dt.date] = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("dates")
    @classmethod
    def validate_dates(cls, v: list[dt.date]) -> list[dt.date]:
        unique = sorted(set(v))
        if len(unique) != len(v):
            v = unique
        return sorted(v)


class TimeOffRequestReview(BaseModel):
    status: str = Field(..., pattern="^(approved|denied)$")
    manager_note: str | None = Field(default=None, max_length=500)


class TimeOffRequestResponse(BaseModel):
    id: int
    worker_id: int
    start_date: dt.date
    end_date: dt.date
    dates: list[str]
    reason: str
    status: str
    manager_note: str | None
    reviewed_by_id: int | None
    reviewed_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime

    worker: WorkerBrief

    class Config:
        from_attributes = True
