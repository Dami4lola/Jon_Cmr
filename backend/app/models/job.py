"""
Job model
"""
from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
from datetime import date, time
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .client import Client
    from .worker import Worker
    from .timesheet import Timesheet
    from .invoice import Invoice
    from .inspection import JobInspection


class JobWorkerLink(SQLModel, table=True):
    """Many-to-many link between jobs and workers"""
    __tablename__ = "job_worker_link"

    job_id: int = Field(foreign_key="job.id", primary_key=True)
    worker_id: int = Field(foreign_key="worker.id", primary_key=True)


class Job(SQLModel, table=True):
    """Job/work order model"""
    __tablename__ = "job"

    id: int | None = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    description: str  # Detailed job description

    # Scheduling
    start_date: date | None = Field(default=None, index=True)
    end_date: date | None = Field(default=None)
    scheduled_time: time | None = Field(default=None)
    estimated_duration: Decimal | None = Field(default=None, max_digits=4, decimal_places=2)

    # Status and financials
    is_completed: bool = Field(default=False, index=True)
    estimate_amount: Decimal | None = Field(default=None, max_digits=10, decimal_places=2)

    # Distance calculation
    calculated_distance_km: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)

    # Address override (if None, use client.address)
    address_override: str | None = Field(
        default=None,
        description="Custom job address. If blank, uses client's default address."
    )

    # Relationships
    client: Optional["Client"] = Relationship(back_populates="jobs")
    assigned_workers: List["Worker"] = Relationship(link_model=JobWorkerLink)
    timesheets: List["Timesheet"] = Relationship(back_populates="job")
    invoice: Optional["Invoice"] = Relationship(back_populates="job")
    inspections: List["JobInspection"] = Relationship(back_populates="job")

    def get_job_address(self, client_address: str | None = None) -> str:
        """Returns job address - uses override if set, else client address"""
        if self.address_override:
            return self.address_override
        if client_address:
            return client_address
        if self.client:
            return self.client.address
        return ""
