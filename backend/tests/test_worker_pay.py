"""
The figure a worker is SHOWN must equal the figure they are PAID.

Before this, the worker-facing preview came from a separate calculator that omitted
travel entirely, never applied the minimum-hours floor despite its docstring claiming
it did, and treated HST as a 1.13 multiplier on labour alone. A one-hour callout
previewed $50 and paid $200 plus travel.

The central assertion drives the real _build_payroll_summaries, so it is an
integration-strength claim rather than a restatement of the preview's own arithmetic.
"""
from decimal import Decimal

import pytest

from app.api.timesheets import _build_payout_preview, timesheet_to_response
from app.services.job_cost import compute_entry_payout, compute_timesheet_cost

from .test_payroll_characterization import build_summary, make_job, make_timesheet, make_worker


def preview_for(timesheet):
    return _build_payout_preview(timesheet, timesheet.worker, timesheet.job)


class TestShownPayEqualsPaidPay:
    @pytest.mark.parametrize("charges_hst", [False, True])
    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"used_company_truck": True},
            {"worked_at_hq": True},
            {"hours_worked": "1.00"},
            {"hours_worked": "1.00", "minimum_hours_override": "0"},
            {"personal_materials": "45.00"},
            {"company_materials": "300.00"},
            {"personal_materials": "20.00", "company_materials": "300.00"},
            {"hours_worked": "7.60", "break_duration": "0.50"},
        ],
    )
    def test_preview_matches_the_payroll_run(self, charges_hst, kwargs):
        worker = make_worker(hourly_rate="50.00", charges_hst=charges_hst)
        job = make_job(distance_km="100.00")
        timesheet = make_timesheet(worker, job, **kwargs)

        assert preview_for(timesheet).calculated_pay == build_summary([timesheet]).grand_total

    def test_timesheet_response_matches_the_payroll_run(self):
        """Pins the worker's own list, the paid list, and the timesheet detail page."""
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="100.00")
        timesheet = make_timesheet(worker, job, personal_materials="20.00")

        response = timesheet_to_response(timesheet)

        assert response.calculated_pay == build_summary([timesheet]).grand_total


class TestTravelIsShown:
    def test_own_vehicle_pays_travel(self):
        preview = preview_for(
            make_timesheet(make_worker(hourly_rate="50.00"), make_job(distance_km="100.00"))
        )

        assert preview.km_distance == Decimal("100.00")
        assert preview.km_rate == Decimal("0.85")
        assert preview.km_cost == Decimal("85.00")
        assert preview.calculated_pay == Decimal("485.00")

    def test_company_truck_shows_the_drive_but_pays_nothing_for_it(self):
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"),
                make_job(distance_km="100.00"),
                used_company_truck=True,
            )
        )

        assert preview.km_distance == Decimal("100.00")
        assert preview.km_rate == Decimal("0")
        assert preview.km_cost == Decimal("0")
        assert preview.calculated_pay == Decimal("400.00")

    def test_hq_shows_no_drive_at_all(self):
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"), make_job(distance_km="100.00"), worked_at_hq=True
            )
        )

        assert preview.km_distance == Decimal("0")
        assert preview.calculated_pay == Decimal("400.00")


class TestMinimumHours:
    def test_short_day_is_floored_and_flagged(self):
        """The regression that mattered most: a callout previewed $50 and paid $200."""
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"), hours_worked="1.00"
            )
        )

        assert preview.rounded_hours == Decimal("1.0")
        assert preview.billable_hours == Decimal("4")
        assert preview.minimum_applied is True
        assert preview.calculated_pay == Decimal("200.00")

    def test_full_day_is_not_flagged(self):
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"), hours_worked="8.00"
            )
        )

        assert preview.minimum_applied is False
        assert preview.calculated_pay == Decimal("400.00")

    def test_override_of_zero_disables_the_floor_and_the_flag(self):
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                hours_worked="1.00", minimum_hours_override="0",
            )
        )

        assert preview.billable_hours == Decimal("1.0")
        assert preview.minimum_applied is False
        assert preview.calculated_pay == Decimal("50.00")

    def test_break_cannot_push_rounded_hours_negative(self):
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                hours_worked="1.00", break_duration="3.00",
            )
        )

        assert preview.rounded_hours == Decimal("0")


class TestWhatIsNotPaid:
    def test_company_materials_never_reach_pay(self):
        worker = make_worker(hourly_rate="50.00")
        job = make_job(distance_km="0.00")

        without = preview_for(make_timesheet(worker, job))
        with_stock = preview_for(make_timesheet(worker, job, company_materials="300.00"))

        assert with_stock.company_materials == Decimal("300.00")
        assert with_stock.calculated_pay == without.calculated_pay

    def test_personal_materials_are_reimbursed(self):
        preview = preview_for(
            make_timesheet(
                make_worker(hourly_rate="50.00"), make_job(distance_km="0.00"),
                personal_materials="45.00",
            )
        )

        assert preview.calculated_pay == Decimal("445.00")

    def test_deleted_worker_is_paid_expenses_only(self):
        timesheet = make_timesheet(make_worker(), make_job(distance_km="0.00"), personal_materials="20.00")
        timesheet.worker = None
        timesheet.worker_id = None
        timesheet.worker_name_snapshot = "Departed"

        cost = compute_timesheet_cost(timesheet)

        assert cost.hourly_rate == Decimal("0")
        assert compute_entry_payout(cost).grand_total == Decimal("20.00")


class TestLegacyEngineIsGone:
    def test_the_broken_calculator_cannot_be_imported(self):
        """Deleted so it cannot drift back into a worker-facing figure."""
        with pytest.raises(ModuleNotFoundError):
            import app.services.payout  # noqa: F401


class TestPayslipRendering:
    """
    The payslip is a document a worker will query, so it must render for every rate
    mix and must never label the KM column from whichever entry happened to be first.
    """

    def _entry(self, km_rate, km_cost, timesheet_id):
        import datetime as dt
        from app.schemas.payroll import PayrollEntryDetail

        return PayrollEntryDetail(
            timesheet_id=timesheet_id, date=dt.date(2026, 1, 5), customer_name="Acme",
            job_description="Job", hours_worked=Decimal("8"), break_duration=Decimal("0"),
            billable_hours=Decimal("8"), labour_rate=Decimal("50"), labour_cost=Decimal("400"),
            km_distance=Decimal("100"), km_rate=km_rate, km_cost=km_cost,
            personal_materials=Decimal("0"), minimum_hours_override=None,
        )

    def _summary(self, entries):
        from app.schemas.payroll import PayrollWorkerSummary

        return PayrollWorkerSummary(
            worker_id=1, worker_name="Bob", entries=entries,
            total_hours=Decimal("8") * len(entries), total_labour=Decimal("400") * len(entries),
            total_km=Decimal("100") * len(entries),
            total_km_cost=sum((e.km_cost for e in entries), Decimal("0")),
            total_personal_materials=Decimal("0"), labour_hst=Decimal("0"),
            km_hst=Decimal("0"), materials_hst=Decimal("0"),
            grand_total=Decimal("0"), charges_hst=False,
        )

    def _render(self, entries):
        """Renders to bytes. ReportLab compresses its streams, so assert on the label
        helper rather than scraping the PDF - a text search here always misses."""
        import datetime as dt
        from app.services.payroll_pdf import generate_payroll_pdf

        return generate_payroll_pdf(self._summary(entries), dt.date(2026, 1, 1), dt.date(2026, 1, 31))

    def test_truck_only_period_renders(self):
        """Regression: the truck footnote crashed on a period with no minimum applied."""
        assert len(self._render([self._entry(Decimal("0"), Decimal("0"), 1)])) > 0

    def test_mixed_rate_period_renders(self):
        pdf = self._render(
            [
                self._entry(Decimal("0"), Decimal("0"), 1),
                self._entry(Decimal("0.85"), Decimal("85"), 2),
            ]
        )

        assert len(pdf) > 0

    def test_uniform_own_vehicle_period_names_the_rate(self):
        from app.services.payroll_pdf import km_rate_label

        assert km_rate_label([self._entry(Decimal("0.85"), Decimal("85"), 1)]) == "$0.85/km"

    def test_mixed_rates_do_not_name_a_single_rate(self):
        """The bug: the old code labelled the whole column from entry zero."""
        from app.services.payroll_pdf import km_rate_label

        label = km_rate_label(
            [
                self._entry(Decimal("0"), Decimal("0"), 1),
                self._entry(Decimal("0.85"), Decimal("85"), 2),
            ]
        )

        assert label == "$"

    def test_truck_only_period_does_not_claim_a_rate(self):
        from app.services.payroll_pdf import km_rate_label

        assert km_rate_label([self._entry(Decimal("0"), Decimal("0"), 1)]) == "$0.00/km"
