"""
Tests for creating clients: the contact rule, and who is allowed to.

Both were learned the hard way. Requiring a phone specifically walled off an estimate
for a prospect who had only ever given an email, and nothing anywhere pinned the
estimator's access to clients - which is how a working permission was mistaken for a
broken one.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool


# Mirrors the role predicates on models.User; keep in sync when new ones are added, or
# every gated route 500s here instead of returning its real status.
class FakeManager:
    id = 1
    is_active = True
    is_manager = True
    is_admin = True
    can_use_estimator = True


class FakeEstimator:
    """An estimator who is not a manager - the account this feature exists for."""
    id = 2
    is_active = True
    is_manager = False
    is_admin = False
    can_use_estimator = True


def build_client(user):
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.makedirs("uploads", exist_ok=True)

    from app.main import app
    from app.api import deps

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_current_user] = lambda: user
    return app, TestClient(app)


@pytest.fixture
def manager_client():
    from app.main import app
    _, test_client = build_client(FakeManager())
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def estimator_client():
    from app.main import app
    _, test_client = build_client(FakeEstimator())
    yield test_client
    app.dependency_overrides.clear()


def payload(**overrides):
    return {"name": "Acme Industrial", "address": "1 Bay St, Toronto", **overrides}


class TestContactRule:
    """A client needs one way to be reached - a phone or an email, either one."""

    def test_phone_alone_is_enough(self, manager_client):
        response = manager_client.post("/api/clients/", json=payload(phone_number="613-555-0142"))

        assert response.status_code == 201, response.text
        assert response.json()["phone_number"] == "613-555-0142"
        assert response.json()["email"] is None

    def test_email_alone_is_enough(self, manager_client):
        """The case that blocked an estimate: a prospect who only ever gave an email."""
        response = manager_client.post("/api/clients/", json=payload(email="bob@vance.com"))

        assert response.status_code == 201, response.text
        assert response.json()["email"] == "bob@vance.com"
        assert response.json()["phone_number"] is None

    def test_both_is_fine(self, manager_client):
        response = manager_client.post(
            "/api/clients/",
            json=payload(phone_number="613-555-0142", email="bob@vance.com"),
        )

        assert response.status_code == 201, response.text

    def test_neither_is_rejected(self, manager_client):
        response = manager_client.post("/api/clients/", json=payload())

        assert response.status_code == 422
        assert "phone number or an email" in response.text

    def test_a_whitespace_phone_does_not_count_as_contact(self, manager_client):
        response = manager_client.post("/api/clients/", json=payload(phone_number="   "))

        assert response.status_code == 422

    def test_an_address_is_still_required(self, manager_client):
        """Unchanged: the address is the site the crew drives to."""
        response = manager_client.post(
            "/api/clients/",
            json={"name": "Acme Industrial", "phone_number": "613-555-0142"},
        )

        assert response.status_code == 422


class TestEstimatorAccess:
    """
    An estimator builds estimates for people who are not clients yet, so they can add
    and correct a client. Deleting stays manager-only - it is destructive.
    """

    def test_estimator_can_list_clients(self, estimator_client):
        assert estimator_client.get("/api/clients/").status_code == 200

    def test_estimator_can_create_a_client(self, estimator_client):
        response = estimator_client.post("/api/clients/", json=payload(email="bob@vance.com"))

        assert response.status_code == 201, response.text

    def test_estimator_can_read_one_client(self, estimator_client):
        created = estimator_client.post(
            "/api/clients/", json=payload(phone_number="613-555-0142")
        ).json()

        assert estimator_client.get(f"/api/clients/{created['id']}").status_code == 200

    def test_estimator_can_correct_a_client(self, estimator_client):
        created = estimator_client.post(
            "/api/clients/", json=payload(phone_number="613-555-0142")
        ).json()

        response = estimator_client.put(
            f"/api/clients/{created['id']}", json={"address": "99 Queen St, Toronto"}
        )

        assert response.status_code == 200, response.text
        assert response.json()["address"] == "99 Queen St, Toronto"

    def test_estimator_cannot_delete_a_client(self, estimator_client):
        created = estimator_client.post(
            "/api/clients/", json=payload(phone_number="613-555-0142")
        ).json()

        response = estimator_client.delete(f"/api/clients/{created['id']}")

        assert response.status_code == 403
        assert response.json()["detail"] == "Manager access required"

    def test_a_manager_can_still_delete(self, manager_client):
        created = manager_client.post(
            "/api/clients/", json=payload(phone_number="613-555-0142")
        ).json()

        assert manager_client.delete(f"/api/clients/{created['id']}").status_code == 204
