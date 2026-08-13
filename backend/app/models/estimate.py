"""
Estimate models - a persisted, reopenable estimate with a written scope of
work, hours broken down into named tasks across three phases, and a full
cost breakdown, replacing the old ephemeral-only calculator output.
"""
from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
from datetime import date
from typing import TYPE_CHECKING, List, Optional
from enum import Enum

if TYPE_CHECKING:
    from .job import Job
    from .client import Client


class EstimatePhase(str, Enum):
    PREPLANNING = "preplanning"
    BUILD = "build"
    FINISHING = "finishing"


class EquipmentCategory(str, Enum):
    HEAVY = "heavy"
    OWNED_RENTAL = "ownedRental"
    SCAFFOLDING = "scaffolding"
    RENTAL_VILLAGE = "rentalVillage"
    FUEL = "fuel"


class EstimateStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Estimate(SQLModel, table=True):
    """A persisted, reopenable estimate - scope of work, phased task hours, and cost breakdown"""
    __tablename__ = "estimate"

    id: int | None = Field(default=None, primary_key=True)

    # Standalone estimates (Admin Estimate page, no job yet) vs job-linked
    # (Manager Dashboard create/edit job flow). client_name_override /
    # address_override mirror Job.address_override's "use this if no linked
    # record" pattern, for prospects who aren't a Client row yet.
    job_id: int | None = Field(default=None, foreign_key="job.id", index=True, unique=True)
    client_id: int | None = Field(default=None, foreign_key="client.id", index=True)
    client_name_override: str | None = Field(default=None, max_length=100)
    address_override: str | None = Field(default=None)

    estimate_number: str = Field(unique=True, index=True, max_length=20)
    created_date: date = Field(default_factory=date.today)

    scope_of_work: str | None = Field(default=None)
    notes: str | None = Field(default=None)

    # Crew / travel
    crew_size: int = Field(default=1)
    techs_traveling: int = Field(default=1)
    distance_km: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    km_rate: Decimal = Field(default=Decimal("1.50"), max_digits=5, decimal_places=2)

    # Flat manually-entered fees (no formula - typed in directly, like admin_fee)
    dump_fee: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    permits_fee: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    admin_fee: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    redseal_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    include_admin_fee: bool = Field(default=True)
    include_hst: bool = Field(default=True)

    # Computed rollups, frozen at save time (recomputed from child rows on every create/update)
    total_hours: Decimal = Field(default=Decimal("0"), max_digits=8, decimal_places=2)
    travel_days: int = Field(default=0)
    labour_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    travel_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    materials_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    heavy_equipment_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    rental_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    fuel_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    admin_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    subtotal: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    hst_amount: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    total: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)

    status: str = Field(default=EstimateStatus.DRAFT.value, max_length=10)

    # Relationships
    job: Optional["Job"] = Relationship(back_populates="estimate")
    client: Optional["Client"] = Relationship()
    tasks: List["EstimateTask"] = Relationship(
        back_populates="estimate", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    equipment_rows: List["EstimateEquipmentRow"] = Relationship(
        back_populates="estimate", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    material_rows: List["EstimateMaterialRow"] = Relationship(
        back_populates="estimate", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class EstimateTask(SQLModel, table=True):
    """A named task with hours, grouped into a phase (preplanning/build/finishing)"""
    __tablename__ = "estimate_task"

    id: int | None = Field(default=None, primary_key=True)
    estimate_id: int = Field(foreign_key="estimate.id", index=True)

    phase: str = Field(max_length=20)  # EstimatePhase value
    description: str = Field(max_length=500)
    hours: Decimal = Field(max_digits=6, decimal_places=2)
    uses_heavy_equipment: bool = Field(default=False)
    sort_order: int = Field(default=0)

    estimate: Optional["Estimate"] = Relationship(back_populates="tasks")


class EstimateEquipmentRow(SQLModel, table=True):
    """An equipment/rental/fuel line item on an estimate"""
    __tablename__ = "estimate_equipment_row"

    id: int | None = Field(default=None, primary_key=True)
    estimate_id: int = Field(foreign_key="estimate.id", index=True)

    category: str = Field(max_length=20)  # EquipmentCategory value
    description: str = Field(max_length=500)
    rate: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    unit: str = Field(default="", max_length=50)
    quantity: Decimal = Field(default=Decimal("1"), max_digits=8, decimal_places=2)
    markup_pct: Decimal = Field(default=Decimal("0"), max_digits=5, decimal_places=2)
    sort_order: int = Field(default=0)

    estimate: Optional["Estimate"] = Relationship(back_populates="equipment_rows")


class EstimateMaterialRow(SQLModel, table=True):
    """A material line item on an estimate"""
    __tablename__ = "estimate_material_row"

    id: int | None = Field(default=None, primary_key=True)
    estimate_id: int = Field(foreign_key="estimate.id", index=True)

    description: str = Field(max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), max_digits=8, decimal_places=2)
    unit_cost: Decimal = Field(default=Decimal("0"), max_digits=10, decimal_places=2)
    sort_order: int = Field(default=0)

    estimate: Optional["Estimate"] = Relationship(back_populates="material_rows")
