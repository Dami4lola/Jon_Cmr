"""
Job Inspection models
"""
from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional
from enum import Enum

if TYPE_CHECKING:
    from .job import Job


class InspectionType(str, Enum):
    PRE = "pre"
    POST = "post"


class InspectionStatus(str, Enum):
    DRAFT = "draft"
    COMPLETED = "completed"


class JobInspection(SQLModel, table=True):
    """Pre or Post inspection for a job"""
    __tablename__ = "job_inspection"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    type: str = Field(max_length=4)  # "pre" or "post"
    date: date

    # Common Fields
    customer_name: str
    is_company_truck_required: bool

    # Pre-Job Specific Fields
    materials_needed: str | None = None
    special_tools_needed: str | None = None
    existing_damage_notes: str | None = None
    flooring_protection_needed: str | None = None

    # Post-Job Specific Fields
    dump_run_required: bool | None = None
    customer_keeping_materials: str | None = None  # "Is customer keeping purchased materials?"
    materials_to_return: str | None = None
    inventory_used: str | None = None  # "Just Jon or Personal"
    pickup_required: str | None = None  # Tools/Trailers
    damages_or_quality_concerns: str | None = None
    scope_change_notes: str | None = None  # "Less work or more work?"

    # Relationships
    job: Optional["Job"] = Relationship(back_populates="inspections")
    photos: List["InspectionPhoto"] = Relationship(back_populates="inspection")

    class Config:
        # Unique constraint: one inspection per job per type
        # Handled in API layer since SQLModel doesn't support compound unique constraints directly
        pass


class InspectionPhoto(SQLModel, table=True):
    """Photos attached to an inspection"""
    __tablename__ = "inspection_photo"

    id: int | None = Field(default=None, primary_key=True)
    inspection_id: int = Field(foreign_key="job_inspection.id", index=True)

    # File info
    image_path: str
    caption: str | None = Field(default=None, max_length=200)

    # Timestamps
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    inspection: Optional["JobInspection"] = Relationship(back_populates="photos")
