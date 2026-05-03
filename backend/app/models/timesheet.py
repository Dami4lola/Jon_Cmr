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
    from .timesheet_inventory_item import TimesheetInventoryItem


class Timesheet(SQLModel, table=True):
    """Timesheet/work log model"""
    __tablename__ = "timesheet"

    id: int | None = Field(default=None, primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", index=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    date: dt.date = Field(index=True)

    # Hours
    hours_worked: Decimal = Field(max_digits=4, decimal_places=2)  # 0.01-24.00
    break_duration: Decimal = Field(default=Decimal("0"), max_digits=4, decimal_places=2)  # hours of break (tracked only)

    # Flags
    used_company_truck: bool = Field(default=False)
    worked_at_hq: bool = Field(default=False)

    # Notes
    notes: str | None = Field(default=None)

    # Expenses
    company_materials: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    personal_materials: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)

    # Minimum hours override (NULL = use default 4hr, 0 = no minimum)
    minimum_hours_override: Decimal | None = Field(default=None, max_digits=4, decimal_places=2)

    # Calculated pay (stored to preserve historical rates)
    calculated_pay: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)

    # Payroll status
    is_paid: bool = Field(default=False, index=True)

    # Timestamps
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

    # Relationships
    worker: Optional["Worker"] = Relationship(back_populates="timesheets")
    job: Optional["Job"] = Relationship(back_populates="timesheets")
    receipts: List["Receipt"] = Relationship(
        back_populates="timesheet",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    inventory_items: List["TimesheetInventoryItem"] = Relationship(
        back_populates="timesheet",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
