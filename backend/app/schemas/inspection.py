"""
Inspection schemas
"""
from pydantic import BaseModel, Field
from datetime import date, time, datetime
from typing import List

from .worker import WorkerBrief
from .job import JobBrief


class InspectionCreate(BaseModel):
    """Create inspection"""
    inspection_type: str = Field(..., pattern="^(pre|post)$")
    inspection_date: date
    inspection_time: time | None = None
    status: str = Field(default="draft")

    # General fields
    site_conditions: str | None = None
    safety_hazards: str | None = None
    notes: str | None = None

    # Pre-inspection specific
    client_present: bool = False
    access_issues: str | None = None
    existing_damage: str | None = None

    # Post-inspection specific
    work_completed: str | None = None
    quality_check_passed: bool = True
    client_satisfied: bool | None = None
    followup_required: bool = False
    followup_notes: str | None = None

    # Client signature
    client_name_signed: str | None = Field(default=None, max_length=100)
    client_signature: str | None = None  # Base64


class InspectionUpdate(BaseModel):
    """Update inspection"""
    inspection_date: date | None = None
    inspection_time: time | None = None
    status: str | None = None
    site_conditions: str | None = None
    safety_hazards: str | None = None
    notes: str | None = None
    client_present: bool | None = None
    access_issues: str | None = None
    existing_damage: str | None = None
    work_completed: str | None = None
    quality_check_passed: bool | None = None
    client_satisfied: bool | None = None
    followup_required: bool | None = None
    followup_notes: str | None = None
    client_name_signed: str | None = None
    client_signature: str | None = None


class InspectionPhotoResponse(BaseModel):
    """Inspection photo response"""
    id: int
    image_path: str
    image_url: str
    caption: str | None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class InspectionResponse(BaseModel):
    """Inspection response"""
    id: int
    inspection_type: str
    inspection_date: date
    inspection_time: time | None
    status: str

    # General fields
    site_conditions: str | None
    safety_hazards: str | None
    notes: str | None

    # Pre-inspection specific
    client_present: bool
    access_issues: str | None
    existing_damage: str | None

    # Post-inspection specific
    work_completed: str | None
    quality_check_passed: bool
    client_satisfied: bool | None
    followup_required: bool
    followup_notes: str | None

    # Client signature
    client_name_signed: str | None
    client_signature: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    # Nested objects
    job: JobBrief
    inspector: WorkerBrief | None
    photos: List[InspectionPhotoResponse]

    class Config:
        from_attributes = True
