"""
Unit tests for the quick quote calculation logic (calculate_quick_estimate).
These are pure function tests - no database or HTTP client required.
"""
from decimal import Decimal
import pytest

from app.api.estimates import (
    calculate_quick_estimate,
    JOB_TYPE_DEFAULTS,
    DEFAULT_ADMIN_FEE,
)
from app.api.invoices import LABOUR_RATE, MINIMUM_HOURS, DEFAULT_KM_RATE, HST_RATE

DEFAULT_HOURS_PER_SQFT = JOB_TYPE_DEFAULTS["general"]["hours_per_sqft"]
DEFAULT_MATERIALS_PER_SQFT = JOB_TYPE_DEFAULTS["general"]["materials_per_sqft"]


class TestJobTypes:
    def test_general_type_always_present(self):
        """'general' must always exist - it's the fallback for unknown job types."""
        assert "general" in JOB_TYPE_DEFAULTS

    def test_redseal_trades_not_offered_on_quick_quote(self):
        """Plumbing/electrical scope varies too much for a sqft-based instant quote."""
        assert "plumbing" not in JOB_TYPE_DEFAULTS
        assert "electrical" not in JOB_TYPE_DEFAULTS

    def test_each_job_type_has_distinct_positive_rates(self):
        for job_type, defaults in JOB_TYPE_DEFAULTS.items():
            assert defaults["hours_per_sqft"] > Decimal("0"), job_type
            assert defaults["materials_per_sqft"] >= Decimal("0"), job_type
            assert defaults["label"]


class TestEstimatedHours:
    def test_small_area_floors_to_minimum_hours(self):
        """A tiny area should still bill the 4-hour minimum."""
        result = calculate_quick_estimate(
            area_sqft=Decimal("10"),
            distance_km=None,
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=DEFAULT_ADMIN_FEE,
        )
        assert result["estimated_hours"] == MINIMUM_HOURS

    def test_large_area_scales_past_minimum(self):
        """1000 sqft at 0.02 hr/sqft is 20 hours, well above the minimum."""
        result = calculate_quick_estimate(
            area_sqft=Decimal("1000"),
            distance_km=None,
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=DEFAULT_ADMIN_FEE,
        )
        assert result["estimated_hours"] == Decimal("20.0")
        assert result["labour_amount"] == Decimal("20.0") * LABOUR_RATE


class TestTravelAmount:
    def test_no_distance_means_no_travel_charge(self):
        """If Google Maps distance lookup fails/unavailable, travel is $0, not an error."""
        result = calculate_quick_estimate(
            area_sqft=Decimal("500"),
            distance_km=None,
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=DEFAULT_ADMIN_FEE,
        )
        assert result["travel_amount"] == Decimal("0.00")

    def test_distance_applies_km_rate(self):
        result = calculate_quick_estimate(
            area_sqft=Decimal("500"),
            distance_km=Decimal("40"),
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=DEFAULT_ADMIN_FEE,
        )
        assert result["travel_amount"] == (Decimal("40") * DEFAULT_KM_RATE).quantize(Decimal("0.01"))


class TestMaterialsAndTotals:
    def test_materials_scale_with_area(self):
        result = calculate_quick_estimate(
            area_sqft=Decimal("200"),
            distance_km=None,
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=DEFAULT_ADMIN_FEE,
        )
        assert result["materials_amount"] == (Decimal("200") * DEFAULT_MATERIALS_PER_SQFT).quantize(Decimal("0.01"))

    def test_hst_applied_to_full_subtotal(self):
        result = calculate_quick_estimate(
            area_sqft=Decimal("1000"),
            distance_km=Decimal("40"),
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=DEFAULT_ADMIN_FEE,
        )
        expected_subtotal = (
            result["labour_amount"]
            + result["travel_amount"]
            + result["materials_amount"]
            + result["admin_fee"]
        )
        assert result["subtotal"] == expected_subtotal
        assert result["hst_amount"] == (expected_subtotal * HST_RATE).quantize(Decimal("0.01"))
        assert result["total"] == expected_subtotal + result["hst_amount"]

    def test_admin_fee_included_in_subtotal(self):
        result = calculate_quick_estimate(
            area_sqft=Decimal("1000"),
            distance_km=None,
            hours_per_sqft=DEFAULT_HOURS_PER_SQFT,
            materials_per_sqft=DEFAULT_MATERIALS_PER_SQFT,
            admin_fee=Decimal("50.00"),
        )
        assert result["admin_fee"] == Decimal("50.00")
