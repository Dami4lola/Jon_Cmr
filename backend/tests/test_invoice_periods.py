"""
Tests for progress invoicing: several invoices per job, each billing a date range.

These run through a TestClient backed by in-memory SQLite rather than the StubSession
the invoice characterization tests use. That is deliberate and load-bearing: StubSession
ignores the statement it is handed and returns every timesheet, so it cannot see a WHERE
clause, and a broken period filter would pass silently there. The fixture is duplicated
from test_estimate_conversion.py rather than shared, matching how this repo does it.
"""
import datetime as dt
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool

from app.models import Client, Job, Timesheet, User, Worker


@pytest.fixture
def engine():
    import os
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.makedirs("uploads", exist_ok=True)

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(engine):
    from app.main import app
    from app.api import deps

    def override_get_session():
        with Session(engine) as s:
            yield s

    class FakeManager:
        id = 1
        is_active = True
        is_manager = True
        is_admin = True
        can_use_estimator = True

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_current_user] = lambda: FakeManager()

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def job_with_two_months(engine):
    """
    An in-progress job with one 8-hour day in January and one in February.

    is_completed stays False throughout: invoicing a job has nothing to do with
    finishing it.
    """
    with Session(engine) as session:
        customer = Client(name="Acme", phone_number="555-0100", address="1 Main St")
        session.add(customer)
        session.commit()
        session.refresh(customer)

        user = User(username="sam", email="sam@example.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)

        job = Job(
            client_id=customer.id,
            title="Boiler recert",
            is_completed=False,
            calculated_distance_km=Decimal("50.00"),
        )
        worker = Worker(user_id=user.id, name="Sam", hourly_rate=Decimal("45.00"))
        session.add(job)
        session.add(worker)
        session.commit()
        session.refresh(job)
        session.refresh(worker)

        for day in (dt.date(2026, 1, 10), dt.date(2026, 2, 10)):
            session.add(
                Timesheet(
                    worker_id=worker.id,
                    job_id=job.id,
                    date=day,
                    hours_worked=Decimal("8.00"),
                    personal_materials=Decimal("20.00"),
                    company_materials=Decimal("30.00"),
                )
            )
        session.commit()

        return job.id


JANUARY = {"period_start": "2026-01-01", "period_end": "2026-01-31"}
FEBRUARY = {"period_start": "2026-02-01", "period_end": "2026-02-28"}


def create_invoice(client, job_id, **body):
    return client.post(f"/api/invoices/job/{job_id}", json=body)


class TestPartialBilling:
    def test_january_invoice_bills_only_january(self, client, job_with_two_months):
        response = create_invoice(client, job_with_two_months, **JANUARY)

        assert response.status_code == 201
        invoice = response.json()
        assert invoice["period_start"] == "2026-01-01"
        assert invoice["period_end"] == "2026-01-31"
        assert Decimal(invoice["total_labour_hours"]) == Decimal("8.00")
        assert Decimal(invoice["labour_amount"]) == Decimal("640.00")
        assert Decimal(invoice["materials_amount"]) == Decimal("20.00")
        # One trip, not two: the February timesheet is outside the period.
        assert Decimal(invoice["total_distance_km"]) == Decimal("50.00")

    def test_the_job_is_not_marked_complete_by_invoicing(self, client, job_with_two_months):
        create_invoice(client, job_with_two_months, **JANUARY)

        job = client.get(f"/api/jobs/{job_with_two_months}").json()

        assert job["is_completed"] is False

    def test_two_periods_bill_disjoint_work(self, client, job_with_two_months):
        january = create_invoice(client, job_with_two_months, **JANUARY).json()
        february = create_invoice(client, job_with_two_months, **FEBRUARY).json()

        assert january["id"] != february["id"]
        assert january["invoice_number"] != february["invoice_number"]
        assert Decimal(february["total_labour_hours"]) == Decimal("8.00")

    def test_partial_invoices_sum_to_the_whole_job(self, client, job_with_two_months):
        """
        The anti-double-billing invariant. Each timesheet has one date, so it lands on
        exactly one invoice, and the two halves must reconstruct the whole.

        Labour and materials are exact. Travel and HST are allowed a cent of drift
        because each is quantized once per invoice, so splitting one rounding into two
        can move the pair by a cent against the single-invoice figure.
        """
        whole = client.get(f"/api/invoices/preview/job/{job_with_two_months}").json()

        january = create_invoice(client, job_with_two_months, **JANUARY).json()
        february = create_invoice(client, job_with_two_months, **FEBRUARY).json()

        assert Decimal(january["labour_amount"]) + Decimal(february["labour_amount"]) == Decimal(
            whole["labour_amount"]
        )
        assert Decimal(january["materials_amount"]) + Decimal(
            february["materials_amount"]
        ) == Decimal(whole["materials_amount"])
        assert abs(
            Decimal(january["subtotal"]) + Decimal(february["subtotal"])
            - Decimal(whole["subtotal"])
        ) <= Decimal("0.02")
        assert abs(
            Decimal(january["total"]) + Decimal(february["total"]) - Decimal(whole["total"])
        ) <= Decimal("0.02")

    def test_work_outside_every_period_is_billed_by_neither(self, client, job_with_two_months):
        march = {"period_start": "2026-03-01", "period_end": "2026-03-31"}

        response = create_invoice(client, job_with_two_months, **march).json()

        assert Decimal(response["total_labour_hours"]) == Decimal("0")
        assert Decimal(response["labour_amount"]) == Decimal("0")

    def test_the_four_hour_minimum_applies_once_per_timesheet(self, client, engine, job_with_two_months):
        """
        A one-hour day still bills four hours, in whichever period it falls - and only
        in that one, so the floor is never charged twice for the same work.
        """
        with Session(engine) as session:
            worker = session.exec(select(Worker)).first()
            session.add(
                Timesheet(
                    worker_id=worker.id,
                    job_id=job_with_two_months,
                    date=dt.date(2026, 3, 5),
                    hours_worked=Decimal("1.00"),
                )
            )
            session.commit()

        march = create_invoice(
            client, job_with_two_months, period_start="2026-03-01", period_end="2026-03-31"
        ).json()

        assert Decimal(march["total_labour_hours"]) == Decimal("4.00")


class TestOverlapBlocking:
    def test_overlapping_period_is_rejected(self, client, job_with_two_months):
        first = create_invoice(client, job_with_two_months, **JANUARY).json()

        response = create_invoice(
            client, job_with_two_months, period_start="2026-01-05", period_end="2026-01-20"
        )

        assert response.status_code == 400
        assert first["invoice_number"] in response.json()["detail"]

    def test_allow_overlap_bills_it_again(self, client, job_with_two_months):
        create_invoice(client, job_with_two_months, **JANUARY)

        response = create_invoice(
            client, job_with_two_months, allow_overlap=True, **JANUARY
        )

        assert response.status_code == 201

    def test_a_second_whole_job_invoice_is_rejected(self, client, job_with_two_months):
        """
        The case with no other guard once one-invoice-per-job is gone: an unbounded
        period overlaps everything, so a second one would bill the entire job twice.
        """
        create_invoice(client, job_with_two_months)

        response = create_invoice(client, job_with_two_months)

        assert response.status_code == 400

    def test_an_empty_overlap_is_not_a_double_bill(self, client, job_with_two_months):
        """Re-billing a window where nobody worked is harmless, so it must not 400."""
        create_invoice(client, job_with_two_months, **JANUARY)

        response = create_invoice(
            client, job_with_two_months, period_start="2026-04-01", period_end="2026-04-30"
        )

        assert response.status_code == 201

    def test_period_end_before_period_start_is_rejected(self, client, job_with_two_months):
        response = create_invoice(
            client, job_with_two_months, period_start="2026-02-01", period_end="2026-01-01"
        )

        assert response.status_code == 422


class TestPreview:
    def test_preview_scopes_to_the_period(self, client, job_with_two_months):
        preview = client.get(
            f"/api/invoices/preview/job/{job_with_two_months}",
            params=JANUARY,
        ).json()

        assert preview["timesheet_count"] == 1
        assert Decimal(preview["labour_hours"]) == Decimal("8.00")

    def test_preview_reports_the_resolved_rates(self, client, job_with_two_months):
        preview = client.get(f"/api/invoices/preview/job/{job_with_two_months}").json()

        assert Decimal(preview["labour_rate"]) == Decimal("80.00")
        assert Decimal(preview["km_rate"]) == Decimal("1.50")
        assert preview["rate_source"] == "default"

    def test_preview_names_the_overlapping_invoices(self, client, job_with_two_months):
        first = create_invoice(client, job_with_two_months, **JANUARY).json()

        preview = client.get(
            f"/api/invoices/preview/job/{job_with_two_months}", params=JANUARY
        ).json()

        assert preview["overlapping_invoice_numbers"] == [first["invoice_number"]]


class TestJobRateOverride:
    def test_invoices_bill_at_the_jobs_labour_rate(self, client, engine, job_with_two_months):
        with Session(engine) as session:
            job = session.get(Job, job_with_two_months)
            job.billable_labour_rate = Decimal("95.00")
            session.add(job)
            session.commit()

        invoice = create_invoice(client, job_with_two_months, **JANUARY).json()

        assert Decimal(invoice["labour_rate"]) == Decimal("95.00")
        assert Decimal(invoice["labour_amount"]) == Decimal("760.00")

    def test_the_rate_is_frozen_onto_the_invoice(self, client, engine, job_with_two_months):
        """A later rate change must not rewrite what an issued invoice was priced at."""
        january = create_invoice(client, job_with_two_months, **JANUARY).json()

        with Session(engine) as session:
            job = session.get(Job, job_with_two_months)
            job.billable_labour_rate = Decimal("95.00")
            session.add(job)
            session.commit()

        reread = client.get(f"/api/invoices/{january['id']}").json()

        assert Decimal(reread["labour_rate"]) == Decimal("80.00")
        assert Decimal(reread["labour_amount"]) == Decimal("640.00")


class TestListJobInvoices:
    def test_returns_every_invoice_in_period_order(self, client, job_with_two_months):
        february = create_invoice(client, job_with_two_months, **FEBRUARY).json()
        january = create_invoice(client, job_with_two_months, **JANUARY).json()

        listed = client.get(f"/api/invoices/job/{job_with_two_months}").json()

        assert [inv["id"] for inv in listed] == [january["id"], february["id"]]

    def test_unbounded_invoices_sort_first(self, client, job_with_two_months):
        whole = create_invoice(client, job_with_two_months).json()
        march = create_invoice(
            client, job_with_two_months, allow_overlap=True,
            period_start="2026-03-01", period_end="2026-03-31",
        ).json()

        listed = client.get(f"/api/invoices/job/{job_with_two_months}").json()

        assert [inv["id"] for inv in listed] == [whole["id"], march["id"]]

    def test_empty_for_a_job_with_no_invoices(self, client, job_with_two_months):
        assert client.get(f"/api/invoices/job/{job_with_two_months}").json() == []


class TestSchema:
    def test_job_id_index_is_not_unique(self):
        """
        Nothing in this suite runs alembic - tests go straight to create_all - so this is
        the only automated check that the one-invoice-per-job rule is gone from the model.
        """
        from app.models import Invoice

        job_id_index = next(
            ix for ix in Invoice.__table__.indexes if ix.name == "ix_invoice_job_id"
        )

        assert job_id_index.unique is False
