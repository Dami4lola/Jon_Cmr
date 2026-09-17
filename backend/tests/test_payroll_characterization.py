"""
Characterization tests pinning the payroll per-line cost math.

These exist to prove that extracting the cost engine into app/services/job_cost.py
did not change what workers actually get paid. They assert current behaviour, not
desired behaviour — if one of these fails after a refactor, the refactor changed a
payout and must be reverted, not re-baselined.

Pure function tests: models are built in memory with relationships wired by hand,
no database or HTTP client required.
"""
import datetime as dt
from decimal import Decimal

import pytest

from app.api.payroll import (
    _round_hours,
    _build_payroll_summaries,
    KM_RATE_OWN_VEHICLE,
    HST_RATE,
    MINIMUM_HOURS,
)
from app.models import Client, Job, Timesheet, Worker


def make_worker(hourly_rate="50.00", charges_hst=False, worker_id=1, name="Test Worker"):
    worker = Worker(
        id=worker_id,
        user_id=worker_id,
        name=name,
        hourly_rate=Decimal(hourly_rate),
        charges_hst=charges_hst,
    )
    return worker


def make_job(distance_km="100.00", job_id=1):
    client = Client(id=1, name="Test Client", address="123 Test St")
    job = Job(
        id=job_id,
        client_id=1,
        title="Test Job",
        start_date=dt.date(2026, 1, 5),
        calculated_distance_km=Decimal(distance_km) if distance_km is not None else None,
    )
    job.client = client
    return job


def make_timesheet(
    worker,
    job,
    hours_worked="8.00",
    break_duration="0.00",
    used_company_truck=False,
    worked_at_hq=False,
    personal_materials="0.00",
    company_materials="0.00",
    minimum_hours_override=None,
    is_redseal=False,
    timesheet_id=1,
):
    timesheet = Timesheet(
        id=timesheet_id,
        worker_id=worker.id if worker else None,
        job_id=job.id,
        date=dt.date(2026, 1, 5),
        hours_worked=Decimal(hours_worked),
        break_duration=Decimal(break_duration),
        used_company_truck=used_company_truck,
        worked_at_hq=worked_at_hq,
        is_redseal=is_redseal,
        personal_materials=Decimal(personal_materials),
        company_materials=Decimal(company_materials),
        minimum_hours_override=(
            Decimal(minimum_hours_override) if minimum_hours_override is not None else None
        ),
    )
    timesheet.worker = worker
    timesheet.job = job
    return timesheet


class StubSession:
    """Stands in for a Session so _build_payroll_summaries can be driven directly."""

    def __init__(self, timesheets):
        self._timesheets = timesheets

    def exec(self, statement):
        return self

    def all(self):
        return self._timesheets


def build_summary(timesheets):
    summaries, _ = _build_payroll_summaries(
        StubSession(timesheets),
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 31),
    )
    return summaries[0]


class TestRateConstants:
    """Billing-critical constants. Changing one changes real payouts."""

    def test_own_vehicle_rate(self):
        assert KM_RATE_OWN_VEHICLE == Decimal("0.85")

    def test_hst_rate(self):
        assert HST_RATE == Decimal("0.13")

    def test_minimum_hours(self):
        assert MINIMUM_HOURS == Decimal("4")


class TestRoundHours:
    def test_break_deducted_after_rounding(self):
        assert _round_hours(Decimal("7.6"), Decimal("0.5")) == Decimal("7.0")

    def test_below_minimum_raised_to_floor(self):
        assert _round_hours(Decimal("1.0")) == Decimal("4")

    def test_override_zero_disables_floor(self):
        assert _round_hours(Decimal("1.0"), minimum_hours=Decimal("0")) == Decimal("1.0")

    def test_rounds_to_nearest_quarter(self):
        assert _round_hours(Decimal("7.6"), minimum_hours=Decimal("0")) == Decimal("7.5")


class TestLabourCost:
    def test_billable_hours_times_rate(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job()
        summary = build_summary([make_timesheet(worker, job, hours_worked="7.6", break_duration="0.5")])

        assert summary.entries[0].billable_hours == Decimal("7.0")
        assert summary.entries[0].labour_cost == Decimal("350.00")

    def test_minimum_floor_applied(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job()
        summary = build_summary([make_timesheet(worker, job, hours_worked="1.00")])

        assert summary.entries[0].billable_hours == Decimal("4")
        assert summary.entries[0].labour_cost == Decimal("200.00")

    def test_minimum_hours_override_zero_disables_floor(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job()
        summary = build_summary(
            [make_timesheet(worker, job, hours_worked="1.00", minimum_hours_override="0")]
        )

        assert summary.entries[0].billable_hours == Decimal("1.0")
        assert summary.entries[0].labour_cost == Decimal("50.00")


class TestTravelCost:
    def test_own_vehicle_charged_at_85_cents(self):
        worker = make_worker()
        job = make_job(distance_km="100.00")
        summary = build_summary([make_timesheet(worker, job)])

        assert summary.entries[0].km_rate == Decimal("0.85")
        assert summary.entries[0].km_cost == Decimal("85.00")

    def test_company_truck_pays_no_travel(self):
        """
        Changed 2026-09-17 by request: a company-truck day reimburses no travel,
        because the company paid for the vehicle and the fuel. The distance is kept
        so the payslip can show the drive was recorded, and the client is still
        billed for it.
        """
        worker = make_worker()
        job = make_job(distance_km="100.00")
        summary = build_summary([make_timesheet(worker, job, used_company_truck=True)])

        assert summary.entries[0].km_distance == Decimal("100.00")
        assert summary.entries[0].km_rate == Decimal("0")
        assert summary.entries[0].km_cost == Decimal("0")
        assert summary.grand_total == Decimal("400.00")

    def test_worked_at_hq_has_no_travel_cost(self):
        worker = make_worker()
        job = make_job(distance_km="100.00")
        summary = build_summary([make_timesheet(worker, job, worked_at_hq=True)])

        assert summary.entries[0].km_distance == Decimal("0")
        assert summary.entries[0].km_rate == Decimal("0")
        assert summary.entries[0].km_cost == Decimal("0")

    def test_worked_at_hq_beats_company_truck(self):
        worker = make_worker()
        job = make_job(distance_km="100.00")
        summary = build_summary(
            [make_timesheet(worker, job, used_company_truck=True, worked_at_hq=True)]
        )

        assert summary.entries[0].km_cost == Decimal("0")

    def test_null_distance_treated_as_zero(self):
        worker = make_worker()
        job = make_job(distance_km=None)
        summary = build_summary([make_timesheet(worker, job)])

        assert summary.entries[0].km_cost == Decimal("0")


class TestHst:
    def test_no_hst_when_worker_does_not_charge(self):
        worker = make_worker(hourly_rate="50.00", charges_hst=False)
        job = make_job(distance_km="100.00")
        summary = build_summary([make_timesheet(worker, job, personal_materials="20.00")])

        assert summary.labour_hst == Decimal("0")
        assert summary.km_hst == Decimal("0")
        assert summary.materials_hst == Decimal("0")
        assert summary.grand_total == Decimal("505.00")

    def test_hst_applied_to_each_summed_total(self):
        worker = make_worker(hourly_rate="50.00", charges_hst=True)
        job = make_job(distance_km="100.00")
        summary = build_summary([make_timesheet(worker, job, personal_materials="20.00")])

        assert summary.total_labour == Decimal("400.00")
        assert summary.labour_hst == Decimal("52.00")
        assert summary.total_km_cost == Decimal("85.00")
        assert summary.km_hst == Decimal("11.05")
        assert summary.total_personal_materials == Decimal("20.00")
        assert summary.materials_hst == Decimal("2.60")
        assert summary.grand_total == Decimal("570.65")


class TestMaterials:
    def test_personal_materials_reimbursed(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")
        summary = build_summary([make_timesheet(worker, job, personal_materials="125.50")])

        assert summary.total_personal_materials == Decimal("125.50")
        assert summary.grand_total == Decimal("525.50")

    def test_company_materials_not_in_payout(self):
        """Company already paid for this stock, so it never reaches the worker."""
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")
        summary = build_summary([make_timesheet(worker, job, company_materials="300.00")])

        assert summary.grand_total == Decimal("400.00")


class TestMultipleEntries:
    def test_totals_accumulate_across_timesheets(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="100.00")
        summary = build_summary(
            [
                make_timesheet(worker, job, hours_worked="8.00", timesheet_id=1),
                make_timesheet(worker, job, hours_worked="6.00", timesheet_id=2),
            ]
        )

        assert summary.total_hours == Decimal("14.0")
        assert summary.total_labour == Decimal("700.00")
        assert summary.total_km_cost == Decimal("170.00")
        assert summary.grand_total == Decimal("870.00")


class TestEmptyRange:
    def test_no_timesheets_raises_404(self):
        """Payroll deliberately 404s on an empty period. Financials must not copy this."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _build_payroll_summaries(StubSession([]), dt.date(2026, 1, 1), dt.date(2026, 1, 31))

        assert exc_info.value.status_code == 404
