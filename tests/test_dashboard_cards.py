"""
Tests for dashboard card improvements:
- After-Tax Exit Proceeds KPI (replaced Exit Price)
- Breakeven vs Hold Period chart (replaced NPV chart)
- Expanded Key Assumptions card
- IRR chart null handling
- Python REET function accuracy
"""

import os
import re
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off

DASHBOARD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "real_estate_dashboard.html"
)


def _read_html():
    with open(DASHBOARD_PATH, "r") as f:
        return f.read()


class TestAfterTaxExitProceedsKPI:
    """The Exit Price KPI was replaced with After-Tax Exit Proceeds."""

    def test_html_has_after_tax_label(self):
        html = _read_html()
        assert 'After-Tax Exit Proceeds' in html
        # Old label should NOT be present as a KPI label
        assert 'id="kpiPWlbl">Exit Price' not in html

    def test_kpi_shows_net_exit_at(self):
        """JS populates the KPI with expected.b.netExitAT, not exit price."""
        html = _read_html()
        assert 'expected.b.netExitAT' in html

    def test_kpi_shows_gross_to_net(self):
        """Detail line shows gross → net conversion."""
        html = _read_html()
        assert "Gross '" in html or "'Gross '" in html or "Gross ' +" in html or 'fmtM(expectedExitPrice)' in html


class TestBreakevenHoldPeriodChart:
    """The NPV bar chart was replaced with a Breakeven vs Hold Period line chart."""

    def test_html_has_breakeven_chart_title(self):
        html = _read_html()
        assert 'Breakeven vs Hold Period' in html
        assert 'Net Present Value Comparison' not in html

    def test_chart_is_line_type(self):
        """Chart should be type: 'line', not 'bar'."""
        html = _read_html()
        # Find the chartNPV init block
        npv_init = html[html.index("chartNPV = new Chart"):]
        npv_init = npv_init[:npv_init.index("chartIRR")]
        assert "type: 'line'" in npv_init

    def test_chart_datasets_have_breakeven_and_offer(self):
        html = _read_html()
        assert "'Breakeven Price'" in html
        assert "'Current Offer'" in html

    def test_chart_loops_hold_periods_1_to_15(self):
        """The recalculate function should sweep hold periods 1–15."""
        html = _read_html()
        assert 'yr <= 15' in html or 'yr < 16' in html

    def test_breakeven_varies_with_hold_period(self):
        """Breakeven price should differ for different hold periods."""
        ra.initial_carrying_costs = 0
        # Simulate different hold periods
        ra.hold_period_years = 5
        b5 = ra.calc_scenario_b(200e6)
        ra.hold_period_years = 10
        b10 = ra.calc_scenario_b(200e6)
        # Breakeven should differ because FV target differs
        assert b5["total_fv_after_tax"] != b10["total_fv_after_tax"]
        # Reset
        ra.hold_period_years = 10


class TestExpandedKeyAssumptions:
    """Key Assumptions card now includes gross sale, cost basis, 1031, REET, TX rates."""

    def test_has_gross_sale_price(self):
        html = _read_html()
        assert "Current Gross Sale Price" in html

    def test_has_cost_basis(self):
        html = _read_html()
        assert "Cost Basis" in html

    def test_has_1031_exchange(self):
        html = _read_html()
        assert "1031 Exchange" in html

    def test_has_reet(self):
        html = _read_html()
        assert "WA REET" in html

    def test_has_tx_cost_rates(self):
        html = _read_html()
        assert "TX Cost" in html and "Sell Now" in html
        assert "TX Cost" in html and "Future" in html


class TestIRRChartNullHandling:
    """IRR chart should show 'No IRR' label and null data instead of 0."""

    def test_null_irr_shows_no_irr_label(self):
        html = _read_html()
        assert 'No IRR' in html

    def test_null_irr_data_is_null_not_zero(self):
        """When IRR is null, chart data should be null, not 0."""
        html = _read_html()
        # Find the IRR chart data assignment
        irr_data_line = [l for l in html.split('\n') if 'chartIRR.data.datasets[0].data' in l][0]
        # Should return null for no-IRR cases, not 0
        assert ': null' in irr_data_line or ':null' in irr_data_line


class TestPythonREETAccuracy:
    """Verify Python calc_reet matches known WA REET brackets."""

    def test_reet_on_100m(self):
        r = ra.calc_reet(100e6)
        # Bracket 1: 525K * 1.1% = 5,775
        # Bracket 2: 1M * 1.28% = 12,800
        # Bracket 3: 1.5M * 2.75% = 41,250
        # Bracket 4: 96.975M * 3% = 2,909,250
        expected_state = 5_775 + 12_800 + 41_250 + 2_909_250
        assert r["state_reet"] == pytest.approx(expected_state, abs=1)
        assert r["local_reet"] == pytest.approx(500_000, abs=1)
        assert r["total_reet"] == pytest.approx(expected_state + 500_000, abs=1)

    def test_reet_on_200m(self):
        r = ra.calc_reet(200e6)
        expected_state = 5_775 + 12_800 + 41_250 + (200e6 - 3_025_000) * 0.03
        assert r["state_reet"] == pytest.approx(expected_state, abs=1)
        assert r["local_reet"] == pytest.approx(1_000_000, abs=1)

    def test_reet_below_first_bracket(self):
        r = ra.calc_reet(400_000)
        assert r["state_reet"] == pytest.approx(400_000 * 0.011, abs=1)

    def test_reet_zero(self):
        r = ra.calc_reet(0)
        assert r["total_reet"] == 0

    def test_reet_negative(self):
        r = ra.calc_reet(-100)
        assert r["total_reet"] == 0
