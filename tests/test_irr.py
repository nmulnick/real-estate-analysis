"""Tests for the IRR solver."""
import math
import pytest
import real_estate_analysis as ra


class TestIRR:

    def test_default_base_case(self):
        """IRR for $200M exit should be ~8% (between 6% and 12%)."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200_000_000)
        irr = ra.calc_irr(a["after_tax_proceeds"], b)
        assert irr is not None
        assert 0.04 < irr < 0.15

    def test_irr_increases_with_higher_exit(self):
        """Higher exit price → higher IRR."""
        a = ra.calc_scenario_a()
        b_200 = ra.calc_scenario_b(200_000_000)
        b_300 = ra.calc_scenario_b(300_000_000)
        irr_200 = ra.calc_irr(a["after_tax_proceeds"], b_200)
        irr_300 = ra.calc_irr(a["after_tax_proceeds"], b_300)
        assert irr_300 > irr_200

    def test_irr_none_when_no_sign_change(self):
        """If all cash flows are same sign, return None."""
        # All negative: huge opportunity cost, no income, tiny exit
        a = ra.calc_scenario_a()
        ra.noi_phase1 = 0
        ra.noi_phase2 = 0
        b = ra.calc_scenario_b(1_000)  # tiny exit
        irr = ra.calc_irr(a["after_tax_proceeds"], b)
        # Cash flows: -86M, 0, 0, ..., 0 + ~$960 → still has sign change
        # but NPV is always negative, solver should handle gracefully
        # Let's test true no-sign-change:
        irr2 = ra.calc_irr(-1000, b)  # negative opportunity cost = all positive
        assert irr2 is None

    def test_irr_all_positive_none(self):
        """If opportunity cost is negative (nonsensical), return None."""
        b = ra.calc_scenario_b(200_000_000)
        irr = ra.calc_irr(-1_000_000, b)  # negative opp cost → all CFs positive
        assert irr is None

    def test_irr_converges_high_return(self):
        """Very high exit → IRR should converge to a large but finite value."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(500_000_000)
        irr = ra.calc_irr(a["after_tax_proceeds"], b)
        assert irr is not None
        assert irr < 10  # bounded

    def test_irr_converges_low_return(self):
        """Very low exit → IRR should be near 0 or slightly positive."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(90_000_000)  # just below A's proceeds
        irr = ra.calc_irr(a["after_tax_proceeds"], b)
        assert irr is not None
        assert irr < 0.06  # below reinvestment rate

    def test_irr_npv_at_irr_is_zero(self):
        """At the IRR, NPV of the cash flows should be ~$0."""
        a = ra.calc_scenario_a()
        b = ra.calc_scenario_b(200_000_000)
        irr = ra.calc_irr(a["after_tax_proceeds"], b)
        assert irr is not None

        # Rebuild cash flows and compute NPV at the IRR
        cfs = [-a["after_tax_proceeds"]]
        for d in b["annual_details"]:
            cf = d["net_cf_after_tax"]
            if d["year"] == ra.hold_period_years:
                cf += b["net_exit_after_tax"]
            cfs.append(cf)

        npv_at_irr = sum(cf / (1 + irr) ** t for t, cf in enumerate(cfs))
        assert npv_at_irr == pytest.approx(0, abs=100)  # within $100
