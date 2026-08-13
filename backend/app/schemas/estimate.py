"""
Estimate schemas - customer-facing quick quotes, manager-facing rate config,
and the persisted full estimate builder (scope of work, phased task hours,
full cost breakdown).
"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date

from .job import JobBrief
from .client import ClientBrief


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


class MaterialSearchResult(BaseModel):
    """A single cached/live Home Depot material match for the manager's autocomplete"""
    product_name: str
    price: str | None
    price_value: float | None
    thumbnail: str | None
    product_url: str | None
    source: str


# ============================================================
# Persisted Estimate builder (scope of work, phased task hours,
# full cost breakdown) - manager only
# ============================================================

class EstimateTaskCreate(BaseModel):
    """A named task with hours, grouped into a phase"""
    phase: str = Field(..., pattern="^(preplanning|build|finishing)$")
    description: str = Field(..., max_length=500)
    hours: Decimal = Field(..., ge=0)
    uses_heavy_equipment: bool = False
    sort_order: int = 0


class EstimateTaskResponse(EstimateTaskCreate):
    id: int

    class Config:
        from_attributes = True


class EstimateEquipmentRowCreate(BaseModel):
    """An equipment/rental/fuel line item"""
    category: str = Field(..., pattern="^(heavy|ownedRental|scaffolding|rentalVillage|fuel)$")
    description: str = Field(..., max_length=500)
    rate: Decimal = Decimal("0")
    unit: str = ""
    quantity: Decimal = Decimal("1")
    markup_pct: Decimal = Decimal("0")
    sort_order: int = 0


class EstimateEquipmentRowResponse(EstimateEquipmentRowCreate):
    id: int

    class Config:
        from_attributes = True


class EstimateMaterialRowCreate(BaseModel):
    """A material line item"""
    description: str = Field(..., max_length=500)
    quantity: Decimal = Decimal("1")
    unit_cost: Decimal = Decimal("0")
    sort_order: int = 0


class EstimateMaterialRowResponse(EstimateMaterialRowCreate):
    id: int

    class Config:
        from_attributes = True


class EstimateCreate(BaseModel):
    """Create/replace an estimate. Child rows are always submitted in full -
    the server replaces existing rows wholesale rather than diffing them."""
    job_id: int | None = None
    client_id: int | None = None
    client_name_override: str | None = Field(default=None, max_length=100)
    address_override: str | None = None

    scope_of_work: str | None = None
    notes: str | None = None

    crew_size: int = Field(default=1, ge=1)
    techs_traveling: int = Field(default=1, ge=1)
    distance_km: Decimal | None = None
    km_rate: Decimal = Decimal("1.50")

    dump_fee: Decimal = Decimal("0")
    permits_fee: Decimal = Decimal("0")
    admin_fee: Decimal = Decimal("0")
    redseal_amount: Decimal = Decimal("0")
    include_admin_fee: bool = True
    include_hst: bool = True

    tasks: list[EstimateTaskCreate] = []
    equipment_rows: list[EstimateEquipmentRowCreate] = []
    material_rows: list[EstimateMaterialRowCreate] = []


class EstimateUpdate(EstimateCreate):
    """Same shape as create - full replace-on-save for child rows"""
    status: str | None = Field(default=None, pattern="^(draft|sent|accepted|declined)$")


class EstimateAmounts(BaseModel):
    """Computed rollup amounts, shared by the preview endpoint and the full response"""
    total_hours: Decimal
    travel_days: int
    labour_amount: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    heavy_equipment_amount: Decimal
    rental_amount: Decimal
    fuel_amount: Decimal
    admin_amount: Decimal
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal


class EstimateResponse(BaseModel):
    """Full estimate detail, including itemized child rows, for reopening/editing"""
    id: int
    estimate_number: str
    created_date: date
    status: str

    job: JobBrief | None
    client: ClientBrief | None
    client_name_override: str | None
    address_override: str | None

    scope_of_work: str | None
    notes: str | None

    crew_size: int
    techs_traveling: int
    distance_km: Decimal | None
    km_rate: Decimal

    dump_fee: Decimal
    permits_fee: Decimal
    admin_fee: Decimal
    redseal_amount: Decimal
    include_admin_fee: bool
    include_hst: bool

    total_hours: Decimal
    travel_days: int
    labour_amount: Decimal
    travel_amount: Decimal
    materials_amount: Decimal
    heavy_equipment_amount: Decimal
    rental_amount: Decimal
    fuel_amount: Decimal
    admin_amount: Decimal
    subtotal: Decimal
    hst_amount: Decimal
    total: Decimal

    tasks: list[EstimateTaskResponse]
    equipment_rows: list[EstimateEquipmentRowResponse]
    material_rows: list[EstimateMaterialRowResponse]

    class Config:
        from_attributes = True


class EstimateListItem(BaseModel):
    """Compact row for the estimates list page"""
    id: int
    estimate_number: str
    created_date: date
    status: str
    job_id: int | None
    client_name: str | None
    total: Decimal

    class Config:
        from_attributes = True
