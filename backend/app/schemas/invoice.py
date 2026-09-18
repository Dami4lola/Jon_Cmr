"""
Invoice schemas
"""
from pydantic import BaseModel, model_validator
from decimal import Decimal
from datetime import date

from .job import JobBrief
from .client import ClientBrief


class InvoiceCreate(BaseModel):
    """Create invoice - auto-calculates from job data, manager can override any field"""
    invoice_number: str | None = None
    scope_of_work: str | None = None

    # Billing period, both ends inclusive; a null bound is unbounded, so leaving both
    # blank bills the whole job.
    period_start: date | None = None
    period_end: date | None = None
    # Bill a period that another invoice already covers. Off by default because that is
    # double-billing; on for re-issuing after a delete, or picking up a late timesheet.
    allow_overlap: bool = False

    labour_amount: Decimal | None = None
    travel_amount: Decimal | None = None
    materials_amount: Decimal | None = None
    inventory_materials: Decimal | None = None
    dump_fee: Decimal = Decimal("0")
    admin_fee: Decimal = Decimal("0")
    total_labour_hours: Decimal | None = None
    total_distance_km: Decimal | None = None
    # Rate overrides for this one invoice. None means take the job's resolved rate -
    # never a literal default, which would silently overwrite it on every request that
    # omitted the field.
    km_rate: Decimal | None = None
    labour_rate: Decimal | None = None
    redseal_rate: Decimal | None = None
    include_hst: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def check_period_order(self) -> "InvoiceCreate":
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("period_end cannot be before period_start")
        return self


class InvoicePreview(BaseModel):
    """Preview of auto-calculated invoice amounts before creation"""
    invoice_number: str
    period_start: date | None
    period_end: date | None
    timesheet_count: int
    labour_hours: Decimal
    labour_amount: Decimal
    travel_km: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    inventory_materials: Decimal
    admin_fee: Decimal
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    labour_rate: Decimal
    redseal_rate: Decimal
    km_rate: Decimal
    rate_source: str
    # Invoices already covering part of this period, so the dialog can warn without a
    # second round trip.
    overlapping_invoice_numbers: list[str] = []


class InvoiceResponse(BaseModel):
    """Invoice response"""
    id: int
    job_id: int
    invoice_number: str
    created_date: date
    due_date: date | None
    period_start: date | None
    period_end: date | None
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    status: str
    notes: str | None

    # Charge breakdown
    scope_of_work: str | None
    labour_amount: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    inventory_materials: Decimal
    dump_fee: Decimal
    admin_fee: Decimal
    total_labour_hours: Decimal
    total_distance_km: Decimal
    km_rate: Decimal
    labour_rate: Decimal
    redseal_rate: Decimal

    # Nested objects
    job: JobBrief
    client: ClientBrief

    class Config:
        from_attributes = True


class InvoiceStatusUpdate(BaseModel):
    """Update invoice status"""
    status: str  # draft, sent, paid, overdue


class InvoiceUpdate(BaseModel):
    """
    Partial update for an existing invoice.

    The billing period is deliberately absent: this endpoint recomputes totals from the
    stored amount columns and never re-reads timesheets, so editing the period here
    would print a period that disagrees with the amounts beside it. Re-scope an invoice
    by deleting it and creating it again.
    """
    labour_amount: Decimal | None = None
    travel_amount: Decimal | None = None
    materials_amount: Decimal | None = None
    inventory_materials: Decimal | None = None
    dump_fee: Decimal | None = None
    admin_fee: Decimal | None = None
    total_labour_hours: Decimal | None = None
    total_distance_km: Decimal | None = None
    km_rate: Decimal | None = None
    scope_of_work: str | None = None
    notes: str | None = None
    include_hst: bool | None = None
