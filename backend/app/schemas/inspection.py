"""
Inspection schemas
"""
from pydantic import BaseModel, Field
from datetime import date
from typing import List

from .job import JobBrief


class InspectionCreate(BaseModel):
    """Create inspection"""
    type: str = Field(..., pattern="^(pre|post)$")
    date: date

    # Common Fields
    customer_name: str
    is_company_truck_required: bool

    # Pre-Job Specific Fields
    materials_needed: bool | None = None
    special_tools_needed: str | None = None
    existing_damage_notes: str | None = None
    flooring_protection_needed: str | None = None

    # Post-Job Specific Fields
    dump_run_required: bool | None = None
    customer_keeping_materials: str | None = None
    materials_to_return: str | None = None
    inventory_used: str | None = None
    pickup_required: str | None = None
    damages_or_quality_concerns: str | None = None
    scope_change_notes: str | None = None


class InspectionUpdate(BaseModel):
    """Update inspection"""
    date: date | None = None
    customer_name: str | None = None
    is_company_truck_required: bool | None = None
    materials_needed: bool | None = None
    special_tools_needed: str | None = None
    existing_damage_notes: str | None = None
    flooring_protection_needed: str | None = None
    dump_run_required: bool | None = None
    customer_keeping_materials: str | None = None
    materials_to_return: str | None = None
    inventory_used: str | None = None
    pickup_required: str | None = None
    damages_or_quality_concerns: str | None = None
    scope_change_notes: str | None = None


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
    type: str
    date: date

    # Common Fields
    customer_name: str
    is_company_truck_required: bool

    # Pre-Job Specific Fields
    materials_needed: bool | None
    special_tools_needed: str | None
    existing_damage_notes: str | None
    flooring_protection_needed: str | None

    # Post-Job Specific Fields
    dump_run_required: bool | None
    customer_keeping_materials: str | None
    materials_to_return: str | None
    inventory_used: str | None
    pickup_required: str | None
    damages_or_quality_concerns: str | None
    scope_change_notes: str | None

    # Nested objects
    job: JobBrief
    photos: List[InspectionPhotoResponse]

    class Config:
        from_attributes = True
