"""
Unit tests for the job cost engine (app/services/job_cost.py).

Pure function tests - models are built in memory, no database required.
Covers the two places job costing deliberately differs from payroll: company
materials are a cost but carry no subcontractor HST, and a deleted worker must
not crash the calculation.
"""
from decimal import Decimal

from app.services.job_cost import (
    KM_RATE_OWN_VEHICLE,
    KM_RATE_COMPANY_TRUCK,
    HST_RATE,
    MINIMUM_HOURS,
    compute_timesheet_cost,
    compute_worker_hst,
)

from .test_payroll_characterization import make_job, make_timesheet, make_worker


class TestRateConstants:
    """Billing-critical constants. Changing one changes real job costs."""

    def test_own_vehicle_rate(self):
        assert KM_RATE_OWN_VEHICLE == Decimal("0.85")

    def test_company_truck_rate(self):
        assert KM_RATE_COMPANY_TRUCK == Decimal("0.50")

    def test_hst_rate(self):
        assert HST_RATE == Decimal("0.13")

    def test_minimum_hours(self):
        assert MINIMUM_HOURS == Decimal("4")


class TestLabour:
    def test_billable_hours_times_rate(self):
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                           hours_worked="7.6", break_duration="0.5")
        )

        assert cost.billable_hours == Decimal("7.0")
        assert cost.labour_cost == Decimal("350.00")

    def test_minimum_floor_applied(self):
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                           hours_worked="1.00")
        )

        assert cost.billable_hours == Decimal("4")
        assert cost.labour_cost == Decimal("200.00")

    def test_override_zero_disables_floor(self):
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                           hours_worked="1.00", minimum_hours_override="0")
        )

        assert cost.billable_hours == Decimal("1.0")
        assert cost.labour_cost == Decimal("50.00")


class TestTravel:
    def test_own_vehicle_rate_used(self):
        cost = compute_timesheet_cost(make_timesheet(make_worker(), make_job(distance_km="100.00")))

        assert cost.km_rate == Decimal("0.85")
        assert cost.km_cost == Decimal("85.00")

    def test_company_truck_rate_used(self):
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(), make_job(distance_km="100.00"), used_company_truck=True)
        )

        assert cost.km_rate == Decimal("0.50")
        assert cost.km_cost == Decimal("50.00")

    def test_worked_at_hq_zeroes_travel(self):
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(), make_job(distance_km="100.00"), worked_at_hq=True)
        )

        assert cost.km_distance == Decimal("0")
        assert cost.km_rate == Decimal("0")
        assert cost.km_cost == Decimal("0")

    def test_null_distance_treated_as_zero(self):
        cost = compute_timesheet_cost(make_timesheet(make_worker(), make_job(distance_km=None)))

        assert cost.km_distance == Decimal("0")
        assert cost.km_cost == Decimal("0")

    def test_missing_job_relationship_does_not_crash(self):
        timesheet = make_timesheet(make_worker(), make_job(distance_km="100.00"))
        timesheet.job = None

        cost = compute_timesheet_cost(timesheet)

        assert cost.km_cost == Decimal("0")


class TestMaterials:
    def test_company_materials_included_in_subtotal(self):
        """Unlike payroll, job cost counts stock the company already paid for."""
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                           company_materials="300.00")
        )

        assert cost.company_materials == Decimal("300.00")
        assert cost.subtotal_cost == Decimal("700.00")

    def test_both_material_kinds_in_subtotal(self):
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(hourly_rate="50.00"), make_job(distance_km="100.00"),
                           personal_materials="20.00", company_materials="30.00")
        )

        assert cost.subtotal_cost == Decimal("535.00")


class TestDeletedWorker:
    """Migration 0018 orphans timesheets rather than cascading the delete."""

    def test_falls_back_to_name_snapshot(self):
        timesheet = make_timesheet(make_worker(), make_job(distance_km="0.00"))
        timesheet.worker = None
        timesheet.worker_id = None
        timesheet.worker_name_snapshot = "Departed Worker"

        cost = compute_timesheet_cost(timesheet)

        assert cost.worker_id is None
        assert cost.worker_name == "Departed Worker"
        assert cost.hourly_rate == Decimal("0")
        assert cost.charges_hst is False
        assert cost.labour_cost == Decimal("0.00")

    def test_missing_snapshot_falls_back_to_placeholder(self):
        timesheet = make_timesheet(make_worker(), make_job(distance_km="0.00"))
        timesheet.worker = None
        timesheet.worker_id = None
        timesheet.worker_name_snapshot = None

        cost = compute_timesheet_cost(timesheet)

        assert cost.worker_name == "Unknown worker"

    def test_materials_still_counted_for_orphaned_timesheet(self):
        timesheet = make_timesheet(
            make_worker(), make_job(distance_km="100.00"), company_materials="40.00"
        )
        timesheet.worker = None
        timesheet.worker_id = None

        cost = compute_timesheet_cost(timesheet)

        assert cost.subtotal_cost == Decimal("125.00")


class TestWorkerHst:
    def test_no_hst_when_worker_does_not_charge(self):
        labour_hst, km_hst, materials_hst = compute_worker_hst(
            Decimal("400.00"), Decimal("85.00"), Decimal("20.00"), charges_hst=False
        )

        assert (labour_hst, km_hst, materials_hst) == (Decimal("0"), Decimal("0"), Decimal("0"))

    def test_hst_applied_to_each_total(self):
        labour_hst, km_hst, materials_hst = compute_worker_hst(
            Decimal("400.00"), Decimal("85.00"), Decimal("20.00"), charges_hst=True
        )

        assert labour_hst == Decimal("52.00")
        assert km_hst == Decimal("11.05")
        assert materials_hst == Decimal("2.60")


class TestPayrollReconciliation:
    """
    The invariant that proves the two engines agree:
        financials.total_cost - company_materials == payroll.grand_total
    """

    def test_subtotal_minus_company_materials_matches_payroll(self):
        from .test_payroll_characterization import build_summary

        worker = make_worker(hourly_rate="50.00", charges_hst=True)
        job = make_job(distance_km="100.00")
        timesheet = make_timesheet(
            worker, job, personal_materials="20.00", company_materials="300.00"
        )

        cost = compute_timesheet_cost(timesheet)
        labour_hst, km_hst, materials_hst = compute_worker_hst(
            cost.labour_cost, cost.km_cost, cost.personal_materials, cost.charges_hst
        )
        total_cost = cost.subtotal_cost + labour_hst + km_hst + materials_hst

        payroll_grand_total = build_summary([timesheet]).grand_total

        assert total_cost - cost.company_materials == payroll_grand_total
