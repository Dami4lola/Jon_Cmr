"""
Worker model
"""
from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .user import User
    from .job import Job
    from .timesheet import Timesheet
    from .time_off_request import TimeOffRequest


class Worker(SQLModel, table=True):
    """Worker profile linked to a user"""
    __tablename__ = "worker"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    name: str = Field(max_length=100)
    hourly_rate: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    charges_hst: bool = Field(default=False)
    is_employee: bool = Field(default=False)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="worker")
    timesheets: List["Timesheet"] = Relationship(back_populates="worker")
    time_off_requests: List["TimeOffRequest"] = Relationship(back_populates="worker")
