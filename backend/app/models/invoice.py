"""
Invoice model
"""
from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
from datetime import date
from typing import TYPE_CHECKING, Optional
from enum import Enum

if TYPE_CHECKING:
    from .job import Job


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"


class Invoice(SQLModel, table=True):
    """Invoice model"""
    __tablename__ = "invoice"

    id: int | None = Field(default=None, primary_key=True)
    # Not unique: a job is billed as many times as it takes. Progress invoices carve
    # the job up by billing period, and a timesheet's single date puts it in exactly
    # one of them.
    job_id: int = Field(foreign_key="job.id", index=True)
    invoice_number: str = Field(unique=True, index=True, max_length=20)

    # Dates
    created_date: date = Field(default_factory=date.today)
    due_date: date | None = Field(default=None)

    # Billing period, both ends inclusive. A null bound is unbounded, so null/null is
    # the whole job - the shape every invoice issued before progress billing carries.
    period_start: date | None = Field(default=None)
    period_end: date | None = Field(default=None)

    # Amounts (aggregates)
    subtotal: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    hst_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    total: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)

    # Charge breakdown (frozen at creation time)
    labour_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    travel_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    materials_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    inventory_materials: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    dump_fee: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    admin_fee: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)

    # Display detail fields
    total_labour_hours: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    # 8 digits, not 6: one trip per timesheet makes >9999.99 km reachable on long jobs.
    total_distance_km: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)

    # Rates frozen at creation. Labour is stored only as an amount otherwise, so an
    # invoice issued before a job's billable rate changed would be unexplainable from
    # any row in the database.
    km_rate: Decimal = Field(default=Decimal("1.50"), max_digits=5, decimal_places=2)
    labour_rate: Decimal = Field(default=Decimal("80.00"), max_digits=6, decimal_places=2)
    redseal_rate: Decimal = Field(default=Decimal("100.00"), max_digits=6, decimal_places=2)

    # Scope of work (narrative description for PDF)
    scope_of_work: str | None = Field(default=None)

    # Status
    status: str = Field(default=InvoiceStatus.DRAFT.value, max_length=10)

    # Notes
    notes: str | None = Field(default=None)

    # Relationships
    job: Optional["Job"] = Relationship(back_populates="invoices")
