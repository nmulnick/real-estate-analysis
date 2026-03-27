// ============================================================
// Real Estate Investment Analysis — Calculation Engine
// Extracted from real_estate_dashboard.html
// ============================================================
(function(global) {
  "use strict";

  const EPSILON = 1e-9;

  const IRR_GRID = [
    -0.9999, -0.99, -0.95, -0.9, -0.75, -0.5, -0.25, -0.1, -0.05,
    0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75,
    1, 1.5, 2, 3, 5,
  ];

  const toFiniteNumber = (value, fallback) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  };

  const maxZero = (value) => Math.max(toFiniteNumber(value, 0), 0);

  function calcCGTax(gain, dep, p, fedOverride) {
    const fed = fedOverride !== undefined ? fedOverride : p.fedCG;
    const recognizedGain = maxZero(gain);
    const depreciation = maxZero(dep);
    if (recognizedGain <= 0) return 0;
    const recaptureGain = Math.min(depreciation, recognizedGain);
    const capitalGain = Math.max(recognizedGain - recaptureGain, 0);
    let tax = (recaptureGain * p.depRecap) + (capitalGain * (fed + p.niit));
    if (p.waEnabled && capitalGain > p.waThreshold) {
      tax += (capitalGain - p.waThreshold) * p.waRate;
    }
    return tax;
  }

  function adjustedBasis(p) {
    return toFiniteNumber(p.costBasis, 0) - maxZero(p.cumDep);
  }

  // WA Real Estate Excise Tax — graduated state + flat local
  const REET_BRACKETS = [
    { threshold:  525000, rate: 0.011  },
    { threshold: 1525000, rate: 0.0128 },
    { threshold: 3025000, rate: 0.0275 },
    { threshold: Infinity, rate: 0.03  },
  ];

  function calcREET(grossPrice, localRate) {
    const safePrice = maxZero(grossPrice);
    const safeLocal = maxZero(localRate);
    let stateREET = 0, prevThreshold = 0;
    for (const bracket of REET_BRACKETS) {
      const taxableSlice = Math.min(safePrice, bracket.threshold) - prevThreshold;
      if (taxableSlice <= 0) break;
      stateREET += taxableSlice * bracket.rate;
      prevThreshold = bracket.threshold;
    }
    const localREET = safePrice * safeLocal;
    return { stateREET, localREET, totalREET: stateREET + localREET };
  }

  function calcDisposition(grossPrice, txRate, p, fedOverride) {
    const safeGrossPrice = maxZero(grossPrice);
    const safeTxRate = maxZero(txRate);
    const txCosts = safeGrossPrice * safeTxRate;
    const reet = p.reetEnabled ? calcREET(safeGrossPrice, p.reetLocalRate)
                               : { stateREET: 0, localREET: 0, totalREET: 0 };
    const netProceeds = safeGrossPrice - txCosts - reet.totalREET;
    const basis = adjustedBasis(p);
    const recognizedGain = Math.max(netProceeds - basis, 0);
    const tax = calcCGTax(recognizedGain, p.cumDep, p, fedOverride);
    return {
      grossPrice: safeGrossPrice, txCosts, reetTotal: reet.totalREET,
      netProceeds, adjustedBasis: basis, recognizedGain, tax,
      afterTaxProceeds: netProceeds - tax,
    };
  }

  function calcAFromGrossSale(grossSale, p, reinvOverride, txOverride, fedOverride) {
    const reinv = reinvOverride !== undefined ? reinvOverride : p.reinvRate;
    const txRate = txOverride !== undefined ? txOverride : p.txNow;
    const fed = fedOverride !== undefined ? fedOverride : p.fedCG;
    const sale = calcDisposition(grossSale, txRate, p, fed);
    const atProceeds = sale.afterTaxProceeds;
    const fvGross = atProceeds * Math.pow(1 + reinv, p.holdYears);
    const invGain = Math.max(fvGross - atProceeds, 0);
    const invTax = calcCGTax(invGain, 0, p, fed);
    const fvAT = fvGross - invTax;
    return {
      grossSale: sale.grossPrice, txCosts: sale.txCosts, reetTotal: sale.reetTotal,
      netSale: sale.netProceeds,
      adjustedBasis: sale.adjustedBasis, saleGain: sale.recognizedGain, saleTax: sale.tax,
      atProceeds, fvGross, invGain, invTax, fvAT, npv: atProceeds,
    };
  }

  function calcA(p, reinvOverride, txOverride, fedOverride) {
    return calcAFromGrossSale(p.grossSale, p, reinvOverride, txOverride, fedOverride);
  }

  function leaseForYear(year, p1End, noi1, noi2) {
    if (year <= Math.floor(p1End)) return noi1;
    if (year === Math.ceil(p1End) && p1End !== Math.floor(p1End)) {
      const frac1 = p1End - Math.floor(p1End);
      return (noi1 * frac1) + (noi2 * (1 - frac1));
    }
    return noi2;
  }

  function calcB(exitPrice, p, reinvOverride, discOverride, txOverride, carryOverride, noiP1Override, fedOverride, ordOverride, noiP2Override) {
    const reinv = reinvOverride !== undefined ? reinvOverride : p.reinvRate;
    const disc = discOverride !== undefined ? discOverride : p.discRate;
    const txRate = txOverride !== undefined ? txOverride : p.txFuture;
    const initC = carryOverride !== undefined ? carryOverride : p.initCarry;
    const noi1 = noiP1Override !== undefined ? noiP1Override : p.noiP1;
    const noi2 = noiP2Override !== undefined ? noiP2Override : p.noiP2;
    const p1End = p.p1End;
    const fed = fedOverride !== undefined ? fedOverride : p.fedCG;
    const ord = ordOverride !== undefined ? ordOverride : p.ordRate;

    let compCF = 0, npvCF = 0;
    const annual = [];
    for (let yr = 1; yr <= p.holdYears; yr++) {
      const carry = initC * Math.pow(1 + p.carryEsc, yr - 1);
      const lease = leaseForYear(yr, p1End, noi1, noi2);
      const netPre = lease - carry;
      const incTax = netPre > 0 ? netPre * ord : 0;
      const netAT = netPre > 0 ? netPre - incTax : netPre;
      compCF = (compCF * (1 + reinv)) + netAT;
      npvCF += netAT / Math.pow(1 + disc, yr);
      annual.push({ yr, carry, lease, netPre, incTax, netAT, compCF });
    }
    const exit = calcDisposition(exitPrice, txRate, p, fed);
    const totalFV = exit.afterTaxProceeds + compCF;
    const pvExit = exit.afterTaxProceeds / Math.pow(1 + disc, p.holdYears);
    const totalNPV = npvCF + pvExit;
    return {
      exitPrice: exit.grossPrice, exitTx: exit.txCosts, exitREET: exit.reetTotal,
      netExit: exit.netProceeds,
      adjustedBasis: exit.adjustedBasis, exitGain: exit.recognizedGain, exitTax: exit.tax,
      netExitAT: exit.afterTaxProceeds, compCF, totalFV, totalNPV, npvCF, pvExit, annual,
    };
  }

  function buildCashFlows(opp, b, p) {
    const cf = [-opp];
    for (let i = 0; i < b.annual.length; i++) {
      const d = b.annual[i];
      let value = d.netAT;
      if (d.yr === p.holdYears) value += b.netExitAT;
      cf.push(value);
    }
    return cf;
  }

  function countSignChanges(values) {
    let previousSign = 0, changes = 0;
    for (let i = 0; i < values.length; i++) {
      const value = values[i];
      if (Math.abs(value) <= EPSILON) continue;
      const currentSign = value > 0 ? 1 : -1;
      if (previousSign !== 0 && currentSign !== previousSign) changes++;
      previousSign = currentSign;
    }
    return changes;
  }

  function npvAtRate(cashFlows, rate) {
    if (rate <= -1) return NaN;
    let total = 0;
    for (let t = 0; t < cashFlows.length; t++) {
      total += cashFlows[t] / Math.pow(1 + rate, t);
    }
    return total;
  }

  function bisectIRR(cashFlows, lo, hi) {
    let loNPV = npvAtRate(cashFlows, lo);
    for (let i = 0; i < 200; i++) {
      const mid = (lo + hi) / 2;
      const midNPV = npvAtRate(cashFlows, mid);
      if (!Number.isFinite(midNPV)) return null;
      if (Math.abs(midNPV) <= 1e-7 || Math.abs(hi - lo) <= 1e-10) return mid;
      if ((loNPV < 0 && midNPV < 0) || (loNPV > 0 && midNPV > 0)) {
        lo = mid; loNPV = midNPV;
      } else {
        hi = mid;
      }
    }
    return (lo + hi) / 2;
  }

  function calcIRR(opp, b, p) {
    const cashFlows = buildCashFlows(opp, b, p);
    let hasPositive = false, hasNegative = false;
    for (let i = 0; i < cashFlows.length; i++) {
      if (cashFlows[i] > EPSILON) hasPositive = true;
      else if (cashFlows[i] < -EPSILON) hasNegative = true;
    }
    if (!hasPositive || !hasNegative) return null;
    if (countSignChanges(cashFlows) > 1) return null;

    let prevRate = IRR_GRID[0];
    let prevNPV = npvAtRate(cashFlows, prevRate);
    if (!Number.isFinite(prevNPV)) {
      prevNPV = null;
    } else if (Math.abs(prevNPV) <= 1e-7) {
      return prevRate;
    }

    for (let j = 1; j < IRR_GRID.length; j++) {
      const currentRate = IRR_GRID[j];
      const currentNPV = npvAtRate(cashFlows, currentRate);
      if (!Number.isFinite(currentNPV)) continue;
      if (Math.abs(currentNPV) <= 1e-7) return currentRate;
      if (prevNPV !== null && ((prevNPV < 0 && currentNPV > 0) || (prevNPV > 0 && currentNPV < 0))) {
        return bisectIRR(cashFlows, prevRate, currentRate);
      }
      prevRate = currentRate;
      prevNPV = currentNPV;
    }
    return null;
  }

  function normalizeExitScenarioWeights(p) {
    if (!p.multiExit) {
      return {
        scenarios: [{ kind: 'exit', label: 'Exit', price: maxZero(p.exitSingle), wt: 1, rawWeight: 1 }],
        notice: '',
      };
    }
    const rawScenarios = [
      { kind: 'bull', label: 'Bull', price: maxZero(p.exitBull), rawWeight: maxZero(p.wtBull) },
      { kind: 'base', label: 'Base', price: maxZero(p.exitBase), rawWeight: maxZero(p.wtBase) },
      { kind: 'bear', label: 'Bear', price: maxZero(p.exitBear), rawWeight: maxZero(p.wtBear) },
    ];
    let totalWeight = 0;
    for (let i = 0; i < rawScenarios.length; i++) totalWeight += rawScenarios[i].rawWeight;

    if (totalWeight <= EPSILON) {
      return {
        scenarios: rawScenarios.map(s => ({
          kind: s.kind, label: s.label, price: s.price,
          wt: 1 / rawScenarios.length, rawWeight: s.rawWeight,
        })),
        notice: 'Exit weights totaled 0%. Using equal weights across bull, base, and bear scenarios.',
      };
    }
    let notice = '';
    if (Math.abs(totalWeight - 1) > 1e-4) {
      notice = 'Exit weights totaled ' + (totalWeight * 100).toFixed(1) + '%. Results have been normalized to 100%.';
    }
    return {
      scenarios: rawScenarios.map(s => ({
        kind: s.kind, label: s.label, price: s.price,
        wt: s.rawWeight / totalWeight, rawWeight: s.rawWeight,
      })),
      notice,
    };
  }

  function weightedAnnual(results) {
    if (!results.length) return [];
    const years = results[0].b.annual.length;
    const annual = [];
    for (let i = 0; i < years; i++) {
      const item = {
        yr: results[0].b.annual[i].yr,
        carry: 0, lease: 0, netPre: 0, incTax: 0, netAT: 0, compCF: 0,
      };
      for (let j = 0; j < results.length; j++) {
        const weight = results[j].wt;
        const source = results[j].b.annual[i];
        item.carry += source.carry * weight;
        item.lease += source.lease * weight;
        item.netPre += source.netPre * weight;
        item.incTax += source.incTax * weight;
        item.netAT += source.netAT * weight;
        item.compCF += source.compCF * weight;
      }
      annual.push(item);
    }
    return annual;
  }

  function buildExpectedScenario(results) {
    const summary = {
      kind: 'expected', label: 'Expected', price: 0, wt: 1, rawWeight: 1,
      b: {
        exitPrice: 0, exitTx: 0, netExit: 0, adjustedBasis: 0,
        exitGain: 0, exitTax: 0, netExitAT: 0, compCF: 0,
        totalFV: 0, totalNPV: 0, npvCF: 0, pvExit: 0, annual: [],
      },
      irr: null,
    };
    let allIRRsValid = true, weightedIRR = 0;
    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      const weight = result.wt;
      summary.price += result.price * weight;
      summary.b.exitPrice += result.b.exitPrice * weight;
      summary.b.exitTx += result.b.exitTx * weight;
      summary.b.netExit += result.b.netExit * weight;
      summary.b.adjustedBasis += result.b.adjustedBasis * weight;
      summary.b.exitGain += result.b.exitGain * weight;
      summary.b.exitTax += result.b.exitTax * weight;
      summary.b.netExitAT += result.b.netExitAT * weight;
      summary.b.compCF += result.b.compCF * weight;
      summary.b.totalFV += result.b.totalFV * weight;
      summary.b.totalNPV += result.b.totalNPV * weight;
      summary.b.npvCF += result.b.npvCF * weight;
      summary.b.pvExit += result.b.pvExit * weight;
      if (result.irr === null || !Number.isFinite(result.irr)) {
        allIRRsValid = false;
      } else {
        weightedIRR += result.irr * weight;
      }
    }
    summary.b.annual = weightedAnnual(results);
    summary.irr = allIRRsValid ? weightedIRR : null;
    return summary;
  }

  function evaluateExitScenarios(p, a) {
    const weightInfo = normalizeExitScenarioWeights(p);
    const baseResults = weightInfo.scenarios.map(scenario => {
      const b = calcB(scenario.price, p);
      return {
        kind: scenario.kind, label: scenario.label, price: scenario.price,
        wt: scenario.wt, rawWeight: scenario.rawWeight, b,
        irr: calcIRR(a.atProceeds, b, p),
      };
    });
    const summary = baseResults.length > 1 ? buildExpectedScenario(baseResults) : baseResults[0];
    const displayResults = baseResults.length > 1 ? baseResults.concat([summary]) : baseResults.slice();
    return {
      baseResults, displayResults, summary,
      weightNotice: weightInfo.notice, scenarioDefs: weightInfo.scenarios,
    };
  }

  function calcBreakevenSalePrice(targetFV, p) {
    if (!Number.isFinite(targetFV)) return { value: null, status: 'invalid_target' };
    const zeroSaleFV = calcAFromGrossSale(0, p).fvAT;
    if (targetFV <= zeroSaleFV + EPSILON) return { value: 0, status: 'zero_sale_beats_target' };
    let lo = 0;
    let hi = Math.max(maxZero(p.grossSale), 1);
    let hiFV = calcAFromGrossSale(hi, p).fvAT;
    for (let i = 0; i < 60 && hiFV < targetFV; i++) {
      hi *= 2;
      hiFV = calcAFromGrossSale(hi, p).fvAT;
    }
    if (hiFV < targetFV) return { value: null, status: 'unreachable' };
    for (let j = 0; j < 120; j++) {
      const mid = (lo + hi) / 2;
      const midFV = calcAFromGrossSale(mid, p).fvAT;
      if (Math.abs(midFV - targetFV) <= 0.01 || Math.abs(hi - lo) <= 0.01) return { value: mid, status: 'ok' };
      if (midFV < targetFV) lo = mid; else hi = mid;
    }
    return { value: (lo + hi) / 2, status: 'ok' };
  }

  // Export public API
  global.RealEstateEngine = {
    calcCGTax,
    calcREET,
    REET_BRACKETS,
    calcDisposition,
    calcAFromGrossSale,
    calcA,
    calcB,
    calcIRR,
    normalizeExitScenarioWeights,
    evaluateExitScenarios,
    calcBreakevenSalePrice,
    leaseForYear,
    adjustedBasis,
    npvAtRate,
  };

})(typeof globalThis !== "undefined" ? globalThis : this);
