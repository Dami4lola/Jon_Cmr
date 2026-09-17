"""
Estimate API endpoints - a public quick quote calculator for customers, plus
manager tools for previewing travel distance, tuning the quick quote's
per-job-type area heuristics before a job exists, and building/persisting a
full estimate (scope of work, phased task hours, full cost breakdown).
"""
import logging
import math
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlmodel import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..models.settings import AppSettings
from ..models import (
    Estimate,
    EstimateTask,
    EstimateEquipmentRow,
    EstimateMaterialRow,
    EstimateScaffoldingRow,
    EstimateToolingRow,
    Job,
    JobWorkerLink,
    JobWorkerSchedule,
    Client,
    Worker,
)
from ..models.estimate import EstimateStatus
from ..services.distance import calculate_distance
from ..services.material_pricing import search_materials
from ..services.estimate_pdf import generate_estimate_pdf
from ..schemas.job import JobBrief, JobResponse
from ..schemas.client import ClientBrief
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
    EstimateCreate,
    EstimateUpdate,
    EstimateResponse,
    EstimateTaskResponse,
    EstimateEquipmentRowResponse,
    EstimateMaterialRowResponse,
    EstimateScaffoldingRowResponse,
    EstimateToolingRowResponse,
    EstimateAmounts,
    EstimateListItem,
    EstimateConvertRequest,
)
from .invoices import LABOUR_RATE, REDSEAL_RATE, MINIMUM_HOURS, DEFAULT_KM_RATE, HST_RATE
from .jobs import job_to_response
from .deps import DBSession, ManagerUser, EstimatorUser

logger = logging.getLogger(__name__)

router = APIRouter()

# Job.estimated_duration is Numeric(4,2) while Estimate.total_hours is Numeric(8,2),
# so a long estimate does not fit in the job's duration column.
JOB_DURATION_MAX = Decimal("99.99")

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
def get_quick_quote_rates(session: DBSession, current_user: EstimatorUser):
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
def distance_preview(data: DistancePreviewRequest, current_user: EstimatorUser):
    """Manager-only: preview round-trip travel km for an address before a job is created"""
    distance_km = calculate_distance(data.address)
    return DistancePreviewResponse(distance_km=distance_km, address=data.address)


@router.get("/materials/search", response_model=list[MaterialSearchResult])
def search_materials_endpoint(q: str, session: DBSession, current_user: EstimatorUser):
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


# ============================================================
# Persisted Estimate builder (scope of work, phased task hours,
# full cost breakdown) - manager only
# ============================================================

def _calculate_estimate_amounts(
    tasks,
    equipment_rows,
    material_rows,
    crew_size: int,
    techs_traveling: int,
    distance_km: Decimal | None,
    km_rate: Decimal,
    dump_fee: Decimal,
    permits_fee: Decimal,
    admin_fee: Decimal,
    redseal_techs: int,
    redseal_rate: Decimal,
    include_admin_fee: bool,
    include_hst: bool,
    scaffolding_rows=(),
    tooling_rows=(),
    engineering_fee: Decimal = Decimal("0"),
    heavy_equipment_rate: Decimal = Decimal("120.00"),
    labour_rate: Decimal = LABOUR_RATE,
    hst_rate: Decimal = HST_RATE,
) -> dict:
    """
    Pure calculation for a persisted estimate - no DB/HTTP needed. Shared by
    the /preview endpoint and the authoritative recompute-on-save.

    Total hours is the sum of every phased task's hours (the task list
    replaces the old simple labor rows entirely). Travel days is total hours
    divided by a 7-hour day, rounded up - multi-day jobs mean multiple round
    trips.

    Tasks tagged uses_redseal bill at redseal_rate *instead of* the standard
    rate: their tech-hours (hours x redseal_techs, capped at the crew) are
    moved out of labour_amount into redseal_amount, so a Red Seal hour bills
    $100 rather than $80 + $100. total_hours still counts every hour once.
    """
    total_hours = sum((t.hours for t in tasks), Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    travel_days = math.ceil(total_hours / 7) if total_hours > 0 else 0

    # Red Seal tech-hours move OUT of standard labour rather than being added on top,
    # so a Red Seal hour bills the Red Seal rate, not that rate plus the standard one.
    # Techs are clamped to the crew: Red Seal techs are a subset of the people on site.
    effective_redseal_techs = min(redseal_techs, crew_size)
    redseal_hours = sum((t.hours for t in tasks if t.uses_redseal), Decimal("0")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    total_tech_hours = total_hours * crew_size
    redseal_tech_hours = min(redseal_hours * effective_redseal_techs, total_tech_hours)
    standard_tech_hours = total_tech_hours - redseal_tech_hours

    labour_amount = (standard_tech_hours * labour_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    redseal_amount = (redseal_tech_hours * redseal_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if distance_km is not None:
        travel_amount = (techs_traveling * distance_km * km_rate * travel_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        travel_amount = Decimal("0.00")

    materials_amount = sum((r.quantity * r.unit_cost for r in material_rows), Decimal("0")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    heavy_equipment_amount = Decimal("0")
    rental_amount = Decimal("0")
    fuel_amount = Decimal("0")
    for row in equipment_rows:
        line_total = row.rate * row.quantity * (1 + row.markup_pct / 100)
        if row.category == "heavy":
            heavy_equipment_amount += line_total
        elif row.category == "fuel":
            fuel_amount += line_total
        else:  # ownedRental, scaffolding, rentalVillage all roll up to Rental
            rental_amount += line_total

    # Tasks tagged uses_heavy_equipment add their hours x heavy_equipment_rate
    # on top of any manually-added "heavy" Equipment & Fuel rows above - both
    # feed the same heavy_equipment_amount total.
    heavy_task_hours = sum((t.hours for t in tasks if t.uses_heavy_equipment), Decimal("0"))
    heavy_equipment_amount += heavy_task_hours * heavy_equipment_rate

    heavy_equipment_amount = heavy_equipment_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rental_amount = rental_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fuel_amount = fuel_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    dump_fee = dump_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    permits_fee = permits_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    engineering_fee = engineering_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Scaffolding is billed per component (frame/crosser/jack/plank) for every
    # day the crew is out on the job - same travel_days used for the km fee.
    scaffolding_amount = sum(
        (row.rate_per_day * row.quantity for row in scaffolding_rows), Decimal("0")
    ) * travel_days
    scaffolding_amount = scaffolding_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    tooling_amount = sum((r.quantity * r.unit_cost for r in tooling_rows), Decimal("0")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Admin fee is charged once per 5-day work week, rounding any partial
    # week up (1-5 days = 1 fee, 6-10 = 2 fees, 11-15 = 3 fees, ...).
    admin_periods = math.ceil(travel_days / 5) if travel_days > 0 else 0
    admin_amt = (admin_fee * admin_periods).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if include_admin_fee else Decimal("0.00")

    subtotal = (
        labour_amount + travel_amount + materials_amount + heavy_equipment_amount
        + rental_amount + fuel_amount + scaffolding_amount + tooling_amount
        + dump_fee + permits_fee + engineering_fee + redseal_amount + admin_amt
    )
    hst_amount = (subtotal * hst_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if include_hst else Decimal("0.00")
    total = subtotal + hst_amount

    return {
        "total_hours": total_hours,
        "travel_days": travel_days,
        "labour_amount": labour_amount,
        "redseal_amount": redseal_amount,
        "travel_amount": travel_amount,
        "materials_amount": materials_amount,
        "heavy_equipment_amount": heavy_equipment_amount,
        "rental_amount": rental_amount,
        "fuel_amount": fuel_amount,
        "scaffolding_amount": scaffolding_amount,
        "tooling_amount": tooling_amount,
        "admin_amount": admin_amt,
        "subtotal": subtotal,
        "hst_amount": hst_amount,
        "total": total,
    }


def generate_estimate_number(session) -> str:
    """Generate unique estimate number: EST-YYYY-NNNN"""
    year = date.today().year
    prefix = f"EST-{year}-"

    statement = (
        select(Estimate)
        .where(Estimate.estimate_number.startswith(prefix))
        .order_by(Estimate.estimate_number.desc())
    )
    last_estimate = session.exec(statement).first()

    if last_estimate:
        last_num = int(last_estimate.estimate_number.split("-")[-1])
        new_num = last_num + 1
    else:
        new_num = 1

    return f"{prefix}{new_num:04d}"


def _load_estimate(session, estimate_id: int) -> Estimate | None:
    statement = (
        select(Estimate)
        .where(Estimate.id == estimate_id)
        .options(
            selectinload(Estimate.job).selectinload(Job.client),
            selectinload(Estimate.client),
            selectinload(Estimate.tasks),
            selectinload(Estimate.equipment_rows),
            selectinload(Estimate.material_rows),
            selectinload(Estimate.scaffolding_rows),
            selectinload(Estimate.tooling_rows),
        )
    )
    return session.exec(statement).first()


def _estimate_to_response(estimate: Estimate) -> EstimateResponse:
    job_brief = None
    if estimate.job:
        client_name = estimate.job.client.name if estimate.job.client else (estimate.client_name_override or "")
        job_brief = JobBrief(
            id=estimate.job.id,
            title=estimate.job.title,
            client_name=client_name,
            start_date=estimate.job.start_date,
            end_date=estimate.job.end_date,
        )

    client_brief = None
    if estimate.client:
        client_brief = ClientBrief(
            id=estimate.client.id,
            name=estimate.client.name,
            phone_number=estimate.client.phone_number,
            address=estimate.client.address,
        )

    return EstimateResponse(
        id=estimate.id,
        estimate_number=estimate.estimate_number,
        created_date=estimate.created_date,
        status=estimate.status,
        job=job_brief,
        client=client_brief,
        client_name_override=estimate.client_name_override,
        address_override=estimate.address_override,
        scope_of_work=estimate.scope_of_work,
        notes=estimate.notes,
        crew_size=estimate.crew_size,
        techs_traveling=estimate.techs_traveling,
        distance_km=estimate.distance_km,
        km_rate=estimate.km_rate,
        redseal_techs=estimate.redseal_techs,
        redseal_rate=estimate.redseal_rate,
        dump_fee=estimate.dump_fee,
        permits_fee=estimate.permits_fee,
        engineering_fee=estimate.engineering_fee,
        admin_fee=estimate.admin_fee,
        heavy_equipment_rate=estimate.heavy_equipment_rate,
        include_admin_fee=estimate.include_admin_fee,
        include_hst=estimate.include_hst,
        total_hours=estimate.total_hours,
        travel_days=estimate.travel_days,
        labour_amount=estimate.labour_amount,
        redseal_amount=estimate.redseal_amount,
        travel_amount=estimate.travel_amount,
        materials_amount=estimate.materials_amount,
        heavy_equipment_amount=estimate.heavy_equipment_amount,
        rental_amount=estimate.rental_amount,
        fuel_amount=estimate.fuel_amount,
        scaffolding_amount=estimate.scaffolding_amount,
        tooling_amount=estimate.tooling_amount,
        admin_amount=estimate.admin_amount,
        subtotal=estimate.subtotal,
        hst_amount=estimate.hst_amount,
        total=estimate.total,
        tasks=[
            EstimateTaskResponse.model_validate(t)
            for t in sorted(estimate.tasks, key=lambda t: (t.phase, t.sort_order))
        ],
        equipment_rows=[
            EstimateEquipmentRowResponse.model_validate(r)
            for r in sorted(estimate.equipment_rows, key=lambda r: r.sort_order)
        ],
        material_rows=[
            EstimateMaterialRowResponse.model_validate(m)
            for m in sorted(estimate.material_rows, key=lambda m: m.sort_order)
        ],
        scaffolding_rows=[
            EstimateScaffoldingRowResponse.model_validate(s)
            for s in sorted(estimate.scaffolding_rows, key=lambda s: s.sort_order)
        ],
        tooling_rows=[
            EstimateToolingRowResponse.model_validate(g)
            for g in sorted(estimate.tooling_rows, key=lambda g: g.sort_order)
        ],
    )


def _get_estimate_or_404(session, estimate_id: int) -> EstimateResponse:
    estimate = _load_estimate(session, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")
    return _estimate_to_response(estimate)


def _estimate_to_list_item(estimate: Estimate) -> EstimateListItem:
    client_name = estimate.client.name if estimate.client else estimate.client_name_override
    return EstimateListItem(
        id=estimate.id,
        estimate_number=estimate.estimate_number,
        created_date=estimate.created_date,
        status=estimate.status,
        job_id=estimate.job_id,
        client_name=client_name,
        total=estimate.total,
    )


@router.post("/preview", response_model=EstimateAmounts)
def preview_estimate(data: EstimateCreate, current_user: EstimatorUser):
    """Manager-only: compute totals without persisting, for live totals while editing"""
    amounts = _calculate_estimate_amounts(
        tasks=data.tasks,
        equipment_rows=data.equipment_rows,
        material_rows=data.material_rows,
        scaffolding_rows=data.scaffolding_rows,
        tooling_rows=data.tooling_rows,
        crew_size=data.crew_size,
        techs_traveling=data.techs_traveling,
        distance_km=data.distance_km,
        km_rate=data.km_rate,
        dump_fee=data.dump_fee,
        permits_fee=data.permits_fee,
        engineering_fee=data.engineering_fee,
        admin_fee=data.admin_fee,
        heavy_equipment_rate=data.heavy_equipment_rate,
        redseal_techs=data.redseal_techs,
        redseal_rate=data.redseal_rate,
        include_admin_fee=data.include_admin_fee,
        include_hst=data.include_hst,
    )
    return EstimateAmounts(**amounts)


@router.post("/", response_model=EstimateResponse, status_code=status.HTTP_201_CREATED)
def create_estimate(data: EstimateCreate, session: DBSession, current_user: EstimatorUser):
    """Manager-only: create a new estimate (standalone or job-linked)"""
    if data.job_id is not None:
        if not session.get(Job, data.job_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        existing = session.exec(select(Estimate).where(Estimate.job_id == data.job_id)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estimate {existing.estimate_number} already exists for this job",
            )

    if data.client_id is not None and not session.get(Client, data.client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    amounts = _calculate_estimate_amounts(
        tasks=data.tasks,
        equipment_rows=data.equipment_rows,
        material_rows=data.material_rows,
        scaffolding_rows=data.scaffolding_rows,
        tooling_rows=data.tooling_rows,
        crew_size=data.crew_size,
        techs_traveling=data.techs_traveling,
        distance_km=data.distance_km,
        km_rate=data.km_rate,
        dump_fee=data.dump_fee,
        permits_fee=data.permits_fee,
        engineering_fee=data.engineering_fee,
        admin_fee=data.admin_fee,
        heavy_equipment_rate=data.heavy_equipment_rate,
        redseal_techs=data.redseal_techs,
        redseal_rate=data.redseal_rate,
        include_admin_fee=data.include_admin_fee,
        include_hst=data.include_hst,
    )

    estimate = Estimate(
        job_id=data.job_id,
        client_id=data.client_id,
        client_name_override=data.client_name_override,
        address_override=data.address_override,
        estimate_number=generate_estimate_number(session),
        scope_of_work=data.scope_of_work,
        notes=data.notes,
        crew_size=data.crew_size,
        techs_traveling=data.techs_traveling,
        distance_km=data.distance_km,
        km_rate=data.km_rate,
        redseal_techs=data.redseal_techs,
        redseal_rate=data.redseal_rate,
        dump_fee=data.dump_fee,
        permits_fee=data.permits_fee,
        engineering_fee=data.engineering_fee,
        admin_fee=data.admin_fee,
        heavy_equipment_rate=data.heavy_equipment_rate,
        include_admin_fee=data.include_admin_fee,
        include_hst=data.include_hst,
        **amounts,
    )
    session.add(estimate)
    session.flush()  # assign estimate.id before adding children

    for t in data.tasks:
        session.add(EstimateTask(estimate_id=estimate.id, **t.model_dump()))
    for r in data.equipment_rows:
        session.add(EstimateEquipmentRow(estimate_id=estimate.id, **r.model_dump()))
    for m in data.material_rows:
        session.add(EstimateMaterialRow(estimate_id=estimate.id, **m.model_dump()))
    for s in data.scaffolding_rows:
        session.add(EstimateScaffoldingRow(estimate_id=estimate.id, **s.model_dump()))
    for g in data.tooling_rows:
        session.add(EstimateToolingRow(estimate_id=estimate.id, **g.model_dump()))

    session.commit()

    return _get_estimate_or_404(session, estimate.id)


@router.get("/", response_model=list[EstimateListItem])
def list_estimates(
    session: DBSession,
    current_user: EstimatorUser,
    job_id: int | None = None,
    standalone: bool = False,
    status_filter: str | None = None,
):
    """Manager-only: list estimates, optionally filtered to one job or standalone-only"""
    statement = select(Estimate).options(selectinload(Estimate.client))

    if job_id is not None:
        statement = statement.where(Estimate.job_id == job_id)
    elif standalone:
        statement = statement.where(Estimate.job_id.is_(None))

    if status_filter:
        statement = statement.where(Estimate.status == status_filter)

    statement = statement.order_by(Estimate.created_date.desc(), Estimate.id.desc())
    estimates = session.exec(statement).all()

    return [_estimate_to_list_item(e) for e in estimates]


@router.get("/{estimate_id}", response_model=EstimateResponse)
def get_estimate(estimate_id: int, session: DBSession, current_user: EstimatorUser):
    """Manager-only: full estimate detail (with itemized rows) for reopening/editing"""
    return _get_estimate_or_404(session, estimate_id)


@router.put("/{estimate_id}", response_model=EstimateResponse)
def update_estimate(estimate_id: int, data: EstimateUpdate, session: DBSession, current_user: EstimatorUser):
    """Manager-only: full update - child rows (tasks/equipment/materials) are replaced wholesale"""
    estimate = session.get(Estimate, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")

    if data.job_id is not None and data.job_id != estimate.job_id:
        if not session.get(Job, data.job_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        existing = session.exec(
            select(Estimate).where(Estimate.job_id == data.job_id, Estimate.id != estimate_id)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estimate {existing.estimate_number} already exists for this job",
            )

    if data.client_id is not None and not session.get(Client, data.client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    amounts = _calculate_estimate_amounts(
        tasks=data.tasks,
        equipment_rows=data.equipment_rows,
        material_rows=data.material_rows,
        scaffolding_rows=data.scaffolding_rows,
        tooling_rows=data.tooling_rows,
        crew_size=data.crew_size,
        techs_traveling=data.techs_traveling,
        distance_km=data.distance_km,
        km_rate=data.km_rate,
        dump_fee=data.dump_fee,
        permits_fee=data.permits_fee,
        engineering_fee=data.engineering_fee,
        admin_fee=data.admin_fee,
        heavy_equipment_rate=data.heavy_equipment_rate,
        redseal_techs=data.redseal_techs,
        redseal_rate=data.redseal_rate,
        include_admin_fee=data.include_admin_fee,
        include_hst=data.include_hst,
    )

    estimate.job_id = data.job_id
    estimate.client_id = data.client_id
    estimate.client_name_override = data.client_name_override
    estimate.address_override = data.address_override
    estimate.scope_of_work = data.scope_of_work
    estimate.notes = data.notes
    estimate.crew_size = data.crew_size
    estimate.techs_traveling = data.techs_traveling
    estimate.distance_km = data.distance_km
    estimate.km_rate = data.km_rate
    estimate.redseal_techs = data.redseal_techs
    estimate.redseal_rate = data.redseal_rate
    estimate.dump_fee = data.dump_fee
    estimate.permits_fee = data.permits_fee
    estimate.engineering_fee = data.engineering_fee
    estimate.admin_fee = data.admin_fee
    estimate.heavy_equipment_rate = data.heavy_equipment_rate
    estimate.include_admin_fee = data.include_admin_fee
    estimate.include_hst = data.include_hst
    if data.status is not None:
        estimate.status = data.status
    for key, value in amounts.items():
        setattr(estimate, key, value)

    for t in list(estimate.tasks):
        session.delete(t)
    for r in list(estimate.equipment_rows):
        session.delete(r)
    for m in list(estimate.material_rows):
        session.delete(m)
    for s in list(estimate.scaffolding_rows):
        session.delete(s)
    for g in list(estimate.tooling_rows):
        session.delete(g)
    session.flush()

    for t in data.tasks:
        session.add(EstimateTask(estimate_id=estimate.id, **t.model_dump()))
    for r in data.equipment_rows:
        session.add(EstimateEquipmentRow(estimate_id=estimate.id, **r.model_dump()))
    for m in data.material_rows:
        session.add(EstimateMaterialRow(estimate_id=estimate.id, **m.model_dump()))
    for s in data.scaffolding_rows:
        session.add(EstimateScaffoldingRow(estimate_id=estimate.id, **s.model_dump()))
    for g in data.tooling_rows:
        session.add(EstimateToolingRow(estimate_id=estimate.id, **g.model_dump()))

    session.commit()

    return _get_estimate_or_404(session, estimate.id)


@router.delete("/{estimate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_estimate(estimate_id: int, session: DBSession, current_user: EstimatorUser):
    """Manager-only: delete an estimate"""
    estimate = session.get(Estimate, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")
    session.delete(estimate)
    session.commit()


# ============================================================
# Convert an estimate into a job
# ============================================================

def _duration_for_job(total_hours: Decimal | None) -> Decimal | None:
    """
    Estimate hours as a job's estimated_duration, or None when they do not fit.

    Job.estimated_duration is Numeric(4,2) but Estimate.total_hours is Numeric(8,2),
    so a long estimate overflows the column. Returning None rather than clamping is
    deliberate: a job reading "99.99 hrs" for a 208-hour build is a number nothing
    downstream can tell apart from a real one, and the true figure is still on the
    linked estimate.
    """
    if total_hours is None or total_hours <= 0:
        return None
    if total_hours > JOB_DURATION_MAX:
        logger.info(
            "Estimate total_hours %s exceeds Job.estimated_duration precision; leaving it unset",
            total_hours,
        )
        return None
    return total_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _is_redseal_estimate(estimate: Estimate) -> bool:
    """
    Whether the estimate actually scoped Red Seal work.

    Tagged tasks are the only signal. redseal_techs deliberately does NOT count: the
    calculator auto-fills it from crew size unless the manager unlinks it, so it is
    non-zero on virtually every estimate and says nothing about the work. Including it
    flagged ordinary jobs as Red Seal, which billed the client $100/hr on a job quoted
    at $80/hr - silently, because the estimate itself charges no Red Seal when no task
    is tagged.
    """
    return any(task.uses_redseal for task in estimate.tasks)


def _resolve_convert_client(session, estimate: Estimate, data: EstimateConvertRequest) -> Client:
    """
    The client the new job belongs to, creating one for a legacy prospect if needed.

    Any branch that resolves a different client also writes it back to the estimate,
    so the estimate and its job never disagree about who the customer is.
    """
    if data.client_id is not None:
        client = session.get(Client, data.client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        estimate.client_id = client.id
        estimate.client_name_override = None
        return client

    if data.new_client is not None:
        client = Client(**data.new_client.model_dump())
        session.add(client)
        session.flush()
        estimate.client_id = client.id
        estimate.client_name_override = None
        if not estimate.address_override:
            estimate.address_override = client.address
        return client

    if estimate.client_id is not None:
        client = session.get(Client, estimate.client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        return client

    name = (estimate.client_name_override or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This estimate has no client. Open the estimate and choose a client before converting it to a job.",
        )

    # Client.address is required because it is the site work happens at: an empty
    # one renders blank to crews, and makes calculate_distance return None, which
    # silently bills zero travel on the eventual invoice.
    address = (estimate.address_override or "").strip()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot create a client for "{name}" without an address. Add a job address to the estimate first.',
        )

    client = Client(name=name, address=address)
    session.add(client)
    session.flush()
    estimate.client_id = client.id
    estimate.client_name_override = None
    return client


@router.post("/{estimate_id}/convert-to-job", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def convert_estimate_to_job(
    estimate_id: int,
    data: EstimateConvertRequest,
    session: DBSession,
    current_user: ManagerUser,
):
    """
    Create a job from an estimate, link the two, and mark the estimate accepted.

    Manager-only rather than estimator-level like the rest of this module: it creates
    a Job, and POST /api/jobs/ is manager-only, so allowing estimators here would be a
    side door around that boundary.
    """
    estimate = _load_estimate(session, estimate_id)
    if not estimate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estimate not found",
        )

    # The unique index on Estimate.job_id stops two estimates sharing one job, but
    # not one estimate being converted twice - that would just repoint this row at a
    # second job and orphan the first one, which keeps its estimate_amount and shows
    # up as a real job. This guard is the only thing preventing it, so it runs before
    # any write.
    if estimate.job_id is not None:
        existing = f"job #{estimate.job_id}"
        if estimate.job:
            existing = f"job #{estimate.job_id} ({estimate.job.title})"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Estimate {estimate.estimate_number} has already been converted to {existing}",
        )

    if data.client_id is not None and data.new_client is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either client_id or new_client, not both",
        )

    if data.start_date and data.end_date and data.end_date < data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date",
        )

    client = _resolve_convert_client(session, estimate, data)

    address_override = data.address_override or estimate.address_override
    job_address = address_override or client.address
    # The estimate's distance wins: it is manager-tuned for staging yards and ferries,
    # and reusing it keeps the invoice's travel line matching what was quoted.
    distance = estimate.distance_km or calculate_distance(job_address)

    job = Job(
        client_id=client.id,
        title=data.title,
        # scope_of_work, never notes - notes are internal margin commentary and
        # Job.details is shown to workers.
        details=data.details if data.details is not None else estimate.scope_of_work,
        start_date=data.start_date,
        end_date=data.end_date,
        scheduled_time=data.scheduled_time,
        estimated_duration=(
            data.estimated_duration
            if data.estimated_duration is not None
            else _duration_for_job(estimate.total_hours)
        ),
        # HST-inclusive on purpose. /financials measures margin from the linked
        # estimate's pre-tax subtotal, so this does not distort it - it is the
        # headline job value a manager wants on the job itself.
        estimate_amount=estimate.total,
        address_override=address_override,
        is_redseal_trade=(
            data.is_redseal_trade
            if data.is_redseal_trade is not None
            else _is_redseal_estimate(estimate)
        ),
        calculated_distance_km=distance,
    )
    session.add(job)
    session.flush()

    scheduled_worker_ids = {entry.worker_id for entry in data.worker_schedule}
    for worker_id in sorted(scheduled_worker_ids | set(data.assigned_worker_ids)):
        # create_job silently skips unknown worker ids; here we reject them, because
        # a manager believing a crew is booked when it is not is worse than an error.
        if not session.get(Worker, worker_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker {worker_id} not found",
            )
        session.add(JobWorkerLink(job_id=job.id, worker_id=worker_id))

    for entry in data.worker_schedule:
        session.add(JobWorkerSchedule(job_id=job.id, worker_id=entry.worker_id, date=entry.date))

    estimate.job_id = job.id
    estimate.status = EstimateStatus.ACCEPTED.value
    session.add(estimate)

    # One commit for the whole conversion: a partial apply would leave either a job
    # with no estimate or an estimate pointing at nothing, and there is no UI to repair
    # that.
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Estimate was converted by another request",
        )

    statement = (
        select(Job)
        .where(Job.id == job.id)
        .options(
            selectinload(Job.client),
            selectinload(Job.assigned_workers),
            selectinload(Job.photos),
            selectinload(Job.worker_schedule),
        )
    )
    return job_to_response(session.exec(statement).first())


@router.get("/{estimate_id}/pdf")
def download_estimate_pdf(
    estimate_id: int,
    session: DBSession,
    current_user: EstimatorUser,
    inline: bool = False,
    customer: bool = False,
):
    """Manager-only: download the estimate as a PDF. customer=true omits the
    internal Preplanning/Build/Finishing hour breakdown - the version meant to
    actually be sent to the client."""
    estimate = _load_estimate(session, estimate_id)
    if not estimate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found")

    pdf_content = generate_estimate_pdf(estimate, customer_copy=customer)

    disposition = "inline" if inline else "attachment"
    suffix = "_Customer" if customer else ""
    filename = f"Estimate_{estimate.estimate_number}{suffix}.pdf"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
