"""
Timesheet schemas
"""
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
import datetime as dt

from .worker import WorkerBrief
from .job import JobBrief


class TimesheetCreate(BaseModel):
    """Create timesheet"""
    job_id: int
    date: dt.date
    hours_worked: Decimal = Field(..., gt=0, le=24)
    round_trip_kms: Decimal = Field(default=Decimal("0"), ge=0, le=9999.99)
    used_company_truck: bool = False
    worked_at_hq: bool = False
    company_materials: Decimal = Field(default=Decimal("0"), ge=0, le=99999.99)
    personal_materials: Decimal = Field(default=Decimal("0"), ge=0, le=99999.99)
    receipts_total: Decimal = Field(default=Decimal("0"), ge=0, le=99999.99)
    receipt_card_digits: str | None = Field(default=None, max_length=4)

    @field_validator("receipt_card_digits")
    @classmethod
    def validate_card_digits(cls, v):
        if v is not None and v != "":
            if not v.isdigit() or len(v) != 4:
                raise ValueError("Card digits must be exactly 4 numbers")
        return v if v else None


class TimesheetUpdate(BaseModel):
    """Update timesheet"""
    job_id: int | None = None
    date: dt.date | None = None
    hours_worked: Decimal | None = Field(default=None, gt=0, le=24)
    round_trip_kms: Decimal | None = Field(default=None, ge=0, le=9999.99)
    used_company_truck: bool | None = None
    worked_at_hq: bool | None = None
    company_materials: Decimal | None = Field(default=None, ge=0, le=99999.99)
    personal_materials: Decimal | None = Field(default=None, ge=0, le=99999.99)
    receipts_total: Decimal | None = Field(default=None, ge=0, le=99999.99)
    receipt_card_digits: str | None = None


class TimesheetResponse(BaseModel):
    """Timesheet response"""
    id: int
    date: dt.date
    hours_worked: Decimal
    round_trip_kms: Decimal
    used_company_truck: bool
    worked_at_hq: bool
    company_materials: Decimal
    personal_materials: Decimal
    receipts_total: Decimal
    receipt_card_digits: str | None
    calculated_pay: Decimal | None
    created_at: dt.datetime

    # Nested objects
    worker: WorkerBrief
    job: JobBrief

    class Config:
        from_attributes = True


class TimesheetSummary(BaseModel):
    """Summary of timesheets for payroll"""
    total_pay: Decimal
    timesheet_count: int
    total_hours: Decimal


class ReceiptResponse(BaseModel):
    """Receipt response"""
    id: int
    timesheet_id: int
    image_path: str
    image_url: str  # Computed URL for frontend
    description: str | None
    amount: Decimal | None
    uploaded_at: dt.datetime

    class Config:
        from_attributes = True


class PayoutPreview(BaseModel):
    """Preview payout calculation result"""
    hours_worked: Decimal
    rounded_hours: Decimal
    billable_hours: Decimal
    minimum_applied: bool
    labor_cost: Decimal
    hst_applied: bool
    km_reimbursement: Decimal
    personal_materials: Decimal
    receipts_reimbursement: Decimal
    calculated_pay: Decimal
