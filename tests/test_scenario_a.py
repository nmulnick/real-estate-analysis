"""Tests for Scenario A: Sell Now & Reinvest."""
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off


class TestScenarioA:

    def test_default_1031_on(self):
        """Default inputs with 1031: no CG tax, full compounding."""
        a = ra.calc_scenario_a()
        assert a["gross_sale"] == 100_000_000
        assert a["tx_costs"] == pytest.approx(14_000_000, abs=1)
        assert a["net_sale_proceeds"] == pytest.approx(86_000_000, abs=1)
        assert a["sale_tax"] == pytest.approx(0, abs=1)
        assert a["after_tax_proceeds"] == pytest.approx(86_000_000, abs=1)
        # 86M * 1.06^10
        expected_fv = 86_000_000 * (1.06 ** 10)
        assert a["future_value_gross"] == pytest.approx(expected_fv, abs=1)
        assert a["inv_tax"] == pytest.approx(0, abs=1)  # 1031 on
        assert a["future_value_after_tax"] == pytest.approx(expected_fv, abs=1)
        assert a["npv"] == pytest.approx(86_000_000, abs=1)

    def test_1031_off(self):
        """With normal tax rates, both sale and investment gains are taxed."""
        set_1031_off()
        a = ra.calc_scenario_a()
        net = 86_000_000
        gain = net - 8_425_000  # $77,575,000
        sale_tax = gain * (0.20 + 0.038)
        after_tax = net - sale_tax
        fv_gross = after_tax * (1.06 ** 10)
        inv_gain = fv_gross - after_tax
        inv_tax = inv_gain * (0.20 + 0.038)
        fv_at = fv_gross - inv_tax

        assert a["sale_tax"] == pytest.approx(sale_tax, abs=1)
        assert a["after_tax_proceeds"] == pytest.approx(after_tax, abs=1)
        assert a["future_value_after_tax"] == pytest.approx(fv_at, abs=1)

    def test_reinvestment_rate_4pct(self):
        a = ra.calc_scenario_a(reinv_rate=0.04)
        expected_fv = 86_000_000 * (1.04 ** 10)
        assert a["future_value_after_tax"] == pytest.approx(expected_fv, abs=1)

    def test_reinvestment_rate_8pct(self):
        a = ra.calc_scenario_a(reinv_rate=0.08)
        expected_fv = 86_000_000 * (1.08 ** 10)
        assert a["future_value_after_tax"] == pytest.approx(expected_fv, abs=1)

    def test_tx_cost_rate_1pct(self):
        a = ra.calc_scenario_a(tx_cost_rate=0.01)
        assert a["tx_costs"] == pytest.approx(1_000_000, abs=1)
        assert a["net_sale_proceeds"] == pytest.approx(99_000_000, abs=1)

    def test_npv_equals_after_tax_proceeds(self):
        """NPV is always = after-tax proceeds (received today)."""
        a = ra.calc_scenario_a()
        assert a["npv"] == a["after_tax_proceeds"]

    def test_zero_gain_no_tax(self):
        """If basis equals net proceeds, no CG tax."""
        set_1031_off()
        ra.cost_basis = 86_000_000  # equals net proceeds
        a = ra.calc_scenario_a()
        assert a["sale_tax"] == pytest.approx(0, abs=1)
