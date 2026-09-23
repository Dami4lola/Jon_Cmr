"""
Tests for what the crew gets off a job - the gear list and the scope of work.

Pure-function tests against in-memory model objects: both projections walk
relationships and do no IO, so there is nothing here worth a database for.
"""
from decimal import Decimal

from app.models import Job
from app.models.estimate import (
    Estimate,
    EstimateEquipmentRow,
    EstimateMaterialRow,
    EstimateScaffoldingRow,
    EstimateTask,
    EstimateToolingRow,
)
from app.services.job_prep import (
    SECTION_EQUIPMENT,
    SECTION_MATERIALS,
    SECTION_SCAFFOLDING,
    SECTION_TOOLING,
    job_scope_from_estimate,
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


def make_estimate(scope=None, tasks=()):
    estimate = Estimate(estimate_number="EST-1", scope_of_work=scope)
    estimate.tasks = list(tasks)
    return estimate


def task(phase, description, hours="4", sort_order=0):
    return EstimateTask(
        phase=phase, description=description,
        hours=Decimal(hours), sort_order=sort_order,
    )


class TestJobScope:
    def test_written_scope_comes_first_then_the_phases(self):
        estimate = make_estimate(
            scope="Rebuild the rear deck to code.",
            tasks=[task("build", "Frame and joist")],
        )

        assert job_scope_from_estimate(estimate) == (
            "Rebuild the rear deck to code.\n\nThe Build\n- Frame and joist"
        )

    def test_phases_read_in_working_order_however_they_were_entered(self):
        """
        The whole point. The estimate response serializer sorts tasks alphabetically
        by phase, which puts The Build ahead of Preplanning.
        """
        estimate = make_estimate(tasks=[
            task("finishing", "Sand and stain"),
            task("build", "Frame and joist"),
            task("preplanning", "Pull the permit"),
        ])

        assert job_scope_from_estimate(estimate) == (
            "Preplanning\n- Pull the permit\n\n"
            "The Build\n- Frame and joist\n\n"
            "Finishing\n- Sand and stain"
        )

    def test_sort_order_holds_within_a_phase(self):
        estimate = make_estimate(tasks=[
            task("build", "Second", sort_order=1),
            task("build", "First", sort_order=0),
        ])

        assert job_scope_from_estimate(estimate) == "The Build\n- First\n- Second"

    def test_hours_never_reach_the_crew(self):
        """Hours are what a task costs, not what it is."""
        estimate = make_estimate(tasks=[task("build", "Frame and joist", hours="12.50")])

        scope = job_scope_from_estimate(estimate)

        assert "12" not in scope
        assert scope == "The Build\n- Frame and joist"

    def test_an_empty_phase_gets_no_heading(self):
        estimate = make_estimate(tasks=[task("build", "Frame and joist")])

        scope = job_scope_from_estimate(estimate)

        assert "Preplanning" not in scope
        assert "Finishing" not in scope

    def test_a_blank_task_is_skipped(self):
        estimate = make_estimate(tasks=[
            task("build", "   "),
            task("build", "Frame and joist", sort_order=1),
        ])

        assert job_scope_from_estimate(estimate) == "The Build\n- Frame and joist"

    def test_a_phase_of_only_blank_tasks_gets_no_heading(self):
        estimate = make_estimate(scope="Deck work", tasks=[task("preplanning", "  ")])

        assert job_scope_from_estimate(estimate) == "Deck work"

    def test_written_scope_alone_when_there_are_no_tasks(self):
        """Older estimates predate the phased task rows."""
        estimate = make_estimate(scope="Recert the boiler")

        assert job_scope_from_estimate(estimate) == "Recert the boiler"

    def test_tasks_alone_when_nothing_was_written(self):
        estimate = make_estimate(tasks=[task("preplanning", "Pull the permit")])

        assert job_scope_from_estimate(estimate) == "Preplanning\n- Pull the permit"

    def test_nothing_at_all_is_none_not_blank(self):
        """Job.details stays null rather than becoming empty text."""
        assert job_scope_from_estimate(make_estimate()) is None

    def test_a_whitespace_only_scope_is_not_treated_as_written(self):
        estimate = make_estimate(scope="   \n ", tasks=[task("build", "Frame")])

        assert job_scope_from_estimate(estimate) == "The Build\n- Frame"
