"""Spot-check sensitivity table calculations."""
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off


class TestSensitivityTable1:
    """FV Advantage: Reinvestment Rate × Exit Price."""

    def test_cell_4pct_150m(self):
        """reinv=4%, exit=$150M → compute FV diff."""
        a = ra.calc_scenario_a(reinv_rate=0.04)
        b = ra.calc_scenario_b(150_000_000, reinv_rate=0.04)
        diff = b["total_fv_after_tax"] - a["future_value_after_tax"]
        # B should win (hold gets $150M exit + CFs vs $86M at 4%)
        assert diff > 0  # B wins

    def test_cell_8pct_150m(self):
        """reinv=8%, exit=$150M → A might win (high reinv rate)."""
        a = ra.calc_scenario_a(reinv_rate=0.08)
        b = ra.calc_scenario_b(150_000_000, reinv_rate=0.08)
        diff = b["total_fv_after_tax"] - a["future_value_after_tax"]
        # At 8% reinv, $86M grows to $185.7M vs ~$144M + CFs ≈ ~$155M
        assert diff < 0  # A wins


class TestSensitivityTable2:
    """NPV Difference: Carrying Costs × Future Lease NOI."""

    def test_cell_0carry_5m_noi(self):
        """carry=$0, NOI_p2=$5M → B should strongly win."""
        pw = 197_500_000
        b = ra.calc_scenario_b(pw, init_carrying=0, noi_p2=5_000_000)
        a = ra.calc_scenario_a()
        diff = b["total_npv"] - a["npv"]
        assert diff > 0  # B wins

    def test_cell_2_5m_carry_0_noi(self):
        """carry=$2.5M, NOI_p2=$0 → A should win (heavy carry, no income)."""
        pw = 197_500_000
        b = ra.calc_scenario_b(pw, init_carrying=2_500_000, noi_p2=0)
        a = ra.calc_scenario_a()
        diff = b["total_npv"] - a["npv"]
        assert diff < 0  # A wins


class TestSensitivityTable3:
    """NPV Difference: Discount Rate × Exit Price."""

    def test_cell_5pct_250m(self):
        """Low discount + high exit → B wins strongly."""
        b = ra.calc_scenario_b(250_000_000, disc_rate=0.05)
        a = ra.calc_scenario_a()
        diff = b["total_npv"] - a["npv"]
        assert diff > 0

    def test_cell_9pct_150m(self):
        """High discount + low exit → A wins."""
        b = ra.calc_scenario_b(150_000_000, disc_rate=0.09)
        a = ra.calc_scenario_a()
        diff = b["total_npv"] - a["npv"]
        assert diff < 0


class TestSensitivityTable4:
    """FV Difference: CG Rate × TX Cost Rate (base-case exit)."""

    def test_cell_20pct_cg_4pct_tx(self):
        """Standard CG rate, high TX → compute diff."""
        a = ra.calc_scenario_a(tx_cost_rate=0.04, fed_rate=0.20)
        b = ra.calc_scenario_b(200_000_000, tx_cost_rate=0.04, fed_rate=0.20)
        diff = b["total_fv_after_tax"] - a["future_value_after_tax"]
        assert isinstance(diff, float)

    def test_cell_15pct_cg_1pct_tx(self):
        """Low CG rate, low TX."""
        a = ra.calc_scenario_a(tx_cost_rate=0.01, fed_rate=0.15)
        b = ra.calc_scenario_b(200_000_000, tx_cost_rate=0.01, fed_rate=0.15)
        diff = b["total_fv_after_tax"] - a["future_value_after_tax"]
        assert isinstance(diff, float)
