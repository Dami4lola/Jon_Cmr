"""
Unit tests for job budget resolution and margin (app/api/financials.py).

Pure function tests - models are built in memory, no database required.
"""
import datetime as dt
from decimal import Decimal

from app.api.financials import (
    _resolve_budget,
    _calculate_margin,
    _build_job_financials,
    BUDGET_SOURCE_INVOICE,
    BUDGET_SOURCE_ESTIMATE,
    BUDGET_SOURCE_JOB_FIELD,
    BUDGET_SOURCE_NONE,
)
from app.models import Estimate, Invoice

from .test_payroll_characterization import make_job, make_timesheet, make_worker


def attach_invoice(job, subtotal="10000.00", total="11300.00", status="sent"):
    invoice = Invoice(
        id=1,
        job_id=job.id,
        invoice_number="INV-2026-0001",
        subtotal=Decimal(subtotal),
        hst_amount=Decimal(total) - Decimal(subtotal),
        total=Decimal(total),
        status=status,
    )
    job.invoice = invoice
    return invoice


def attach_estimate(job, subtotal="8000.00", total="9040.00", status="accepted"):
    estimate = Estimate(
        id=1,
        job_id=job.id,
        estimate_number="EST-2026-0001",
        created_date=dt.date(2026, 1, 1),
        subtotal=Decimal(subtotal),
        hst_amount=Decimal(total) - Decimal(subtotal),
        total=Decimal(total),
        status=status,
    )
    job.estimate = estimate
    return estimate


class TestBudgetPrecedence:
    def test_invoice_wins(self):
        job = make_job()
        job.estimate_amount = Decimal("5000.00")
        attach_estimate(job)
        attach_invoice(job)

        budget = _resolve_budget(job)

        assert budget["budget_source"] == BUDGET_SOURCE_INVOICE
        assert budget["budget_amount"] == Decimal("10000.00")
        assert budget["budget_total_with_hst"] == Decimal("11300.00")
        assert budget["invoice_total"] == Decimal("11300.00")
        assert budget["invoice_status"] == "sent"

    def test_estimate_record_beats_job_estimate_amount(self):
        """Estimate.total is recomputed on save; Job.estimate_amount is never re-synced."""
        job = make_job()
        job.estimate_amount = Decimal("5000.00")
        attach_estimate(job)

        budget = _resolve_budget(job)

        assert budget["budget_source"] == BUDGET_SOURCE_ESTIMATE
        assert budget["budget_amount"] == Decimal("8000.00")
        assert budget["estimate_amount"] == Decimal("9040.00")
        assert budget["invoice_total"] is None

    def test_falls_back_to_job_estimate_amount(self):
        job = make_job()
        job.estimate_amount = Decimal("5000.00")

        budget = _resolve_budget(job)

        assert budget["budget_source"] == BUDGET_SOURCE_JOB_FIELD
        assert budget["budget_amount"] == Decimal("5000.00")
        assert budget["estimate_amount"] == Decimal("5000.00")

    def test_no_budget_at_all(self):
        job = make_job()
        job.estimate_amount = None

        budget = _resolve_budget(job)

        assert budget["budget_source"] == BUDGET_SOURCE_NONE
        assert budget["budget_amount"] is None
        assert budget["estimate_amount"] is None
        assert budget["invoice_total"] is None

    def test_estimate_still_reported_when_invoice_wins(self):
        """The UI shows spend against both, so neither figure is dropped."""
        job = make_job()
        attach_estimate(job)
        attach_invoice(job)

        budget = _resolve_budget(job)

        assert budget["estimate_amount"] == Decimal("9040.00")
        assert budget["invoice_total"] == Decimal("11300.00")


class TestMargin:
    def test_under_budget_positive_margin(self):
        margin = _calculate_margin(Decimal("10000.00"), Decimal("7500.00"))

        assert margin["margin_amount"] == Decimal("2500.00")
        assert margin["margin_percent"] == Decimal("25.0")
        assert margin["is_over_budget"] is False

    def test_over_budget_negative_margin(self):
        margin = _calculate_margin(Decimal("10000.00"), Decimal("12000.00"))

        assert margin["margin_amount"] == Decimal("-2000.00")
        assert margin["margin_percent"] == Decimal("-20.0")
        assert margin["is_over_budget"] is True

    def test_exactly_on_budget_is_not_over(self):
        margin = _calculate_margin(Decimal("10000.00"), Decimal("10000.00"))

        assert margin["margin_amount"] == Decimal("0.00")
        assert margin["is_over_budget"] is False

    def test_absent_budget_yields_nulls(self):
        margin = _calculate_margin(None, Decimal("7500.00"))

        assert margin["margin_amount"] is None
        assert margin["margin_percent"] is None
        assert margin["is_over_budget"] is False

    def test_zero_budget_does_not_divide_by_zero(self):
        margin = _calculate_margin(Decimal("0.00"), Decimal("7500.00"))

        assert margin["margin_amount"] == Decimal("-7500.00")
        assert margin["margin_percent"] is None
        assert margin["is_over_budget"] is True


class TestJobRollup:
    def test_job_with_no_timesheets_is_zero_not_an_error(self):
        job = make_job()
        job.timesheets = []

        fields, workers = _build_job_financials(job)

        assert workers == []
        assert fields["total_cost"] == Decimal("0.00")
        assert fields["timesheet_count"] == 0
        assert fields["worker_count"] == 0

    def test_cost_lines_roll_up_across_workers(self):
        job = make_job(distance_km="100.00")
        worker_one = make_worker(worker_id=1, name="Alice", hourly_rate="50.00")
        worker_two = make_worker(worker_id=2, name="Bob", hourly_rate="40.00")
        job.timesheets = [
            make_timesheet(worker_one, job, hours_worked="8.00", company_materials="100.00", timesheet_id=1),
            make_timesheet(worker_two, job, hours_worked="8.00", personal_materials="50.00", timesheet_id=2),
        ]

        fields, workers = _build_job_financials(job)

        assert len(workers) == 2
        assert fields["worker_count"] == 2
        assert fields["labour_cost"] == Decimal("720.00")
        assert fields["travel_cost"] == Decimal("170.00")
        assert fields["company_materials_cost"] == Decimal("100.00")
        assert fields["personal_materials_cost"] == Decimal("50.00")
        assert fields["subtotal_cost"] == Decimal("1040.00")

    def test_deleted_workers_are_not_collapsed_together(self):
        job = make_job(distance_km="0.00")
        job.timesheets = []
        for index, name in enumerate(["Departed One", "Departed Two"], start=1):
            timesheet = make_timesheet(
                make_worker(), job, hours_worked="8.00", timesheet_id=index
            )
            timesheet.worker = None
            timesheet.worker_id = None
            timesheet.worker_name_snapshot = name
            job.timesheets.append(timesheet)

        _, workers = _build_job_financials(job)

        assert len(workers) == 2
        assert {w.worker_name for w in workers} == {"Departed One", "Departed Two"}

    def test_unpaid_cost_counts_only_unpaid_lines(self):
        job = make_job(distance_km="0.00")
        worker = make_worker(hourly_rate="50.00")
        paid = make_timesheet(worker, job, hours_worked="8.00", timesheet_id=1)
        paid.is_paid = True
        unpaid = make_timesheet(worker, job, hours_worked="8.00", timesheet_id=2)
        job.timesheets = [paid, unpaid]

        fields, _ = _build_job_financials(job)

        assert fields["subtotal_cost"] == Decimal("800.00")
        assert fields["unpaid_cost"] == Decimal("400.00")

    def test_subcontractor_hst_separated_from_pretax_cost(self):
        job = make_job(distance_km="0.00")
        worker = make_worker(hourly_rate="50.00", charges_hst=True)
        job.timesheets = [make_timesheet(worker, job, hours_worked="8.00")]

        fields, _ = _build_job_financials(job)

        assert fields["subtotal_cost"] == Decimal("400.00")
        assert fields["hst_cost"] == Decimal("52.00")
        assert fields["total_cost"] == Decimal("452.00")

    def test_margin_measured_against_pretax_cost(self):
        job = make_job(distance_km="0.00")
        attach_invoice(job, subtotal="1000.00", total="1130.00")
        worker = make_worker(hourly_rate="50.00", charges_hst=True)
        job.timesheets = [make_timesheet(worker, job, hours_worked="8.00")]

        fields, _ = _build_job_financials(job)

        assert fields["margin_amount"] == Decimal("600.00")
        assert fields["is_over_budget"] is False
