"""
Tests for the crew's gear and materials list.

Pure-function tests against in-memory model objects: prep_items_for_job walks
relationships and does no IO, so there is nothing here worth a database for.
"""
from decimal import Decimal

from app.models import Job
from app.models.estimate import (
    Estimate,
    EstimateEquipmentRow,
    EstimateMaterialRow,
    EstimateScaffoldingRow,
    EstimateToolingRow,
)
from app.services.job_prep import (
    SECTION_EQUIPMENT,
    SECTION_MATERIALS,
    SECTION_SCAFFOLDING,
    SECTION_TOOLING,
    prep_items_for_job,
)


def make_job(**rows) -> Job:
    estimate = Estimate(estimate_number="EST-1")
    estimate.equipment_rows = rows.get("equipment", [])
    estimate.material_rows = rows.get("materials", [])
    estimate.tooling_rows = rows.get("tooling", [])
    estimate.scaffolding_rows = rows.get("scaffolding", [])
    job = Job(client_id=1, title="Deck rebuild")
    job.estimate = estimate
    return job


class TestSections:
    def test_equipment_row_names_its_category(self):
        """The reported case: the crew never learned a jackhammer had to be rented."""
        job = make_job(equipment=[
            EstimateEquipmentRow(
                category="rentalVillage", description="Jackhammer",
                quantity=Decimal("1"), unit="per day", rate=Decimal("95"),
            )
        ])

        items = prep_items_for_job(job)

        assert len(items) == 1
        assert items[0].section == SECTION_EQUIPMENT
        assert items[0].description == "Jackhammer (Outside rental)"
        assert items[0].quantity == "1"
        assert items[0].unit == "per day"

    def test_materials_and_tooling_land_in_their_own_sections(self):
        job = make_job(
            materials=[EstimateMaterialRow(description="2x6 cedar", quantity=Decimal("24"))],
            tooling=[EstimateToolingRow(description="Impact driver", quantity=Decimal("2"))],
        )

        sections = {item.section: item.description for item in prep_items_for_job(job)}

        assert sections == {
            SECTION_MATERIALS: "2x6 cedar",
            SECTION_TOOLING: "Impact driver",
        }

    def test_scaffolding_component_is_labelled(self):
        job = make_job(scaffolding=[
            EstimateScaffoldingRow(component="frame", quantity=Decimal("40"), rate_per_day=Decimal("1"))
        ])

        items = prep_items_for_job(job)

        assert items[0].section == SECTION_SCAFFOLDING
        assert items[0].description == "Frames (incl. crossers)"

    def test_sections_come_out_in_packing_order(self):
        job = make_job(
            equipment=[EstimateEquipmentRow(category="heavy", description="Excavator", quantity=Decimal("1"))],
            materials=[EstimateMaterialRow(description="Concrete", quantity=Decimal("12"))],
            tooling=[EstimateToolingRow(description="Laser level", quantity=Decimal("1"))],
            scaffolding=[EstimateScaffoldingRow(component="jack", quantity=Decimal("20"))],
        )

        assert [item.section for item in prep_items_for_job(job)] == [
            SECTION_EQUIPMENT, SECTION_MATERIALS, SECTION_TOOLING, SECTION_SCAFFOLDING,
        ]

    def test_rows_keep_the_estimators_ordering(self):
        job = make_job(materials=[
            EstimateMaterialRow(description="Second", quantity=Decimal("1"), sort_order=1),
            EstimateMaterialRow(description="First", quantity=Decimal("1"), sort_order=0),
        ])

        assert [item.description for item in prep_items_for_job(job)] == ["First", "Second"]


class TestEmptyRowsAreDropped:
    def test_zero_quantity_scaffolding_is_not_listed(self):
        """
        A new estimate seeds all three components at zero so the boxes start empty.
        Without this every converted job would list scaffolding nobody asked for.
        """
        job = make_job(scaffolding=[
            EstimateScaffoldingRow(component="frame", quantity=Decimal("0")),
            EstimateScaffoldingRow(component="jack", quantity=Decimal("0")),
            EstimateScaffoldingRow(component="plank", quantity=Decimal("35")),
        ])

        items = prep_items_for_job(job)

        assert [item.description for item in items] == ["Planks"]

    def test_blank_description_is_not_listed(self):
        job = make_job(materials=[
            EstimateMaterialRow(description="   ", quantity=Decimal("5")),
            EstimateMaterialRow(description="Screws", quantity=Decimal("2")),
        ])

        assert [item.description for item in prep_items_for_job(job)] == ["Screws"]

    def test_zero_quantity_material_is_not_listed(self):
        job = make_job(materials=[EstimateMaterialRow(description="Sand", quantity=Decimal("0"))])

        assert prep_items_for_job(job) == []

    def test_job_with_no_estimate_has_no_list(self):
        """Jobs created by hand on the Manager Dashboard have no estimate behind them."""
        job = Job(client_id=1, title="Callout")
        job.estimate = None

        assert prep_items_for_job(job) == []


class TestNoCostsLeak:
    def test_no_money_field_reaches_the_crew(self):
        """
        The whole point of the projection. This list is served to every assigned
        worker on GET /api/jobs/, so a rate or unit cost here is a leak.
        """
        job = make_job(
            equipment=[EstimateEquipmentRow(
                category="heavy", description="Excavator", quantity=Decimal("1"),
                rate=Decimal("120"), markup_pct=Decimal("15"),
            )],
            materials=[EstimateMaterialRow(
                description="Concrete", quantity=Decimal("12"), unit_cost=Decimal("8.50"),
            )],
            scaffolding=[EstimateScaffoldingRow(
                component="plank", quantity=Decimal("35"), rate_per_day=Decimal("3"),
            )],
        )

        for item in prep_items_for_job(job):
            dumped = item.model_dump()
            assert set(dumped) == {"section", "description", "quantity", "unit"}
            assert "120" not in str(dumped)
            assert "8.50" not in str(dumped)


class TestQuantityFormatting:
    def test_trailing_zeros_are_trimmed(self):
        job = make_job(materials=[EstimateMaterialRow(description="Board", quantity=Decimal("4.00"))])

        assert prep_items_for_job(job)[0].quantity == "4"

    def test_a_real_fraction_survives(self):
        job = make_job(materials=[EstimateMaterialRow(description="Board", quantity=Decimal("2.50"))])

        assert prep_items_for_job(job)[0].quantity == "2.5"
