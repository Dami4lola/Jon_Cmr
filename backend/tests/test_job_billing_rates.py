"""
Tests for billable rate resolution (app/services/job_cost.py).

The rates a job bills at come from one resolver shared by the invoice and the Job
Financials page, so the two cannot price the same timesheets differently. Pure function
tests - models are built in memory, no database required.
"""
import datetime as dt
from decimal import Decimal

from app.models import Estimate, Invoice
from app.services.job_cost import (
    invoice_billing_rates,
    resolve_billing_rates,
    BILLABLE_KM_RATE,
    LABOUR_RATE,
    REDSEAL_RATE,
)

from .test_payroll_characterization import make_job


def attach_estimate(job, km_rate="2.00", redseal_rate="125.00"):
    estimate = Estimate(
        id=1,
        job_id=job.id,
        estimate_number="EST-2026-0001",
        created_date=dt.date(2026, 1, 1),
        km_rate=Decimal(km_rate),
        redseal_rate=Decimal(redseal_rate),
    )
    job.estimate = estimate
    return estimate


class TestDefaults:
    def test_bare_job_takes_the_global_constants(self):
        rates = resolve_billing_rates(make_job())

        assert rates.labour_rate == LABOUR_RATE
        assert rates.redseal_rate == REDSEAL_RATE
        assert rates.km_rate == BILLABLE_KM_RATE
        assert rates.source == "default"


class TestEstimatePrecedence:
    def test_estimate_supplies_km_and_redseal(self):
        job = make_job()
        attach_estimate(job)

        rates = resolve_billing_rates(job)

        assert rates.km_rate == Decimal("2.00")
        assert rates.redseal_rate == Decimal("125.00")
        assert rates.source == "estimate"

    def test_estimate_does_not_supply_labour(self):
        """Estimate has no labour rate column, so labour falls straight through."""
        job = make_job()
        attach_estimate(job)

        assert resolve_billing_rates(job).labour_rate == LABOUR_RATE


class TestJobOverride:
    def test_job_labour_rate_wins(self):
        job = make_job()
        job.billable_labour_rate = Decimal("95.00")

        rates = resolve_billing_rates(job)

        assert rates.labour_rate == Decimal("95.00")
        assert rates.source == "job"

    def test_job_km_rate_beats_the_estimate(self):
        job = make_job()
        attach_estimate(job, km_rate="2.00")
        job.billable_km_rate = Decimal("1.75")

        assert resolve_billing_rates(job).km_rate == Decimal("1.75")

    def test_job_redseal_rate_beats_the_estimate(self):
        job = make_job()
        attach_estimate(job, redseal_rate="125.00")
        job.billable_redseal_rate = Decimal("140.00")

        assert resolve_billing_rates(job).redseal_rate == Decimal("140.00")

    def test_rates_resolve_independently(self):
        """
        Overriding one rate must not drag the other two to the same tier: a job can set
        its own kilometre rate while still taking Red Seal from the estimate and labour
        from the global constant.
        """
        job = make_job()
        attach_estimate(job, km_rate="2.00", redseal_rate="125.00")
        job.billable_km_rate = Decimal("1.75")

        rates = resolve_billing_rates(job)

        assert rates.km_rate == Decimal("1.75")
        assert rates.redseal_rate == Decimal("125.00")
        assert rates.labour_rate == LABOUR_RATE

    def test_null_override_falls_through_rather_than_reading_as_zero(self):
        job = make_job()
        attach_estimate(job, km_rate="2.00")
        job.billable_km_rate = None

        rates = resolve_billing_rates(job)

        assert rates.km_rate == Decimal("2.00")
        assert rates.source == "estimate"


class TestIssuedInvoicesAreNotASource:
    def test_invoices_do_not_move_the_forward_rate(self):
        """
        With several progress invoices there is no single "the invoice rate", and reading
        one would let a manual tweak on invoice 2 silently reprice invoices 3 and 4.
        """
        job = make_job()
        attach_estimate(job, km_rate="2.00")
        job.invoices.append(
            Invoice(
                id=1,
                job_id=job.id,
                invoice_number="INV-2026-0001",
                km_rate=Decimal("1.75"),
                labour_rate=Decimal("90.00"),
                redseal_rate=Decimal("110.00"),
            )
        )

        rates = resolve_billing_rates(job)

        assert rates.km_rate == Decimal("2.00")
        assert rates.labour_rate == LABOUR_RATE
        assert rates.source == "estimate"

    def test_invoice_billing_rates_reads_the_frozen_columns(self):
        invoice = Invoice(
            id=1,
            job_id=1,
            invoice_number="INV-2026-0001",
            km_rate=Decimal("1.75"),
            labour_rate=Decimal("90.00"),
            redseal_rate=Decimal("110.00"),
        )

        rates = invoice_billing_rates(invoice)

        assert rates.km_rate == Decimal("1.75")
        assert rates.labour_rate == Decimal("90.00")
        assert rates.redseal_rate == Decimal("110.00")
        assert rates.source == "invoice"
