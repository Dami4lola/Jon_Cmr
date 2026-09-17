"""
Characterization tests pinning the invoice amount calculation.

These exist so that extracting the billing math into services/job_cost.py can be
proven not to have changed a single customer invoice. They assert current
behaviour, not desired behaviour - if one fails after a refactor, the refactor
changed what a customer is billed and must be reverted, not re-baselined.

Two behaviours pinned here were changed on 2026-09-17 by explicit request, and the
assertions were re-baselined in that same commit:

  - an HQ day billed a travel trip; it now bills none, because no drive happened
  - two timesheets on one date billed one trip; each now bills its own trip

Everything else in this file is still a hard contract: a failure means the change
altered a customer invoice and must be reverted, not re-baselined.

Pure function tests: models are built in memory and driven through a StubSession,
so no database is required.
"""
import datetime as dt
from decimal import Decimal

from app.api.invoices import (
    _calculate_invoice_amounts,
    LABOUR_RATE,
    REDSEAL_RATE,
    DEFAULT_KM_RATE,
    HST_RATE,
    MINIMUM_HOURS,
)

from .test_payroll_characterization import StubSession, make_job, make_timesheet, make_worker


INVOICE_AMOUNT_KEYS = {
    "total_labour_hours",
    "labour_amount",
    "total_distance_km",
    "km_rate",
    "travel_amount",
    "materials_amount",
    "inventory_materials",
    "dump_fee",
    "admin_fee",
    "subtotal",
    "hst_amount",
    "total",
}


def amounts_for(timesheets, job, data=None):
    return _calculate_invoice_amounts(StubSession(timesheets), job, data)


class TestRateConstants:
    """Billing-critical constants. Changing one changes what customers are charged."""

    def test_labour_rate(self):
        assert LABOUR_RATE == Decimal("80.00")

    def test_redseal_rate(self):
        assert REDSEAL_RATE == Decimal("100.00")

    def test_km_rate(self):
        assert DEFAULT_KM_RATE == Decimal("1.50")

    def test_hst_rate(self):
        assert HST_RATE == Decimal("0.13")

    def test_minimum_hours_value(self):
        assert MINIMUM_HOURS == Decimal("4.0")

    def test_minimum_hours_string_form(self):
        """
        The quick quote returns estimated_hours = max(rounded, MINIMUM_HOURS) and the
        public /quote page renders it raw, so the trailing zero is customer-visible.
        Decimal("4") would render "4 hrs" instead of "4.0 hrs".
        """
        assert str(MINIMUM_HOURS) == "4.0"


class TestLabour:
    def test_uses_the_job_rate_not_the_worker_rate(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")

        amounts = amounts_for([make_timesheet(worker, job, hours_worked="8.00")], job)

        assert amounts["labour_amount"] == Decimal("640.00")

    def test_job_redseal_flag_does_not_price_anything(self):
        """
        Changed 2026-09-17 on request: the job flag used to force every hour to the Red
        Seal rate, which made the per-timesheet checkbox inert and showed rows reading
        "not Red Seal" billing $100/hr. The timesheet's own flag is now the only signal.
        """
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")
        job.is_redseal_trade = True

        amounts = amounts_for([make_timesheet(worker, job, hours_worked="8.00")], job)

        assert amounts["labour_amount"] == Decimal("640.00")

    def test_minimum_hours_floor_applied(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")

        amounts = amounts_for([make_timesheet(worker, job, hours_worked="1.00")], job)

        assert amounts["total_labour_hours"] == Decimal("4.0")
        assert amounts["labour_amount"] == Decimal("320.00")

    def test_minimum_hours_override_zero_disables_floor(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [make_timesheet(worker, job, hours_worked="1.00", minimum_hours_override="0")], job
        )

        assert amounts["total_labour_hours"] == Decimal("1.0")
        assert amounts["labour_amount"] == Decimal("80.00")

    def test_break_deducted_after_rounding(self):
        worker = make_worker()
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [make_timesheet(worker, job, hours_worked="7.60", break_duration="0.50")], job
        )

        assert amounts["total_labour_hours"] == Decimal("7.0")


class TestTravelTripCounting:
    def test_two_workers_one_date_is_two_trips(self):
        job = make_job(distance_km="100.00")
        a = make_worker(worker_id=1, name="A")
        b = make_worker(worker_id=2, name="B")

        amounts = amounts_for(
            [make_timesheet(a, job, timesheet_id=1), make_timesheet(b, job, timesheet_id=2)], job
        )

        assert amounts["total_distance_km"] == Decimal("200.00")
        assert amounts["travel_amount"] == Decimal("300.00")

    def test_one_worker_two_dates_is_two_trips(self):
        job = make_job(distance_km="100.00")
        worker = make_worker()
        second = make_timesheet(worker, job, timesheet_id=2)
        second.date = dt.date(2026, 1, 6)

        amounts = amounts_for([make_timesheet(worker, job, timesheet_id=1), second], job)

        assert amounts["total_distance_km"] == Decimal("200.00")

    def test_one_worker_twice_on_one_date_is_two_trips(self):
        """Each timesheet is its own round trip - billing now matches cost."""
        job = make_job(distance_km="100.00")
        worker = make_worker()

        amounts = amounts_for(
            [
                make_timesheet(worker, job, hours_worked="4.00", timesheet_id=1),
                make_timesheet(worker, job, hours_worked="4.00", timesheet_id=2),
            ],
            job,
        )

        assert amounts["total_distance_km"] == Decimal("200.00")
        assert amounts["travel_amount"] == Decimal("300.00")

    def test_hq_day_bills_no_trip(self):
        """No drive, no travel charge."""
        job = make_job(distance_km="100.00")
        worker = make_worker()

        amounts = amounts_for([make_timesheet(worker, job, worked_at_hq=True)], job)

        assert amounts["total_distance_km"] == Decimal("0.00")
        assert amounts["travel_amount"] == Decimal("0.00")

    def test_two_orphaned_workers_on_one_date_are_two_trips(self):
        """Trip counting no longer keys on worker_id, which is None for every orphan."""
        job = make_job(distance_km="100.00")
        timesheets = []
        for index, name in enumerate(["Gone One", "Gone Two"], start=1):
            ts = make_timesheet(make_worker(), job, timesheet_id=index)
            ts.worker = None
            ts.worker_id = None
            ts.worker_name_snapshot = name
            timesheets.append(ts)

        amounts = amounts_for(timesheets, job)

        assert amounts["total_distance_km"] == Decimal("200.00")

    def test_company_truck_does_not_change_billing(self):
        """The truck rate is a payout concept; customers are billed the same either way."""
        job = make_job(distance_km="100.00")
        worker = make_worker()

        amounts = amounts_for([make_timesheet(worker, job, used_company_truck=True)], job)

        assert amounts["travel_amount"] == Decimal("150.00")

    def test_null_distance_bills_no_travel(self):
        job = make_job(distance_km=None)

        amounts = amounts_for([make_timesheet(make_worker(), job)], job)

        assert amounts["total_distance_km"] == Decimal("0")
        assert amounts["travel_amount"] == Decimal("0.00")

    def test_total_distance_km_is_the_raw_unquantized_product(self):
        job = make_job(distance_km="10.01")
        a = make_worker(worker_id=1, name="A")
        b = make_worker(worker_id=2, name="B")

        amounts = amounts_for(
            [make_timesheet(a, job, timesheet_id=1), make_timesheet(b, job, timesheet_id=2)], job
        )

        assert amounts["total_distance_km"] == Decimal("20.02")
        assert amounts["travel_amount"] == Decimal("30.03")


class TestMaterials:
    def test_personal_and_company_materials_are_split(self):
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [
                make_timesheet(
                    make_worker(), job, personal_materials="45.00", company_materials="200.00"
                )
            ],
            job,
        )

        assert amounts["materials_amount"] == Decimal("45.00")
        assert amounts["inventory_materials"] == Decimal("200.00")

    def test_materials_pass_through_without_markup(self):
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [
                make_timesheet(make_worker(), job, personal_materials="12.34", timesheet_id=1),
                make_timesheet(make_worker(), job, personal_materials="1.66", timesheet_id=2),
            ],
            job,
        )

        assert amounts["materials_amount"] == Decimal("14.00")


class TestDefaultsWhenNoInvoiceData:
    def test_km_rate_defaults(self):
        job = make_job(distance_km="100.00")
        assert amounts_for([make_timesheet(make_worker(), job)], job)["km_rate"] == Decimal("1.50")

    def test_fees_default_to_zero(self):
        job = make_job(distance_km="0.00")
        amounts = amounts_for([make_timesheet(make_worker(), job)], job)

        assert amounts["dump_fee"] == Decimal("0")
        assert amounts["admin_fee"] == Decimal("0")

    def test_hst_charged_by_default(self):
        job = make_job(distance_km="0.00")
        worker = make_worker(hourly_rate="50.00")

        amounts = amounts_for([make_timesheet(worker, job, hours_worked="8.00")], job)

        assert amounts["subtotal"] == Decimal("640.00")
        assert amounts["hst_amount"] == Decimal("83.20")
        assert amounts["total"] == Decimal("723.20")


class TestReturnedShape:
    def test_key_set_is_exactly_the_invoice_columns(self):
        """The dict is splatted into Invoice(**amounts), so the key set is a contract."""
        job = make_job(distance_km="0.00")

        amounts = amounts_for([make_timesheet(make_worker(), job)], job)

        assert set(amounts) == INVOICE_AMOUNT_KEYS


class TestGoldenCase:
    def test_three_workers_two_dates_full_breakdown(self):
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

        amounts = amounts_for(timesheets, job)

        assert amounts["total_labour_hours"] == Decimal("48.0")
        assert amounts["labour_amount"] == Decimal("3840.00")
        assert amounts["total_distance_km"] == Decimal("360.00")
        assert amounts["km_rate"] == Decimal("1.50")
        assert amounts["travel_amount"] == Decimal("540.00")
        assert amounts["materials_amount"] == Decimal("60.00")
        assert amounts["inventory_materials"] == Decimal("150.00")
        assert amounts["dump_fee"] == Decimal("0")
        assert amounts["admin_fee"] == Decimal("0")
        assert amounts["subtotal"] == Decimal("4590.00")
        assert amounts["hst_amount"] == Decimal("596.70")
        assert amounts["total"] == Decimal("5186.70")


class TestRedSealPerTimesheet:
    """
    The timesheet's own flag is the only thing that sets the Red Seal rate.
    """

    def test_ticked_timesheet_on_a_standard_job_bills_the_redseal_rate(self):
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [make_timesheet(make_worker(), job, hours_worked="8.00", is_redseal=True)], job
        )

        assert amounts["labour_amount"] == Decimal("800.00")

    def test_unticked_timesheet_bills_the_standard_rate_even_on_a_flagged_job(self):
        """An unticked entry bills $80/hr, so the row and the rate finally agree."""
        job = make_job(distance_km="0.00")
        job.is_redseal_trade = True

        amounts = amounts_for(
            [make_timesheet(make_worker(), job, hours_worked="8.00", is_redseal=False)], job
        )

        assert amounts["labour_amount"] == Decimal("640.00")

    def test_ticking_one_entry_on_a_mixed_job_moves_only_that_entry(self):
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [
                make_timesheet(make_worker(worker_id=1, name="A"), job,
                               hours_worked="8.00", is_redseal=True, timesheet_id=1),
                make_timesheet(make_worker(worker_id=2, name="B"), job,
                               hours_worked="8.00", is_redseal=False, timesheet_id=2),
            ],
            job,
        )

        assert amounts["labour_amount"] == Decimal("1440.00")

    def test_mixed_redseal_and_standard_on_one_job(self):
        job = make_job(distance_km="0.00")

        amounts = amounts_for(
            [
                make_timesheet(
                    make_worker(worker_id=1, name="A"), job,
                    hours_worked="8.00", is_redseal=True, timesheet_id=1,
                ),
                make_timesheet(
                    make_worker(worker_id=2, name="B"), job,
                    hours_worked="8.00", is_redseal=False, timesheet_id=2,
                ),
            ],
            job,
        )

        assert amounts["labour_amount"] == Decimal("1440.00")
