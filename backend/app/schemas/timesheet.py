"""
Timesheet schemas
"""
from pydantic import BaseModel, Field
from decimal import Decimal
import datetime as dt

from .worker import WorkerBrief
from .job import JobBrief


class TimesheetCreate(BaseModel):
    """Create timesheet"""
    job_id: int
    date: dt.date
    hours_worked: Decimal = Field(..., gt=0, le=24)
    break_duration: Decimal = Field(default=Decimal("0"), ge=0, le=24)
    used_company_truck: bool = False
    worked_at_hq: bool = False
    company_materials: Decimal = Field(default=Decimal("0"), ge=0, le=99999.99)
    personal_materials: Decimal = Field(default=Decimal("0"), ge=0, le=99999.99)


class TimesheetUpdate(BaseModel):
    """Update timesheet"""
    job_id: int | None = None
    date: dt.date | None = None
    hours_worked: Decimal | None = Field(default=None, gt=0, le=24)
    break_duration: Decimal | None = Field(default=None, ge=0, le=24)
    used_company_truck: bool | None = None
    worked_at_hq: bool | None = None
    company_materials: Decimal | None = Field(default=None, ge=0, le=99999.99)
    personal_materials: Decimal | None = Field(default=None, ge=0, le=99999.99)


class TimesheetResponse(BaseModel):
    """Timesheet response"""
    id: int
    date: dt.date
    hours_worked: Decimal
    break_duration: Decimal
    used_company_truck: bool
    worked_at_hq: bool
    company_materials: Decimal
    personal_materials: Decimal
    calculated_pay: Decimal | None
    is_paid: bool
    receipt_count: int = 0
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
    image_url: str  # Public S3 URL
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
    break_duration: Decimal
    personal_materials: Decimal
    calculated_pay: Decimal
