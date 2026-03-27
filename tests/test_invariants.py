"""Invariant tests — properties that must hold true for ANY valid inputs."""
import math
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off

# Test with multiple input combinations
PARAM_COMBOS = [
    {"label": "defaults_1031_on"},
    {"label": "1031_off", "setup": lambda: set_1031_off()},
    {"label": "high_depreciation", "setup": lambda: (set_1031_off(), setattr(ra, 'cumulative_depreciation', 5_000_000))},
    {"label": "high_carry", "setup": lambda: setattr(ra, 'initial_carrying_costs', 2_000_000)},
    {"label": "low_reinv", "setup": lambda: setattr(ra, 'reinvestment_rate', 0.02)},
]


def setup_params(combo):
    """Apply parameter setup if defined."""
    if "setup" in combo:
        combo["setup"]()


class TestScenarioAInvariants:
    """Properties that must always hold for Scenario A."""

    @pytest.mark.parametrize("combo", PARAM_COMBOS, ids=lambda c: c["label"])
    def test_npv_equals_after_tax_proceeds(self, combo):
        """NPV = after-tax proceeds (received today, no discounting)."""
        setup_params(combo)
        a = ra.calc_scenario_a()
        assert a["npv"] == a["after_tax_proceeds"]

    @pytest.mark.parametrize("combo", PARAM_COMBOS, ids=lambda c: c["label"])
    def test_net_proceeds_leq_gross(self, combo):
        """Net proceeds ≤ gross sale (TX costs only reduce)."""
        setup_params(combo)
        a = ra.calc_scenario_a()
        assert a["net_sale_proceeds"] <= a["gross_sale"]

    @pytest.mark.parametrize("combo", PARAM_COMBOS, ids=lambda c: c["label"])
    def test_sale_tax_non_negative(self, combo):
        """Sale tax can never be negative."""
        setup_params(combo)
        a = ra.calc_scenario_a()
        assert a["sale_tax"] >= 0

    @pytest.mark.parametrize("combo", PARAM_COMBOS, ids=lambda c: c["label"])
    def test_inv_tax_non_negative(self, combo):
        """Investment gain tax can never be negative."""
        setup_params(combo)
        a = ra.calc_scenario_a()
        assert a["inv_tax"] >= 0

    @pytest.mark.parametrize("combo", PARAM_COMBOS, ids=lambda c: c["label"])
    def test_fv_geq_after_tax_proceeds(self, combo):
        """FV ≥ after-tax proceeds (compounding can't lose money at positive rate)."""
        setup_params(combo)
        a = ra.calc_scenario_a()
        # Only true when reinvestment rate ≥ 0
        if ra.reinvestment_rate >= 0:
            assert a["future_value_gross"] >= a["after_tax_proceeds"] - 1

    @pytest.mark.parametrize("combo", PARAM_COMBOS, ids=lambda c: c["label"])
    def test_after_tax_fv_leq_gross_fv(self, combo):
        """After-tax FV ≤ gross FV (tax only reduces)."""
        setup_params(combo)
        a = ra.calc_scenario_a()
        assert a["future_value_after_tax"] <= a["future_value_gross"] + 1


class TestScenarioBInvariants:
    """Properties that must always hold for Scenario B."""

    EXIT_PRICES = [50_000_000, 100_000_000, 200_000_000, 300_000_000]

    @pytest.mark.parametrize("exit_price", EXIT_PRICES)
    def test_total_fv_identity(self, exit_price):
        """Total FV = net exit after tax + compounded CFs."""
        b = ra.calc_scenario_b(exit_price)
        assert b["total_fv_after_tax"] == pytest.approx(
            b["net_exit_after_tax"] + b["compounded_cf"], abs=1)

    @pytest.mark.parametrize("exit_price", EXIT_PRICES)
    def test_exit_tax_non_negative(self, exit_price):
        """Exit tax can never be negative."""
        set_1031_off()
        b = ra.calc_scenario_b(exit_price)
        assert b["exit_tax"] >= 0

    @pytest.mark.parametrize("exit_price", EXIT_PRICES)
    def test_net_exit_leq_gross(self, exit_price):
        """Net exit ≤ gross exit (TX costs only reduce)."""
        b = ra.calc_scenario_b(exit_price)
        assert b["net_exit"] <= exit_price + 1

    @pytest.mark.parametrize("exit_price", EXIT_PRICES)
    def test_npv_components_sum(self, exit_price):
        """Total NPV = PV of CFs + PV of exit."""
        b = ra.calc_scenario_b(exit_price)
        assert b["total_npv"] == pytest.approx(b["npv_cf_sum"] + b["pv_exit"], abs=1)

    @pytest.mark.parametrize("exit_price", EXIT_PRICES)
    def test_annual_details_length(self, exit_price):
        """Annual details should have exactly hold_period_years entries."""
        b = ra.calc_scenario_b(exit_price)
        assert len(b["annual_details"]) == ra.hold_period_years

    @pytest.mark.parametrize("exit_price", EXIT_PRICES)
    def test_income_tax_non_negative(self, exit_price):
        """Income tax on lease is never negative."""
        b = ra.calc_scenario_b(exit_price)
        for d in b["annual_details"]:
            assert d["income_tax"] >= 0


class TestIRRInvariants:
    """Properties that must always hold for the IRR calculation."""

    @pytest.mark.parametrize("exit_price", [100_000_000, 200_000_000, 300_000_000])
    def test_irr_npv_is_zero(self, exit_price):
        """At the computed IRR, NPV of cash flows should be ≈ $0."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(exit_price)
        irr = ra.calc_irr(a["after_tax_proceeds"], b)
        if irr is None:
            pytest.skip("No valid IRR for this case")

        cfs = [-a["after_tax_proceeds"]]
        for d in b["annual_details"]:
            cf = d["net_cf_after_tax"]
            if d["year"] == ra.hold_period_years:
                cf += b["net_exit_after_tax"]
            cfs.append(cf)

        npv_at_irr = sum(cf / (1 + irr) ** t for t, cf in enumerate(cfs))
        assert npv_at_irr == pytest.approx(0, abs=1000)

    def test_higher_exit_higher_irr(self):
        """Monotonicity: higher exit price → higher or equal IRR."""
        a = ra.calc_scenario_a()
        exits = [100e6, 150e6, 200e6, 250e6, 300e6]
        irrs = []
        for ep in exits:
            b = ra.calc_scenario_b(ep)
            irr = ra.calc_irr(a["after_tax_proceeds"], b)
            if irr is not None:
                irrs.append(irr)
        # Each successive IRR should be ≥ the previous
        for i in range(1, len(irrs)):
            assert irrs[i] >= irrs[i-1] - 0.001  # small tolerance


class TestBreakevenInvariants:

    @pytest.mark.parametrize("exit_price", [100_000_000, 200_000_000, 300_000_000])
    def test_breakeven_round_trip(self, exit_price):
        """calcA(breakeven).FV ≈ calcB(exit).FV — the fundamental identity."""
        b = ra.calc_scenario_b(exit_price)
        target = b["total_fv_after_tax"]
        result = ra.calc_breakeven_sale_price(target)
        if result["status"] != "ok" or result["value"] is None:
            pytest.skip("No valid breakeven for this case")

        a_check = ra.calc_scenario_a_from_gross_sale(result["value"])
        assert a_check["future_value_after_tax"] == pytest.approx(target, abs=100)

    def test_breakeven_non_negative(self):
        """Breakeven sale price can never be negative."""
        b = ra.calc_scenario_b(200_000_000)
        result = ra.calc_breakeven_sale_price(b["total_fv_after_tax"])
        if result["value"] is not None:
            assert result["value"] >= 0


class TestWeightInvariants:

    def test_normalized_weights_sum_to_one(self):
        """After normalization, weights always sum to 1.0."""
        ra.weight_bull = 0.4
        ra.weight_base = 0.4
        ra.weight_bear = 0.4
        result = ra.normalize_exit_scenario_weights()
        total = sum(s["wt"] for s in result["scenarios"])
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_zero_weights_get_equal_distribution(self):
        """All-zero weights → equal distribution (1/3 each)."""
        ra.weight_bull = 0
        ra.weight_base = 0
        ra.weight_bear = 0
        result = ra.normalize_exit_scenario_weights()
        for s in result["scenarios"]:
            assert s["wt"] == pytest.approx(1/3, abs=1e-6)

    def test_correct_weights_no_notice(self):
        """Weights summing to 1.0 → no notice."""
        ra.weight_bull = 0.25
        ra.weight_base = 0.50
        ra.weight_bear = 0.25
        result = ra.normalize_exit_scenario_weights()
        assert result["notice"] == ""


class TestCGTaxInvariants:

    @pytest.mark.parametrize("gain", [-10_000_000, -1_000_000, 0, 1_000_000, 50_000_000, 100_000_000])
    def test_tax_non_negative(self, gain):
        """Tax can never be negative for any gain amount."""
        set_1031_off()
        tax = ra.calc_cap_gains_tax(gain, 0, fed_rate=0.20, niit=0.038)
        assert tax >= 0

    @pytest.mark.parametrize("gain", [1_000_000, 50_000_000])
    def test_higher_rate_higher_tax(self, gain):
        """Higher CG rate → higher or equal tax."""
        tax_15 = ra.calc_cap_gains_tax(gain, 0, fed_rate=0.15, niit=0.038)
        tax_20 = ra.calc_cap_gains_tax(gain, 0, fed_rate=0.20, niit=0.038)
        tax_25 = ra.calc_cap_gains_tax(gain, 0, fed_rate=0.25, niit=0.038)
        assert tax_15 <= tax_20 + 1
        assert tax_20 <= tax_25 + 1

    @pytest.mark.parametrize("gain", [-5_000_000, 0])
    def test_no_tax_on_loss(self, gain):
        """No tax when gain ≤ 0."""
        set_1031_off()
        tax = ra.calc_cap_gains_tax(gain, 0, fed_rate=0.20, niit=0.038)
        assert tax == 0
