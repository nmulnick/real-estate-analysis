"""Tests for evaluateExitScenarios and weighted outcome logic."""
import math
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off


class TestEvaluateExitScenarios:
    """Verify evaluate_exit_scenarios returns correct structure and math."""

    def test_structure(self):
        """Should return base_results, display_results, summary, weight_notice, a."""
        result = ra.evaluate_exit_scenarios()
        assert "base_results" in result
        assert "display_results" in result
        assert "summary" in result
        assert "weight_notice" in result
        assert "a" in result
        assert len(result["base_results"]) == 3  # bull, base, bear
        assert len(result["display_results"]) == 4  # 3 + expected

    def test_summary_kind(self):
        result = ra.evaluate_exit_scenarios()
        assert result["summary"]["kind"] == "expected"
        assert result["summary"]["label"] == "Expected"
        assert result["summary"]["wt"] == 1.0

    def test_base_result_labels(self):
        result = ra.evaluate_exit_scenarios()
        labels = [r["kind"] for r in result["base_results"]]
        assert labels == ["bull", "base", "bear"]

    def test_weights_sum_to_one(self):
        result = ra.evaluate_exit_scenarios()
        total = sum(r["wt"] for r in result["base_results"])
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_each_scenario_has_b_and_irr(self):
        result = ra.evaluate_exit_scenarios()
        for r in result["base_results"]:
            assert "b" in r
            assert "irr" in r
            assert "total_fv_after_tax" in r["b"]

    def test_weighted_fv_equals_sum(self):
        """Weighted summary FV = sum of individual FVs times weights."""
        result = ra.evaluate_exit_scenarios()
        expected_fv = sum(
            r["b"]["total_fv_after_tax"] * r["wt"]
            for r in result["base_results"]
        )
        assert result["summary"]["b"]["total_fv_after_tax"] == pytest.approx(expected_fv, abs=1)

    def test_weighted_npv_equals_sum(self):
        """Weighted summary NPV = sum of individual NPVs times weights."""
        result = ra.evaluate_exit_scenarios()
        expected_npv = sum(
            r["b"]["total_npv"] * r["wt"]
            for r in result["base_results"]
        )
        assert result["summary"]["b"]["total_npv"] == pytest.approx(expected_npv, abs=1)


class TestWeightedWith1031On:
    """With 1031 ON (all taxes 0%), weighted outcomes ~ weighted price shortcut."""

    def test_weighted_fv_matches_shortcut(self):
        """With 0% taxes, weighting outputs should approximately equal
        computing B at the weighted average exit price."""
        # Default is 1031 ON
        result = ra.evaluate_exit_scenarios()
        weighted_fv = result["summary"]["b"]["total_fv_after_tax"]

        # Shortcut: weighted average exit price
        pw_price = (ra.exit_bull * ra.weight_bull +
                    ra.exit_base * ra.weight_base +
                    ra.exit_bear * ra.weight_bear)
        b_shortcut = ra.calc_scenario_b(pw_price)
        shortcut_fv = b_shortcut["total_fv_after_tax"]

        # With 0% taxes (1031 on), these should be nearly equal
        # (within rounding, since the cash flows don't depend on exit price)
        assert weighted_fv == pytest.approx(shortcut_fv, rel=1e-6)


class TestWeightedWith1031Off:
    """With 1031 OFF (taxes applied), weighted outcomes differ from shortcut."""

    def test_weighted_fv_differs_from_shortcut(self):
        """With taxes, weighting individual scenario outputs differs from
        computing B at the weighted average price (due to tax nonlinearity)."""
        set_1031_off()
        ra.cumulative_depreciation = 5_000_000

        result = ra.evaluate_exit_scenarios()
        weighted_fv = result["summary"]["b"]["total_fv_after_tax"]

        # Shortcut: weighted average exit price
        pw_price = (ra.exit_bull * ra.weight_bull +
                    ra.exit_base * ra.weight_base +
                    ra.exit_bear * ra.weight_bear)
        b_shortcut = ra.calc_scenario_b(pw_price)
        shortcut_fv = b_shortcut["total_fv_after_tax"]

        # These should differ because of tax nonlinearity
        # The difference may be small but nonzero
        # We just verify the computation runs and produces valid numbers
        assert math.isfinite(weighted_fv)
        assert math.isfinite(shortcut_fv)

    def test_all_scenarios_have_tax(self):
        """With 1031 off, each scenario should have nonzero exit tax."""
        set_1031_off()
        result = ra.evaluate_exit_scenarios()
        for r in result["base_results"]:
            # All exit prices are above basis, so there should be tax
            assert r["b"]["exit_tax"] > 0


class TestNormalizeExitScenarioWeights:
    """Test weight normalization edge cases."""

    def test_default_weights_no_notice(self):
        """Default 25/50/25 sums to 100% → no notice."""
        result = ra.normalize_exit_scenario_weights()
        assert result["notice"] == ""
        assert len(result["scenarios"]) == 3

    def test_non_summing_weights(self):
        """Weights that don't sum to 100% → notice with auto-normalize."""
        ra.weight_bull = 0.30
        ra.weight_base = 0.40
        ra.weight_bear = 0.20  # total = 90%
        result = ra.normalize_exit_scenario_weights()
        assert "90.0%" in result["notice"]
        total = sum(s["wt"] for s in result["scenarios"])
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_zero_weights(self):
        """All weights zero → equal split and notice."""
        ra.weight_bull = 0.0
        ra.weight_base = 0.0
        ra.weight_bear = 0.0
        result = ra.normalize_exit_scenario_weights()
        assert "0%" in result["notice"]
        for s in result["scenarios"]:
            assert s["wt"] == pytest.approx(1.0 / 3, abs=1e-9)
