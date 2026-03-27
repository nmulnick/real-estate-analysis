"""Tests for Scenario B: Hold, Lease & Sell Later."""
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off


class TestScenarioBLease:
    """Stepped lease allocation and annual cash flows."""

    def test_lease_years_1_to_3(self):
        """Years 1-3 should use Phase 1 NOI ($600K)."""
        b = ra.calc_scenario_b(200_000_000)
        for yr_detail in b["annual_details"][:3]:
            assert yr_detail["lease"] == pytest.approx(600_000, abs=1)

    def test_lease_year_4_prorated(self):
        """Year 4 with p1_end=3.5 → 50% × $600K + 50% × $2M = $1.3M."""
        b = ra.calc_scenario_b(200_000_000)
        yr4 = b["annual_details"][3]
        assert yr4["lease"] == pytest.approx(1_300_000, abs=1)

    def test_lease_years_5_to_10(self):
        """Years 5-10 should use Phase 2 NOI ($2M)."""
        b = ra.calc_scenario_b(200_000_000)
        for yr_detail in b["annual_details"][4:]:
            assert yr_detail["lease"] == pytest.approx(2_000_000, abs=1)

    def test_integer_transition(self):
        """p1_end=3.0 → years 1-3 phase1, year 4+ phase2 (no proration)."""
        ra.phase1_end_year = 3.0
        b = ra.calc_scenario_b(200_000_000)
        assert b["annual_details"][2]["lease"] == pytest.approx(600_000, abs=1)  # yr 3
        assert b["annual_details"][3]["lease"] == pytest.approx(2_000_000, abs=1)  # yr 4


class TestScenarioBCarrying:
    """Carrying cost escalation."""

    def test_zero_carrying(self):
        """Default carrying = $0, all years should be $0."""
        b = ra.calc_scenario_b(200_000_000)
        for yr_detail in b["annual_details"]:
            assert yr_detail["carrying"] == pytest.approx(0, abs=1)

    def test_nonzero_carrying_escalation(self):
        """$1.5M carrying at 3% escalation."""
        b = ra.calc_scenario_b(200_000_000, init_carrying=1_500_000)
        for i, yr_detail in enumerate(b["annual_details"]):
            expected = 1_500_000 * (1.03 ** i)
            assert yr_detail["carrying"] == pytest.approx(expected, abs=1)


class TestScenarioBTax:
    """Income tax on net cash flows."""

    def test_positive_cf_taxed(self):
        """Positive net CF taxed at ordinary rate (37%)."""
        b = ra.calc_scenario_b(200_000_000)
        yr5 = b["annual_details"][4]  # Year 5: lease=$2M, carry=$0, net=$2M
        assert yr5["income_tax"] == pytest.approx(2_000_000 * 0.37, abs=1)
        assert yr5["net_cf_after_tax"] == pytest.approx(2_000_000 * 0.63, abs=1)

    def test_negative_cf_no_tax(self):
        """Negative net CF → no tax (no refund modeled)."""
        b = ra.calc_scenario_b(200_000_000, init_carrying=1_500_000)
        yr1 = b["annual_details"][0]  # Year 1: lease=$600K, carry=$1.5M → net=-$900K
        assert yr1["net_cf_pretax"] < 0
        assert yr1["income_tax"] == 0
        assert yr1["net_cf_after_tax"] == yr1["net_cf_pretax"]


class TestScenarioBCompounding:
    """Compounding of after-tax cash flows."""

    def test_compounding_formula(self):
        """Verify: balance = prior × (1 + rate) + current_CF."""
        b = ra.calc_scenario_b(200_000_000)
        details = b["annual_details"]
        # Year 1
        assert details[0]["compounded_cf"] == pytest.approx(details[0]["net_cf_after_tax"], abs=1)
        # Year 2+
        for i in range(1, len(details)):
            expected = details[i-1]["compounded_cf"] * 1.06 + details[i]["net_cf_after_tax"]
            assert details[i]["compounded_cf"] == pytest.approx(expected, abs=1)

    def test_final_compounded_cf_matches_output(self):
        """Last year's compounded CF should match the summary value."""
        b = ra.calc_scenario_b(200_000_000)
        assert b["compounded_cf"] == pytest.approx(b["annual_details"][-1]["compounded_cf"], abs=1)


class TestScenarioBExit:
    """Exit sale calculations."""

    def test_exit_1031(self):
        """1031: exit CG tax = $0."""
        b = ra.calc_scenario_b(200_000_000)
        assert b["exit_tx_costs"] == pytest.approx(200_000_000 * 0.04, abs=1)
        assert b["net_exit"] == pytest.approx(192_000_000, abs=1)
        assert b["exit_tax"] == pytest.approx(0, abs=1)
        assert b["net_exit_after_tax"] == pytest.approx(192_000_000, abs=1)

    def test_exit_with_tax(self):
        """Non-1031: CG tax on gain above basis."""
        set_1031_off()
        b = ra.calc_scenario_b(200_000_000)
        gain = 192_000_000 - 8_425_000  # $183,575,000
        expected_tax = gain * (0.20 + 0.038)
        assert b["exit_tax"] == pytest.approx(expected_tax, abs=1)

    def test_underwater_exit(self):
        """Exit below basis → no CG tax."""
        set_1031_off()
        b = ra.calc_scenario_b(5_000_000)
        # Net = 5M * 0.96 = 4.8M, gain = 4.8M - 8.425M = negative
        assert b["exit_tax"] == pytest.approx(0, abs=1)

    def test_total_fv(self):
        """Total FV = net exit after tax + compounded CFs."""
        b = ra.calc_scenario_b(200_000_000)
        assert b["total_fv_after_tax"] == pytest.approx(
            b["net_exit_after_tax"] + b["compounded_cf"], abs=1)


class TestScenarioBNPV:
    """NPV discounting."""

    def test_npv_sum(self):
        """NPV = sum of discounted CFs + discounted exit."""
        b = ra.calc_scenario_b(200_000_000)
        npv_cfs = sum(d["pv_cf"] for d in b["annual_details"])
        pv_exit = b["net_exit_after_tax"] / (1.07 ** 10)
        assert b["total_npv"] == pytest.approx(npv_cfs + pv_exit, abs=1)

    def test_pv_of_each_cf(self):
        """Each year's PV = after_tax_cf / (1 + disc)^yr."""
        b = ra.calc_scenario_b(200_000_000)
        for d in b["annual_details"]:
            expected_pv = d["net_cf_after_tax"] / (1.07 ** d["year"])
            assert d["pv_cf"] == pytest.approx(expected_pv, abs=1)
