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
    is_redseal: bool
    minimum_hours_override: Decimal | None

    labour_billable_rate: Decimal
    labour_billable: Decimal
    is_billable_trip: bool
    billable_km: Decimal
    billable_km_rate: Decimal
    travel_billable: Decimal
    subtotal_billable: Decimal


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

    total_labour_billable: Decimal
    billable_trip_count: int
    total_billable_km: Decimal
    total_travel_billable: Decimal
    subtotal_billable: Decimal
    gross_profit: Decimal


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

    # Billed to date, summed across every progress invoice on the job, and always
    # reported whichever source won the budget - a part-billed job must still show what
    # has gone out the door. invoice_status is a worst-state-first rollup.
    invoice_count: int
    invoice_subtotal_billed: Decimal | None
    invoice_total: Decimal | None
    invoice_status: str | None

    # Worked value not yet on any invoice, and the timesheets behind it. A non-zero
    # count on a job whose periods look complete means a timesheet was filed late,
    # dated inside a window already billed.
    uninvoiced_billable: Decimal
    uninvoiced_timesheet_count: int

    margin_amount: Decimal | None
    margin_percent: Decimal | None
    is_over_budget: bool

    # Billed-out figures: what these timesheets are worth at the rates the job was
    # quoted at. worker.hourly_rate never contributes to any of these.
    labour_billable: Decimal
    travel_billable: Decimal
    materials_billable: Decimal
    inventory_materials_billable: Decimal
    subtotal_billable: Decimal
    hst_billable: Decimal
    total_billable: Decimal
    billable_km: Decimal
    billable_trip_count: int
    labour_billable_rate: Decimal
    redseal_billable_rate: Decimal
    redseal_hours: Decimal
    redseal_labour_billable: Decimal
    billable_km_rate: Decimal
    rate_source: str
    is_redseal_trade: bool
    estimate_subtotal: Decimal | None

    # Quote variance is budget - billable. It is NOT profit; profit is billable - cost.
    variance_amount: Decimal | None
    variance_percent: Decimal | None
    is_over_quote: bool
    gross_profit_amount: Decimal
    gross_profit_percent: Decimal | None


class JobInvoiceBrief(BaseModel):
    """One invoice on a job, enough to list the progress invoices and their periods."""

    id: int
    invoice_number: str
    created_date: date
    period_start: date | None
    period_end: date | None
    subtotal: Decimal
    total: Decimal
    status: str


class JobFinancialsDetail(JobFinancialsSummary):
    job_address: str
    calculated_distance_km: Decimal | None
    estimate_id: int | None
    estimate_number: str | None
    estimate_status: str | None
    # The most recent invoice, so "open the invoice" still has one target. The amounts
    # below are sums across every invoice on the job.
    invoice_id: int | None
    invoice_number: str | None
    invoice_subtotal: Decimal | None
    # How far the issued invoices sit above the timesheet total - catches dump/admin
    # fees and any manual override applied at invoicing time. Goes NEGATIVE on a
    # part-billed job, where it is exactly the worked value not yet invoiced.
    invoice_extra_fees: Decimal | None
    invoice_variance_amount: Decimal | None
    invoices: list[JobInvoiceBrief]
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

    labour_billable: Decimal
    travel_billable: Decimal
    materials_billable: Decimal
    inventory_materials_billable: Decimal
    subtotal_billable: Decimal
    hst_billable: Decimal
    total_billable: Decimal
    total_gross_profit: Decimal
    total_gross_profit_percent: Decimal | None
    total_variance: Decimal
    total_variance_percent: Decimal | None
    jobs_over_quote: int


class JobFinancialsListResponse(BaseModel):
    jobs: list[JobFinancialsSummary]
    totals: FinancialsTotals
