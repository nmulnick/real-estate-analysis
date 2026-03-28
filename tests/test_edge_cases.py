"""Edge case tests — extreme or unusual input combinations."""
import math
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off


class TestHoldPeriodEdges:

    def test_hold_1_year(self):
        """Minimal hold period — single year of lease, minimal compounding."""
        ra.hold_period_years = 1
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200_000_000)
        assert a["future_value_after_tax"] > 0
        assert b["total_fv_after_tax"] > 0
        assert len(b["annual_details"]) == 1
        # Only 1 year of lease — should be phase 1 ($600K)
        assert b["annual_details"][0]["lease"] == pytest.approx(600_000, abs=1)

    def test_hold_30_years(self):
        """Max hold — heavy compounding, all years use phase 2 after transition."""
        ra.hold_period_years = 30
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200_000_000)
        assert len(b["annual_details"]) == 30
        assert a["future_value_after_tax"] > 0
        assert b["total_fv_after_tax"] > 0
        # Years 5-30 should all use phase 2
        for d in b["annual_details"][4:]:
            assert d["lease"] == pytest.approx(2_000_000, abs=1)


class TestZeroAndExtremeInputs:

    def test_zero_gross_sale(self):
        """Selling for $0 — net proceeds = 0, no tax, FV = 0."""
        ra.current_gross_sale_price = 0
        a = ra.calc_scenario_a()
        assert a["net_sale_proceeds"] == 0
        assert a["sale_tax"] == 0
        assert a["future_value_after_tax"] == 0

    def test_zero_exit_price(self):
        """Exit at $0 — only compounded CFs matter."""
        b = ra.calc_scenario_b(0)
        assert b["net_exit_after_tax"] == 0
        assert b["total_fv_after_tax"] == b["compounded_cf"]

    def test_100pct_tx_cost(self):
        """100% transaction cost — net proceeds = -REET (tx eats gross, REET on top)."""
        a = ra.calc_scenario_a(tx_cost_rate=1.0)
        reet = ra.calc_reet(ra.current_gross_sale_price)["total_reet"]
        assert a["net_sale_proceeds"] == pytest.approx(-reet, abs=1)
        expected_fv = -reet * (1.06 ** 10)  # negative proceeds compound negatively
        assert a["future_value_after_tax"] == pytest.approx(expected_fv, abs=1)

    def test_zero_reinvestment_rate(self):
        """0% reinvestment — FV should equal after-tax proceeds (no growth)."""
        a = ra.calc_scenario_a(reinv_rate=0.0)
        assert a["future_value_after_tax"] == pytest.approx(a["after_tax_proceeds"], abs=1)

    def test_very_high_reinvestment_rate(self):
        """20% reinvestment — should still compute without error."""
        a = ra.calc_scenario_a(reinv_rate=0.20)
        assert a["future_value_after_tax"] > a["after_tax_proceeds"]


class TestLeaseEdges:

    def test_identical_phase1_phase2(self):
        """Same NOI in both phases — should behave like flat lease."""
        ra.noi_phase1 = 2_000_000
        ra.noi_phase2 = 2_000_000
        b = ra.calc_scenario_b(200_000_000)
        for d in b["annual_details"]:
            assert d["lease"] == pytest.approx(2_000_000, abs=1)

    def test_phase1_end_at_zero(self):
        """Transition at year 0 — all years use phase 2."""
        ra.phase1_end_year = 0
        b = ra.calc_scenario_b(200_000_000)
        for d in b["annual_details"]:
            assert d["lease"] == pytest.approx(2_000_000, abs=1)

    def test_phase1_end_at_hold_period(self):
        """Transition at year 10 — all years use phase 1."""
        ra.phase1_end_year = 10
        b = ra.calc_scenario_b(200_000_000)
        for d in b["annual_details"]:
            assert d["lease"] == pytest.approx(600_000, abs=1)

    def test_zero_noi_both_phases(self):
        """No lease income at all — CFs should be negative (carry only) or zero."""
        ra.noi_phase1 = 0
        ra.noi_phase2 = 0
        b = ra.calc_scenario_b(200_000_000)
        for d in b["annual_details"]:
            assert d["lease"] == 0
            assert d["net_cf_after_tax"] <= 0


class TestDepreciationEdges:

    def test_very_large_depreciation(self):
        """Depreciation exceeding basis — no negative basis, no crash."""
        set_1031_off()
        ra.cumulative_depreciation = 50_000_000  # way more than $8.425M basis
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200_000_000)
        assert a["sale_tax"] >= 0
        assert b["exit_tax"] >= 0
        assert a["future_value_after_tax"] > 0

    def test_depreciation_equals_basis(self):
        """Fully depreciated property."""
        set_1031_off()
        ra.cumulative_depreciation = 8_425_000
        a = ra.calc_scenario_a()
        assert a["sale_tax"] >= 0


class TestCarryingCostEdges:

    def test_negative_carry_escalation(self):
        """Declining carrying costs — should still work."""
        ra.initial_carrying_costs = 1_000_000
        ra.carrying_cost_escalation = -0.05  # 5% decline per year
        b = ra.calc_scenario_b(200_000_000)
        # Year 10 carry should be less than year 1
        assert b["annual_details"][9]["carrying"] < b["annual_details"][0]["carrying"]

    def test_zero_carry_zero_noi(self):
        """No income, no expenses — CFs all zero, only exit matters."""
        ra.initial_carrying_costs = 0
        ra.noi_phase1 = 0
        ra.noi_phase2 = 0
        b = ra.calc_scenario_b(200_000_000)
        assert b["compounded_cf"] == pytest.approx(0, abs=1)
        assert b["total_fv_after_tax"] == pytest.approx(b["net_exit_after_tax"], abs=1)


class TestMultiExitEdges:

    def test_all_three_exits_identical(self):
        """If all exit prices are the same, multi-exit should equal single-exit."""
        ra.exit_bull = 200_000_000
        ra.exit_base = 200_000_000
        ra.exit_bear = 200_000_000
        ra.weight_bull = 0.25
        ra.weight_base = 0.50
        ra.weight_bear = 0.25

        result = ra.evaluate_exit_scenarios()
        single = ra.calc_scenario_b(200_000_000)

        assert result["summary"]["b"]["total_fv_after_tax"] == pytest.approx(
            single["total_fv_after_tax"], abs=1)

    def test_single_scenario_weight_100(self):
        """One scenario at 100% weight — should equal direct calc."""
        ra.exit_bull = 200_000_000
        ra.exit_base = 0
        ra.exit_bear = 0
        ra.weight_bull = 1.0
        ra.weight_base = 0.0
        ra.weight_bear = 0.0

        result = ra.evaluate_exit_scenarios()
        direct = ra.calc_scenario_b(200_000_000)

        assert result["summary"]["b"]["total_fv_after_tax"] == pytest.approx(
            direct["total_fv_after_tax"], abs=1)
