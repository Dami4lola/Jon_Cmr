"""
Unit tests for the job cost engine (app/services/job_cost.py).

Pure function tests - models are built in memory, no database required.
Covers the two places job costing deliberately differs from payroll: company
materials are a cost but carry no subcontractor HST, and a deleted worker must
not crash the calculation.
"""
import datetime as dt
from decimal import Decimal

from app.services.job_cost import (
    BillingRates,
    compute_job_billing,
    BILLABLE_KM_RATE,
    REDSEAL_RATE,
    KM_RATE_OWN_VEHICLE,
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

    def test_company_truck_pays_no_travel(self):
        """The drive happened and is billed to the client; the worker is not reimbursed."""
        cost = compute_timesheet_cost(
            make_timesheet(make_worker(), make_job(distance_km="100.00"), used_company_truck=True)
        )

        assert cost.km_distance == Decimal("100.00")
        assert cost.km_rate == Decimal("0")
        assert cost.km_cost == Decimal("0")

    def test_hq_beats_company_truck(self):
        """HQ zeroes the distance too - no trip happened at all."""
        cost = compute_timesheet_cost(
            make_timesheet(
                make_worker(), make_job(distance_km="100.00"),
                used_company_truck=True, worked_at_hq=True,
            )
        )

        assert cost.km_distance == Decimal("0")

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


class TestComputeJobBilling:
    """
    Billing prices timesheets at the billed-out rates. worker.hourly_rate must never
    reach any of these numbers.
    """

    def test_labour_uses_the_billed_rate_not_the_worker_rate(self):
        job = make_job(distance_km="0.00")
        billing = compute_job_billing(
            job, [make_timesheet(make_worker(hourly_rate="50.00"), job, hours_worked="8.00")]
        )

        assert billing.labour_amount == Decimal("640.00")

    def test_worker_rate_does_not_affect_billing(self):
        job = make_job(distance_km="100.00")
        cheap = compute_job_billing(
            job, [make_timesheet(make_worker(hourly_rate="20.00"), job, hours_worked="8.00")]
        )
        pricey = compute_job_billing(
            job, [make_timesheet(make_worker(hourly_rate="95.00"), job, hours_worked="8.00")]
        )

        assert cheap.subtotal == pricey.subtotal

    def test_job_redseal_flag_does_not_price_anything(self):
        """Changed 2026-09-17: only the timesheet's own Red Seal tick sets the rate."""
        job = make_job(distance_km="0.00")
        job.is_redseal_trade = True

        billing = compute_job_billing(job, [make_timesheet(make_worker(), job, hours_worked="8.00")])

        assert billing.labour_amount == Decimal("640.00")
        assert billing.redseal_hours == Decimal("0")

    def test_custom_rates_are_honoured(self):
        job = make_job(distance_km="100.00")
        rates = BillingRates(
            labour_rate=Decimal("95.00"),
            redseal_rate=Decimal("120.00"),
            km_rate=Decimal("2.00"),
            source="estimate",
        )

        billing = compute_job_billing(
            job, [make_timesheet(make_worker(), job, hours_worked="8.00")], rates=rates
        )

        assert billing.labour_amount == Decimal("760.00")
        assert billing.travel_amount == Decimal("200.00")
        assert billing.rates.source == "estimate"

    def test_each_timesheet_is_its_own_trip(self):
        job = make_job(distance_km="100.00")
        worker = make_worker()

        billing = compute_job_billing(
            job,
            [
                make_timesheet(worker, job, hours_worked="4.00", timesheet_id=1),
                make_timesheet(worker, job, hours_worked="4.00", timesheet_id=2),
            ],
        )

        assert billing.billable_trip_count == 2
        assert billing.travel_amount == Decimal("300.00")

    def test_hq_day_bills_no_trip(self):
        """No drive, no travel charge - billing and cost agree on this now."""
        job = make_job(distance_km="100.00")

        billing = compute_job_billing(job, [make_timesheet(make_worker(), job, worked_at_hq=True)])

        assert billing.billable_trip_count == 0
        assert billing.travel_amount == Decimal("0.00")

    def test_line_travel_sums_to_the_job_total(self):
        """The residual case: per-line quantizing alone would be a cent out."""
        job = make_job(distance_km="10.01")
        a = make_worker(worker_id=1, name="A")
        b = make_worker(worker_id=2, name="B")

        billing = compute_job_billing(
            job, [make_timesheet(a, job, timesheet_id=1), make_timesheet(b, job, timesheet_id=2)]
        )

        assert billing.travel_amount == Decimal("30.03")
        assert sum(line.travel_billable for line in billing.lines) == billing.travel_amount

    def test_line_labour_sums_to_the_job_total(self):
        job = make_job(distance_km="0.00")
        rates = BillingRates(
            labour_rate=Decimal("95.55"),
            redseal_rate=REDSEAL_RATE,
            km_rate=BILLABLE_KM_RATE,
            source="estimate",
        )
        timesheets = [
            make_timesheet(make_worker(), job, hours_worked="4.25", timesheet_id=i)
            for i in range(1, 4)
        ]

        billing = compute_job_billing(job, timesheets, rates=rates)

        assert sum(line.labour_billable for line in billing.lines) == billing.labour_amount

    def test_trip_flags_match_the_trip_count(self):
        job = make_job(distance_km="50.00")
        a = make_worker(worker_id=1, name="A")
        b = make_worker(worker_id=2, name="B")
        second_day = make_timesheet(a, job, timesheet_id=3)
        second_day.date = dt.date(2026, 1, 6)

        billing = compute_job_billing(
            job,
            [
                make_timesheet(a, job, timesheet_id=1),
                make_timesheet(b, job, timesheet_id=2),
                second_day,
            ],
        )

        assert sum(1 for line in billing.lines if line.is_billable_trip) == billing.billable_trip_count
        assert billing.billable_trip_count == 3

    def test_job_with_no_timesheets_is_all_zeros(self):
        billing = compute_job_billing(make_job(distance_km="100.00"), [])

        assert billing.lines == []
        assert billing.labour_amount == Decimal("0.00")
        assert billing.travel_amount == Decimal("0.00")
        assert billing.subtotal == Decimal("0.00")
        assert billing.billable_trip_count == 0

    def test_materials_pass_through_at_cost(self):
        job = make_job(distance_km="0.00")

        billing = compute_job_billing(
            job,
            [
                make_timesheet(
                    make_worker(), job, personal_materials="45.00", company_materials="200.00"
                )
            ],
        )

        assert billing.materials_amount == Decimal("45.00")
        assert billing.inventory_materials == Decimal("200.00")


class TestBillingMatchesTheInvoice:
    """
    The guarantee this refactor exists to provide: at default rates, the financials
    billable figure is exactly the invoice this job would generate.
    """

    def test_equivalence_with_calculate_invoice_amounts(self):
        from app.api.invoices import _calculate_invoice_amounts
        from app.services.job_cost import invoice_amounts

        from .test_payroll_characterization import StubSession

        job = make_job(distance_km="60.00")
        workers = [make_worker(worker_id=i, name=f"W{i}", hourly_rate="45.00") for i in (1, 2, 3)]
        timesheets = []
        timesheet_id = 1
        for day_offset in (0, 1):
            for worker in workers:
                ts = make_timesheet(
                    worker,
                    job,
                    hours_worked="8.00",
                    personal_materials="10.00",
                    company_materials="25.00",
                    timesheet_id=timesheet_id,
                )
                ts.date = dt.date(2026, 1, 5 + day_offset)
                timesheets.append(ts)
                timesheet_id += 1

        from_billing = invoice_amounts(compute_job_billing(job, timesheets))
        from_invoice = _calculate_invoice_amounts(StubSession(timesheets), job, None)

        assert from_billing == from_invoice


class TestRedSealPerTimesheet:
    def test_ticked_timesheet_bills_the_redseal_rate(self):
        job = make_job(distance_km="0.00")

        billing = compute_job_billing(
            job, [make_timesheet(make_worker(), job, hours_worked="8.00", is_redseal=True)]
        )

        assert billing.labour_amount == Decimal("800.00")
        assert billing.redseal_hours == Decimal("8.0")
        assert billing.redseal_labour_billable == Decimal("800.00")

    def test_redseal_rollups_cover_only_the_ticked_lines(self):
        job = make_job(distance_km="0.00")
        billing = compute_job_billing(
            job,
            [
                make_timesheet(make_worker(1, "A"), job, hours_worked="8.00", is_redseal=True, timesheet_id=1),
                make_timesheet(make_worker(2, "B"), job, hours_worked="8.00", is_redseal=False, timesheet_id=2),
            ],
        )

        assert billing.labour_amount == Decimal("1440.00")
        assert billing.redseal_hours == Decimal("8.0")
        assert billing.redseal_labour_billable == Decimal("800.00")

    def test_mixed_rate_line_labour_sums_to_the_job_total(self):
        job = make_job(distance_km="0.00")
        billing = compute_job_billing(
            job,
            [
                make_timesheet(make_worker(1, "A"), job, hours_worked="7.25", is_redseal=True, timesheet_id=1),
                make_timesheet(make_worker(2, "B"), job, hours_worked="6.75", is_redseal=False, timesheet_id=2),
            ],
        )

        assert sum(line.labour_billable for line in billing.lines) == billing.labour_amount


class TestTravelPopulationMatchesCost:
    def test_billing_and_cost_charge_the_same_lines_the_same_km(self):
        """After the HQ fix the two sides differ only in rate, never in population."""
        job = make_job(distance_km="100.00")
        timesheets = [
            make_timesheet(make_worker(1, "A"), job, timesheet_id=1),
            make_timesheet(make_worker(2, "B"), job, worked_at_hq=True, timesheet_id=2),
            make_timesheet(make_worker(3, "C"), job, used_company_truck=True, timesheet_id=3),
        ]

        billing = compute_job_billing(job, timesheets)

        for line, timesheet in zip(billing.lines, timesheets):
            assert line.billable_km == compute_timesheet_cost(timesheet).km_distance


class TestCompanyTruckMargin:
    """
    The two halves of the truck rule together: the worker is not reimbursed, but the
    client is still billed, so a truck day simply earns more margin.
    """

    def test_truck_day_costs_no_travel_but_still_bills_it(self):
        job = make_job(distance_km="100.00")
        timesheet = make_timesheet(make_worker(), job, used_company_truck=True)

        assert compute_timesheet_cost(timesheet).km_cost == Decimal("0")
        assert compute_job_billing(job, [timesheet]).travel_amount == Decimal("150.00")

    def test_truck_day_earns_the_full_travel_as_margin(self):
        job = make_job(distance_km="100.00")
        own = make_timesheet(make_worker(), job, timesheet_id=1)
        truck = make_timesheet(make_worker(), job, used_company_truck=True, timesheet_id=2)

        own_margin = Decimal("150.00") - compute_timesheet_cost(own).km_cost
        truck_margin = Decimal("150.00") - compute_timesheet_cost(truck).km_cost

        assert truck_margin - own_margin == Decimal("85.00")
