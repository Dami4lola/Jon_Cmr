"""
What the crew needs on site, taken from the job's estimate.

The estimator already itemises every rental, material and tool while pricing the work,
but none of it was reaching the people doing the job: the rows live on the estimate, the
conversion copies none of them onto the Job, and every estimate endpoint is gated behind
EstimatorUser, which a worker fails. This projects those rows into a crew-facing list.

Costs are deliberately absent. The crew needs to know a jackhammer has to be picked up,
not what it rents for, and the list is served on GET /api/jobs/ to whoever is assigned.
"""
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models.estimate import EquipmentCategory, ScaffoldingComponent
from ..schemas.job import JobPrepItem

if TYPE_CHECKING:
    from ..models.job import Job
    from ..models.estimate import Estimate


EQUIPMENT_CATEGORY_LABELS = {
    EquipmentCategory.HEAVY.value: "Heavy equipment",
    EquipmentCategory.OWNED_RENTAL.value: "Owned rental",
    EquipmentCategory.SCAFFOLDING.value: "Scaffolding",
    EquipmentCategory.RENTAL_VILLAGE.value: "Outside rental",
    EquipmentCategory.FUEL.value: "Fuel",
}

SCAFFOLDING_LABELS = {
    ScaffoldingComponent.FRAME.value: "Frames (incl. crossers)",
    ScaffoldingComponent.CROSSER.value: "Crossers",
    ScaffoldingComponent.JACK.value: "Jacks",
    ScaffoldingComponent.PLANK.value: "Planks",
}

SECTION_EQUIPMENT = "Equipment & rentals"
SECTION_MATERIALS = "Materials"
SECTION_TOOLING = "Tooling & supplies"
SECTION_SCAFFOLDING = "Scaffolding"


def _format_quantity(quantity: Decimal) -> str:
    """
    Trim the stored scale so Numeric(8,2)'s 4.00 reads as 4 and 2.50 as 2.5.

    Not the estimate PDF's f"{value:g}" - that silently does nothing to a Decimal,
    which is why hours still print as 4.00 there. normalize() alone would turn 40
    into 4E+1, so the fixed-point format is what brings it back.
    """
    return f"{quantity.normalize():f}"


def _equipment_items(estimate: "Estimate") -> list[JobPrepItem]:
    items = []
    for row in sorted(estimate.equipment_rows, key=lambda r: r.sort_order):
        if not row.description.strip() or row.quantity <= 0:
            continue
        # The category is what separates "pick this up from the rental yard" from
        # "it is already on the truck", so it rides along with the description.
        label = EQUIPMENT_CATEGORY_LABELS.get(row.category)
        items.append(JobPrepItem(
            section=SECTION_EQUIPMENT,
            description=f"{row.description} ({label})" if label else row.description,
            quantity=_format_quantity(row.quantity),
            unit=row.unit or None,
        ))
    return items


def _described_items(rows, section: str) -> list[JobPrepItem]:
    """Material and tooling rows - identical shape, only the section differs."""
    items = []
    for row in sorted(rows, key=lambda r: r.sort_order):
        if not row.description.strip() or row.quantity <= 0:
            continue
        items.append(JobPrepItem(
            section=section,
            description=row.description,
            quantity=_format_quantity(row.quantity),
            unit=None,
        ))
    return items


def _scaffolding_items(estimate: "Estimate") -> list[JobPrepItem]:
    items = []
    for row in sorted(estimate.scaffolding_rows, key=lambda r: r.sort_order):
        # A new estimate seeds every component at zero so the boxes start empty -
        # without this the crew list would show three components nobody asked for.
        if row.quantity <= 0:
            continue
        items.append(JobPrepItem(
            section=SECTION_SCAFFOLDING,
            description=SCAFFOLDING_LABELS.get(row.component, row.component),
            quantity=_format_quantity(row.quantity),
            unit=None,
        ))
    return items


def prep_items_for_job(job: "Job") -> list[JobPrepItem]:
    """
    The gear and materials list for this job, or empty when it has no estimate.

    Read straight off the linked estimate rather than copied at conversion, so a
    material added while the job is still open reaches the crew instead of stranding
    them with whatever was quoted weeks earlier.
    """
    estimate = job.estimate
    if not estimate:
        return []

    return [
        *_equipment_items(estimate),
        *_described_items(estimate.material_rows, SECTION_MATERIALS),
        *_described_items(estimate.tooling_rows, SECTION_TOOLING),
        *_scaffolding_items(estimate),
    ]
