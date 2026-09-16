"""
Job cost engine - the single source of truth for what a timesheet COSTS the company.

Extracted from app/api/payroll.py so that the payroll payout run and the Job
Financials reporting endpoints cannot drift apart. app/services/payout.py and the
cached Timesheet.calculated_pay column are broken legacy and must not be used for
any cost figure.

Payroll and financials differ in exactly one place: company_materials. It is stock
the company already paid for, so it never reaches the worker's payout, but it is a
real job cost. Financials adds it; payroll does not. That yields the invariant:

    financials.total_cost - company_materials_cost == payroll.grand_total

for the same set of timesheets.
"""
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from ..models import Timesheet

KM_RATE_OWN_VEHICLE = Decimal("0.85")
KM_RATE_COMPANY_TRUCK = Decimal("0.50")
HST_RATE = Decimal("0.13")
MINIMUM_HOURS = Decimal("4")

CENTS = Decimal("0.01")


def q(value: Decimal) -> Decimal:
    """Quantize a money value to cents, half-up."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _round_hours(hours_worked: Decimal, break_duration: Decimal = Decimal("0"), minimum_hours: Decimal = MINIMUM_HOURS) -> Decimal:
    """
    Round raw hours worked to the nearest quarter-hour, subtract break time,
    and enforce a minimum billable floor.

    Rounding uses float round() at 0.25-hour granularity (scale × 4, round, ÷ 4).
    Break is subtracted after rounding. Result is floored at minimum_hours.

    Args:
        hours_worked: Raw hours from the timesheet entry.
        break_duration: Unpaid break time in hours to subtract after rounding.
        minimum_hours: Minimum billable floor (default 4.0 hours).

    Returns:
        Billable hours as a Decimal, >= 0 and >= minimum_hours.
    """
    hours_float = float(hours_worked)
    break_float = float(break_duration)
    rounded = (round(hours_float * 4) / 4) - break_float
    billable = Decimal(str(max(rounded, 0)))
    return max(billable, minimum_hours)


@dataclass(frozen=True)
class TimesheetCost:
    """What a single timesheet entry costs, before any HST."""

    timesheet_id: int
    date: dt.date
    worker_id: int | None
    worker_name: str
    hourly_rate: Decimal
    charges_hst: bool
    hours_worked: Decimal
    break_duration: Decimal
    minimum_hours_override: Decimal | None
    billable_hours: Decimal
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


def _resolve_worker_identity(timesheet: Timesheet) -> tuple[str, Decimal, bool]:
    """
    Worker details for a timesheet, tolerating a deleted worker.

    Migration 0018 orphans timesheets instead of cascading the delete, so worker_id
    and the worker relationship can both be None while worker_name_snapshot holds
    the name the entry was filed under.
    """
    worker = timesheet.worker
    if worker is None:
        return (timesheet.worker_name_snapshot or "Unknown worker", Decimal("0"), False)
    return (worker.name, worker.hourly_rate, worker.charges_hst)


def _calculate_travel(timesheet: Timesheet) -> tuple[Decimal, Decimal, Decimal]:
    """
    Travel distance, rate and cost for one timesheet entry.

    Returns (km_distance, km_rate, km_cost).
    """
    if timesheet.worked_at_hq:
        return (Decimal("0"), Decimal("0"), Decimal("0"))

    job = timesheet.job
    km_distance = (job.calculated_distance_km or Decimal("0")) if job else Decimal("0")
    km_rate = KM_RATE_COMPANY_TRUCK if timesheet.used_company_truck else KM_RATE_OWN_VEHICLE
    return (km_distance, km_rate, q(km_distance * km_rate))


def compute_timesheet_cost(timesheet: Timesheet) -> TimesheetCost:
    """Cost of a single timesheet entry to the company, excluding HST."""
    worker_name, hourly_rate, charges_hst = _resolve_worker_identity(timesheet)

    effective_minimum = (
        timesheet.minimum_hours_override
        if timesheet.minimum_hours_override is not None
        else MINIMUM_HOURS
    )
    billable_hours = _round_hours(timesheet.hours_worked, timesheet.break_duration, effective_minimum)
    labour_cost = q(billable_hours * hourly_rate)

    km_distance, km_rate, km_cost = _calculate_travel(timesheet)

    subtotal_cost = q(
        labour_cost + km_cost + timesheet.personal_materials + timesheet.company_materials
    )

    return TimesheetCost(
        timesheet_id=timesheet.id,
        date=timesheet.date,
        worker_id=timesheet.worker_id,
        worker_name=worker_name,
        hourly_rate=hourly_rate,
        charges_hst=charges_hst,
        hours_worked=timesheet.hours_worked,
        break_duration=timesheet.break_duration,
        minimum_hours_override=timesheet.minimum_hours_override,
        billable_hours=billable_hours,
        labour_cost=labour_cost,
        km_distance=km_distance,
        km_rate=km_rate,
        km_cost=km_cost,
        personal_materials=timesheet.personal_materials,
        company_materials=timesheet.company_materials,
        subtotal_cost=subtotal_cost,
        worked_at_hq=timesheet.worked_at_hq,
        used_company_truck=timesheet.used_company_truck,
        is_paid=timesheet.is_paid,
    )


def compute_worker_hst(
    total_labour: Decimal,
    total_km_cost: Decimal,
    total_personal_materials: Decimal,
    charges_hst: bool,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Subcontractor HST on a worker's summed totals.

    HST is applied to the summed totals rather than per entry, matching how the
    subcontractor actually invoices. company_materials is deliberately absent: a
    subcontractor invoices for what they fronted, not for company-purchased stock.

    Returns (labour_hst, km_hst, materials_hst).
    """
    if not charges_hst:
        return (Decimal("0"), Decimal("0"), Decimal("0"))

    return (
        q(total_labour * HST_RATE),
        q(total_km_cost * HST_RATE),
        q(total_personal_materials * HST_RATE),
    )
