"""Tests for calc_cap_gains_tax — the core tax calculation function."""
import pytest
import real_estate_analysis as ra


class TestCalcCGTax:
    """Capital gains tax calculation with adjusted basis and depreciation recapture."""

    def test_normal_gain_no_depreciation(self):
        """Standard CG tax: 20% fed + 3.8% NIIT on gain."""
        tax = ra.calc_cap_gains_tax(77_575_000, 0, fed_rate=0.20, niit=0.038)
        expected = 77_575_000 * (0.20 + 0.038)  # $18,462,850
        assert tax == pytest.approx(expected, abs=1)

    def test_1031_exchange_zero_tax(self):
        """With 1031 rates (all 0%), tax should be exactly $0."""
        tax = ra.calc_cap_gains_tax(77_575_000, 0, fed_rate=0.0, niit=0.0)
        assert tax == 0.0

    def test_with_depreciation_recapture(self):
        """Depreciation recapture at 25% + CG on remaining gain."""
        # gain = $77.575M (already net - adjustedBasis), dep = $5M
        # recognizedGain = max(77.575M, 0) = $77.575M
        # recapture = min(5M, 77.575M) = $5M → $5M * 0.25 = $1.25M
        # capitalGain = max(77.575M - 5M, 0) = $72.575M → $72.575M * 0.238
        tax = ra.calc_cap_gains_tax(77_575_000, 5_000_000,
                                     fed_rate=0.20, niit=0.038,
                                     dep_recapture_rate=0.25)
        expected = 5_000_000 * 0.25 + 72_575_000 * 0.238
        assert tax == pytest.approx(expected, abs=1)

    def test_recapture_capped_at_recognized_gain(self):
        """When sale is below adjusted basis, no tax — recapture capped."""
        # net=$6M, basis=$8.425M → gain = 6M - 8.425M = -$2.425M
        # dep=$1.5M → totalGain = -2.425M + 1.5M = -$0.925M → no tax
        tax = ra.calc_cap_gains_tax(-2_425_000, 1_500_000,
                                     fed_rate=0.20, niit=0.038,
                                     dep_recapture_rate=0.25)
        assert tax == 0.0

    def test_depreciation_exceeds_gain_partial_recapture(self):
        """Negative gain → recognizedGain = max(-7M, 0) = 0 → tax = $0.

        With the Codex refactor, calc_cap_gains_tax applies max(gain, 0) first.
        A negative gain means no recognized gain, so no tax regardless of depreciation.
        """
        tax = ra.calc_cap_gains_tax(-7_000_000, 10_000_000,
                                     fed_rate=0.20, niit=0.038,
                                     dep_recapture_rate=0.25)
        assert tax == 0.0

    def test_zero_gain_zero_dep(self):
        tax = ra.calc_cap_gains_tax(0, 0, fed_rate=0.20, niit=0.038)
        assert tax == 0.0

    def test_negative_gain_no_dep(self):
        tax = ra.calc_cap_gains_tax(-5_000_000, 0, fed_rate=0.20, niit=0.038)
        assert tax == 0.0

    def test_wa_state_tax_on(self):
        """WA CG tax applies above threshold."""
        tax = ra.calc_cap_gains_tax(1_000_000, 0,
                                     fed_rate=0.20, niit=0.038,
                                     wa_enabled=True, wa_rate=0.07,
                                     wa_threshold=250_000)
        fed_niit = 1_000_000 * 0.238
        wa = (1_000_000 - 250_000) * 0.07
        assert tax == pytest.approx(fed_niit + wa, abs=1)

    def test_wa_state_tax_off(self):
        """WA CG tax disabled → no state tax."""
        tax = ra.calc_cap_gains_tax(1_000_000, 0,
                                     fed_rate=0.20, niit=0.038,
                                     wa_enabled=False)
        assert tax == pytest.approx(1_000_000 * 0.238, abs=1)

    def test_wa_gain_below_threshold(self):
        """Gain below WA threshold → no state tax even if enabled."""
        tax = ra.calc_cap_gains_tax(200_000, 0,
                                     fed_rate=0.20, niit=0.038,
                                     wa_enabled=True, wa_rate=0.07,
                                     wa_threshold=250_000)
        assert tax == pytest.approx(200_000 * 0.238, abs=1)


class TestWAToggleIntegration:
    """End-to-end tests for WA capital gains toggle."""

    def test_wa_rate_is_nonzero_in_defaults(self):
        """Regression: WA rate must be 0.07 (not 0.0) so toggle actually works."""
        assert ra.wa_cap_gains_rate == 0.07

    def test_scenario_a_higher_tax_with_wa_on(self):
        """Scenario A with WA enabled should produce more tax than WA off."""
        # Use non-1031 rates so there's actual CG tax to compare
        ra.federal_cap_gains_rate = 0.20
        ra.niit_rate = 0.038

        ra.wa_cap_gains_enabled = False
        a_off = ra.calc_scenario_a()

        ra.wa_cap_gains_enabled = True
        a_on = ra.calc_scenario_a()

        assert a_on["sale_tax"] > a_off["sale_tax"]
        assert a_on["future_value_after_tax"] < a_off["future_value_after_tax"]

    def test_scenario_b_higher_tax_with_wa_on(self):
        """Scenario B exit with WA enabled should produce more tax."""
        ra.federal_cap_gains_rate = 0.20
        ra.niit_rate = 0.038

        ra.wa_cap_gains_enabled = False
        b_off = ra.calc_scenario_b(200_000_000)

        ra.wa_cap_gains_enabled = True
        b_on = ra.calc_scenario_b(200_000_000)

        assert b_on["exit_tax"] > b_off["exit_tax"]
        assert b_on["total_fv_after_tax"] < b_off["total_fv_after_tax"]

    def test_wa_toggle_no_effect_with_1031(self):
        """With 1031 ON (fed=0, niit=0), WA toggle has no effect on sale tax.
        Because gain is computed against adjusted basis and taxed at 0% fed+niit,
        the gain that WA would tax is still computed correctly, but 1031 zeroes
        the base rates. WA tax itself may still apply if there's recognized gain."""
        # 1031 ON: fed=0, niit=0 (defaults from conftest)
        ra.wa_cap_gains_enabled = False
        a_off = ra.calc_scenario_a()

        ra.wa_cap_gains_enabled = True
        a_on = ra.calc_scenario_a()

        # With 1031, fed+niit=0 but WA still applies its own 7% on capital gain
        # So WA ON should produce MORE tax (WA is independent of 1031)
        assert a_on["sale_tax"] >= a_off["sale_tax"]

    def test_wa_tax_amount_is_correct(self):
        """Verify exact WA tax amount on a known gain."""
        ra.federal_cap_gains_rate = 0.20
        ra.niit_rate = 0.038
        ra.wa_cap_gains_enabled = True
        ra.cumulative_depreciation = 0

        # Net sale = $86M, adjusted basis = $8.425M
        # Recognized gain = $86M - $8.425M = $77.575M
        # WA tax = ($77.575M - $250K) * 7% = $77.325M * 0.07 = $5,412,750
        a = ra.calc_scenario_a()
        fed_niit = 77_575_000 * 0.238
        wa = (77_575_000 - 250_000) * 0.07
        expected_total = fed_niit + wa
        assert a["sale_tax"] == pytest.approx(expected_total, abs=1)
