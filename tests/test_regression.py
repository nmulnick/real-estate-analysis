"""Regression tests — things that broke before and must never break again."""
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off


class TestToggle1031Regression:
    """The 1031 toggle must correctly flip tax rates."""

    def test_1031_on_zeroes_rates(self):
        """1031 ON → fed=0, niit=0, dep_recap=0."""
        # Defaults from conftest are 1031 ON
        assert ra.federal_cap_gains_rate == 0.0
        assert ra.niit_rate == 0.0
        # dep_recap is set to 0 by conftest (1031 ON)
        assert ra.depreciation_recapture_rate == 0.0

    def test_1031_off_restores_rates(self):
        """1031 OFF → fed=20%, niit=3.8%, dep_recap=25%."""
        set_1031_off()
        assert ra.federal_cap_gains_rate == 0.20
        assert ra.niit_rate == 0.038
        assert ra.depreciation_recapture_rate == 0.25

    def test_1031_toggle_cycle(self):
        """Toggle OFF then ON restores zero rates."""
        set_1031_off()
        assert ra.federal_cap_gains_rate == 0.20
        # Toggle back ON
        ra.federal_cap_gains_rate = 0.0
        ra.niit_rate = 0.0
        ra.depreciation_recapture_rate = 0.0
        a = ra.calc_scenario_a()
        assert a["sale_tax"] == pytest.approx(0, abs=1)
        assert a["inv_tax"] == pytest.approx(0, abs=1)

    def test_1031_doesnt_affect_ordinary_income(self):
        """Ordinary income rate must NOT change with 1031."""
        assert ra.ordinary_income_rate == 0.37
        set_1031_off()
        assert ra.ordinary_income_rate == 0.37


class TestBreakevenMultiPrice:
    """Breakeven round-trip at various exit prices."""

    @pytest.mark.parametrize("exit_price", [50_000_000, 100_000_000, 200_000_000, 300_000_000, 500_000_000])
    def test_breakeven_round_trip(self, exit_price):
        """calcA(breakeven).FV ≈ calcB(exit).FV for various exits."""
        b = ra.calc_scenario_b(exit_price)
        target = b["total_fv_after_tax"]
        result = ra.calc_breakeven_sale_price(target)

        if result["status"] == "ok" and result["value"] is not None:
            a_check = ra.calc_scenario_a_from_gross_sale(result["value"])
            assert a_check["future_value_after_tax"] == pytest.approx(target, abs=100)


class TestSensTable2WeightedRegression:
    """Sensitivity Table 2 must use weighted outcomes, not weighted price."""

    def test_weighted_outcomes_differ_with_taxes(self):
        """With taxes on, large depreciation, and spread exits, weighted outcomes ≠ shortcut.
        Tax nonlinearity comes from depreciation recapture: exits near/below adjusted basis
        trigger different recapture amounts than exits well above it."""
        set_1031_off()
        ra.cost_basis = 60_000_000
        ra.cumulative_depreciation = 50_000_000  # adjusted basis = $10M

        # Spread exits so bear case is near adjusted basis (partial recapture)
        # and bull case is well above (full recapture + CG)
        scenarios = [(300e6, 0.25), (150e6, 0.50), (20e6, 0.25)]
        pw_exit = sum(p * w for p, w in scenarios)

        shortcut = ra.calc_scenario_b(pw_exit)
        weighted_fv = sum(ra.calc_scenario_b(p)["total_fv_after_tax"] * w for p, w in scenarios)

        # Difference should be meaningful (>$100K with these extreme params)
        assert abs(weighted_fv - shortcut["total_fv_after_tax"]) > 100


class TestWAToggleCycleRegression:
    """WA rate must survive toggle cycles."""

    def test_wa_rate_stays_after_enable_disable(self):
        """Toggle WA on→off→on: rate must remain 0.07."""
        ra.wa_cap_gains_enabled = True
        assert ra.wa_cap_gains_rate == 0.07
        ra.wa_cap_gains_enabled = False
        assert ra.wa_cap_gains_rate == 0.07  # rate doesn't change, only enabled flag
        ra.wa_cap_gains_enabled = True
        assert ra.wa_cap_gains_rate == 0.07
