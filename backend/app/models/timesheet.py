"""
Timesheet model
"""
from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
import datetime as dt
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .worker import Worker
    from .job import Job
    from .receipt import Receipt


class Timesheet(SQLModel, table=True):
    """Timesheet/work log model"""
    __tablename__ = "timesheet"

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    date: dt.date = Field(index=True)

    # Hours and distance
    hours_worked: Decimal = Field(max_digits=4, decimal_places=2)  # 0.01-24.00
    round_trip_kms: Decimal = Field(default=Decimal("0"), max_digits=6, decimal_places=2)

    # Flags
    used_company_truck: bool = Field(default=False)
    worked_at_hq: bool = Field(default=False)

    # Expenses
    company_materials: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    personal_materials: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    receipts_total: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    receipt_card_digits: str | None = Field(default=None, max_length=4)

    # Calculated pay (stored to preserve historical rates)
    calculated_pay: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)

    # Timestamps
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

    # Relationships
    worker: Optional["Worker"] = Relationship(back_populates="timesheets")
    job: Optional["Job"] = Relationship(back_populates="timesheets")
    receipts: List["Receipt"] = Relationship(back_populates="timesheet")
