"""
Time-off request model
"""
from sqlmodel import SQLModel, Field, Relationship
import datetime as dt
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .worker import Worker


class TimeOffRequest(SQLModel, table=True):
    __tablename__ = "time_off_request"

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    start_date: dt.date
    end_date: dt.date
    reason: str = Field(max_length=500)
    status: str = Field(default="pending", index=True)
    manager_note: str | None = Field(default=None, max_length=500)
    reviewed_by_id: int | None = Field(default=None, foreign_key="user.id")
    reviewed_at: dt.datetime | None = Field(default=None)
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

    worker: Optional["Worker"] = Relationship(back_populates="time_off_requests")
