"""
Invoice schemas
"""
from pydantic import BaseModel
from decimal import Decimal
from datetime import date

from .job import JobBrief
from .client import ClientBrief


class InvoiceCreate(BaseModel):
    """Create invoice - auto-calculates from job data, manager can override any field"""
    invoice_number: str | None = None
    scope_of_work: str | None = None
    labour_amount: Decimal | None = None
    travel_amount: Decimal | None = None
    materials_amount: Decimal | None = None
    inventory_materials: Decimal | None = None
    dump_fee: Decimal = Decimal("0")
    admin_fee: Decimal = Decimal("0")
    total_labour_hours: Decimal | None = None
    total_distance_km: Decimal | None = None
    km_rate: Decimal = Decimal("1.50")
    include_hst: bool = True
    notes: str | None = None


class InvoicePreview(BaseModel):
    """Preview of auto-calculated invoice amounts before creation"""
    invoice_number: str
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

    # Nested objects
    job: JobBrief
    client: ClientBrief

    class Config:
        from_attributes = True


class InvoiceStatusUpdate(BaseModel):
    """Update invoice status"""
    status: str  # draft, sent, paid, overdue


class InvoiceUpdate(BaseModel):
    """Partial update for an existing invoice"""
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
