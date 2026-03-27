"""Shared fixtures for real estate analysis tests."""
import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import real_estate_analysis as ra


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset all module-level globals to production defaults before each test."""
    ra.current_gross_sale_price = 100_000_000
    ra.cost_basis = 8_425_000
    ra.hold_period_years = 10
    ra.reinvestment_rate = 0.06
    ra.discount_rate = 0.07

    ra.exit_bull = 250_000_000
    ra.exit_base = 200_000_000
    ra.exit_bear = 140_000_000
    ra.weight_bull = 0.25
    ra.weight_base = 0.50
    ra.weight_bear = 0.25

    ra.initial_carrying_costs = 0
    ra.carrying_cost_escalation = 0.03
    ra.noi_phase1 = 600_000
    ra.noi_phase2 = 2_000_000
    ra.phase1_end_year = 3.5

    ra.transaction_cost_rate_now = 0.14
    ra.transaction_cost_rate_future = 0.04

    ra.federal_cap_gains_rate = 0.0   # 1031 ON by default
    ra.niit_rate = 0.0                # 1031 ON
    ra.wa_cap_gains_rate = 0.07         # 7% rate, but disabled by default
    ra.wa_cap_gains_enabled = False
    ra.wa_cap_gains_threshold = 250_000
    ra.depreciation_recapture_rate = 0.0  # 1031 ON
    ra.cumulative_depreciation = 0
    ra.ordinary_income_rate = 0.37
    yield
