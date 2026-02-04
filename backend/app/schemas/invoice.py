"""
Invoice schemas
"""
from pydantic import BaseModel
from decimal import Decimal
from datetime import date

from .job import JobBrief
from .client import ClientBrief


class InvoiceCreate(BaseModel):
    """Create invoice - mostly auto-generated from job"""
    job_id: int
    notes: str | None = None


class InvoiceResponse(BaseModel):
    """Invoice response"""
    id: int
    invoice_number: str
    created_date: date
    due_date: date | None
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    status: str
    notes: str | None

    # Nested objects
    job: JobBrief
    client: ClientBrief

    class Config:
        from_attributes = True


class InvoiceStatusUpdate(BaseModel):
    """Update invoice status"""
    status: str  # draft, sent, paid, overdue
