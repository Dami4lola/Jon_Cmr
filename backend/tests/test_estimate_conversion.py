"""
Tests for converting an estimate into a job.

Pure-function tests for the two mapping helpers, plus full HTTP tests through a
TestClient backed by in-memory SQLite. The fixture is duplicated from
test_estimate_persistence.py rather than shared, matching how this repo does it.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.api.estimates import _duration_for_job, _is_redseal_estimate
from app.models import Estimate, EstimateTask


class TestDurationForJob:
    """Job.estimated_duration is Numeric(4,2); Estimate.total_hours is Numeric(8,2)."""

    def test_zero_hours_returns_none(self):
        assert _duration_for_job(Decimal("0")) is None

    def test_none_returns_none(self):
        assert _duration_for_job(None) is None

    def test_normal_hours_pass_through(self):
        assert _duration_for_job(Decimal("66.50")) == Decimal("66.50")

    def test_boundary_fits(self):
        assert _duration_for_job(Decimal("99.99")) == Decimal("99.99")

    def test_just_over_boundary_returns_none(self):
        assert _duration_for_job(Decimal("100.00")) is None

    def test_large_estimate_returns_none(self):
        """The regression case: this would overflow Numeric(4,2) on Postgres."""
        assert _duration_for_job(Decimal("208.50")) is None


class TestIsRedsealEstimate:
    def test_tech_count_alone_does_not_flag_the_job(self):
        """
        Changed 2026-09-17: this used to assert True, which was the bug. The calculator
        auto-fills redseal_techs from crew size, so it is non-zero on nearly every
        estimate. Flagging on it billed ordinary jobs $100/hr against an $80/hr quote.
        """
        estimate = Estimate(estimate_number="EST-1", redseal_techs=2)
        estimate.tasks = []
        assert _is_redseal_estimate(estimate) is False

    def test_true_from_tagged_task(self):
        """A tagged task is the only signal, and it works with no tech count set."""
        estimate = Estimate(estimate_number="EST-1", redseal_techs=0)
        estimate.tasks = [
            EstimateTask(phase="build", description="Weld", hours=Decimal("4"), uses_redseal=True)
        ]
        assert _is_redseal_estimate(estimate) is True

    def test_false_when_neither(self):
        estimate = Estimate(estimate_number="EST-1", redseal_techs=0)
        estimate.tasks = [
            EstimateTask(phase="build", description="Paint", hours=Decimal("4"), uses_redseal=False)
        ]
        assert _is_redseal_estimate(estimate) is False


@pytest.fixture
def client():
    import os
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.makedirs("uploads", exist_ok=True)

    from app.main import app
    from app.api import deps

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    class FakeManager:
        id = 1
        is_active = True
        is_manager = True
        is_admin = True
        can_use_estimator = True

    def override_get_current_user():
        return FakeManager()

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_current_user] = override_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()


BASE_ESTIMATE = {
    "scope_of_work": "Recert the boiler\nSecond line of scope",
    "crew_size": 2,
    "techs_traveling": 2,
    "admin_fee": 50,
    "include_admin_fee": True,
    "include_hst": True,
    "tasks": [
        {"phase": "build", "description": "Build", "hours": 10, "sort_order": 0},
    ],
}

CONVERT_BODY = {
    "title": "Boiler Recert",
    "start_date": "2026-03-02",
    "end_date": "2026-03-06",
    "scheduled_time": "08:00:00",
}


def make_client(client, name="Acme Industrial", address="1 Bay St, Toronto", phone="613-555-0142"):
    response = client.post(
        "/api/clients/",
        json={"name": name, "address": address, "phone_number": phone},
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_estimate(client, **overrides):
    payload = {**BASE_ESTIMATE, **overrides}
    response = client.post("/api/estimates/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def convert(client, estimate_id, **overrides):
    return client.post(
        f"/api/estimates/{estimate_id}/convert-to-job",
        json={**CONVERT_BODY, **overrides},
    )


class TestConvertEstimateToJob:
    def test_convert_with_existing_client(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        response = convert(client, estimate["id"])

        assert response.status_code == 201, response.text
        job = response.json()
        assert job["title"] == "Boiler Recert"
        assert job["client"]["id"] == customer["id"]
        assert job["start_date"] == "2026-03-02"
        assert job["end_date"] == "2026-03-06"
        # HST-inclusive total, per the product decision
        assert Decimal(job["estimate_amount"]) == Decimal(estimate["total"])
        assert Decimal(job["estimated_duration"]) == Decimal(estimate["total_hours"])

    def test_details_default_to_the_written_scope_and_the_tasks(self, client):
        """
        Changed 2026-09-22: details used to be a plain copy of scope_of_work, which
        left the crew with the estimator's paragraph and none of the work breakdown
        that was actually priced.
        """
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        job = convert(client, estimate["id"]).json()

        assert job["details"] == (
            "Recert the boiler\nSecond line of scope\n\nThe Build\n- Build"
        )

    def test_details_the_manager_typed_still_win(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        job = convert(client, estimate["id"], details="Go in through the rear gate").json()

        assert job["details"] == "Go in through the rear gate"

    def test_estimate_marked_accepted_and_linked(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        job = convert(client, estimate["id"]).json()

        reloaded = client.get(f"/api/estimates/{estimate['id']}").json()
        assert reloaded["status"] == "accepted"
        assert reloaded["job"]["id"] == job["id"]

    def test_double_convert_returns_409(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])
        first = convert(client, estimate["id"]).json()

        second = convert(client, estimate["id"], title="Duplicate")

        assert second.status_code == 409
        assert str(first["id"]) in second.json()["detail"]
        assert len(client.get("/api/jobs/").json()) == 1
        assert client.get(f"/api/estimates/{estimate['id']}").json()["job"]["id"] == first["id"]

    def test_legacy_prospect_autocreates_client(self, client):
        estimate = make_estimate(
            client,
            client_name_override="Prospect Co",
            address_override="99 Queen St, Toronto",
        )

        response = convert(client, estimate["id"])

        assert response.status_code == 201, response.text
        job = response.json()
        assert job["client"]["name"] == "Prospect Co"

        created = [c for c in client.get("/api/clients/").json() if c["name"] == "Prospect Co"]
        assert len(created) == 1
        assert created[0]["address"] == "99 Queen St, Toronto"

        reloaded = client.get(f"/api/estimates/{estimate['id']}").json()
        assert reloaded["client"]["name"] == "Prospect Co"
        assert reloaded["client_name_override"] is None

    def test_prospect_without_address_is_rejected(self, client):
        estimate = make_estimate(client, client_name_override="Prospect Co")

        response = convert(client, estimate["id"])

        assert response.status_code == 400
        assert "address" in response.json()["detail"].lower()
        # Nothing partial was committed - this is the transaction test
        assert client.get("/api/jobs/").json() == []
        assert client.get("/api/clients/").json() == []
        assert client.get(f"/api/estimates/{estimate['id']}").json()["status"] == "draft"

    def test_new_client_inline_creates_and_links(self, client):
        estimate = make_estimate(client, client_name_override="Prospect Co")

        response = convert(
            client,
            estimate["id"],
            new_client={"name": "Prospect Co", "address": "5 King St, Toronto"},
        )

        assert response.status_code == 201, response.text
        assert response.json()["client"]["name"] == "Prospect Co"
        created = [c for c in client.get("/api/clients/").json() if c["name"] == "Prospect Co"]
        assert created[0]["address"] == "5 King St, Toronto"

    def test_new_client_phone_reaches_the_client_record(self, client):
        """
        The crew calls this number off the job card. The passthrough existed but was
        untested, and the convert dialog never sent one - so every job converted for a
        new client arrived with nobody to ring.
        """
        estimate = make_estimate(client, client_name_override="Prospect Co")

        response = convert(
            client,
            estimate["id"],
            new_client={
                "name": "Prospect Co",
                "address": "5 King St, Toronto",
                "phone_number": "613-555-0142",
            },
        )

        assert response.status_code == 201, response.text
        assert response.json()["client"]["phone_number"] == "613-555-0142"

    def test_client_id_and_new_client_together_is_400(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        response = convert(
            client,
            estimate["id"],
            client_id=customer["id"],
            new_client={"name": "Other", "address": "1 Yonge St"},
        )

        assert response.status_code == 400
        assert "not both" in response.json()["detail"]

    def test_estimate_with_no_client_at_all_is_rejected(self, client):
        estimate = make_estimate(client)

        response = convert(client, estimate["id"])

        assert response.status_code == 400
        assert "no client" in response.json()["detail"].lower()
        assert client.get("/api/jobs/").json() == []

    def test_large_estimate_leaves_duration_unset(self, client):
        """Regression: 208 hours overflows Job.estimated_duration's Numeric(4,2)."""
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            tasks=[{"phase": "build", "description": "Long build", "hours": 208.5, "sort_order": 0}],
        )

        response = convert(client, estimate["id"])

        assert response.status_code == 201, response.text
        job = response.json()
        assert job["estimated_duration"] is None
        # The rest of the row still landed
        assert Decimal(job["estimate_amount"]) == Decimal(estimate["total"])

    def test_redseal_flag_derived_from_tagged_task(self, client):
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            redseal_techs=0,
            tasks=[{"phase": "build", "description": "Weld", "hours": 6, "uses_redseal": True, "sort_order": 0}],
        )

        job = convert(client, estimate["id"]).json()

        assert job["is_redseal_trade"] is True

    def test_redseal_flag_can_be_overridden(self, client):
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            redseal_techs=2,
            tasks=[{"phase": "build", "description": "Weld", "hours": 6, "uses_redseal": True, "sort_order": 0}],
        )

        job = convert(client, estimate["id"], is_redseal_trade=False).json()

        assert job["is_redseal_trade"] is False

    def test_estimate_distance_carried_to_job(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"], distance_km=42.5)

        job = convert(client, estimate["id"]).json()

        assert Decimal(job["calculated_distance_km"]) == Decimal("42.50")

    def test_missing_title_is_422(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        response = client.post(
            f"/api/estimates/{estimate['id']}/convert-to-job",
            json={"start_date": "2026-03-02"},
        )

        assert response.status_code == 422

    def test_blank_title_is_422(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        assert convert(client, estimate["id"], title="").status_code == 422

    def test_end_before_start_is_400(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        response = convert(client, estimate["id"], start_date="2026-03-06", end_date="2026-03-02")

        assert response.status_code == 400
        assert "End date" in response.json()["detail"]

    def test_unknown_estimate_is_404(self, client):
        assert convert(client, 9999).status_code == 404

    def test_unknown_worker_is_404_and_creates_nothing(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        response = convert(client, estimate["id"], assigned_worker_ids=[999])

        assert response.status_code == 404
        assert "Worker 999" in response.json()["detail"]
        assert client.get("/api/jobs/").json() == []
        assert client.get(f"/api/estimates/{estimate['id']}").json()["status"] == "draft"

    def test_estimate_still_editable_after_convert(self, client):
        """The link must survive a round-trip save, or /financials loses the budget."""
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])
        job = convert(client, estimate["id"]).json()

        update = {**BASE_ESTIMATE, "client_id": customer["id"], "job_id": job["id"]}
        response = client.put(f"/api/estimates/{estimate['id']}", json=update)

        assert response.status_code == 200, response.text
        assert response.json()["job"]["id"] == job["id"]

    def test_converted_estimate_hidden_from_standalone_listing(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])
        convert(client, estimate["id"])

        standalone = client.get("/api/estimates/?standalone=true").json()
        everything = client.get("/api/estimates/").json()

        assert [e["id"] for e in standalone] == []
        assert estimate["id"] in [e["id"] for e in everything]
        assert [e for e in everything if e["id"] == estimate["id"]][0]["job_id"] is not None


class TestRedSealFlagOnConversion:
    """
    A converted job is a Red Seal trade only when the estimate tagged Red Seal work.

    redseal_techs must not count: it used to be auto-filled from crew size, so it is
    non-zero on almost every estimate saved before that default was dropped. Keying off
    it flagged ordinary jobs as Red Seal and billed them $100/hr against an $80/hr quote.
    """

    def test_untagged_estimate_does_not_make_a_redseal_job(self, client):
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            crew_size=2,
            redseal_techs=2,  # what the calculator used to auto-fill
            tasks=[{"phase": "build", "description": "Paint", "hours": 10, "sort_order": 0}],
        )
        assert Decimal(estimate["redseal_amount"]) == Decimal("0"), "estimate quoted no Red Seal"

        job = convert(client, estimate["id"]).json()

        assert job["is_redseal_trade"] is False

    def test_tagged_estimate_does_make_a_redseal_job(self):
        from app.api.estimates import _is_redseal_estimate
        from app.models import Estimate, EstimateTask

        estimate = Estimate(estimate_number="EST-1", redseal_techs=0)
        estimate.tasks = [
            EstimateTask(phase="build", description="Weld", hours=Decimal("6"), uses_redseal=True)
        ]

        assert _is_redseal_estimate(estimate) is True

    def test_tech_count_alone_is_not_a_signal(self):
        from app.api.estimates import _is_redseal_estimate
        from app.models import Estimate, EstimateTask

        estimate = Estimate(estimate_number="EST-1", redseal_techs=5)
        estimate.tasks = [
            EstimateTask(phase="build", description="Paint", hours=Decimal("6"), uses_redseal=False)
        ]

        assert _is_redseal_estimate(estimate) is False


class TestConvertedJobReachesTheCrew:
    """
    The reported failure: a job went through from an estimate and the crew arrived
    with no phone number for the client, no idea a jackhammer had to be rented, and
    no material list. All three ride on the job response now.
    """

    def test_job_carries_the_gear_and_materials_to_the_crew(self, client):
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            equipment_rows=[
                {
                    "category": "rentalVillage", "description": "Jackhammer",
                    "rate": 95, "unit": "per day", "quantity": 1, "sort_order": 0,
                },
            ],
            material_rows=[
                {"description": "Concrete mix", "quantity": 12, "unit_cost": 8.5, "sort_order": 0},
            ],
            tooling_rows=[
                {"description": "Breaker bits", "quantity": 2, "unit_cost": 40, "sort_order": 0},
            ],
        )

        job = convert(client, estimate["id"]).json()
        fetched = client.get(f"/api/jobs/{job['id']}")

        assert fetched.status_code == 200, fetched.text
        items = fetched.json()["prep_items"]
        assert [(i["section"], i["description"], i["quantity"]) for i in items] == [
            ("Equipment & rentals", "Jackhammer (Outside rental)", "1"),
            ("Materials", "Concrete mix", "12"),
            ("Tooling & supplies", "Breaker bits", "2"),
        ]

    def test_crew_list_never_carries_a_price(self, client):
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            material_rows=[
                {"description": "Concrete mix", "quantity": 12, "unit_cost": 8.5, "sort_order": 0},
            ],
        )

        job = convert(client, estimate["id"]).json()
        items = client.get(f"/api/jobs/{job['id']}").json()["prep_items"]

        assert items
        for item in items:
            assert set(item) == {"section", "description", "quantity", "unit"}
            assert "8.5" not in str(item)

    def test_empty_scaffolding_does_not_reach_the_crew(self, client):
        """A new estimate seeds all three components at zero so the boxes start empty."""
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            scaffolding_rows=[
                {"component": "frame", "rate_per_day": 0, "quantity": 0, "sort_order": 0},
                {"component": "jack", "rate_per_day": 0, "quantity": 0, "sort_order": 1},
            ],
        )

        job = convert(client, estimate["id"]).json()

        assert client.get(f"/api/jobs/{job['id']}").json()["prep_items"] == []

    def test_job_carries_the_client_phone(self, client):
        customer = make_client(client, phone="613-555-0142")
        estimate = make_estimate(client, client_id=customer["id"])

        job = convert(client, estimate["id"]).json()
        fetched = client.get(f"/api/jobs/{job['id']}").json()

        assert fetched["client"]["phone_number"] == "613-555-0142"

    def test_job_carries_the_scope_of_work(self, client):
        customer = make_client(client)
        estimate = make_estimate(client, client_id=customer["id"])

        job = convert(client, estimate["id"]).json()
        fetched = client.get(f"/api/jobs/{job['id']}").json()

        assert fetched["details"] == (
            "Recert the boiler\nSecond line of scope\n\nThe Build\n- Build"
        )

    def test_the_crew_reads_the_phases_in_working_order(self, client):
        """
        Entered finishing-first, and the estimate response serializer sorts tasks
        alphabetically by phase, so anything trusting that order would hand the crew
        The Build before Preplanning.
        """
        customer = make_client(client)
        estimate = make_estimate(
            client,
            client_id=customer["id"],
            scope_of_work=None,
            tasks=[
                {"phase": "finishing", "description": "Sand and stain", "hours": 4, "sort_order": 0},
                {"phase": "build", "description": "Frame and joist", "hours": 12, "sort_order": 0},
                {"phase": "preplanning", "description": "Pull the permit", "hours": 2, "sort_order": 0},
            ],
        )

        job = convert(client, estimate["id"]).json()
        details = client.get(f"/api/jobs/{job['id']}").json()["details"]

        assert details == (
            "Preplanning\n- Pull the permit\n\n"
            "The Build\n- Frame and joist\n\n"
            "Finishing\n- Sand and stain"
        )
        assert "12" not in details, "hours price the task, they do not describe it"

    def test_a_job_with_no_estimate_has_no_crew_list(self, client):
        customer = make_client(client)
        created = client.post(
            "/api/jobs/",
            json={"client_id": customer["id"], "title": "Callout"},
        )

        assert created.status_code == 201, created.text
        assert created.json()["prep_items"] == []
