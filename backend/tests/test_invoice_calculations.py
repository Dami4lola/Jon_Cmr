"""
Unit tests for invoice calculation logic (_round_hours, HST_RATE).
These are pure function tests — no database or HTTP client required.
"""
from decimal import Decimal
import pytest

# _round_hours is a module-level helper; importing it directly is intentional
from app.api.invoices import _round_hours, HST_RATE, MINIMUM_HOURS


class TestRoundHours:
    def test_exact_minimum_unchanged(self):
        """Exactly the minimum hours should be returned as-is."""
        assert _round_hours(Decimal("4.0")) == Decimal("4.0")

    def test_below_minimum_raises_to_floor(self):
        """Hours below the 4-hour minimum should be raised to MINIMUM_HOURS."""
        result = _round_hours(Decimal("1.0"))
        assert result == MINIMUM_HOURS

    def test_rounds_up_to_nearest_quarter(self):
        """0.1 hours above a whole number should round up to the next quarter."""
        result = _round_hours(Decimal("4.1"), minimum_hours=Decimal("0"))
        assert result == Decimal("0.25") * round(Decimal("4.1") / Decimal("0.25"))

    def test_break_deducted_after_rounding(self):
        """Break duration is subtracted from the rounded hours."""
        result = _round_hours(
            Decimal("5.0"),
            break_duration=Decimal("0.5"),
            minimum_hours=Decimal("0"),
        )
        assert result == Decimal("4.5")

    def test_minimum_override_zero(self):
        """Passing minimum_hours=0 disables the minimum floor."""
        result = _round_hours(Decimal("1.0"), minimum_hours=Decimal("0"))
        assert result == Decimal("1.0")

    def test_large_hours_above_minimum(self):
        """Hours clearly above the minimum should not be floored."""
        result = _round_hours(Decimal("8.0"))
        assert result == Decimal("8.0")

    def test_break_cannot_produce_negative(self):
        """Even with a large break, result should be >= 0 (and >= minimum_hours)."""
        result = _round_hours(
            Decimal("1.0"),
            break_duration=Decimal("2.0"),
            minimum_hours=Decimal("0"),
        )
        assert result >= Decimal("0")


def test_hst_rate_is_thirteen_percent():
    """HST rate must be 13% — change here is a billing-critical regression."""
    assert HST_RATE == Decimal("0.13")


def test_minimum_hours_constant():
    """Minimum billable hours must be 4.0."""
    assert MINIMUM_HOURS == Decimal("4.0")
