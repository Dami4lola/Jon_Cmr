"""
Job Inspection models
"""
from sqlmodel import SQLModel, Field, Relationship
from datetime import date, time, datetime
from typing import TYPE_CHECKING, List, Optional
from enum import Enum

if TYPE_CHECKING:
    from .job import Job
    from .worker import Worker


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
    inspection_type: str = Field(max_length=4)  # "pre" or "post"
    inspector_id: int | None = Field(default=None, foreign_key="worker.id")

    # When
    inspection_date: date
    inspection_time: time | None = Field(default=None)

    # Status
    status: str = Field(default=InspectionStatus.DRAFT.value, max_length=10)

    # General fields
    site_conditions: str | None = Field(default=None)
    safety_hazards: str | None = Field(default=None)
    notes: str | None = Field(default=None)

    # Pre-inspection specific
    client_present: bool = Field(default=False)
    access_issues: str | None = Field(default=None)
    existing_damage: str | None = Field(default=None)

    # Post-inspection specific
    work_completed: str | None = Field(default=None)
    quality_check_passed: bool = Field(default=True)
    client_satisfied: bool | None = Field(default=None)
    followup_required: bool = Field(default=False)
    followup_notes: str | None = Field(default=None)

    # Client signature
    client_signature: str | None = Field(default=None)  # Base64 or file path
    client_name_signed: str | None = Field(default=None, max_length=100)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)

    # Relationships
    job: Optional["Job"] = Relationship(back_populates="inspections")
    inspector: Optional["Worker"] = Relationship(back_populates="inspections")
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
