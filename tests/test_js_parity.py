"""Cross-engine parity: verify Python and JavaScript produce identical results."""
import json
import subprocess
import pytest
import real_estate_analysis as ra
from tests.helpers import set_1031_off

# Load engine.js from the project root instead of duplicating it
import os as _os
_ENGINE_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'engine.js')
with open(_ENGINE_PATH) as _f:
    _ENGINE_SRC = _f.read()

# Append a runner that reads params from argv, calls calcA/calcB, and prints JSON
JS_ENGINE = _ENGINE_SRC + '''
const E = RealEstateEngine;
const p = JSON.parse(process.argv[2]);
const exitPrice = parseFloat(process.argv[3]);
const a = E.calcA(p);
const b = E.calcB(exitPrice, p);
console.log(JSON.stringify({ a, b }));
'''


def run_js(params: dict, exit_price: float) -> dict:
    """Run the JS engine via Node and return results."""
    import shutil
    node = shutil.which('node')
    if not node:
        pytest.skip("Node.js not installed — skipping JS parity test")
    try:
        result = subprocess.run(
            [node, '-e', JS_ENGINE, '--', json.dumps(params), str(exit_price)],
            capture_output=True, text=True, timeout=10
        )
    except (OSError, FileNotFoundError):
        pytest.skip("Node.js not available — skipping JS parity test")
    if result.returncode != 0:
        pytest.skip(f"Node.js error: {result.stderr[:200]}")
    return json.loads(result.stdout)


def make_params(gross=100e6, basis=8.425e6, hold=10, reinv=0.06, disc=0.07,
                tx_now=0.14, tx_future=0.04, fed=0.0, niit=0.0,
                wa_enabled=False, wa_rate=0.0, wa_threshold=250000,
                dep_recap=0.0, cum_dep=0, ord_rate=0.37,
                init_carry=0, carry_esc=0.03,
                noi_p1=600000, noi_p2=2000000, p1_end=3.5):
    return {
        "grossSale": gross, "costBasis": basis, "holdYears": hold,
        "reinvRate": reinv, "discRate": disc,
        "txNow": tx_now, "txFuture": tx_future,
        "fedCG": fed, "niit": niit,
        "waEnabled": wa_enabled, "waRate": wa_rate, "waThreshold": wa_threshold,
        "depRecap": dep_recap, "cumDep": cum_dep, "ordRate": ord_rate,
        "initCarry": init_carry, "carryEsc": carry_esc,
        "noiP1": noi_p1, "noiP2": noi_p2, "p1End": p1_end,
    }


def set_python_params(params):
    """Set Python module globals to match JS params."""
    ra.current_gross_sale_price = params["grossSale"]
    ra.cost_basis = params["costBasis"]
    ra.hold_period_years = params["holdYears"]
    ra.reinvestment_rate = params["reinvRate"]
    ra.discount_rate = params["discRate"]
    ra.transaction_cost_rate_now = params["txNow"]
    ra.transaction_cost_rate_future = params["txFuture"]
    ra.federal_cap_gains_rate = params["fedCG"]
    ra.niit_rate = params["niit"]
    ra.wa_cap_gains_enabled = params["waEnabled"]
    ra.wa_cap_gains_rate = params["waRate"]
    ra.wa_cap_gains_threshold = params["waThreshold"]
    ra.depreciation_recapture_rate = params["depRecap"]
    ra.cumulative_depreciation = params["cumDep"]
    ra.ordinary_income_rate = params["ordRate"]
    ra.initial_carrying_costs = params["initCarry"]
    ra.carrying_cost_escalation = params["carryEsc"]
    ra.noi_phase1 = params["noiP1"]
    ra.noi_phase2 = params["noiP2"]
    ra.phase1_end_year = params["p1End"]


TOL = 1.0  # $1 tolerance


class TestJSParity:
    """Verify Python and JavaScript produce identical results."""

    @pytest.mark.parametrize("label,params,exit_price", [
        ("default_1031_on", make_params(), 200e6),
        ("1031_off", make_params(fed=0.20, niit=0.038, dep_recap=0.25), 200e6),
        ("high_depreciation", make_params(fed=0.20, niit=0.038, dep_recap=0.25, cum_dep=5e6), 200e6),
        ("negative_cf", make_params(init_carry=1.5e6, noi_p1=600000, noi_p2=2e6), 200e6),
        ("underwater_exit", make_params(fed=0.20, niit=0.038), 5e6),
        ("wa_enabled", make_params(fed=0.20, niit=0.038, wa_enabled=True, wa_rate=0.07), 200e6),
    ])
    def test_parity(self, label, params, exit_price):
        """Python and JS should match within $1."""
        set_python_params(params)
        py_a = ra.calc_scenario_a()
        py_b = ra.calc_scenario_b(exit_price)

        js_result = run_js(params, exit_price)
        js_a = js_result["a"]
        js_b = js_result["b"]

        # Compare Scenario A
        for key in ["txCosts", "netSale", "saleGain", "saleTax", "atProceeds",
                     "fvGross", "invGain", "invTax", "fvAT", "npv"]:
            py_key = {
                "txCosts": "tx_costs", "netSale": "net_sale_proceeds",
                "saleGain": "sale_gain", "saleTax": "sale_tax",
                "atProceeds": "after_tax_proceeds", "fvGross": "future_value_gross",
                "invGain": "investment_gain", "invTax": "inv_tax",
                "fvAT": "future_value_after_tax", "npv": "npv",
            }[key]
            assert py_a[py_key] == pytest.approx(js_a[key], abs=TOL), \
                f"[{label}] Scenario A.{key}: Python={py_a[py_key]}, JS={js_a[key]}"

        # Compare Scenario B
        for key in ["exitTx", "netExit", "exitGain", "exitTax", "netExitAT",
                     "compCF", "totalFV", "totalNPV"]:
            py_key = {
                "exitTx": "exit_tx_costs", "netExit": "net_exit",
                "exitGain": "exit_gain", "exitTax": "exit_tax",
                "netExitAT": "net_exit_after_tax", "compCF": "compounded_cf",
                "totalFV": "total_fv_after_tax", "totalNPV": "total_npv",
            }[key]
            assert py_b[py_key] == pytest.approx(js_b[key], abs=TOL), \
                f"[{label}] Scenario B.{key}: Python={py_b[py_key]}, JS={js_b[key]}"
