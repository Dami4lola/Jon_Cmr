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
    job_id: int = Field(foreign_key="job.id", unique=True, index=True)
    invoice_number: str = Field(unique=True, index=True, max_length=20)

    # Dates
    created_date: date = Field(default_factory=date.today)
    due_date: date | None = Field(default=None)

    # Amounts
    subtotal: Decimal = Field(max_digits=10, decimal_places=2)
    hst_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    total: Decimal = Field(max_digits=10, decimal_places=2)

    # Status
    status: str = Field(default=InvoiceStatus.DRAFT.value, max_length=10)

    # Notes
    notes: str | None = Field(default=None)

    # Relationships
    job: Optional["Job"] = Relationship(back_populates="invoice")
