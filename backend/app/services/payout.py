"""
Payout calculation service - ported from Django
"""
from decimal import Decimal, ROUND_HALF_UP

from ..models import Timesheet, Worker
from ..config import settings


# Minimum hours threshold for payout
MINIMUM_HOURS = Decimal("4.0")

# KM reimbursement rate per kilometer
KM_RATE = Decimal("0.50")

# HST rate (Ontario)
HST_RATE = Decimal("1.13")


def is_company_card(card_digits: str | None) -> bool:
    """
    Check if the card digits belong to a company card.
    Company cards are configured in settings.
    """
    if not card_digits:
        return False

    # Normalize: strip whitespace and ensure 4 digits
    normalized = card_digits.strip()

    # Get company card digits from settings (comma-separated list)
    company_cards = getattr(settings, 'COMPANY_CARD_DIGITS', '5564')
    if isinstance(company_cards, str):
        company_cards = [c.strip() for c in company_cards.split(',')]

    return normalized in company_cards


def validate_timesheet_values(timesheet: Timesheet) -> None:
    """
    Validate timesheet values before calculation.
    Raises ValueError for invalid data.
    """
    if timesheet.hours_worked <= 0:
        raise ValueError("Hours worked must be greater than 0")

    if timesheet.round_trip_kms < 0:
        raise ValueError("Round trip KMs cannot be negative")

    if timesheet.personal_materials < 0:
        raise ValueError("Personal materials cannot be negative")

    if timesheet.receipts_total < 0:
        raise ValueError("Receipts total cannot be negative")

    if timesheet.company_materials < 0:
        raise ValueError("Company materials cannot be negative")


def calculate_payout(timesheet: Timesheet, worker: Worker) -> Decimal:
    """
    Calculate the payout for a timesheet.

    Logic:
    1. Validate input values
    2. Round hours to nearest 0.25
    3. Apply minimum 4-hour threshold
    4. Add hourly rate × hours (with HST if applicable)
    5. Add km reimbursement ($0.50/km) unless using company truck or at HQ
    6. Add personal materials reimbursement
    7. Add receipts reimbursement (except if using company card)
    """
    # Validate inputs
    validate_timesheet_values(timesheet)

    total = Decimal("0")

    # 1. Round hours to nearest 0.25
    hours_float = float(timesheet.hours_worked)
    rounded_hours = round(hours_float * 4) / 4
    payable_hours = max(Decimal(str(rounded_hours)), MINIMUM_HOURS)

    # 2. Labor cost
    labor = payable_hours * worker.hourly_rate
    if worker.charges_hst:
        labor *= HST_RATE
    total += labor

    # 3. KM reimbursement (0 if company truck or at HQ)
    km_reimbursement = Decimal("0")
    if not timesheet.used_company_truck and not timesheet.worked_at_hq:
        km_reimbursement = timesheet.round_trip_kms * KM_RATE
        total += km_reimbursement

    # 4. Personal materials (worker paid, gets reimbursed)
    total += timesheet.personal_materials

    # 5. Receipts reimbursement (check for company card)
    receipts_reimbursement = Decimal("0")
    if not is_company_card(timesheet.receipt_card_digits):
        receipts_reimbursement = timesheet.receipts_total
        total += receipts_reimbursement

    # Note: company_materials is NOT added to worker pay (company already paid)

    # Round to 2 decimal places
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_payout_breakdown(timesheet: Timesheet, worker: Worker) -> dict:
    """
    Calculate payout with detailed breakdown for preview.
    Returns dict with all components of the calculation.
    """
    # Validate inputs
    validate_timesheet_values(timesheet)

    # 1. Hours calculation
    hours_float = float(timesheet.hours_worked)
    rounded_hours = Decimal(str(round(hours_float * 4) / 4))
    billable_hours = max(rounded_hours, MINIMUM_HOURS)
    minimum_applied = rounded_hours < MINIMUM_HOURS

    # 2. Labor cost
    labor_cost = billable_hours * worker.hourly_rate
    if worker.charges_hst:
        labor_cost *= HST_RATE
    labor_cost = labor_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 3. KM reimbursement
    km_reimbursement = Decimal("0")
    if not timesheet.used_company_truck and not timesheet.worked_at_hq:
        km_reimbursement = (timesheet.round_trip_kms * KM_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # 4. Receipts reimbursement
    receipts_reimbursement = Decimal("0")
    if not is_company_card(timesheet.receipt_card_digits):
        receipts_reimbursement = timesheet.receipts_total

    # 5. Total
    total = labor_cost + km_reimbursement + timesheet.personal_materials + receipts_reimbursement
    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "hours_worked": timesheet.hours_worked,
        "rounded_hours": rounded_hours,
        "billable_hours": billable_hours,
        "minimum_applied": minimum_applied,
        "labor_cost": labor_cost,
        "hst_applied": worker.charges_hst,
        "km_reimbursement": km_reimbursement,
        "personal_materials": timesheet.personal_materials,
        "receipts_reimbursement": receipts_reimbursement,
        "calculated_pay": total,
    }


def calculate_hours_display(hours_worked: Decimal) -> dict:
    """
    Calculate display values for hours.
    Returns both actual and billable hours.
    """
    hours_float = float(hours_worked)
    rounded_hours = round(hours_float * 4) / 4
    billable_hours = max(rounded_hours, float(MINIMUM_HOURS))

    return {
        "actual_hours": hours_worked,
        "rounded_hours": Decimal(str(rounded_hours)),
        "billable_hours": Decimal(str(billable_hours)),
        "minimum_applied": rounded_hours < float(MINIMUM_HOURS),
    }
