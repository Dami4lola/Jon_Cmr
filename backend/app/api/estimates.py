"""
Estimate API endpoints - a public quick quote calculator for customers, plus
manager tools for previewing travel distance and tuning the quick quote's
per-job-type area heuristics before a job exists.
"""
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, status

from ..models.settings import AppSettings
from ..services.distance import calculate_distance
from ..services.material_pricing import search_materials
from ..schemas.estimate import (
    JobTypeOption,
    JobTypeRate,
    JobTypeRateUpdate,
    AdminFeeUpdate,
    QuickQuoteRequest,
    QuickQuoteResponse,
    QuickQuoteRatesResponse,
    DistancePreviewRequest,
    DistancePreviewResponse,
    MaterialSearchResult,
)
from .invoices import LABOUR_RATE, REDSEAL_RATE, MINIMUM_HOURS, DEFAULT_KM_RATE, HST_RATE
from .deps import DBSession, ManagerUser

router = APIRouter()

# Rough starter defaults for each area-based job type on the quick quote form.
# Tunable per type by managers via PUT /quick-quote-rates/{job_type} without a
# code deploy. These are placeholders based on generic industry rules of thumb,
# not this business's actual job history - adjust once real data is available.
#
# Red Seal trades (plumbing, electrical) are deliberately not offered here -
# their scope varies too much job to job for a sqft-based instant quote, so
# those still go through a manual estimate.
JOB_TYPE_DEFAULTS: dict[str, dict] = {
    "general": {
        "label": "General / Other",
        "hours_per_sqft": Decimal("0.02"),
        "materials_per_sqft": Decimal("3.00"),
    },
    "painting": {
        "label": "Painting (Interior/Exterior)",
        "hours_per_sqft": Decimal("0.008"),
        "materials_per_sqft": Decimal("0.75"),
    },
    "drywall": {
        "label": "Drywall Install/Repair",
        "hours_per_sqft": Decimal("0.03"),
        "materials_per_sqft": Decimal("1.50"),
    },
    "flooring": {
        "label": "Flooring Install",
        "hours_per_sqft": Decimal("0.04"),
        "materials_per_sqft": Decimal("4.00"),
    },
}

DEFAULT_ADMIN_FEE = Decimal("50.00")

QUICK_QUOTE_DISCLAIMER = (
    "This is an automated rough estimate based on square footage only. "
    "Final pricing is confirmed after an on-site assessment."
)


def _setting_keys(job_type: str) -> tuple[str, str]:
    return f"quick_quote_hours_per_sqft__{job_type}", f"quick_quote_materials_per_sqft__{job_type}"


def _get_setting(session, key: str, default: Decimal) -> Decimal:
    setting = session.get(AppSettings, key)
    return Decimal(setting.value) if setting else default


def _set_setting(session, key: str, value: Decimal) -> None:
    setting = session.get(AppSettings, key)
    if setting:
        setting.value = str(value)
    else:
        setting = AppSettings(key=key, value=str(value))
    session.add(setting)


def _get_job_type_rate(session, job_type: str) -> JobTypeRate:
    defaults = JOB_TYPE_DEFAULTS[job_type]
    hours_key, materials_key = _setting_keys(job_type)
    return JobTypeRate(
        job_type=job_type,
        label=defaults["label"],
        hours_per_sqft=_get_setting(session, hours_key, defaults["hours_per_sqft"]),
        materials_per_sqft=_get_setting(session, materials_key, defaults["materials_per_sqft"]),
    )


def calculate_quick_estimate(
    area_sqft: Decimal,
    distance_km: Decimal | None,
    hours_per_sqft: Decimal,
    materials_per_sqft: Decimal,
    admin_fee: Decimal,
    labour_rate: Decimal = LABOUR_RATE,
    km_rate: Decimal = DEFAULT_KM_RATE,
    hst_rate: Decimal = HST_RATE,
    minimum_hours: Decimal = MINIMUM_HOURS,
) -> dict:
    """
    Pure calculation for the customer-facing quick quote - no DB or HTTP needed.

    Hours are derived from area x hours_per_sqft, rounded to the nearest
    quarter hour the same way real timesheets are rounded in invoices.py,
    then floored at minimum_hours.
    """
    raw_hours = float(area_sqft) * float(hours_per_sqft)
    rounded_hours = Decimal(str(round(raw_hours * 4) / 4))
    estimated_hours = max(rounded_hours, minimum_hours)

    labour_amount = (estimated_hours * labour_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if distance_km is not None:
        travel_amount = (distance_km * km_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        travel_amount = Decimal("0.00")

    materials_amount = (area_sqft * materials_per_sqft).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    admin_fee = admin_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    subtotal = labour_amount + travel_amount + materials_amount + admin_fee
    hst_amount = (subtotal * hst_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = subtotal + hst_amount

    return {
        "estimated_hours": estimated_hours,
        "labour_amount": labour_amount,
        "travel_amount": travel_amount,
        "materials_amount": materials_amount,
        "admin_fee": admin_fee,
        "subtotal": subtotal,
        "hst_amount": hst_amount,
        "total": total,
    }


@router.get("/job-types", response_model=list[JobTypeOption])
def list_job_types():
    """Public: job type choices for the quick quote form dropdown"""
    return [
        JobTypeOption(value=key, label=defaults["label"])
        for key, defaults in JOB_TYPE_DEFAULTS.items()
    ]


@router.post("/quick-quote", response_model=QuickQuoteResponse)
def quick_quote(data: QuickQuoteRequest, session: DBSession):
    """
    Public, unauthenticated endpoint backing the customer-facing quick estimate
    form. Only needs a work type, area size, and address - no login required.
    """
    job_type = data.job_type if data.job_type in JOB_TYPE_DEFAULTS else "general"
    rate = _get_job_type_rate(session, job_type)
    admin_fee = _get_setting(session, "quick_quote_admin_fee", DEFAULT_ADMIN_FEE)

    distance_km = calculate_distance(data.address)

    amounts = calculate_quick_estimate(
        area_sqft=data.area_sqft,
        distance_km=distance_km,
        hours_per_sqft=rate.hours_per_sqft,
        materials_per_sqft=rate.materials_per_sqft,
        admin_fee=admin_fee,
    )

    return QuickQuoteResponse(
        job_type=job_type,
        job_type_label=rate.label,
        address=data.address,
        area_sqft=data.area_sqft,
        distance_km=distance_km,
        disclaimer=QUICK_QUOTE_DISCLAIMER,
        **amounts,
    )


@router.get("/quick-quote-rates", response_model=QuickQuoteRatesResponse)
def get_quick_quote_rates(session: DBSession, current_user: ManagerUser):
    """Manager-only: view the rates driving both invoices and the quick quote calculator"""
    return QuickQuoteRatesResponse(
        labour_rate=LABOUR_RATE,
        redseal_rate=REDSEAL_RATE,
        minimum_hours=MINIMUM_HOURS,
        km_rate=DEFAULT_KM_RATE,
        hst_rate=HST_RATE,
        admin_fee=_get_setting(session, "quick_quote_admin_fee", DEFAULT_ADMIN_FEE),
        job_types=[_get_job_type_rate(session, jt) for jt in JOB_TYPE_DEFAULTS],
    )


@router.put("/quick-quote-rates/{job_type}", response_model=JobTypeRate)
def update_job_type_rate(job_type: str, data: JobTypeRateUpdate, session: DBSession, current_user: ManagerUser):
    """Manager-only: tune one job type's area-based hours/materials heuristics"""
    if job_type not in JOB_TYPE_DEFAULTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown job type '{job_type}'")

    hours_key, materials_key = _setting_keys(job_type)
    _set_setting(session, hours_key, data.hours_per_sqft)
    _set_setting(session, materials_key, data.materials_per_sqft)
    session.commit()

    return _get_job_type_rate(session, job_type)


@router.put("/quick-quote-admin-fee", response_model=QuickQuoteRatesResponse)
def update_admin_fee(data: AdminFeeUpdate, session: DBSession, current_user: ManagerUser):
    """Manager-only: update the shared admin fee applied to every quick quote"""
    _set_setting(session, "quick_quote_admin_fee", data.admin_fee)
    session.commit()

    return QuickQuoteRatesResponse(
        labour_rate=LABOUR_RATE,
        redseal_rate=REDSEAL_RATE,
        minimum_hours=MINIMUM_HOURS,
        km_rate=DEFAULT_KM_RATE,
        hst_rate=HST_RATE,
        admin_fee=data.admin_fee,
        job_types=[_get_job_type_rate(session, jt) for jt in JOB_TYPE_DEFAULTS],
    )


@router.post("/distance-preview", response_model=DistancePreviewResponse)
def distance_preview(data: DistancePreviewRequest, current_user: ManagerUser):
    """Manager-only: preview round-trip travel km for an address before a job is created"""
    distance_km = calculate_distance(data.address)
    return DistancePreviewResponse(distance_km=distance_km, address=data.address)


@router.get("/materials/search", response_model=list[MaterialSearchResult])
def search_materials_endpoint(q: str, session: DBSession, current_user: ManagerUser):
    """Manager-only: autocomplete search for Home Depot material prices, cached in the DB"""
    if len(q.strip()) < 3:
        return []

    results = search_materials(session, q)
    return [
        MaterialSearchResult(
            product_name=r.product_name,
            price=r.price,
            price_value=r.price_value,
            thumbnail=r.thumbnail,
            product_url=r.product_url,
            source=r.source,
        )
        for r in results
    ]
