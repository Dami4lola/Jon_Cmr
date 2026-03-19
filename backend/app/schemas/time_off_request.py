"""
Time-off request schemas
"""
from pydantic import BaseModel, Field, model_validator
import datetime as dt

from .worker import WorkerBrief


class TimeOffRequestCreate(BaseModel):
    start_date: dt.date
    end_date: dt.date
    reason: str = Field(..., min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TimeOffRequestReview(BaseModel):
    status: str = Field(..., pattern="^(approved|denied)$")
    manager_note: str | None = Field(default=None, max_length=500)


class TimeOffRequestResponse(BaseModel):
    id: int
    worker_id: int
    start_date: dt.date
    end_date: dt.date
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
