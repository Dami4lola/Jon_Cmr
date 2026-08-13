"""
Tests for the persisted Estimate builder: the pure calculation function
(_calculate_estimate_amounts) and the full CRUD + PDF API.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.api.estimates import _calculate_estimate_amounts
from app.schemas.estimate import EstimateTaskCreate, EstimateEquipmentRowCreate, EstimateMaterialRowCreate


def _task(phase, hours, heavy=False):
    return EstimateTaskCreate(phase=phase, description="task", hours=Decimal(str(hours)), uses_heavy_equipment=heavy)


def _equipment(category, rate, qty=1, markup=0):
    return EstimateEquipmentRowCreate(
        category=category, description="equip", rate=Decimal(str(rate)),
        quantity=Decimal(str(qty)), markup_pct=Decimal(str(markup)),
    )


def _material(qty, unit_cost):
    return EstimateMaterialRowCreate(description="material", quantity=Decimal(str(qty)), unit_cost=Decimal(str(unit_cost)))


class TestCalculateEstimateAmounts:
    def test_matches_sample_estimate(self):
        """Verified against the user-provided sample: 66.5 total hours, 2 techs,
        $80/hr standard rate -> $10,640 labour, ceil(66.5/7) = 10 travel days."""
        tasks = [
            *[_task("preplanning", h) for h in [3, 1, 2, 1.5, 2, 4, 3, 1]],
            _task("preplanning", 1, heavy=True),
            _task("preplanning", 4, heavy=True),
            *[_task("build", h) for h in [12, 10, 5, 3, 6, 0.5, 1]],
            _task("build", 1, heavy=True),
            *[_task("finishing", h) for h in [1.5, 2, 1]],
            _task("finishing", 1, heavy=True),
        ]
        amounts = _calculate_estimate_amounts(
            tasks=tasks, equipment_rows=[], material_rows=[],
            crew_size=2, techs_traveling=2, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=True,
        )
        assert amounts["total_hours"] == Decimal("66.5")
        assert amounts["travel_days"] == 10
        assert amounts["labour_amount"] == Decimal("10640.00")

    def test_travel_amount_scales_with_days(self):
        amounts = _calculate_estimate_amounts(
            tasks=[_task("build", 14)], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=2, distance_km=Decimal("20"), km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=True,
        )
        # 14 hours -> ceil(14/7) = 2 days; 2 techs * 20km * $1.50 * 2 days = $120
        assert amounts["travel_days"] == 2
        assert amounts["travel_amount"] == Decimal("120.00")

    def test_no_distance_means_no_travel_charge(self):
        amounts = _calculate_estimate_amounts(
            tasks=[_task("build", 10)], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=True,
        )
        assert amounts["travel_amount"] == Decimal("0.00")

    def test_zero_hours_means_zero_travel_days(self):
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=Decimal("20"), km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=True,
        )
        assert amounts["travel_days"] == 0
        assert amounts["travel_amount"] == Decimal("0.00")

    def test_equipment_category_rollup(self):
        equipment_rows = [
            _equipment("heavy", 100),
            _equipment("ownedRental", 50),
            _equipment("scaffolding", 30),
            _equipment("rentalVillage", 20),
            _equipment("fuel", 40),
        ]
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=equipment_rows, material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=True,
        )
        assert amounts["heavy_equipment_amount"] == Decimal("100.00")
        assert amounts["fuel_amount"] == Decimal("40.00")
        # ownedRental + scaffolding + rentalVillage = 50 + 30 + 20
        assert amounts["rental_amount"] == Decimal("100.00")

    def test_materials_amount_sums_quantity_times_unit_cost(self):
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=[], material_rows=[_material(3, 10), _material(2, 5)],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=True,
        )
        assert amounts["materials_amount"] == Decimal("40.00")

    def test_admin_fee_excluded_when_toggle_off(self):
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("100"),
            redseal_amount=Decimal("0"), include_admin_fee=False, include_hst=True,
        )
        assert amounts["subtotal"] == Decimal("0.00")

    def test_hst_excluded_when_toggle_off(self):
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("100"), permits_fee=Decimal("0"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=False,
        )
        assert amounts["hst_amount"] == Decimal("0.00")
        assert amounts["total"] == amounts["subtotal"] == Decimal("100.00")

    def test_dump_permits_redseal_are_flat_additions(self):
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("50"), permits_fee=Decimal("75"), admin_fee=Decimal("0"),
            redseal_amount=Decimal("200"), include_admin_fee=True, include_hst=False,
        )
        assert amounts["subtotal"] == Decimal("325.00")

    @pytest.mark.parametrize(
        "hours,expected_travel_days,expected_periods",
        [
            (49, 7, 1),    # 7 travel days -> 1 admin fee
            (98, 14, 2),   # 14 travel days -> 2 admin fees
            (147, 21, 3),  # 21 travel days -> 3 admin fees
            (66.5, 10, 1),  # sample estimate: 10 travel days -> still just 1 fee
        ],
    )
    def test_admin_fee_charged_once_per_complete_7day_period(self, hours, expected_travel_days, expected_periods):
        amounts = _calculate_estimate_amounts(
            tasks=[_task("build", hours)], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("50"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=False,
        )
        assert amounts["travel_days"] == expected_travel_days
        assert amounts["admin_amount"] == Decimal("50.00") * expected_periods

    def test_admin_fee_applies_once_for_a_short_job_under_7_days(self):
        # 10 hours -> 2 travel days (under a full 7-day period), but the
        # admin fee still applies once since there's real work on the job.
        amounts = _calculate_estimate_amounts(
            tasks=[_task("build", 10)], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("50"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=False,
        )
        assert amounts["travel_days"] == 2
        assert amounts["admin_amount"] == Decimal("50.00")

    def test_admin_fee_is_zero_with_no_tasks(self):
        # No tasks at all -> nothing to charge an admin fee against yet
        amounts = _calculate_estimate_amounts(
            tasks=[], equipment_rows=[], material_rows=[],
            crew_size=1, techs_traveling=1, distance_km=None, km_rate=Decimal("1.50"),
            dump_fee=Decimal("0"), permits_fee=Decimal("0"), admin_fee=Decimal("50"),
            redseal_amount=Decimal("0"), include_admin_fee=True, include_hst=False,
        )
        assert amounts["travel_days"] == 0
        assert amounts["admin_amount"] == Decimal("0.00")


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

    def override_get_current_user():
        return FakeManager()

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_current_user] = override_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()


MINIMAL_PAYLOAD = {
    "scope_of_work": "Test job",
    "crew_size": 2,
    "techs_traveling": 2,
    "dump_fee": 0,
    "permits_fee": 0,
    "admin_fee": 50,
    "redseal_amount": 0,
    "include_admin_fee": True,
    "include_hst": True,
    "tasks": [
        {"phase": "preplanning", "description": "Prep", "hours": 3.5, "uses_heavy_equipment": False, "sort_order": 0},
        {"phase": "build", "description": "Build", "hours": 10, "uses_heavy_equipment": True, "sort_order": 0},
    ],
    "equipment_rows": [
        {"category": "heavy", "description": "Excavator", "rate": 100, "unit": "per day", "quantity": 1, "markup_pct": 0, "sort_order": 0},
    ],
    "material_rows": [
        {"description": "Lumber", "quantity": 2, "unit_cost": 25, "sort_order": 0},
    ],
}


class TestEstimateApi:
    def test_create_and_get(self, client):
        resp = client.post("/api/estimates/", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_hours"] == "13.50"
        assert data["estimate_number"].startswith("EST-")
        assert len(data["tasks"]) == 2
        assert len(data["equipment_rows"]) == 1
        assert len(data["material_rows"]) == 1

        get_resp = client.get(f"/api/estimates/{data['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == data["id"]

    def test_update_replaces_child_rows_and_recomputes(self, client):
        create_resp = client.post("/api/estimates/", json=MINIMAL_PAYLOAD)
        estimate_id = create_resp.json()["id"]

        updated_payload = dict(MINIMAL_PAYLOAD)
        updated_payload["tasks"] = [
            {"phase": "finishing", "description": "Only task now", "hours": 5, "uses_heavy_equipment": False, "sort_order": 0},
        ]
        update_resp = client.put(f"/api/estimates/{estimate_id}", json=updated_payload)
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["description"] == "Only task now"
        assert data["total_hours"] == "5.00"

    def test_list_filters_standalone(self, client):
        client.post("/api/estimates/", json=MINIMAL_PAYLOAD)
        resp = client.get("/api/estimates/", params={"standalone": True})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_pdf_download(self, client):
        create_resp = client.post("/api/estimates/", json=MINIMAL_PAYLOAD)
        estimate_id = create_resp.json()["id"]
        pdf_resp = client.get(f"/api/estimates/{estimate_id}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content[:4] == b"%PDF"

    def test_delete(self, client):
        create_resp = client.post("/api/estimates/", json=MINIMAL_PAYLOAD)
        estimate_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/estimates/{estimate_id}")
        assert del_resp.status_code == 204
        get_resp = client.get(f"/api/estimates/{estimate_id}")
        assert get_resp.status_code == 404

    def test_preview_does_not_persist(self, client):
        resp = client.post("/api/estimates/preview", json=MINIMAL_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["total_hours"] == "13.50"
        list_resp = client.get("/api/estimates/", params={"standalone": True})
        assert len(list_resp.json()) == 0

    def test_duplicate_job_id_rejected(self, client):
        job_resp = client.post(
            "/api/jobs/",
            json={"client_id": self._make_client(client), "title": "Test job", "details": "x"},
        )
        job_id = job_resp.json()["id"]

        payload = dict(MINIMAL_PAYLOAD)
        payload["job_id"] = job_id
        first = client.post("/api/estimates/", json=payload)
        assert first.status_code == 201

        second = client.post("/api/estimates/", json=payload)
        assert second.status_code == 400

    @staticmethod
    def _make_client(client):
        resp = client.post("/api/clients/", json={"name": "Test Client", "address": "1 Test St"})
        return resp.json()["id"]
