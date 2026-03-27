"""Tests for the breakeven sale price calculation."""
import math
import pytest
import real_estate_analysis as ra


class TestBreakeven:

    def test_round_trip(self):
        """Selling at breakeven price should produce FV matching Scenario B."""
        b = ra.calc_scenario_b(200_000_000)
        target = b["total_fv_after_tax"]
        result = ra.calc_breakeven_sale_price(target)

        assert result["status"] == "ok"
        breakeven = result["value"]
        assert breakeven is not None

        # Verify: run Scenario A at breakeven price
        a_check = ra.calc_scenario_a_from_gross_sale(breakeven)
        assert a_check["future_value_after_tax"] == pytest.approx(target, abs=100)

    def test_breakeven_exceeds_current_offer(self):
        """With default inputs, breakeven should exceed $100M offer."""
        b = ra.calc_scenario_b(200_000_000)
        result = ra.calc_breakeven_sale_price(b["total_fv_after_tax"])
        assert result["status"] == "ok"
        assert result["value"] > 100_000_000

    def test_invalid_target(self):
        """Non-finite target → invalid_target status."""
        result = ra.calc_breakeven_sale_price(float('nan'))
        assert result["status"] == "invalid_target"
        assert result["value"] is None

    def test_inf_target(self):
        result = ra.calc_breakeven_sale_price(float('inf'))
        assert result["status"] == "invalid_target"
        assert result["value"] is None

    def test_zero_sale_beats_target(self):
        """Very small target → zero sale beats it."""
        result = ra.calc_breakeven_sale_price(-5_000_000)
        assert result["status"] == "zero_sale_beats_target"
        assert result["value"] == 0

    def test_large_target_converges(self):
        """Even with a very large target, search should converge."""
        result = ra.calc_breakeven_sale_price(500_000_000)
        assert result["status"] == "ok"
        assert result["value"] is not None
        assert result["value"] > 0
