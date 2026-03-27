"""Shared test helpers."""
import real_estate_analysis as ra


def set_1031_off():
    """Set tax rates to normal (non-1031) values."""
    ra.federal_cap_gains_rate = 0.20
    ra.niit_rate = 0.038
    ra.depreciation_recapture_rate = 0.25
