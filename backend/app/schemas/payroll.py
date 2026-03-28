"""
Payroll processing schemas
"""
from pydantic import BaseModel
from decimal import Decimal
from datetime import date


class PayrollProcessRequest(BaseModel):
    start_date: date
    end_date: date
    worker_ids: list[int] | None = None


class PayrollEntryDetail(BaseModel):
    timesheet_id: int
    date: date
    customer_name: str
    job_description: str
    hours_worked: Decimal
    break_duration: Decimal
    billable_hours: Decimal
    labour_rate: Decimal
    labour_cost: Decimal
    km_distance: Decimal
    km_rate: Decimal
    km_cost: Decimal
    personal_materials: Decimal
    minimum_hours_override: Decimal | None


class PayrollWorkerSummary(BaseModel):
    worker_id: int
    worker_name: str
    entries: list[PayrollEntryDetail]
    total_hours: Decimal
    total_labour: Decimal
    total_km: Decimal
    total_km_cost: Decimal
    total_personal_materials: Decimal
    labour_hst: Decimal
    km_hst: Decimal
    materials_hst: Decimal
    grand_total: Decimal
    charges_hst: bool


class PayrollProcessResponse(BaseModel):
    workers_processed: int
    timesheets_archived: int
    worker_summaries: list[PayrollWorkerSummary]
