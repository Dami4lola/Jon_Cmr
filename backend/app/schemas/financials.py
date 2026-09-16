"""
Job financials schemas - what a job has cost, versus what it is worth.
"""
from pydantic import BaseModel
from decimal import Decimal
from datetime import date


class JobCostLineDetail(BaseModel):
    timesheet_id: int
    date: date
    worker_id: int | None
    worker_name: str
    hours_worked: Decimal
    break_duration: Decimal
    billable_hours: Decimal
    labour_rate: Decimal
    labour_cost: Decimal
    km_distance: Decimal
    km_rate: Decimal
    km_cost: Decimal
    personal_materials: Decimal
    company_materials: Decimal
    subtotal_cost: Decimal
    worked_at_hq: bool
    used_company_truck: bool
    is_paid: bool
    minimum_hours_override: Decimal | None


class JobWorkerCostSummary(BaseModel):
    worker_id: int | None
    worker_name: str
    charges_hst: bool
    hourly_rate: Decimal
    timesheet_count: int
    entries: list[JobCostLineDetail]
    total_hours: Decimal
    total_labour: Decimal
    total_km: Decimal
    total_km_cost: Decimal
    total_personal_materials: Decimal
    total_company_materials: Decimal
    labour_hst: Decimal
    km_hst: Decimal
    materials_hst: Decimal
    total_hst: Decimal
    subtotal_cost: Decimal
    total_cost: Decimal


class JobFinancialsSummary(BaseModel):
    job_id: int
    job_title: str
    client_id: int | None
    client_name: str
    start_date: date | None
    end_date: date | None
    is_completed: bool

    timesheet_count: int
    worker_count: int
    total_hours: Decimal

    labour_cost: Decimal
    travel_cost: Decimal
    personal_materials_cost: Decimal
    company_materials_cost: Decimal
    subtotal_cost: Decimal
    hst_cost: Decimal
    total_cost: Decimal
    unpaid_cost: Decimal

    # budget_amount is the pre-tax side of whichever source won, and is what margin
    # is measured against. estimate_amount and invoice_total are both always
    # populated when known so the UI can show spend against each.
    budget_amount: Decimal | None
    budget_total_with_hst: Decimal | None
    budget_source: str
    estimate_amount: Decimal | None
    invoice_total: Decimal | None
    invoice_status: str | None

    margin_amount: Decimal | None
    margin_percent: Decimal | None
    is_over_budget: bool


class JobFinancialsDetail(JobFinancialsSummary):
    job_address: str
    calculated_distance_km: Decimal | None
    estimate_id: int | None
    estimate_number: str | None
    estimate_status: str | None
    invoice_id: int | None
    invoice_number: str | None
    invoice_subtotal: Decimal | None
    workers: list[JobWorkerCostSummary]


class FinancialsTotals(BaseModel):
    job_count: int
    total_hours: Decimal
    labour_cost: Decimal
    travel_cost: Decimal
    personal_materials_cost: Decimal
    company_materials_cost: Decimal
    subtotal_cost: Decimal
    hst_cost: Decimal
    total_cost: Decimal
    unpaid_cost: Decimal

    # total_budget and total_margin cover only jobs that have a budget, otherwise
    # unbudgeted jobs would drag portfolio margin negative for no reason.
    total_budget: Decimal
    total_margin: Decimal
    total_margin_percent: Decimal | None
    jobs_over_budget: int
    jobs_without_budget: int


class JobFinancialsListResponse(BaseModel):
    jobs: list[JobFinancialsSummary]
    totals: FinancialsTotals
