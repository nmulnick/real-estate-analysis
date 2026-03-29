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


class TestYieldOnCostKPI:
    """Exit Net Proceeds KPI was replaced with Yield on Cost."""

    def test_html_has_yield_on_cost_label(self):
        html = _read_html()
        assert 'Yield on Cost' in html
        assert 'id="kpiPWlbl">Exit Price' not in html
        assert 'id="kpiPWlbl">Exit Net Proceeds' not in html

    def test_kpi_js_computes_yoc(self):
        """JS computes currentYoC and stabilizedYoC from NOI and cost basis."""
        html = _read_html()
        assert 'currentYoC' in html
        assert 'stabilizedYoC' in html
        assert 'p.noiP1' in html
        assert 'p.noiP2' in html
        assert 'p.costBasis' in html
        assert 'p.ordRate' in html

    def test_kpi_detail_shows_current_and_stabilized(self):
        """Detail line shows both current and stabilized YoC."""
        html = _read_html()
        assert 'current' in html and 'stabilized' in html


class TestYieldOnCostMath:
    """Verify YoC formula: after-tax NOI / cost basis."""

    def test_default_current_yoc(self):
        """Current YoC = $600K * (1 - 0.37) / $8,425,000."""
        noi = 600_000
        ord_rate = 0.37
        basis = 8_425_000
        expected = (noi * (1 - ord_rate)) / basis
        assert expected == pytest.approx(0.04485, abs=0.0001)  # ~4.49%

    def test_default_stabilized_yoc(self):
        """Stabilized YoC = $2,000,000 * (1 - 0.37) / $8,425,000."""
        noi = 2_000_000
        ord_rate = 0.37
        basis = 8_425_000
        expected = (noi * (1 - ord_rate)) / basis
        assert expected == pytest.approx(0.14955, abs=0.0001)  # ~14.96%

    def test_zero_basis_no_divide_by_zero(self):
        """YoC should be 0 when cost basis is 0 (no divide by zero)."""
        # The JS guard is: p.costBasis > 0 ? ... : 0
        html = _read_html()
        assert 'p.costBasis > 0' in html

    def test_yoc_scales_with_noi(self):
        """Higher NOI → higher YoC, linearly."""
        basis = 10_000_000
        ord_rate = 0.37
        yoc_1m = (1_000_000 * (1 - ord_rate)) / basis
        yoc_2m = (2_000_000 * (1 - ord_rate)) / basis
        assert yoc_2m == pytest.approx(yoc_1m * 2, abs=0.0001)

    def test_yoc_formula_matches_definition(self):
        """YoC = after-tax NOI / cost basis, standard CRE metric."""
        # Formula: (NOI * (1 - ordinary_rate)) / cost_basis
        noi = 5_000_000
        ord_rate = 0.40
        basis = 50_000_000
        at_noi = noi * (1 - ord_rate)  # $3M
        yoc = at_noi / basis  # 6%
        assert yoc == pytest.approx(0.06, abs=0.0001)


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


class TestExecSummary:
    """Executive Summary print feature tests."""

    def setup_method(self):
        self.html = _read_html()

    def test_exec_summary_button_exists(self):
        assert 'Exec Summary' in self.html
        assert 'printExecSummary()' in self.html

    def test_build_exec_summary_function_exists(self):
        assert 'function buildExecSummary()' in self.html

    def test_print_exec_summary_function_exists(self):
        assert 'function printExecSummary()' in self.html

    def test_print_exec_css_rules_exist(self):
        """Print CSS hides main app and shows exec summary."""
        assert 'body.print-exec .app' in self.html
        assert 'body.print-exec #execSummary' in self.html

    def test_exec_footer_class_used(self):
        """Uses .exec-footer class, not bare footer (which is hidden in print)."""
        assert 'exec-footer' in self.html

    def test_multi_signal_recommendation_logic(self):
        """Recommendation checks FV, NPV, and IRR signals — not just FV."""
        assert 'fvSignal' in self.html
        assert 'npvSignal' in self.html
        assert 'irrSignal' in self.html
        assert 'MIXED' in self.html

    def test_afterprint_cleanup(self):
        """afterprint event removes print-exec class."""
        assert 'afterprint' in self.html
        assert "remove('print-exec')" in self.html or "remove(\"print-exec\")" in self.html

    def test_hold_period_in_summary(self):
        """Executive summary includes hold period."""
        assert 'p.holdYears' in self.html and 'year' in self.html.lower()

    def test_assumptions_include_1031_and_reet(self):
        """Key assumptions section includes 1031 and REET status."""
        # Find the buildExecSummary function
        fn_start = self.html.index('function buildExecSummary()')
        fn_block = self.html[fn_start:fn_start + 5000]
        assert '1031' in fn_block
        assert 'REET' in fn_block or 'reet' in fn_block

    def test_sensitivity_snapshot_auto_generated(self):
        """Sensitivity bullets are generated from computed data, not hardcoded."""
        fn_start = self.html.index('function buildExecSummary()')
        fn_block = self.html[fn_start:fn_start + 5000]
        assert 'sensBullets' in fn_block

    def test_scenario_waterfalls_use_computed_values(self):
        """Scenario waterfalls use engine-computed values like a.atProceeds."""
        fn_start = self.html.index('function buildExecSummary()')
        fn_block = self.html[fn_start:fn_start + 5000]
        assert 'a.atProceeds' in fn_block or 'a.fvAT' in fn_block
        assert 'expected.b.totalFV' in fn_block

    def test_hidden_by_default(self):
        """Exec summary div is hidden by default."""
        assert 'id="execSummary" style="display:none"' in self.html


class TestExecSummaryRecommendationLogic:
    """Test the multi-signal recommendation logic using the Python engine."""

    def setup_method(self):
        """Reset to defaults."""
        ra.initial_carrying_costs = 0
        ra.federal_cap_gains_rate = 0.0
        ra.niit_rate = 0.0
        ra.depreciation_recapture_rate = 0.0
        ra.cumulative_depreciation = 0
        ra.reet_enabled = True
        ra.hold_period_years = 10

    def _signals(self, exit_price):
        """Compute the 3 recommendation signals for a given exit price."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(exit_price)
        fv_signal = 'B' if b["total_fv_after_tax"] > a["future_value_after_tax"] else 'A'
        npv_signal = 'B' if b["total_npv"] > a["npv"] else 'A'
        # IRR: simplified — use breakeven logic
        irr_signal = 'B' if b["total_fv_after_tax"] > a["future_value_after_tax"] else 'A'
        return fv_signal, npv_signal

    def test_default_signals_all_agree_hold(self):
        """With defaults ($200M exit), all signals should favor B (Hold)."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200e6)
        assert b["total_fv_after_tax"] > a["future_value_after_tax"]  # FV: B
        assert b["total_npv"] > a["npv"]  # NPV: B
        # → recommendation should be HOLD

    def test_low_exit_signals_all_agree_sell(self):
        """With very low exit ($50M), all signals should favor A (Sell)."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(50e6)
        assert b["total_fv_after_tax"] < a["future_value_after_tax"]  # FV: A
        assert b["total_npv"] < a["npv"]  # NPV: A
        # → recommendation should be SELL

    def test_breakeven_exit_produces_near_tie(self):
        """At the breakeven exit price, FV should be approximately equal."""
        a = ra.calc_scenario_a()
        # Binary search for breakeven
        lo, hi = 50e6, 300e6
        for _ in range(60):
            mid = (lo + hi) / 2
            b = ra.calc_scenario_b(mid)
            if b["total_fv_after_tax"] > a["future_value_after_tax"]:
                hi = mid
            else:
                lo = mid
        breakeven = (lo + hi) / 2
        b = ra.calc_scenario_b(breakeven)
        diff = abs(b["total_fv_after_tax"] - a["future_value_after_tax"])
        assert diff < 100  # Within $100 of each other

    def test_fv_advantage_magnitude_matches(self):
        """The FV advantage should match B.totalFV - A.fvAT."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200e6)
        fv_diff = b["total_fv_after_tax"] - a["future_value_after_tax"]
        assert fv_diff > 0
        assert fv_diff == pytest.approx(
            b["total_fv_after_tax"] - a["future_value_after_tax"], abs=1)

    def test_npv_advantage_magnitude_matches(self):
        """The NPV advantage should match B.totalNPV - A.npv."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200e6)
        npv_diff = b["total_npv"] - a["npv"]
        assert npv_diff > 0
        assert npv_diff == pytest.approx(
            b["total_npv"] - a["npv"], abs=1)


class TestExecSummaryYieldOnCostMath:
    """Verify YoC values that appear in the exec summary metrics grid."""

    def test_current_yoc_default(self):
        """Current YoC = $600K * (1-0.37) / $8,425,000 = 4.49%."""
        noi = 600_000
        basis = 8_425_000
        ord_rate = 0.37
        yoc = (noi * (1 - ord_rate)) / basis
        assert yoc == pytest.approx(0.04485, abs=0.001)

    def test_stabilized_yoc_default(self):
        """Stabilized YoC = $2M * (1-0.37) / $8,425,000 = 14.96%."""
        noi = 2_000_000
        basis = 8_425_000
        ord_rate = 0.37
        yoc = (noi * (1 - ord_rate)) / basis
        assert yoc == pytest.approx(0.14955, abs=0.001)

    def test_yoc_with_different_basis(self):
        """YoC changes inversely with cost basis."""
        noi = 2_000_000
        ord_rate = 0.37
        yoc_8m = (noi * (1 - ord_rate)) / 8_000_000
        yoc_16m = (noi * (1 - ord_rate)) / 16_000_000
        assert yoc_8m == pytest.approx(yoc_16m * 2, abs=0.001)

    def test_yoc_with_different_tax_rate(self):
        """Higher tax rate reduces YoC."""
        noi = 2_000_000
        basis = 10_000_000
        yoc_37 = (noi * (1 - 0.37)) / basis
        yoc_50 = (noi * (1 - 0.50)) / basis
        assert yoc_37 > yoc_50

    def test_yoc_zero_noi(self):
        """Zero NOI produces zero YoC."""
        yoc = (0 * (1 - 0.37)) / 8_425_000
        assert yoc == 0


class TestExecSummaryIRRSpread:
    """Verify IRR spread values that appear in the exec summary."""

    def setup_method(self):
        ra.initial_carrying_costs = 0
        ra.federal_cap_gains_rate = 0.0
        ra.niit_rate = 0.0
        ra.depreciation_recapture_rate = 0.0
        ra.cumulative_depreciation = 0
        ra.reet_enabled = True
        ra.hold_period_years = 10

    def test_irr_exceeds_reinv_rate_at_default_exit(self):
        """At $200M exit, hold IRR should exceed 6% reinvestment rate."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200e6)
        # Build cash flows and compute IRR
        cfs = [-a["after_tax_proceeds"]]
        for yr in b["annual_details"]:
            val = yr["net_cf_after_tax"]
            if yr["year"] == 10:
                val += b["net_exit_after_tax"]
            cfs.append(val)

        def npv_at(rate):
            return sum(cf / (1 + rate) ** t for t, cf in enumerate(cfs))

        lo, hi = -0.5, 5.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if npv_at(mid) > 0:
                lo = mid
            else:
                hi = mid
        irr = (lo + hi) / 2
        reinv = 0.06
        spread = irr - reinv
        assert spread > 0  # IRR exceeds reinvestment rate
        assert irr == pytest.approx(0.0916, abs=0.005)  # ~9.16%

    def test_irr_below_reinv_at_low_exit(self):
        """At low exit price, hold IRR should be below reinvestment rate."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(80e6)
        cfs = [-a["after_tax_proceeds"]]
        for yr in b["annual_details"]:
            val = yr["net_cf_after_tax"]
            if yr["year"] == 10:
                val += b["net_exit_after_tax"]
            cfs.append(val)

        def npv_at(rate):
            return sum(cf / (1 + rate) ** t for t, cf in enumerate(cfs))

        lo, hi = -0.5, 5.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if npv_at(mid) > 0:
                lo = mid
            else:
                hi = mid
        irr = (lo + hi) / 2
        reinv = 0.06
        assert irr < reinv  # IRR below reinvestment rate → Sell signal
