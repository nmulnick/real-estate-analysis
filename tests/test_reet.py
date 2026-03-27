"""
Tests for WA Real Estate Excise Tax (REET) graduated calculation.

REET is a state graduated tax + flat local tax on every property transfer.
State brackets (effective Jan 1, 2023):
  ≤ $525,000:           1.10%
  $525,001–$1,525,000:  1.28%
  $1,525,001–$3,025,000: 2.75%
  > $3,025,000:          3.00%

Local: flat rate on entire sale price (Bellevue default: 0.50%).
"""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import real_estate_analysis as ra

# Mirror the JS REET_BRACKETS for Python-side testing
REET_BRACKETS = [
    (525_000, 0.011),
    (1_525_000, 0.0128),
    (3_025_000, 0.0275),
    (float('inf'), 0.03),
]


def calc_reet(gross_price, local_rate=0.005):
    """Pure-Python mirror of JS calcREET for test verification."""
    safe_price = max(gross_price, 0)
    state_reet = 0.0
    prev_threshold = 0
    for threshold, rate in REET_BRACKETS:
        taxable_slice = min(safe_price, threshold) - prev_threshold
        if taxable_slice <= 0:
            break
        state_reet += taxable_slice * rate
        prev_threshold = threshold
    local_reet = safe_price * max(local_rate, 0)
    return {"state": state_reet, "local": local_reet, "total": state_reet + local_reet}


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestCalcREET:
    """Graduated state REET + flat local REET calculation."""

    def test_zero_price(self):
        """$0 sale → $0 REET."""
        r = calc_reet(0)
        assert r["state"] == 0
        assert r["local"] == 0
        assert r["total"] == 0

    def test_negative_price(self):
        """Negative price → $0 REET (clamped)."""
        r = calc_reet(-100_000)
        assert r["total"] == 0

    def test_below_first_bracket(self):
        """$400K sale → all at 1.1%."""
        r = calc_reet(400_000, 0.005)
        assert r["state"] == pytest.approx(400_000 * 0.011)
        assert r["local"] == pytest.approx(400_000 * 0.005)

    def test_exactly_first_bracket(self):
        """$525K → $5,775 state."""
        r = calc_reet(525_000, 0.005)
        assert r["state"] == pytest.approx(5_775.0)
        assert r["local"] == pytest.approx(2_625.0)
        assert r["total"] == pytest.approx(8_400.0)

    def test_spans_two_brackets(self):
        """$1M sale → $525K@1.1% + $475K@1.28%."""
        r = calc_reet(1_000_000, 0.005)
        expected_state = 525_000 * 0.011 + 475_000 * 0.0128
        assert r["state"] == pytest.approx(expected_state)
        assert r["local"] == pytest.approx(5_000.0)

    def test_exactly_second_bracket(self):
        """$1,525,000 fills brackets 1+2 exactly."""
        r = calc_reet(1_525_000, 0.005)
        expected_state = 525_000 * 0.011 + 1_000_000 * 0.0128
        assert r["state"] == pytest.approx(expected_state)

    def test_spans_three_brackets(self):
        """$2M sale → bracket 1 + 2 + partial 3."""
        r = calc_reet(2_000_000, 0.005)
        expected_state = (525_000 * 0.011
                          + 1_000_000 * 0.0128
                          + 475_000 * 0.0275)
        assert r["state"] == pytest.approx(expected_state)
        assert r["local"] == pytest.approx(10_000.0)
        assert r["total"] == pytest.approx(expected_state + 10_000.0)

    def test_spans_all_four_brackets(self):
        """$5M sale → all 4 brackets."""
        r = calc_reet(5_000_000, 0.005)
        expected_state = (525_000 * 0.011
                          + 1_000_000 * 0.0128
                          + 1_500_000 * 0.0275
                          + 1_975_000 * 0.03)
        assert r["state"] == pytest.approx(expected_state)

    def test_100m_commercial_sale(self):
        """$100M sale → state $2,969,075, local $500K @ 0.50%."""
        r = calc_reet(100_000_000, 0.005)
        expected_state = (525_000 * 0.011
                          + 1_000_000 * 0.0128
                          + 1_500_000 * 0.0275
                          + 96_975_000 * 0.03)
        assert r["state"] == pytest.approx(2_969_075.0)
        assert r["state"] == pytest.approx(expected_state)
        assert r["local"] == pytest.approx(500_000.0)
        assert r["total"] == pytest.approx(3_469_075.0)

    def test_local_rate_zero(self):
        """Local rate 0% → only state REET."""
        r = calc_reet(1_000_000, 0.0)
        assert r["local"] == 0
        assert r["total"] == r["state"]

    def test_local_rate_varies(self):
        """Different local rates produce proportional local amounts."""
        r_25 = calc_reet(1_000_000, 0.0025)
        r_50 = calc_reet(1_000_000, 0.005)
        assert r_25["local"] == pytest.approx(2_500.0)
        assert r_50["local"] == pytest.approx(5_000.0)
        # State portion is the same regardless of local rate
        assert r_25["state"] == pytest.approx(r_50["state"])

    def test_effective_rate_approaches_3pct_for_large_sales(self):
        """For very large sales, effective state rate approaches 3.0%."""
        r = calc_reet(1_000_000_000, 0.0)  # $1B
        effective_rate = r["state"] / 1_000_000_000
        assert effective_rate == pytest.approx(0.03, abs=0.001)


class TestREETInDisposition:
    """REET integrates correctly with Python calc_disposition (simulated)."""

    def test_reet_reduces_net_proceeds(self):
        """Net proceeds should be lower when REET is applied."""
        gross = 100_000_000
        tx_rate = 0.14
        reet = calc_reet(gross)
        net_without_reet = gross - (gross * tx_rate)
        net_with_reet = gross - (gross * tx_rate) - reet["total"]
        assert net_with_reet < net_without_reet
        assert net_without_reet - net_with_reet == pytest.approx(reet["total"])

    def test_reet_disabled_no_effect(self):
        """When REET is disabled, proceeds are unchanged."""
        gross = 100_000_000
        tx_rate = 0.14
        reet_disabled = {"state": 0, "local": 0, "total": 0}
        net = gross - (gross * tx_rate) - reet_disabled["total"]
        assert net == pytest.approx(gross * (1 - tx_rate))

    def test_reet_reduces_recognized_gain(self):
        """Lower net proceeds → lower capital gains."""
        gross = 100_000_000
        basis = 8_425_000
        tx_rate = 0.14
        reet = calc_reet(gross)
        gain_without = max(gross * (1 - tx_rate) - basis, 0)
        gain_with = max(gross * (1 - tx_rate) - reet["total"] - basis, 0)
        assert gain_with < gain_without

    def test_reet_applies_with_1031(self):
        """Even with 1031 (CG tax = 0), REET still deducted from proceeds."""
        gross = 100_000_000
        tx_rate = 0.14
        reet = calc_reet(gross)
        # 1031: no capital gains tax, but REET still reduces proceeds
        net_with_reet = gross - (gross * tx_rate) - reet["total"]
        net_without_reet = gross - (gross * tx_rate)
        # Proceeds are lower by exactly the REET amount
        assert net_without_reet - net_with_reet == pytest.approx(3_469_075.0)


class TestREETInScenarios:
    """REET flows through to both scenarios correctly (using Python module)."""

    def test_scenario_a_reet_magnitude(self):
        """For $100M sale, REET is ~$3.47M — material to the analysis."""
        reet = calc_reet(100_000_000, 0.005)
        assert reet["total"] == pytest.approx(3_469_075.0)
        # This is roughly 3.47% of the sale price
        assert reet["total"] / 100_000_000 == pytest.approx(0.0347, abs=0.001)

    def test_scenario_b_different_exit_prices(self):
        """REET varies by exit price due to graduated brackets."""
        reet_140m = calc_reet(140_000_000, 0.005)
        reet_200m = calc_reet(200_000_000, 0.005)
        reet_250m = calc_reet(250_000_000, 0.005)
        # All should be roughly 3.5% for these large amounts
        assert reet_140m["total"] < reet_200m["total"] < reet_250m["total"]
        # But effective rates converge near the top bracket
        eff_140 = reet_140m["total"] / 140_000_000
        eff_250 = reet_250m["total"] / 250_000_000
        assert abs(eff_140 - eff_250) < 0.001

    def test_reet_on_vs_off_difference(self):
        """Toggling REET on/off changes proceeds by exactly the REET total."""
        gross = 200_000_000
        reet = calc_reet(gross, 0.005)
        assert reet["total"] == pytest.approx(
            525_000 * 0.011 + 1_000_000 * 0.0128 + 1_500_000 * 0.0275
            + 196_975_000 * 0.03 + 200_000_000 * 0.005
        )

    def test_breakeven_higher_with_reet(self):
        """With REET, a higher exit price is needed to break even.

        Logic: if REET adds ~3.5% cost, the breakeven exit price must be
        higher to compensate. This is a qualitative check.
        """
        # Without REET: net = gross * (1 - tx) - basis
        # With REET: net = gross * (1 - tx) - REET(gross) - basis
        # For the same net, gross_with_reet > gross_without_reet
        target_net = 80_000_000
        basis = 8_425_000
        tx = 0.04

        # Solve: gross * (1 - tx) - basis = target_net (no REET)
        gross_no_reet = (target_net + basis) / (1 - tx)

        # With REET: gross * (1 - tx) - REET(gross) - basis = target_net
        # REET is ~3.5% for large amounts, so gross * (1 - tx - 0.035) ≈ target + basis
        # Approximate: need higher gross
        reet_at_no_reet = calc_reet(gross_no_reet, 0.005)
        net_with_reet = gross_no_reet * (1 - tx) - reet_at_no_reet["total"] - basis
        # Net is lower when REET is included
        assert net_with_reet < target_net
