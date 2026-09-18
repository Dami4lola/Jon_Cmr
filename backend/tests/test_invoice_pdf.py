"""
Tests for the invoice PDF (app/services/invoice_pdf.py).

Smoke coverage only - the PDF is a customer-facing artifact rendered from the invoice's
own frozen columns, so what matters here is that it still renders and that the billing
period reads correctly.
"""
import datetime as dt
from decimal import Decimal

from app.models import Client, Invoice
from app.services.invoice_pdf import _format_billing_period, generate_invoice_pdf


def make_invoice(period_start=None, period_end=None):
    return Invoice(
        id=1,
        job_id=1,
        invoice_number="INV-2026-0001",
        created_date=dt.date(2026, 1, 20),
        period_start=period_start,
        period_end=period_end,
        subtotal=Decimal("640.00"),
        hst_amount=Decimal("83.20"),
        total=Decimal("723.20"),
        labour_amount=Decimal("640.00"),
    )


def make_client():
    return Client(id=1, name="Acme", phone_number="555-0100", address="1 Main St")


class TestFormatBillingPeriod:
    def test_both_bounds(self):
        invoice = make_invoice(dt.date(2026, 1, 1), dt.date(2026, 1, 15))

        assert _format_billing_period(invoice) == "January 01 - January 15, 2026"

    def test_start_only(self):
        invoice = make_invoice(period_start=dt.date(2026, 1, 1))

        assert _format_billing_period(invoice) == "From January 01, 2026"

    def test_end_only(self):
        invoice = make_invoice(period_end=dt.date(2026, 1, 15))

        assert _format_billing_period(invoice) == "Up to January 15, 2026"

    def test_no_period_renders_no_row(self):
        """A whole-job invoice reprints exactly as it was first sent to the client."""
        assert _format_billing_period(make_invoice()) is None


class TestRenders:
    def test_periodless_invoice(self):
        assert generate_invoice_pdf(make_invoice(), make_client()).startswith(b"%PDF")

    def test_perioded_invoice(self):
        invoice = make_invoice(dt.date(2026, 1, 1), dt.date(2026, 1, 15))

        assert generate_invoice_pdf(invoice, make_client()).startswith(b"%PDF")
