#!/usr/bin/env python3
"""
Commercial Development Site Analysis: 411 116th Avenue NE, Bellevue, WA
Compares Sell Now & Reinvest (Scenario A) vs Hold, Lease & Sell Later (Scenario B)
"""

import csv
import math
import os
from typing import Dict, List, Tuple

# =============================================================================
# ALL ASSUMPTIONS — MODIFY THESE VARIABLES AS NEEDED
# =============================================================================

# Sale & Hold Assumptions
current_gross_sale_price = 100_000_000
cost_basis = 8_425_000
hold_period_years = 10
reinvestment_rate = 0.06
discount_rate = 0.07

# Exit Price Scenarios (Scenario B)
exit_bull = 250_000_000
exit_base = 200_000_000
exit_bear = 140_000_000
weight_bull = 0.25
weight_base = 0.50
weight_bear = 0.25

# Carrying Costs & Net Operating Income
initial_carrying_costs = 1_500_000
carrying_cost_escalation = 0.03

# Stepped lease: current lease nets $600K/yr through 9/30/2029,
# then $2M/yr net after re-leasing. Analysis starts ~Mar 2026,
# so phase 1 covers years 1-3, year 4 is prorated, years 5-10 are phase 2.
noi_phase1 = 600_000             # Net operating income, current lease
noi_phase2 = 2_000_000           # Net operating income, future lease
phase1_end_year = 3.5            # Years until current lease expires (Sep 2029)

# Legacy variables (kept for backward compatibility with sensitivity tables)
initial_lease_income = noi_phase1
lease_income_escalation = 0.0

# Transaction Costs
transaction_cost_rate_now = 0.14    # Scenario A: sell now
transaction_cost_rate_future = 0.04  # Scenario B: sell in year 10

# Tax Rates
# 1031 Exchange assumed — all capital gains taxes deferred/eliminated
federal_cap_gains_rate = 0.0
niit_rate = 0.0
wa_cap_gains_rate = 0.07             # 7% when enabled; default is disabled since WA CG tax doesn't apply to RE
wa_cap_gains_enabled = False         # Toggle for WA capital gains tax
wa_cap_gains_threshold = 250_000     # WA exempts first $250K of gains
depreciation_recapture_rate = 0.25
cumulative_depreciation = 0          # Set > 0 if depreciation was claimed
ordinary_income_rate = 0.37          # Marginal rate on lease income

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def fmt(value: float) -> str:
    """Format dollar amounts with commas and no decimals."""
    if abs(value) >= 1_000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def fmt_m(value: float) -> str:
    """Format dollar amounts in millions."""
    return f"${value / 1_000_000:,.1f}M"


def fmt_pct(value: float) -> str:
    """Format as percentage."""
    return f"{value * 100:.2f}%"


def adjusted_basis() -> float:
    """Return cost basis minus cumulative depreciation (floored at 0)."""
    return cost_basis - max(cumulative_depreciation, 0)


def calc_cap_gains_tax(gain: float, depreciation: float = 0,
                       fed_rate: float = None, niit: float = None,
                       wa_enabled: bool = None, wa_rate: float = None,
                       wa_threshold: float = None,
                       dep_recapture_rate: float = None) -> float:
    """Calculate total capital gains tax on a gain amount.

    Matches JS calcCGTax: applies max(gain, 0) and max(dep, 0) on inputs,
    then computes recognizedGain, recapture capped at recognizedGain, and
    capitalGain = max(recognizedGain - recapture, 0).
    """
    if fed_rate is None:
        fed_rate = federal_cap_gains_rate
    if niit is None:
        niit = niit_rate
    if wa_enabled is None:
        wa_enabled = wa_cap_gains_enabled
    if wa_rate is None:
        wa_rate = wa_cap_gains_rate
    if wa_threshold is None:
        wa_threshold = wa_cap_gains_threshold
    if dep_recapture_rate is None:
        dep_recapture_rate = depreciation_recapture_rate

    recognized_gain = max(gain, 0)
    dep = max(depreciation, 0)

    if recognized_gain <= 0:
        return 0.0

    tax = 0.0

    # Depreciation recapture (taxed at recapture rate, capped by recognized gain)
    recapture = min(dep, recognized_gain)
    if recapture > 0:
        tax += recapture * dep_recapture_rate

    # Federal capital gains + NIIT on the remaining capital gain
    capital_gain = max(recognized_gain - recapture, 0)
    tax += capital_gain * (fed_rate + niit)

    # Washington state capital gains tax
    # Note: WA's capital gains tax (effective 2022) applies to gains from the
    # sale of stocks/bonds; real estate is generally EXEMPT. Toggle included
    # for scenario modeling if tax law changes or for conservative planning.
    if wa_enabled and capital_gain > wa_threshold:
        wa_taxable = capital_gain - wa_threshold
        tax += wa_taxable * wa_rate

    return tax


def calc_disposition(gross_price: float, tx_rate: float,
                     fed_rate: float = None) -> Dict:
    """Compute sale disposition: transaction costs, gain, tax, after-tax proceeds.

    Mirrors JS calcDisposition — uses adjustedBasis() for gain computation.
    """
    tx_costs = gross_price * tx_rate
    net_proceeds = gross_price - tx_costs
    basis = adjusted_basis()
    recognized_gain = max(net_proceeds - basis, 0)
    tax = calc_cap_gains_tax(recognized_gain, cumulative_depreciation,
                             fed_rate=fed_rate)
    return {
        "gross_price": gross_price,
        "tx_costs": tx_costs,
        "net_proceeds": net_proceeds,
        "adjusted_basis": basis,
        "recognized_gain": recognized_gain,
        "tax": tax,
        "after_tax_proceeds": net_proceeds - tax,
    }


def calc_scenario_a_from_gross_sale(gross_sale: float,
                                    reinv_rate: float = None,
                                    tx_cost_rate: float = None,
                                    fed_rate: float = None) -> Dict:
    """Calculate Scenario A from a given gross sale price. Mirrors JS calcAFromGrossSale."""
    if reinv_rate is None:
        reinv_rate = reinvestment_rate
    if tx_cost_rate is None:
        tx_cost_rate = transaction_cost_rate_now
    if fed_rate is None:
        fed_rate = federal_cap_gains_rate

    sale = calc_disposition(gross_sale, tx_cost_rate, fed_rate=fed_rate)
    after_tax_proceeds = sale["after_tax_proceeds"]

    # Reinvest for hold_period_years
    future_value_gross = after_tax_proceeds * (1 + reinv_rate) ** hold_period_years
    investment_gain = max(future_value_gross - after_tax_proceeds, 0)

    # Tax on investment gains at year 10
    inv_tax = calc_cap_gains_tax(investment_gain, 0, fed_rate=fed_rate)
    future_value_after_tax = future_value_gross - inv_tax

    # NPV: the net proceeds today (already in present dollars)
    npv = after_tax_proceeds

    return {
        "gross_sale": sale["gross_price"],
        "tx_costs": sale["tx_costs"],
        "net_sale_proceeds": sale["net_proceeds"],
        "adjusted_basis": sale["adjusted_basis"],
        "sale_gain": sale["recognized_gain"],
        "sale_tax": sale["tax"],
        "after_tax_proceeds": after_tax_proceeds,
        "future_value_gross": future_value_gross,
        "investment_gain": investment_gain,
        "inv_tax": inv_tax,
        "future_value_after_tax": future_value_after_tax,
        "npv": npv,
    }


def calc_scenario_a(reinv_rate: float = None,
                    tx_cost_rate: float = None,
                    fed_rate: float = None) -> Dict:
    """Calculate Scenario A: Sell Now & Reinvest. Wraps calc_scenario_a_from_gross_sale."""
    return calc_scenario_a_from_gross_sale(current_gross_sale_price,
                                           reinv_rate=reinv_rate,
                                           tx_cost_rate=tx_cost_rate,
                                           fed_rate=fed_rate)


def lease_for_year(year: int, p1_end: float, noi1: float, noi2: float) -> float:
    """Return lease income for a given year, handling stepped-lease proration."""
    if year <= math.floor(p1_end):
        return noi1
    if year == math.ceil(p1_end) and p1_end != math.floor(p1_end):
        frac1 = p1_end - math.floor(p1_end)
        return noi1 * frac1 + noi2 * (1 - frac1)
    return noi2


def calc_scenario_b(exit_price: float,
                    reinv_rate: float = None,
                    disc_rate: float = None,
                    tx_cost_rate: float = None,
                    init_carrying: float = None,
                    noi_p1: float = None,
                    noi_p2: float = None,
                    p1_end: float = None,
                    fed_rate: float = None,
                    ord_rate: float = None) -> Dict:
    """Calculate Scenario B: Hold, Lease & Sell Later for a given exit price."""
    if reinv_rate is None:
        reinv_rate = reinvestment_rate
    if disc_rate is None:
        disc_rate = discount_rate
    if tx_cost_rate is None:
        tx_cost_rate = transaction_cost_rate_future
    if init_carrying is None:
        init_carrying = initial_carrying_costs
    if noi_p1 is None:
        noi_p1 = noi_phase1
    if noi_p2 is None:
        noi_p2 = noi_phase2
    if p1_end is None:
        p1_end = phase1_end_year
    if fed_rate is None:
        fed_rate = federal_cap_gains_rate
    if ord_rate is None:
        ord_rate = ordinary_income_rate

    annual_details = []
    compounded_cf = 0.0  # running compounded value of reinvested net cash flows
    npv_cf_sum = 0.0     # sum of discounted after-tax cash flows

    for yr in range(1, hold_period_years + 1):
        carrying = init_carrying * (1 + carrying_cost_escalation) ** (yr - 1)
        lease = lease_for_year(yr, p1_end, noi_p1, noi_p2)

        net_cf_pretax = lease - carrying

        # Tax lease income at ordinary income rate (carrying costs deductible)
        taxable_income = max(net_cf_pretax, 0)
        income_tax = taxable_income * ord_rate
        net_cf_after_tax = net_cf_pretax - income_tax
        # If net_cf_pretax < 0, assume the loss offsets other income (no refund modeled)
        if net_cf_pretax < 0:
            net_cf_after_tax = net_cf_pretax  # full loss (no tax benefit modeled simply)

        # Compound prior balance + this year's cash flow
        compounded_cf = compounded_cf * (1 + reinv_rate) + net_cf_after_tax

        # Discount for NPV
        pv_cf = net_cf_after_tax / (1 + disc_rate) ** yr
        npv_cf_sum += pv_cf

        annual_details.append({
            "year": yr,
            "carrying": carrying,
            "lease": lease,
            "net_cf_pretax": net_cf_pretax,
            "income_tax": income_tax,
            "net_cf_after_tax": net_cf_after_tax,
            "compounded_cf": compounded_cf,
            "pv_cf": pv_cf,
        })

    # Year 10 sale — use calc_disposition
    exit_sale = calc_disposition(exit_price, tx_cost_rate, fed_rate=fed_rate)
    net_exit_after_tax = exit_sale["after_tax_proceeds"]

    # Total after-tax future value at year 10
    total_fv_after_tax = net_exit_after_tax + compounded_cf

    # NPV of exit proceeds
    pv_exit = net_exit_after_tax / (1 + disc_rate) ** hold_period_years
    total_npv = npv_cf_sum + pv_exit

    return {
        "exit_price": exit_sale["gross_price"],
        "exit_tx_costs": exit_sale["tx_costs"],
        "net_exit": exit_sale["net_proceeds"],
        "adjusted_basis": exit_sale["adjusted_basis"],
        "exit_gain": exit_sale["recognized_gain"],
        "exit_tax": exit_sale["tax"],
        "net_exit_after_tax": net_exit_after_tax,
        "compounded_cf": compounded_cf,
        "total_fv_after_tax": total_fv_after_tax,
        "total_npv": total_npv,
        "npv_cf_sum": npv_cf_sum,
        "pv_exit": pv_exit,
        "annual_details": annual_details,
    }


IRR_GRID = [
    -0.9999, -0.99, -0.95, -0.9, -0.75, -0.5, -0.25, -0.1, -0.05,
    0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75,
    1, 1.5, 2, 3, 5,
]

EPSILON = 1e-9


def npv_at_rate(cash_flows: List[float], rate: float) -> float:
    """Compute NPV at a given discount rate."""
    if rate <= -1:
        return float('nan')
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))


def _count_sign_changes(values: List[float]) -> int:
    """Count sign changes in a list of values (skipping near-zero)."""
    prev_sign = 0
    changes = 0
    for v in values:
        if abs(v) <= EPSILON:
            continue
        cur_sign = 1 if v > 0 else -1
        if prev_sign != 0 and cur_sign != prev_sign:
            changes += 1
        prev_sign = cur_sign
    return changes


def bisect_irr(cash_flows: List[float], lo: float, hi: float):
    """Bisection IRR solver between lo and hi. Returns float or None."""
    lo_npv = npv_at_rate(cash_flows, lo)
    for _ in range(200):
        mid = (lo + hi) / 2
        mid_npv = npv_at_rate(cash_flows, mid)
        if not math.isfinite(mid_npv):
            return None
        if abs(mid_npv) <= 1e-7 or abs(hi - lo) <= 1e-10:
            return mid
        if (lo_npv < 0 and mid_npv < 0) or (lo_npv > 0 and mid_npv > 0):
            lo, lo_npv = mid, mid_npv
        else:
            hi = mid
    return (lo + hi) / 2


def _build_cash_flows(scenario_a_proceeds: float, scenario_b: Dict) -> List[float]:
    """Build cash flow vector for IRR calculation."""
    cash_flows = [-scenario_a_proceeds]
    for detail in scenario_b["annual_details"]:
        cf = detail["net_cf_after_tax"]
        if detail["year"] == hold_period_years:
            cf += scenario_b["net_exit_after_tax"]
        cash_flows.append(cf)
    return cash_flows


def calc_irr(scenario_a_proceeds: float, scenario_b: Dict,
             tol: float = 1e-8, max_iter: int = 1000):
    """
    Calculate IRR for the decision to hold instead of sell.
    Uses grid search + bisection. Returns float or None (not NaN).
    """
    cash_flows = _build_cash_flows(scenario_a_proceeds, scenario_b)

    # Check for sign change — no valid IRR if all CFs are same sign
    has_pos = any(cf > EPSILON for cf in cash_flows)
    has_neg = any(cf < -EPSILON for cf in cash_flows)
    if not has_pos or not has_neg:
        return None

    if _count_sign_changes(cash_flows) > 1:
        return None

    prev_rate = IRR_GRID[0]
    prev_npv = npv_at_rate(cash_flows, prev_rate)
    if not math.isfinite(prev_npv):
        prev_npv = None
    elif abs(prev_npv) <= 1e-7:
        return prev_rate

    for j in range(1, len(IRR_GRID)):
        current_rate = IRR_GRID[j]
        current_npv = npv_at_rate(cash_flows, current_rate)
        if not math.isfinite(current_npv):
            continue
        if abs(current_npv) <= 1e-7:
            return current_rate
        if prev_npv is not None and (
            (prev_npv < 0 and current_npv > 0) or
            (prev_npv > 0 and current_npv < 0)
        ):
            return bisect_irr(cash_flows, prev_rate, current_rate)
        prev_rate = current_rate
        prev_npv = current_npv

    return None


def calc_breakeven_sale_price(target_fv: float) -> Dict:
    """Binary search for breakeven gross sale price matching target FV.

    Returns dict with 'value' and 'status'.
    """
    if not math.isfinite(target_fv):
        return {"value": None, "status": "invalid_target"}

    zero_fv = calc_scenario_a_from_gross_sale(0)["future_value_after_tax"]
    if target_fv <= zero_fv + EPSILON:
        return {"value": 0, "status": "zero_sale_beats_target"}

    lo = 0.0
    hi = max(current_gross_sale_price, 1.0)
    hi_fv = calc_scenario_a_from_gross_sale(hi)["future_value_after_tax"]
    for _ in range(60):
        if hi_fv >= target_fv:
            break
        hi *= 2
        hi_fv = calc_scenario_a_from_gross_sale(hi)["future_value_after_tax"]
    else:
        if hi_fv < target_fv:
            return {"value": None, "status": "unreachable"}

    for _ in range(120):
        mid = (lo + hi) / 2
        mid_fv = calc_scenario_a_from_gross_sale(mid)["future_value_after_tax"]
        if abs(mid_fv - target_fv) <= 0.01 or abs(hi - lo) <= 0.01:
            return {"value": mid, "status": "ok"}
        if mid_fv < target_fv:
            lo = mid
        else:
            hi = mid

    return {"value": (lo + hi) / 2, "status": "ok"}


def evaluate_exit_scenarios() -> Dict:
    """Compute each exit scenario independently, then weight the OUTPUTS.

    Returns structure matching JS evaluateExitScenarios.
    """
    a = calc_scenario_a()

    scenarios = [
        {"kind": "bull", "label": "Bull", "price": exit_bull, "raw_weight": weight_bull},
        {"kind": "base", "label": "Base", "price": exit_base, "raw_weight": weight_base},
        {"kind": "bear", "label": "Bear", "price": exit_bear, "raw_weight": weight_bear},
    ]

    total_weight = sum(s["raw_weight"] for s in scenarios)
    notice = ""
    if total_weight <= EPSILON:
        for s in scenarios:
            s["wt"] = 1.0 / len(scenarios)
        notice = "Exit weights totaled 0%. Using equal weights."
    else:
        if abs(total_weight - 1) > 1e-4:
            notice = f"Exit weights totaled {total_weight * 100:.1f}%. Results have been normalized to 100%."
        for s in scenarios:
            s["wt"] = s["raw_weight"] / total_weight

    base_results = []
    for s in scenarios:
        b = calc_scenario_b(s["price"])
        irr = calc_irr(a["after_tax_proceeds"], b)
        base_results.append({
            "kind": s["kind"], "label": s["label"], "price": s["price"],
            "wt": s["wt"], "raw_weight": s["raw_weight"],
            "b": b, "irr": irr,
        })

    # Build weighted summary
    summary_b = {}
    for key in ["exit_price", "exit_tx_costs", "net_exit", "adjusted_basis",
                "exit_gain", "exit_tax", "net_exit_after_tax", "compounded_cf",
                "total_fv_after_tax", "total_npv", "npv_cf_sum", "pv_exit"]:
        summary_b[key] = sum(r["b"][key] * r["wt"] for r in base_results)

    # Weighted annual details
    n_years = len(base_results[0]["b"]["annual_details"])
    summary_annual = []
    for i in range(n_years):
        item = {"year": base_results[0]["b"]["annual_details"][i]["year"]}
        for key in ["carrying", "lease", "net_cf_pretax", "income_tax",
                     "net_cf_after_tax", "compounded_cf", "pv_cf"]:
            item[key] = sum(r["b"]["annual_details"][i][key] * r["wt"] for r in base_results)
        summary_annual.append(item)
    summary_b["annual_details"] = summary_annual

    all_irrs_valid = all(r["irr"] is not None and math.isfinite(r["irr"]) for r in base_results)
    weighted_irr = sum(r["irr"] * r["wt"] for r in base_results) if all_irrs_valid else None

    summary = {
        "kind": "expected", "label": "Expected",
        "price": sum(r["price"] * r["wt"] for r in base_results),
        "wt": 1.0, "raw_weight": 1.0,
        "b": summary_b, "irr": weighted_irr,
    }

    display_results = base_results + [summary]
    return {
        "base_results": base_results,
        "display_results": display_results,
        "summary": summary,
        "weight_notice": notice,
        "a": a,
    }


def normalize_exit_scenario_weights() -> Dict:
    """Normalize exit scenario weights. Mirrors JS normalizeExitScenarioWeights."""
    raw_scenarios = [
        {"kind": "bull", "label": "Bull", "price": exit_bull, "raw_weight": weight_bull},
        {"kind": "base", "label": "Base", "price": exit_base, "raw_weight": weight_base},
        {"kind": "bear", "label": "Bear", "price": exit_bear, "raw_weight": weight_bear},
    ]
    total_weight = sum(s["raw_weight"] for s in raw_scenarios)
    notice = ""
    if total_weight <= EPSILON:
        return {
            "scenarios": [
                {**s, "wt": 1.0 / len(raw_scenarios)} for s in raw_scenarios
            ],
            "notice": "Exit weights totaled 0%. Using equal weights.",
        }
    if abs(total_weight - 1) > 1e-4:
        notice = f"Exit weights totaled {total_weight * 100:.1f}%. Results have been normalized to 100%."
    return {
        "scenarios": [
            {**s, "wt": s["raw_weight"] / total_weight} for s in raw_scenarios
        ],
        "notice": notice,
    }


def print_separator(char: str = "=", width: int = 80):
    print(char * width)


def print_header(title: str, width: int = 80):
    print()
    print_separator("=", width)
    print(f"  {title}")
    print_separator("=", width)


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def run_analysis():
    # Probability-weighted exit price
    pw_exit = (exit_bull * weight_bull +
               exit_base * weight_base +
               exit_bear * weight_bear)

    exit_scenarios = [
        ("Bull Case", exit_bull, weight_bull),
        ("Base Case", exit_base, weight_base),
        ("Bear Case", exit_bear, weight_bear),
        ("Prob-Weighted", pw_exit, 1.0),
    ]

    # --- Scenario A ---
    a = calc_scenario_a()

    # --- Scenario B for each exit ---
    b_results = {}
    for label, price, weight in exit_scenarios:
        b_results[label] = calc_scenario_b(price)

    # --- IRR for each exit ---
    irr_results = {}
    for label, price, weight in exit_scenarios:
        irr_results[label] = calc_irr(a["after_tax_proceeds"], b_results[label])

    # =========================================================================
    # 1. FUTURE VALUE COMPARISON
    # =========================================================================
    print_header("1. FUTURE VALUE COMPARISON (Year 10, After Tax)")

    print(f"\n  SCENARIO A — Sell Now & Reinvest")
    print(f"  {'Gross Sale Price:':<35} {fmt(a['gross_sale']):>18}")
    print(f"  {'Transaction Costs (%.1f%%):'  % (transaction_cost_rate_now*100):<35} {fmt(-a['tx_costs']):>18}")
    print(f"  {'Net Sale Proceeds:':<35} {fmt(a['net_sale_proceeds']):>18}")
    print(f"  {'Capital Gains Tax on Sale:':<35} {fmt(-a['sale_tax']):>18}")
    print(f"  {'After-Tax Proceeds to Invest:':<35} {fmt(a['after_tax_proceeds']):>18}")
    print(f"  {'Compounded @ {:.1f}% for {} yrs:'.format(reinvestment_rate*100, hold_period_years):<35} {fmt(a['future_value_gross']):>18}")
    print(f"  {'Tax on Investment Gain:':<35} {fmt(-a['inv_tax']):>18}")
    print(f"  {'AFTER-TAX FUTURE VALUE:':<35} {fmt(a['future_value_after_tax']):>18}")

    print(f"\n  SCENARIO B — Hold, Lease & Sell Later")
    print(f"  {'':18} {'Bull ($250M)':>15} {'Base ($200M)':>15} {'Bear ($140M)':>15} {'Prob-Wtd':>15}")
    print(f"  {'':-<18} {'':-<15} {'':-<15} {'':-<15} {'':-<15}")

    labels_short = ["Bull Case", "Base Case", "Bear Case", "Prob-Weighted"]
    rows_b = [
        ("Gross Exit Price", "exit_price"),
        ("Transaction Costs", "exit_tx_costs"),
        ("Net Exit Proceeds", "net_exit"),
        ("Cap Gains Tax on Sale", "exit_tax"),
        ("Net Exit After Tax", "net_exit_after_tax"),
        ("Compounded Net CF", "compounded_cf"),
        ("AFTER-TAX FV", "total_fv_after_tax"),
    ]
    for row_label, key in rows_b:
        vals = [b_results[l][key] for l in labels_short]
        sign = -1 if key in ("exit_tx_costs", "exit_tax") else 1
        line = f"  {row_label:<18}"
        for v in vals:
            line += f" {fmt_m(v * sign):>15}"
        print(line)

    print(f"\n  {'COMPARISON':>18} {'Bull':>15} {'Base':>15} {'Bear':>15} {'Prob-Wtd':>15}")
    print(f"  {'':-<18} {'':-<15} {'':-<15} {'':-<15} {'':-<15}")
    line_a = f"  {'Scenario A FV':<18}"
    for _ in labels_short:
        line_a += f" {fmt_m(a['future_value_after_tax']):>15}"
    print(line_a)
    line_b = f"  {'Scenario B FV':<18}"
    for l in labels_short:
        line_b += f" {fmt_m(b_results[l]['total_fv_after_tax']):>15}"
    print(line_b)
    line_d = f"  {'Advantage':<18}"
    for l in labels_short:
        diff = b_results[l]["total_fv_after_tax"] - a["future_value_after_tax"]
        winner = "B" if diff > 0 else "A"
        line_d += f" {winner} +{fmt_m(abs(diff)):>12}"
    print(line_d)

    # =========================================================================
    # 2. NPV / DISCOUNTED CASH FLOW
    # =========================================================================
    print_header("2. NET PRESENT VALUE (NPV) COMPARISON")
    print(f"  Discount Rate: {fmt_pct(discount_rate)}\n")

    print(f"  {'Scenario A NPV (after-tax proceeds today):':<48} {fmt(a['npv']):>18}")
    print()
    print(f"  {'Scenario B NPV':18} {'Bull':>15} {'Base':>15} {'Bear':>15} {'Prob-Wtd':>15}")
    print(f"  {'':-<18} {'':-<15} {'':-<15} {'':-<15} {'':-<15}")

    npv_rows = [
        ("PV of Cash Flows", "npv_cf_sum"),
        ("PV of Exit", "pv_exit"),
        ("Total NPV", "total_npv"),
    ]
    for row_label, key in npv_rows:
        line = f"  {row_label:<18}"
        for l in labels_short:
            line += f" {fmt_m(b_results[l][key]):>15}"
        print(line)

    print()
    line_d = f"  {'NPV Advantage':<18}"
    for l in labels_short:
        diff = b_results[l]["total_npv"] - a["npv"]
        winner = "B" if diff > 0 else "A"
        line_d += f" {winner} +{fmt_m(abs(diff)):>12}"
    print(line_d)

    # =========================================================================
    # 3. IRR FOR SCENARIO B
    # =========================================================================
    print_header("3. INTERNAL RATE OF RETURN (IRR) — Hold vs. Sell Decision")
    print(f"  Opportunity cost (Year 0): {fmt(a['after_tax_proceeds'])} (forgo Scenario A proceeds)\n")

    print(f"  {'Exit Scenario':<18} {'IRR':>10}")
    print(f"  {'':-<18} {'':-<10}")
    for l in labels_short:
        irr_val = irr_results[l]
        print(f"  {l:<18} {'N/A' if irr_val is None else fmt_pct(irr_val):>10}")

    print(f"\n  Interpretation: IRR > reinvestment rate ({fmt_pct(reinvestment_rate)}) favors holding.")
    for l in labels_short:
        irr_val = irr_results[l]
        if irr_val is None:
            print(f"    {l}: N/A → No valid IRR")
        else:
            verdict = "HOLD" if irr_val > reinvestment_rate else "SELL"
            print(f"    {l}: {fmt_pct(irr_val)} → {verdict}")

    # =========================================================================
    # 4. ANNUAL CASH FLOW DETAIL (Scenario B, Prob-Weighted)
    # =========================================================================
    print_header("ANNUAL CASH FLOW DETAIL — Scenario B (Prob-Weighted Exit)")

    pw = b_results["Prob-Weighted"]
    print(f"  {'Year':>4} {'Carrying':>12} {'Lease':>12} {'Net Pre-Tax':>12} "
          f"{'Inc Tax':>12} {'Net AT':>12} {'Compounded':>14}")
    print(f"  {'':-<4} {'':-<12} {'':-<12} {'':-<12} {'':-<12} {'':-<12} {'':-<14}")
    for d in pw["annual_details"]:
        print(f"  {d['year']:>4} {fmt_m(d['carrying']):>12} {fmt_m(d['lease']):>12} "
              f"{fmt_m(d['net_cf_pretax']):>12} {fmt_m(-d['income_tax']):>12} "
              f"{fmt_m(d['net_cf_after_tax']):>12} {fmt_m(d['compounded_cf']):>14}")

    # =========================================================================
    # 5. SENSITIVITY TABLES
    # =========================================================================
    print_header("4. SENSITIVITY ANALYSIS")

    # --- Table 1: Reinvestment Rate × Base-Case Exit Price → FV Advantage ---
    print("\n  TABLE 1: After-Tax FV Advantage — Reinvestment Rate × Exit Price")
    print(f"  (Positive = B wins, Negative = A wins)\n")

    reinv_rates = [0.04, 0.05, 0.06, 0.07, 0.08]
    exit_prices_t1 = [150_000_000, 175_000_000, 200_000_000, 225_000_000, 250_000_000]

    header = f"  {'Reinv Rate':<12}"
    for ep in exit_prices_t1:
        header += f" {fmt_m(ep):>14}"
    print(header)
    print(f"  {'':-<12}" + f" {'':-<14}" * len(exit_prices_t1))

    table1_data = []
    for rr in reinv_rates:
        a_r = calc_scenario_a(reinv_rate=rr)
        line = f"  {fmt_pct(rr):<12}"
        row_data = [fmt_pct(rr)]
        for ep in exit_prices_t1:
            b_r = calc_scenario_b(ep, reinv_rate=rr)
            diff = b_r["total_fv_after_tax"] - a_r["future_value_after_tax"]
            winner = "B" if diff > 0 else "A"
            cell = f"{winner} +{fmt_m(abs(diff))}"
            line += f" {cell:>14}"
            row_data.append(cell)
        print(line)
        table1_data.append(row_data)

    # --- Table 2: Carrying Costs × Future Lease NOI → NPV Difference ---
    print(f"\n  TABLE 2: NPV Difference (B - A) — Carrying Costs × Future Lease NOI")
    print(f"  (Current lease ${noi_phase1:,.0f}/yr through yr {phase1_end_year}; PW exit; Positive = B wins)\n")

    carry_vals = [500_000, 1_000_000, 1_500_000, 2_000_000, 2_500_000]
    lease_vals = [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000]

    header = f"  {'Carrying':<12}"
    for lv in lease_vals:
        header += f" {fmt_m(lv):>12}"
    print(header)
    print(f"  {'':-<12}" + f" {'':-<12}" * len(lease_vals))

    table2_data = []
    for cv in carry_vals:
        line = f"  {fmt_m(cv):<12}"
        row_data = [fmt_m(cv)]
        for lv in lease_vals:
            b_r = calc_scenario_b(pw_exit, init_carrying=cv, noi_p2=lv)
            diff = b_r["total_npv"] - a["npv"]
            winner = "B" if diff > 0 else "A"
            cell = f"{winner} +{fmt_m(abs(diff))}"
            line += f" {cell:>12}"
            row_data.append(cell)
        print(line)
        table2_data.append(row_data)

    # --- Table 3: Discount Rate × Prob-Weighted Exit → NPV Difference ---
    print(f"\n  TABLE 3: NPV Difference — Discount Rate × Exit Price")
    print(f"  (Positive = B wins)\n")

    disc_rates = [0.05, 0.06, 0.07, 0.08, 0.09]
    exit_prices_t3 = [150_000_000, 175_000_000, 200_000_000, 225_000_000, 250_000_000]

    header = f"  {'Disc Rate':<12}"
    for ep in exit_prices_t3:
        header += f" {fmt_m(ep):>14}"
    print(header)
    print(f"  {'':-<12}" + f" {'':-<14}" * len(exit_prices_t3))

    table3_data = []
    for dr in disc_rates:
        line = f"  {fmt_pct(dr):<12}"
        row_data = [fmt_pct(dr)]
        for ep in exit_prices_t3:
            b_r = calc_scenario_b(ep, disc_rate=dr)
            # Scenario A NPV is the same regardless of discount rate (it's today's value)
            diff = b_r["total_npv"] - a["npv"]
            winner = "B" if diff > 0 else "A"
            cell = f"{winner} +{fmt_m(abs(diff))}"
            line += f" {cell:>14}"
            row_data.append(cell)
        print(line)
        table3_data.append(row_data)

    # --- Table 4: Cap Gains Rate × Transaction Cost Rate → FV Difference ---
    print(f"\n  TABLE 4: FV Difference — Cap Gains Rate × Transaction Cost Rate")
    print(f"  (Base-case $200M exit; Positive = B wins)\n")

    cg_rates = [0.15, 0.20, 0.25]
    tx_rates = [0.01, 0.02, 0.03, 0.04]

    header = f"  {'CG Rate':<12}"
    for tr in tx_rates:
        header += f" {'TX ' + fmt_pct(tr):>14}"
    print(header)
    print(f"  {'':-<12}" + f" {'':-<14}" * len(tx_rates))

    table4_data = []
    for cg in cg_rates:
        line = f"  {fmt_pct(cg):<12}"
        row_data = [fmt_pct(cg)]
        for tr in tx_rates:
            a_r = calc_scenario_a(tx_cost_rate=tr, fed_rate=cg)
            b_r = calc_scenario_b(exit_base, tx_cost_rate=tr, fed_rate=cg)
            diff = b_r["total_fv_after_tax"] - a_r["future_value_after_tax"]
            winner = "B" if diff > 0 else "A"
            cell = f"{winner} +{fmt_m(abs(diff))}"
            line += f" {cell:>14}"
            row_data.append(cell)
        print(line)
        table4_data.append(row_data)

    # =========================================================================
    # KEY ASSUMPTIONS SUMMARY
    # =========================================================================
    print_header("KEY ASSUMPTIONS")
    print(f"  Current Gross Sale Price:      {fmt(current_gross_sale_price)}")
    print(f"  Cost Basis:                    {fmt(cost_basis)}")
    print(f"  Hold Period:                   {hold_period_years} years")
    print(f"  Reinvestment Rate:             {fmt_pct(reinvestment_rate)}")
    print(f"  Discount Rate:                 {fmt_pct(discount_rate)}")
    print(f"  Federal Cap Gains Rate:        {fmt_pct(federal_cap_gains_rate)}")
    print(f"  NIIT Rate:                     {fmt_pct(niit_rate)}")
    print(f"  WA Cap Gains Tax:              {'ON' if wa_cap_gains_enabled else 'OFF'} ({fmt_pct(wa_cap_gains_rate)} above {fmt(wa_cap_gains_threshold)})")
    print(f"  Depreciation Recapture:        {fmt_pct(depreciation_recapture_rate)} on {fmt(cumulative_depreciation)}")
    print(f"  Ordinary Income Rate:          {fmt_pct(ordinary_income_rate)}")
    print(f"  TX Cost (Sell Now):            {fmt_pct(transaction_cost_rate_now)}")
    print(f"  TX Cost (Sell Year 10):        {fmt_pct(transaction_cost_rate_future)}")
    print(f"  NOI Phase 1 (current lease):   {fmt(noi_phase1)}/yr through yr {phase1_end_year}")
    print(f"  NOI Phase 2 (future lease):    {fmt(noi_phase2)}/yr")
    print(f"  Carrying Costs:                {fmt(initial_carrying_costs)}/yr escalating {fmt_pct(carrying_cost_escalation)}")
    print(f"  Prob-Weighted Exit:            {fmt(pw_exit)}")
    print(f"    Bull: {fmt(exit_bull)} @ {weight_bull:.0%}")
    print(f"    Base: {fmt(exit_base)} @ {weight_base:.0%}")
    print(f"    Bear: {fmt(exit_bear)} @ {weight_bear:.0%}")

    # =========================================================================
    # EXPORT TO CSV
    # =========================================================================
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "real_estate_analysis_output.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)

        # Section 1: Assumptions
        w.writerow(["=== KEY ASSUMPTIONS ==="])
        w.writerow(["Parameter", "Value"])
        assumptions = [
            ("Current Gross Sale Price", current_gross_sale_price),
            ("Cost Basis", cost_basis),
            ("Hold Period (years)", hold_period_years),
            ("Reinvestment Rate", reinvestment_rate),
            ("Discount Rate", discount_rate),
            ("Federal Cap Gains Rate", federal_cap_gains_rate),
            ("NIIT Rate", niit_rate),
            ("WA Cap Gains Enabled", wa_cap_gains_enabled),
            ("WA Cap Gains Rate", wa_cap_gains_rate),
            ("Depreciation Recapture Rate", depreciation_recapture_rate),
            ("Cumulative Depreciation", cumulative_depreciation),
            ("Ordinary Income Rate", ordinary_income_rate),
            ("TX Cost Rate (Now)", transaction_cost_rate_now),
            ("TX Cost Rate (Future)", transaction_cost_rate_future),
            ("Exit Bull", exit_bull),
            ("Exit Base", exit_base),
            ("Exit Bear", exit_bear),
            ("Weight Bull", weight_bull),
            ("Weight Base", weight_base),
            ("Weight Bear", weight_bear),
            ("Prob-Weighted Exit", pw_exit),
            ("Initial Carrying Costs", initial_carrying_costs),
            ("Carrying Cost Escalation", carrying_cost_escalation),
            ("Initial Lease Income", initial_lease_income),
            ("Lease Income Escalation", lease_income_escalation),
        ]
        for param, val in assumptions:
            w.writerow([param, val])
        w.writerow([])

        # Section 2: Scenario A
        w.writerow(["=== SCENARIO A: SELL NOW & REINVEST ==="])
        w.writerow(["Metric", "Value"])
        for key, label in [
            ("gross_sale", "Gross Sale"),
            ("tx_costs", "Transaction Costs"),
            ("net_sale_proceeds", "Net Sale Proceeds"),
            ("sale_gain", "Capital Gain on Sale"),
            ("sale_tax", "Capital Gains Tax"),
            ("after_tax_proceeds", "After-Tax Proceeds"),
            ("future_value_gross", "FV Gross (Year 10)"),
            ("investment_gain", "Investment Gain"),
            ("inv_tax", "Tax on Investment Gain"),
            ("future_value_after_tax", "After-Tax Future Value"),
            ("npv", "NPV"),
        ]:
            w.writerow([label, f"{a[key]:.2f}"])
        w.writerow([])

        # Section 3: Scenario B for each exit
        w.writerow(["=== SCENARIO B: HOLD, LEASE & SELL (BY EXIT SCENARIO) ==="])
        b_header = ["Metric"] + labels_short
        w.writerow(b_header)
        b_metrics = [
            ("exit_price", "Exit Price"),
            ("exit_tx_costs", "Transaction Costs"),
            ("net_exit", "Net Exit Proceeds"),
            ("exit_gain", "Capital Gain"),
            ("exit_tax", "Capital Gains Tax"),
            ("net_exit_after_tax", "Net Exit After Tax"),
            ("compounded_cf", "Compounded Net Cash Flows"),
            ("total_fv_after_tax", "After-Tax Future Value"),
            ("total_npv", "NPV"),
            ("npv_cf_sum", "PV of Cash Flows"),
            ("pv_exit", "PV of Exit"),
        ]
        for key, label in b_metrics:
            row = [label]
            for l in labels_short:
                row.append(f"{b_results[l][key]:.2f}")
            w.writerow(row)
        w.writerow([])

        # Section 4: IRR
        w.writerow(["=== IRR (HOLD VS SELL) ==="])
        w.writerow(["Exit Scenario", "IRR"])
        for l in labels_short:
            w.writerow([l, f"{irr_results[l]:.4%}"])
        w.writerow([])

        # Section 5: FV Comparison
        w.writerow(["=== FUTURE VALUE COMPARISON ==="])
        w.writerow(["Scenario", "After-Tax FV", "Advantage"])
        w.writerow(["A (Sell & Reinvest)", f"{a['future_value_after_tax']:.2f}", ""])
        for l in labels_short:
            diff = b_results[l]["total_fv_after_tax"] - a["future_value_after_tax"]
            winner = "B" if diff > 0 else "A"
            w.writerow([f"B ({l})", f"{b_results[l]['total_fv_after_tax']:.2f}",
                        f"{winner} +{abs(diff):.2f}"])
        w.writerow([])

        # Section 6: NPV Comparison
        w.writerow(["=== NPV COMPARISON ==="])
        w.writerow(["Scenario", "NPV", "Advantage"])
        w.writerow(["A (Sell & Reinvest)", f"{a['npv']:.2f}", ""])
        for l in labels_short:
            diff = b_results[l]["total_npv"] - a["npv"]
            winner = "B" if diff > 0 else "A"
            w.writerow([f"B ({l})", f"{b_results[l]['total_npv']:.2f}",
                        f"{winner} +{abs(diff):.2f}"])
        w.writerow([])

        # Section 7: Annual Detail
        w.writerow(["=== ANNUAL CASH FLOW DETAIL (PROB-WEIGHTED) ==="])
        w.writerow(["Year", "Carrying Costs", "Lease Income", "Net Pre-Tax",
                     "Income Tax", "Net After-Tax", "Compounded CF"])
        for d in pw["annual_details"]:
            w.writerow([d["year"], f"{d['carrying']:.2f}", f"{d['lease']:.2f}",
                        f"{d['net_cf_pretax']:.2f}", f"{d['income_tax']:.2f}",
                        f"{d['net_cf_after_tax']:.2f}", f"{d['compounded_cf']:.2f}"])
        w.writerow([])

        # Section 8: Sensitivity Tables
        w.writerow(["=== SENSITIVITY TABLE 1: Reinvestment Rate x Exit Price → FV Advantage ==="])
        header_row = ["Reinv Rate"] + [fmt_m(ep) for ep in exit_prices_t1]
        w.writerow(header_row)
        for row in table1_data:
            w.writerow(row)
        w.writerow([])

        w.writerow(["=== SENSITIVITY TABLE 2: Carrying Costs x Lease Income → NPV Difference ==="])
        header_row = ["Carrying"] + [fmt_m(lv) for lv in lease_vals]
        w.writerow(header_row)
        for row in table2_data:
            w.writerow(row)
        w.writerow([])

        w.writerow(["=== SENSITIVITY TABLE 3: Discount Rate x Exit Price → NPV Difference ==="])
        header_row = ["Disc Rate"] + [fmt_m(ep) for ep in exit_prices_t3]
        w.writerow(header_row)
        for row in table3_data:
            w.writerow(row)
        w.writerow([])

        w.writerow(["=== SENSITIVITY TABLE 4: Cap Gains Rate x TX Cost Rate → FV Difference ==="])
        header_row = ["CG Rate"] + [f"TX {fmt_pct(tr)}" for tr in tx_rates]
        w.writerow(header_row)
        for row in table4_data:
            w.writerow(row)

    print(f"\n  CSV exported to: {csv_path}")
    print()


if __name__ == "__main__":
    run_analysis()
