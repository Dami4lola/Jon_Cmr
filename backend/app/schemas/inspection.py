"""
Inspection schemas
"""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional

from .job import JobBrief


class InspectionCreate(BaseModel):
    """Create inspection"""
    type: str = Field(..., pattern="^(pre|post)$")
    date: date

    # Common Fields
    customer_name: str
    is_company_truck_required: bool

    # Pre-Job Specific Fields
    materials_needed: Optional[str] = None
    special_tools_needed: Optional[str] = None
    existing_damage_notes: Optional[str] = None
    flooring_protection_needed: Optional[str] = None

    # Post-Job Specific Fields
    dump_run_required: Optional[bool] = None
    customer_keeping_materials: Optional[str] = None
    materials_to_return: Optional[str] = None
    inventory_used: Optional[str] = None
    pickup_required: Optional[str] = None
    damages_or_quality_concerns: Optional[str] = None
    scope_change_notes: Optional[str] = None


class InspectionUpdate(BaseModel):
    """Update inspection"""
    date: Optional[date] = None
    customer_name: Optional[str] = None
    is_company_truck_required: Optional[bool] = None
    materials_needed: Optional[str] = None
    special_tools_needed: Optional[str] = None
    existing_damage_notes: Optional[str] = None
    flooring_protection_needed: Optional[str] = None
    dump_run_required: Optional[bool] = None
    customer_keeping_materials: Optional[str] = None
    materials_to_return: Optional[str] = None
    inventory_used: Optional[str] = None
    pickup_required: Optional[str] = None
    damages_or_quality_concerns: Optional[str] = None
    scope_change_notes: Optional[str] = None


class InspectionPhotoResponse(BaseModel):
    """Inspection photo response"""
    id: int
    image_path: str
    image_url: str
    caption: Optional[str]
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
    materials_needed: Optional[str]
    special_tools_needed: Optional[str]
    existing_damage_notes: Optional[str]
    flooring_protection_needed: Optional[str]

    # Post-Job Specific Fields
    dump_run_required: Optional[bool]
    customer_keeping_materials: Optional[str]
    materials_to_return: Optional[str]
    inventory_used: Optional[str]
    pickup_required: Optional[str]
    damages_or_quality_concerns: Optional[str]
    scope_change_notes: Optional[str]

    # Nested objects
    job: JobBrief
    photos: List[InspectionPhotoResponse]

    class Config:
        from_attributes = True
