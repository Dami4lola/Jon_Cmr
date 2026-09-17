"""
Job money engine - the single source of truth for what a timesheet COSTS the company
and what it BILLS the client.

Extracted from app/api/payroll.py and app/api/invoices.py so that the payout run, the
invoice, and the Job Financials page cannot drift apart. app/services/payout.py and
the cached Timesheet.calculated_pay column are broken legacy and must not be used for
any figure.

The two sides differ in exactly three places:

  labour   cost bills worker.hourly_rate; billing uses the billed-out rate - the Red
           Seal rate when the job is a Red Seal trade OR the worker ticked Red Seal on
           that entry, otherwise LABOUR_RATE
  travel   both sides are per timesheet and both skip HQ days; only the rate differs
           (the own-vehicle cost rate, zero on a company truck, vs the billed km rate).
           Every timesheet is its own round trip
  HST      cost carries subcontractor HST (only when worker.charges_hst); billing
           carries the 13% charged to the client

Materials are identical on both sides - passed through at what was spent, no markup.

Until 2026-09 billing counted one trip per distinct (date, worker) pair and charged a
trip for HQ days, while cost did neither. Both were changed deliberately on request:
an HQ day involves no drive, and a worker who files two timesheets in a day made two
trips. tests/test_invoice_characterization.py was re-baselined in the same commit.

Cost-side invariant, for the same set of timesheets:

    financials.total_cost - company_materials_cost == payroll.grand_total
"""
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from ..models import Job, Timesheet, Worker

KM_RATE_OWN_VEHICLE = Decimal("0.85")
# There is no company-truck rate: a truck day reimburses no travel, because the
# company already paid for the vehicle and the fuel. The client is still billed
# those kilometres - see compute_job_billing, which never reads the truck flag.
HST_RATE = Decimal("0.13")
MINIMUM_HOURS = Decimal("4")

# Billed-out rates, as used by the estimator and the invoice.
LABOUR_RATE = Decimal("80.00")
REDSEAL_RATE = Decimal("100.00")
BILLABLE_KM_RATE = Decimal("1.50")

CENTS = Decimal("0.01")


def q(value: Decimal) -> Decimal:
    """Quantize a money value to cents, half-up."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def rounded_hours_before_minimum(hours_worked: Decimal, break_duration: Decimal = Decimal("0")) -> Decimal:
    """
    Quarter-hour rounded hours net of break, before the minimum floor is applied.

    Exposed so callers can tell whether the floor actually bit, rather than guessing.
    """
    hours_float = float(hours_worked)
    break_float = float(break_duration)
    rounded = (round(hours_float * 4) / 4) - break_float
    return Decimal(str(max(rounded, 0)))


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
    return max(rounded_hours_before_minimum(hours_worked, break_duration), minimum_hours)


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
    is_redseal: bool
    is_paid: bool


def _resolve_worker_identity(timesheet: Timesheet, worker: "Worker | None") -> tuple[str, Decimal, bool]:
    """
    Worker details for a timesheet, tolerating a deleted worker.

    Migration 0018 orphans timesheets instead of cascading the delete, so worker_id
    and the worker relationship can both be None while worker_name_snapshot holds
    the name the entry was filed under.
    """
    if worker is None:
        return (timesheet.worker_name_snapshot or "Unknown worker", Decimal("0"), False)
    return (worker.name, worker.hourly_rate, worker.charges_hst)


def _calculate_travel(timesheet: Timesheet, job: Job | None) -> tuple[Decimal, Decimal, Decimal]:
    """
    Travel distance, rate and cost for one timesheet entry.

    The two zeroing rules are deliberately asymmetric: HQ zeroes the DISTANCE because
    no trip happened, while a company truck zeroes only the RATE because the trip did
    happen and the client is billed for it - the worker simply is not reimbursed.

    Returns (km_distance, km_rate, km_cost).
    """
    if timesheet.worked_at_hq:
        return (Decimal("0"), Decimal("0"), Decimal("0"))

    km_distance = (job.calculated_distance_km or Decimal("0")) if job else Decimal("0")
    if timesheet.used_company_truck:
        return (km_distance, Decimal("0"), Decimal("0"))
    return (km_distance, KM_RATE_OWN_VEHICLE, q(km_distance * KM_RATE_OWN_VEHICLE))


def compute_timesheet_cost(
    timesheet: Timesheet,
    *,
    worker: "Worker | None" = None,
    job: Job | None = None,
) -> TimesheetCost:
    """
    Cost of a single timesheet entry to the company, excluding HST.

    worker and job default to the timesheet's own relationships. Callers holding a
    TRANSIENT timesheet (the payout preview) must pass them explicitly rather than
    assigning them: Job.timesheets cascades all, delete-orphan, so assigning a
    persistent Job would push the unsaved row into that collection and a later flush
    would insert a timesheet nobody submitted.
    """
    worker = worker if worker is not None else timesheet.worker
    job = job if job is not None else timesheet.job
    worker_name, hourly_rate, charges_hst = _resolve_worker_identity(timesheet, worker)

    effective_minimum = (
        timesheet.minimum_hours_override
        if timesheet.minimum_hours_override is not None
        else MINIMUM_HOURS
    )
    billable_hours = _round_hours(timesheet.hours_worked, timesheet.break_duration, effective_minimum)
    labour_cost = q(billable_hours * hourly_rate)

    km_distance, km_rate, km_cost = _calculate_travel(timesheet, job)

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
        is_redseal=timesheet.is_redseal,
        is_paid=timesheet.is_paid,
    )


@dataclass(frozen=True)
class WorkerPayout:
    """What a worker is owed, for a single entry or a whole period."""

    total_labour: Decimal
    total_km_cost: Decimal
    total_personal_materials: Decimal
    charges_hst: bool
    labour_hst: Decimal
    km_hst: Decimal
    materials_hst: Decimal
    grand_total: Decimal


def compute_worker_payout(
    total_labour: Decimal,
    total_km_cost: Decimal,
    total_personal_materials: Decimal,
    charges_hst: bool,
) -> WorkerPayout:
    """
    The only definition of what a worker is paid.

    company_materials is absent by construction: it is stock the company already
    bought, so it is a job cost but never a payout. A caller holding a TimesheetCost
    must pass labour_cost / km_cost / personal_materials, never subtotal_cost.

    Note HST is quantized per component on whatever totals it is given, so summing
    per-entry payouts across many entries can differ from a period run by a cent or
    two. A per-entry payout is exact for the entry it quotes.
    """
    labour_hst, km_hst, materials_hst = compute_worker_hst(
        total_labour, total_km_cost, total_personal_materials, charges_hst
    )
    return WorkerPayout(
        total_labour=total_labour,
        total_km_cost=total_km_cost,
        total_personal_materials=total_personal_materials,
        charges_hst=charges_hst,
        labour_hst=labour_hst,
        km_hst=km_hst,
        materials_hst=materials_hst,
        grand_total=q(
            total_labour + total_km_cost + total_personal_materials
            + labour_hst + km_hst + materials_hst
        ),
    )


def compute_entry_payout(cost: TimesheetCost) -> WorkerPayout:
    """What a single timesheet entry pays, standalone - what the preview quotes."""
    return compute_worker_payout(
        cost.labour_cost, cost.km_cost, cost.personal_materials, cost.charges_hst
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


# ============================================================
# Billing - what a job's timesheets are worth to the client
# ============================================================

@dataclass(frozen=True)
class BillingRates:
    """
    The billed-out rates a job is priced at.

    Resolved per job so a job quoted at a non-default rate is tracked at the rate it
    was actually quoted, rather than at the global default.
    """

    labour_rate: Decimal
    redseal_rate: Decimal
    km_rate: Decimal
    source: str = "default"

    @classmethod
    def defaults(cls) -> "BillingRates":
        return cls(
            labour_rate=LABOUR_RATE,
            redseal_rate=REDSEAL_RATE,
            km_rate=BILLABLE_KM_RATE,
            source="default",
        )

    def labour_rate_for(self, job: Job, timesheet: Timesheet) -> Decimal:
        """
        The rate this entry's hours bill at.

        Either flag triggers the Red Seal rate: a Red Seal job bills every one of its
        hours at it regardless, and on a standard job a worker can tick Red Seal on the
        individual entry. The per-timesheet flag is purely additive - it can never take
        the Red Seal rate away from a Red Seal job.
        """
        if job.is_redseal_trade or timesheet.is_redseal:
            return self.redseal_rate
        return self.labour_rate


@dataclass(frozen=True)
class TimesheetBilling:
    """What a single timesheet entry bills, before tax."""

    timesheet_id: int
    date: dt.date
    worker_id: int | None
    worker_name: str
    billable_hours: Decimal
    labour_rate: Decimal
    labour_billable: Decimal
    personal_materials: Decimal
    company_materials: Decimal
    is_billable_trip: bool
    billable_km: Decimal
    billable_km_rate: Decimal
    travel_billable: Decimal
    subtotal_billable: Decimal


@dataclass(frozen=True)
class JobBilling:
    """What a job's timesheets bill in total."""

    lines: list[TimesheetBilling]
    rates: BillingRates
    total_labour_hours: Decimal
    labour_amount: Decimal
    total_distance_km: Decimal
    km_rate: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    inventory_materials: Decimal
    dump_fee: Decimal
    admin_fee: Decimal
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    billable_trip_count: int
    redseal_hours: Decimal
    redseal_labour_billable: Decimal


def _distribute_residual(values: list[Decimal], total: Decimal) -> list[Decimal]:
    """
    Nudge the largest entry so the parts sum exactly to the authoritative total.

    Per-line figures are a presentation split of a job-level number that was quantized
    once, so without this the breakdown can miss the total by a cent: two workers on a
    10.01 km job give q(15.015) x 2 = 30.04 per line against a billed 30.03.
    """
    residual = total - sum(values)
    if residual == 0 or not values:
        return values
    target = max(range(len(values)), key=lambda i: (values[i], -i))
    adjusted = list(values)
    adjusted[target] += residual
    return adjusted


def compute_job_billing(
    job: Job,
    timesheets: Iterable[Timesheet],
    *,
    rates: BillingRates | None = None,
    dump_fee: Decimal = Decimal("0"),
    admin_fee: Decimal = Decimal("0"),
    include_hst: bool = True,
    minimum_hours: Decimal = MINIMUM_HOURS,
) -> JobBilling:
    """
    Price a job's timesheets at the billed-out rates.

    Timesheets supply only hours, materials, and which worker was on site on which day.
    Every rate comes from `rates`; worker.hourly_rate is never consulted.
    """
    rates = rates or BillingRates.defaults()
    timesheets = list(timesheets)

    per_tech_km = job.calculated_distance_km or Decimal("0")
    # One round trip per timesheet, and none for a day worked at HQ - the same
    # population the cost side charges, only at a different rate.
    billable_trip_count = sum(1 for ts in timesheets if not ts.worked_at_hq)
    # Left unquantized: this raw product is what is stored on the invoice.
    total_distance_km = per_tech_km * billable_trip_count
    travel_amount = q(total_distance_km * rates.km_rate)

    total_labour_hours = Decimal("0")
    labour_raw = Decimal("0")
    redseal_hours = Decimal("0")
    redseal_labour_raw = Decimal("0")
    materials_raw = Decimal("0")
    inventory_raw = Decimal("0")

    per_line_labour: list[Decimal] = []
    per_line_travel: list[Decimal] = []
    partial_lines: list[dict] = []

    for timesheet in timesheets:
        effective_minimum = (
            timesheet.minimum_hours_override
            if timesheet.minimum_hours_override is not None
            else minimum_hours
        )
        billable_hours = _round_hours(timesheet.hours_worked, timesheet.break_duration, effective_minimum)
        # Resolved per line: a standard job can carry individually ticked Red Seal entries.
        labour_rate = rates.labour_rate_for(job, timesheet)
        line_labour_raw = billable_hours * labour_rate

        if labour_rate == rates.redseal_rate:
            redseal_hours += billable_hours
            redseal_labour_raw += line_labour_raw

        total_labour_hours += billable_hours
        labour_raw += line_labour_raw
        materials_raw += timesheet.personal_materials or Decimal("0")
        inventory_raw += timesheet.company_materials or Decimal("0")

        is_billable_trip = not timesheet.worked_at_hq
        billable_km = per_tech_km if is_billable_trip else Decimal("0")

        per_line_labour.append(q(line_labour_raw))
        per_line_travel.append(q(billable_km * rates.km_rate))
        partial_lines.append(
            {
                "timesheet_id": timesheet.id,
                "date": timesheet.date,
                "worker_id": timesheet.worker_id,
                "worker_name": _resolve_worker_identity(timesheet, timesheet.worker)[0],
                "billable_hours": billable_hours,
                "labour_rate": labour_rate,
                "personal_materials": timesheet.personal_materials,
                "company_materials": timesheet.company_materials,
                "is_billable_trip": is_billable_trip,
                "billable_km": billable_km,
                "billable_km_rate": rates.km_rate if is_billable_trip else Decimal("0"),
            }
        )

    # Accumulate raw and quantize once per total, exactly as the invoice does.
    labour_amount = q(labour_raw)
    materials_amount = q(materials_raw)
    inventory_materials = q(inventory_raw)

    per_line_labour = _distribute_residual(per_line_labour, labour_amount)
    per_line_travel = _distribute_residual(per_line_travel, travel_amount)

    lines = [
        TimesheetBilling(
            labour_billable=per_line_labour[index],
            travel_billable=per_line_travel[index],
            subtotal_billable=q(
                per_line_labour[index]
                + per_line_travel[index]
                + partial["personal_materials"]
                + partial["company_materials"]
            ),
            **partial,
        )
        for index, partial in enumerate(partial_lines)
    ]

    subtotal = labour_amount + travel_amount + materials_amount + inventory_materials + dump_fee + admin_fee
    hst_amount = q(subtotal * HST_RATE) if include_hst else Decimal("0")

    return JobBilling(
        lines=lines,
        rates=rates,
        total_labour_hours=total_labour_hours,
        labour_amount=labour_amount,
        total_distance_km=total_distance_km,
        km_rate=rates.km_rate,
        travel_amount=travel_amount,
        materials_amount=materials_amount,
        inventory_materials=inventory_materials,
        dump_fee=dump_fee,
        admin_fee=admin_fee,
        subtotal=subtotal,
        hst_amount=hst_amount,
        total=subtotal + hst_amount,
        billable_trip_count=billable_trip_count,
        redseal_hours=redseal_hours,
        redseal_labour_billable=q(redseal_labour_raw),
    )


def invoice_amounts(billing: JobBilling) -> dict:
    """The billing totals keyed for Invoice(**amounts)."""
    return {
        "total_labour_hours": billing.total_labour_hours,
        "labour_amount": billing.labour_amount,
        "total_distance_km": billing.total_distance_km,
        "km_rate": billing.km_rate,
        "travel_amount": billing.travel_amount,
        "materials_amount": billing.materials_amount,
        "inventory_materials": billing.inventory_materials,
        "dump_fee": billing.dump_fee,
        "admin_fee": billing.admin_fee,
        "subtotal": billing.subtotal,
        "hst_amount": billing.hst_amount,
        "total": billing.total,
    }
