"""
Estimate schemas - customer-facing quick quotes and manager-facing rate config
"""
from pydantic import BaseModel, Field
from decimal import Decimal


class JobTypeOption(BaseModel):
    """A selectable job type for the quick quote form dropdown"""
    value: str
    label: str


class QuickQuoteRequest(BaseModel):
    """Customer-facing quick estimate request: work type, address, area size"""
    job_type: str = Field(default="general", max_length=50)
    address: str = Field(..., min_length=3, max_length=300)
    area_sqft: Decimal = Field(..., gt=0, le=100000)


class QuickQuoteResponse(BaseModel):
    """Computed quick estimate breakdown"""
    job_type: str
    job_type_label: str
    address: str
    area_sqft: Decimal
    distance_km: Decimal | None
    estimated_hours: Decimal
    labour_amount: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    admin_fee: Decimal
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal
    disclaimer: str


class JobTypeRate(BaseModel):
    """Area-based heuristic rates for one quick quote job type"""
    job_type: str
    label: str
    hours_per_sqft: Decimal
    materials_per_sqft: Decimal


class QuickQuoteRatesResponse(BaseModel):
    """Current tunable rates behind the quick quote calculation"""
    labour_rate: Decimal
    redseal_rate: Decimal
    minimum_hours: Decimal
    km_rate: Decimal
    hst_rate: Decimal
    admin_fee: Decimal
    job_types: list[JobTypeRate]


class JobTypeRateUpdate(BaseModel):
    """Manager-editable heuristic for a single job type"""
    hours_per_sqft: Decimal = Field(..., gt=0, le=10)
    materials_per_sqft: Decimal = Field(..., ge=0, le=1000)


class AdminFeeUpdate(BaseModel):
    """Manager-editable shared admin fee applied to every quick quote"""
    admin_fee: Decimal = Field(..., ge=0, le=10000)


class DistancePreviewRequest(BaseModel):
    """Manager tool: preview round-trip travel distance for an address before a job exists"""
    address: str = Field(..., min_length=3, max_length=300)


class DistancePreviewResponse(BaseModel):
    distance_km: Decimal | None
    address: str
