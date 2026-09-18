"""
Job financials API endpoints - what each job has cost, versus what it is worth.

Cost is derived from the timesheets workers filed against the job, using the shared
engine in services/job_cost.py so these figures cannot drift from what payroll
actually pays out.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ..models import Job, Timesheet
from ..schemas.financials import (
    JobCostLineDetail,
    JobInvoiceBrief,
    JobWorkerCostSummary,
    JobFinancialsSummary,
    JobFinancialsDetail,
    FinancialsTotals,
    JobFinancialsListResponse,
)
from ..services.job_cost import (
    compute_job_billing,
    compute_timesheet_cost,
    compute_worker_hst,
    date_in_period,
    q,
    resolve_billing_rates,
)
from .deps import DBSession, ManagerUser

router = APIRouter()

TENTHS = Decimal("0.1")

BUDGET_SOURCE_INVOICE = "invoice"
BUDGET_SOURCE_ESTIMATE = "estimate"
BUDGET_SOURCE_JOB_FIELD = "job_estimate_amount"
BUDGET_SOURCE_NONE = "none"


def _job_query():
    """
    Base job query with everything job costing reads, eager-loaded.

    selectinload issues one extra SELECT per relationship rather than one per row,
    so this stays at a flat handful of queries no matter how many jobs match.
    joinedload would cartesian the timesheet collection against client/invoice.
    """
    return select(Job).options(
        selectinload(Job.client),
        selectinload(Job.invoices),
        selectinload(Job.estimate),
        selectinload(Job.timesheets).selectinload(Timesheet.worker),
    )


def _uninvoiced_timesheets(job: Job) -> list[Timesheet]:
    """
    Timesheets that fall inside no invoice's billing period.

    The signal for work that has been done but not billed. It is coverage by date, so it
    does NOT catch a timesheet filed after an invoice went out but dated inside the
    period that invoice covered - that one surfaces as invoice_variance_amount going
    negative, the invoice having billed less than its own period is now worth.

    Pure Python over relationships _job_query already eager-loads, so no extra query.
    """
    return [
        timesheet
        for timesheet in job.timesheets
        if not any(
            date_in_period(timesheet.date, invoice.period_start, invoice.period_end)
            for invoice in job.invoices
        )
    ]


def _rollup_invoice_status(invoices: list) -> str | None:
    """
    One status across several progress invoices, worst state first.

    Anything overdue makes the job overdue; otherwise a draft still sitting unsent
    outranks money already sent or collected. The per-invoice truth ships alongside in
    the detail response.
    """
    if not invoices:
        return None
    statuses = {invoice.status for invoice in invoices}
    for state in ("overdue", "draft", "sent"):
        if state in statuses:
            return state
    return "paid"


def _resolve_budget(job: Job) -> dict:
    """
    Decide what this job is worth, and by which source.

    Precedence is invoices, then a full Estimate record, then the hand-typed
    Job.estimate_amount. Issued invoices are what was actually billed, so they beat a
    forecast; and Estimate.total is recomputed from its child rows on every save
    whereas Job.estimate_amount is typed once and never re-synced.

    Invoices only win once they cover EVERY timesheet. Cost is whole-job and cannot be
    split by billing period, so measuring it against a job that is only half billed
    would report a loss on every job mid-progress-billing. Until then the estimate is
    the honest comparison, and the amounts actually billed are reported separately.

    Margin compares the PRE-TAX side of both. HST is a pass-through in both
    directions - remitted on client invoices, reclaimed as an input tax credit on
    subcontractor HST - so mixing tax into either side invents a margin that is not
    real.
    """
    invoices = job.invoices
    estimate = job.estimate

    if estimate is not None:
        estimate_amount = estimate.total
        estimate_subtotal = estimate.subtotal
    elif job.estimate_amount is not None:
        estimate_amount = job.estimate_amount
        estimate_subtotal = job.estimate_amount
    else:
        estimate_amount = None
        estimate_subtotal = None

    invoiced_subtotal = sum((invoice.subtotal for invoice in invoices), Decimal("0"))
    invoiced_total = sum((invoice.total for invoice in invoices), Decimal("0"))
    fully_invoiced = bool(invoices) and not _uninvoiced_timesheets(job)

    if fully_invoiced:
        budget_amount = invoiced_subtotal
        budget_total_with_hst = invoiced_total
        budget_source = BUDGET_SOURCE_INVOICE
    elif estimate is not None:
        budget_amount = estimate_subtotal
        budget_total_with_hst = estimate_amount
        budget_source = BUDGET_SOURCE_ESTIMATE
    elif job.estimate_amount is not None:
        budget_amount = job.estimate_amount
        budget_total_with_hst = job.estimate_amount
        budget_source = BUDGET_SOURCE_JOB_FIELD
    else:
        budget_amount = None
        budget_total_with_hst = None
        budget_source = BUDGET_SOURCE_NONE

    return {
        "budget_amount": budget_amount,
        "budget_total_with_hst": budget_total_with_hst,
        "budget_source": budget_source,
        "estimate_amount": estimate_amount,
        "invoice_count": len(invoices),
        "invoice_subtotal_billed": invoiced_subtotal if invoices else None,
        "invoice_total": invoiced_total if invoices else None,
        "invoice_status": _rollup_invoice_status(invoices),
    }


def _calculate_variance(budget_amount: Decimal | None, subtotal_billable: Decimal) -> dict:
    """
    How far the work billed so far sits from what was quoted.

    This is NOT profit - profit compares billable against cost, not against the quote.
    Negative means we are billing above what we quoted.
    """
    if budget_amount is None:
        return {"variance_amount": None, "variance_percent": None, "is_over_quote": False}

    variance_amount = q(budget_amount - subtotal_billable)
    variance_percent = (
        None
        if budget_amount == 0
        else (variance_amount / budget_amount * Decimal("100")).quantize(
            TENTHS, rounding=ROUND_HALF_UP
        )
    )

    return {
        "variance_amount": variance_amount,
        "variance_percent": variance_percent,
        "is_over_quote": subtotal_billable > budget_amount,
    }


def _calculate_gross_profit(subtotal_billable: Decimal, subtotal_cost: Decimal) -> dict:
    """Real profit: what we charge minus what we pay, both pre-tax."""
    gross_profit_amount = q(subtotal_billable - subtotal_cost)
    gross_profit_percent = (
        None
        if subtotal_billable == 0
        else (gross_profit_amount / subtotal_billable * Decimal("100")).quantize(
            TENTHS, rounding=ROUND_HALF_UP
        )
    )
    return {
        "gross_profit_amount": gross_profit_amount,
        "gross_profit_percent": gross_profit_percent,
    }


def _calculate_margin(budget_amount: Decimal | None, subtotal_cost: Decimal) -> dict:
    """Margin of a pre-tax budget over pre-tax cost, tolerating an absent or zero budget."""
    if budget_amount is None:
        return {"margin_amount": None, "margin_percent": None, "is_over_budget": False}

    margin_amount = q(budget_amount - subtotal_cost)
    margin_percent = (
        None
        if budget_amount == 0
        else (margin_amount / budget_amount * Decimal("100")).quantize(
            TENTHS, rounding=ROUND_HALF_UP
        )
    )

    return {
        "margin_amount": margin_amount,
        "margin_percent": margin_percent,
        "is_over_budget": subtotal_cost > budget_amount,
    }


def _build_worker_summaries(job: Job, billing) -> list[JobWorkerCostSummary]:
    """
    Per-worker cost and billable breakdown for a job.

    Grouped on (worker_id, worker_name) rather than worker_id alone: deleted workers
    all share a null worker_id, and collapsing two of them into one row would
    misattribute cost. Billing now charges a trip per timesheet, so the grouping here
    and the trip assignment in compute_job_billing finally agree.
    """
    billing_by_timesheet = {line.timesheet_id: line for line in billing.lines}

    grouped: dict[tuple[int | None, str], list] = defaultdict(list)
    for timesheet in job.timesheets:
        cost = compute_timesheet_cost(timesheet)
        grouped[(cost.worker_id, cost.worker_name)].append(cost)

    summaries: list[JobWorkerCostSummary] = []

    for (worker_id, worker_name), costs in grouped.items():
        bills = [billing_by_timesheet[cost.timesheet_id] for cost in costs]
        entries = [
            JobCostLineDetail(
                timesheet_id=cost.timesheet_id,
                date=cost.date,
                worker_id=cost.worker_id,
                worker_name=cost.worker_name,
                hours_worked=cost.hours_worked,
                break_duration=cost.break_duration,
                billable_hours=cost.billable_hours,
                labour_rate=cost.hourly_rate,
                labour_cost=cost.labour_cost,
                km_distance=cost.km_distance,
                km_rate=cost.km_rate,
                km_cost=cost.km_cost,
                personal_materials=cost.personal_materials,
                company_materials=cost.company_materials,
                subtotal_cost=cost.subtotal_cost,
                worked_at_hq=cost.worked_at_hq,
                used_company_truck=cost.used_company_truck,
                is_paid=cost.is_paid,
                is_redseal=cost.is_redseal,
                minimum_hours_override=cost.minimum_hours_override,
                labour_billable_rate=bill.labour_rate,
                labour_billable=bill.labour_billable,
                is_billable_trip=bill.is_billable_trip,
                billable_km=bill.billable_km,
                billable_km_rate=bill.billable_km_rate,
                travel_billable=bill.travel_billable,
                subtotal_billable=bill.subtotal_billable,
            )
            for cost, bill in zip(costs, bills)
        ]

        total_hours = sum((c.billable_hours for c in costs), Decimal("0"))
        total_labour = sum((c.labour_cost for c in costs), Decimal("0"))
        total_km = sum((c.km_distance for c in costs), Decimal("0"))
        total_km_cost = sum((c.km_cost for c in costs), Decimal("0"))
        total_personal_materials = sum((c.personal_materials for c in costs), Decimal("0"))
        total_company_materials = sum((c.company_materials for c in costs), Decimal("0"))

        charges_hst = costs[0].charges_hst
        labour_hst, km_hst, materials_hst = compute_worker_hst(
            total_labour, total_km_cost, total_personal_materials, charges_hst
        )
        total_hst = q(labour_hst + km_hst + materials_hst)

        subtotal_cost = q(
            total_labour + total_km_cost + total_personal_materials + total_company_materials
        )

        total_labour_billable = sum((b.labour_billable for b in bills), Decimal("0"))
        total_travel_billable = sum((b.travel_billable for b in bills), Decimal("0"))
        subtotal_billable = q(
            total_labour_billable
            + total_travel_billable
            + total_personal_materials
            + total_company_materials
        )

        summaries.append(
            JobWorkerCostSummary(
                worker_id=worker_id,
                worker_name=worker_name,
                charges_hst=charges_hst,
                hourly_rate=costs[0].hourly_rate,
                timesheet_count=len(costs),
                entries=sorted(entries, key=lambda e: e.date, reverse=True),
                total_hours=total_hours,
                total_labour=total_labour,
                total_km=total_km,
                total_km_cost=total_km_cost,
                total_personal_materials=total_personal_materials,
                total_company_materials=total_company_materials,
                labour_hst=labour_hst,
                km_hst=km_hst,
                materials_hst=materials_hst,
                total_hst=total_hst,
                subtotal_cost=subtotal_cost,
                total_cost=q(subtotal_cost + total_hst),
                total_labour_billable=total_labour_billable,
                billable_trip_count=sum(1 for b in bills if b.is_billable_trip),
                total_billable_km=sum((b.billable_km for b in bills), Decimal("0")),
                total_travel_billable=total_travel_billable,
                subtotal_billable=subtotal_billable,
                gross_profit=q(subtotal_billable - subtotal_cost),
            )
        )

    return sorted(summaries, key=lambda s: s.subtotal_billable, reverse=True)


def _build_job_financials(job: Job) -> tuple[dict, list[JobWorkerCostSummary]]:
    """
    Roll a job's timesheets up into the fields shared by the list row and the detail
    view, so the two can never disagree. A job with no timesheets is a valid zero.
    """
    rates = resolve_billing_rates(job)
    billing = compute_job_billing(job, job.timesheets, rates=rates)
    workers = _build_worker_summaries(job, billing)

    labour_cost = q(sum((w.total_labour for w in workers), Decimal("0")))
    travel_cost = q(sum((w.total_km_cost for w in workers), Decimal("0")))
    personal_materials_cost = q(sum((w.total_personal_materials for w in workers), Decimal("0")))
    company_materials_cost = q(sum((w.total_company_materials for w in workers), Decimal("0")))
    hst_cost = q(sum((w.total_hst for w in workers), Decimal("0")))
    subtotal_cost = q(
        labour_cost + travel_cost + personal_materials_cost + company_materials_cost
    )

    unpaid_cost = q(
        sum(
            (entry.subtotal_cost for worker in workers for entry in worker.entries if not entry.is_paid),
            Decimal("0"),
        )
    )

    uninvoiced = _uninvoiced_timesheets(job)
    budget = _resolve_budget(job)
    subtotal_billable = billing.subtotal
    invoiced_subtotal = budget.pop("invoice_subtotal_billed") or Decimal("0")

    fields = {
        "job_id": job.id,
        "job_title": job.title,
        "client_id": job.client_id,
        "client_name": job.client.name if job.client else "Unknown",
        "start_date": job.start_date,
        "end_date": job.end_date,
        "is_completed": job.is_completed,
        "timesheet_count": len(job.timesheets),
        "worker_count": len(workers),
        "total_hours": sum((w.total_hours for w in workers), Decimal("0")),
        "labour_cost": labour_cost,
        "travel_cost": travel_cost,
        "personal_materials_cost": personal_materials_cost,
        "company_materials_cost": company_materials_cost,
        "subtotal_cost": subtotal_cost,
        "hst_cost": hst_cost,
        "total_cost": q(subtotal_cost + hst_cost),
        "unpaid_cost": unpaid_cost,
        "labour_billable": billing.labour_amount,
        "travel_billable": billing.travel_amount,
        "materials_billable": billing.materials_amount,
        "inventory_materials_billable": billing.inventory_materials,
        "subtotal_billable": subtotal_billable,
        "hst_billable": billing.hst_amount,
        "total_billable": billing.total,
        "billable_km": billing.total_distance_km,
        "billable_trip_count": billing.billable_trip_count,
        "labour_billable_rate": rates.labour_rate,
        "redseal_billable_rate": rates.redseal_rate,
        "redseal_hours": billing.redseal_hours,
        "redseal_labour_billable": billing.redseal_labour_billable,
        "billable_km_rate": rates.km_rate,
        "rate_source": rates.source,
        "is_redseal_trade": job.is_redseal_trade,
        "estimate_subtotal": job.estimate.subtotal if job.estimate else None,
        "invoice_subtotal_billed": invoiced_subtotal if job.invoices else None,
        # Priced from the uncovered timesheets themselves rather than by subtracting
        # what was invoiced, so a dump fee or a manual override on one invoice cannot
        # disguise work that has not been billed.
        "uninvoiced_billable": (
            compute_job_billing(job, uninvoiced, rates=rates).subtotal
            if uninvoiced else Decimal("0")
        ),
        "uninvoiced_timesheet_count": len(uninvoiced),
        **budget,
        **_calculate_margin(budget["budget_amount"], subtotal_cost),
        **_calculate_variance(budget["budget_amount"], subtotal_billable),
        **_calculate_gross_profit(subtotal_billable, subtotal_cost),
    }

    return fields, workers


def _build_totals(summaries: list[JobFinancialsSummary]) -> FinancialsTotals:
    """Portfolio rollup. Budget and margin cover only the jobs that have a budget."""
    budgeted = [s for s in summaries if s.budget_amount is not None]
    total_budget = sum((s.budget_amount for s in budgeted), Decimal("0"))
    budgeted_cost = sum((s.subtotal_cost for s in budgeted), Decimal("0"))
    total_margin = q(total_budget - budgeted_cost)

    subtotal_cost = q(sum((s.subtotal_cost for s in summaries), Decimal("0")))
    hst_cost = q(sum((s.hst_cost for s in summaries), Decimal("0")))

    subtotal_billable = q(sum((s.subtotal_billable for s in summaries), Decimal("0")))
    hst_billable = q(sum((s.hst_billable for s in summaries), Decimal("0")))
    budgeted_billable = sum((s.subtotal_billable for s in budgeted), Decimal("0"))
    total_variance = q(total_budget - budgeted_billable)
    total_gross_profit = q(subtotal_billable - subtotal_cost)

    return FinancialsTotals(
        job_count=len(summaries),
        total_hours=sum((s.total_hours for s in summaries), Decimal("0")),
        labour_cost=q(sum((s.labour_cost for s in summaries), Decimal("0"))),
        travel_cost=q(sum((s.travel_cost for s in summaries), Decimal("0"))),
        personal_materials_cost=q(
            sum((s.personal_materials_cost for s in summaries), Decimal("0"))
        ),
        company_materials_cost=q(
            sum((s.company_materials_cost for s in summaries), Decimal("0"))
        ),
        subtotal_cost=subtotal_cost,
        hst_cost=hst_cost,
        total_cost=q(subtotal_cost + hst_cost),
        unpaid_cost=q(sum((s.unpaid_cost for s in summaries), Decimal("0"))),
        total_budget=q(total_budget),
        total_margin=total_margin,
        total_margin_percent=(
            None
            if total_budget == 0
            else (total_margin / total_budget * Decimal("100")).quantize(
                TENTHS, rounding=ROUND_HALF_UP
            )
        ),
        jobs_over_budget=sum(1 for s in summaries if s.is_over_budget),
        jobs_without_budget=len(summaries) - len(budgeted),
        labour_billable=q(sum((s.labour_billable for s in summaries), Decimal("0"))),
        travel_billable=q(sum((s.travel_billable for s in summaries), Decimal("0"))),
        materials_billable=q(sum((s.materials_billable for s in summaries), Decimal("0"))),
        inventory_materials_billable=q(
            sum((s.inventory_materials_billable for s in summaries), Decimal("0"))
        ),
        subtotal_billable=subtotal_billable,
        hst_billable=hst_billable,
        total_billable=q(subtotal_billable + hst_billable),
        total_gross_profit=total_gross_profit,
        total_gross_profit_percent=(
            None
            if subtotal_billable == 0
            else (total_gross_profit / subtotal_billable * Decimal("100")).quantize(
                TENTHS, rounding=ROUND_HALF_UP
            )
        ),
        total_variance=total_variance,
        total_variance_percent=(
            None
            if total_budget == 0
            else (total_variance / total_budget * Decimal("100")).quantize(
                TENTHS, rounding=ROUND_HALF_UP
            )
        ),
        jobs_over_quote=sum(1 for s in summaries if s.is_over_quote),
    )


@router.get("/jobs", response_model=JobFinancialsListResponse)
def list_job_financials(
    session: DBSession,
    current_user: ManagerUser,
    completed: bool | None = None,
    client_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    has_timesheets_only: bool = False,
    skip: int = 0,
    limit: int = 200,
):
    """
    Cost, budget and margin for every job. Manager only.

    Totals are computed over the whole filtered set before the page is sliced, so
    the headline figures stay correct when the list paginates.
    """
    statement = _job_query().order_by(Job.start_date.desc())

    if completed is not None:
        statement = statement.where(Job.is_completed == completed)
    if client_id is not None:
        statement = statement.where(Job.client_id == client_id)
    if start_date is not None:
        statement = statement.where(Job.start_date >= start_date)
    if end_date is not None:
        statement = statement.where(Job.start_date <= end_date)

    jobs = session.exec(statement).all()

    summaries: list[JobFinancialsSummary] = []
    for job in jobs:
        if has_timesheets_only and not job.timesheets:
            continue
        fields, _ = _build_job_financials(job)
        summaries.append(JobFinancialsSummary(**fields))

    return JobFinancialsListResponse(
        jobs=summaries[skip : skip + limit],
        totals=_build_totals(summaries),
    )


@router.get("/jobs/{job_id}", response_model=JobFinancialsDetail)
def get_job_financials(
    job_id: int,
    session: DBSession,
    current_user: ManagerUser,
):
    """Full cost breakdown for one job, by worker and by timesheet. Manager only."""
    job = session.exec(_job_query().where(Job.id == job_id)).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    fields, workers = _build_job_financials(job)
    estimate = job.estimate
    invoices = job.invoices
    # The most recent invoice, so the single-invoice affordances on the page keep
    # working; the sums beside them cover every progress invoice.
    latest = max(invoices, key=lambda inv: (inv.created_date, inv.id)) if invoices else None
    invoiced_subtotal = sum((inv.subtotal for inv in invoices), Decimal("0"))

    return JobFinancialsDetail(
        **fields,
        job_address=job.get_job_address(job.client.address if job.client else None),
        calculated_distance_km=job.calculated_distance_km,
        estimate_id=estimate.id if estimate else None,
        estimate_number=estimate.estimate_number if estimate else None,
        estimate_status=estimate.status if estimate else None,
        invoice_id=latest.id if latest else None,
        invoice_number=latest.invoice_number if latest else None,
        invoice_subtotal=invoiced_subtotal if invoices else None,
        invoice_extra_fees=(
            sum((inv.dump_fee + inv.admin_fee for inv in invoices), Decimal("0"))
            if invoices else None
        ),
        invoice_variance_amount=(
            q(invoiced_subtotal - fields["subtotal_billable"]) if invoices else None
        ),
        invoices=[
            JobInvoiceBrief(
                id=inv.id,
                invoice_number=inv.invoice_number,
                created_date=inv.created_date,
                period_start=inv.period_start,
                period_end=inv.period_end,
                subtotal=inv.subtotal,
                total=inv.total,
                status=inv.status,
            )
            for inv in invoices
        ],
        workers=workers,
    )
