"""
What the crew gets off the job, taken from the estimate behind it.

The estimator itemises every rental, material and tool while pricing the work, and writes
the work itself out as tasks under three phases - but none of it was reaching the people
doing the job. The rows live on the estimate, the conversion copied only the free-text
scope, and every estimate endpoint is gated behind EstimatorUser, which a worker fails.

Two projections live here: the gear list, and the scope of work. Both drop the money and
the hours. The crew needs to know a jackhammer has to be picked up and what the task is,
not what either costs, and this is served to whoever is assigned to the job.
"""
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models.estimate import EquipmentCategory, EstimatePhase, ScaffoldingComponent
from ..schemas.job import JobPrepItem

if TYPE_CHECKING:
    from ..models.job import Job
    from ..models.estimate import Estimate


# Phases read in the order the work happens, never alphabetically - the estimate response
# serializer sorts them by name, which puts The Build before Preplanning.
PHASE_ORDER = [
    EstimatePhase.PREPLANNING.value,
    EstimatePhase.BUILD.value,
    EstimatePhase.FINISHING.value,
]

PHASE_LABELS = {
    EstimatePhase.PREPLANNING.value: "Preplanning",
    EstimatePhase.BUILD.value: "The Build",
    EstimatePhase.FINISHING.value: "Finishing",
}

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


def _phase_block(estimate: "Estimate", phase: str) -> str | None:
    """One phase heading and its task lines, or nothing when the phase is empty."""
    lines = [
        f"- {task.description.strip()}"
        for task in sorted(estimate.tasks, key=lambda t: t.sort_order)
        if task.phase == phase and task.description.strip()
    ]
    if not lines:
        return None
    return "\n".join([PHASE_LABELS[phase], *lines])


def job_scope_from_estimate(estimate: "Estimate") -> str | None:
    """
    The scope of work as the crew reads it: the estimator's written scope, then the
    tasks they priced, grouped under their phase.

    Hours are left out. They are what the task costs, not what it is, and the crew
    reading this on their dashboard needs the second. The Red Seal and heavy-equipment
    tags the PDF appends are left out for the same reason.

    None rather than an empty string when there is nothing to say, so Job.details
    stays null instead of becoming blank text.
    """
    written = (estimate.scope_of_work or "").strip()
    blocks = [written] if written else []
    blocks.extend(
        block for block in (_phase_block(estimate, phase) for phase in PHASE_ORDER) if block
    )
    return "\n\n".join(blocks) or None
