(function (global) {
  "use strict";

  var EPSILON = 1e-9;
  var IRR_GRID = [
    -0.9999,
    -0.99,
    -0.95,
    -0.9,
    -0.75,
    -0.5,
    -0.25,
    -0.1,
    -0.05,
    0,
    0.02,
    0.04,
    0.06,
    0.08,
    0.1,
    0.15,
    0.2,
    0.3,
    0.5,
    0.75,
    1,
    1.5,
    2,
    3,
    5,
  ];

  function toFiniteNumber(value, fallback) {
    var num = Number(value);
    return Number.isFinite(num) ? num : fallback;
  }

  function maxZero(value) {
    return Math.max(toFiniteNumber(value, 0), 0);
  }

  function calcCGTax(gain, dep, p, fedOverride) {
    var fed = fedOverride !== undefined ? fedOverride : p.fedCG;
    var recognizedGain = maxZero(gain);
    var depreciation = maxZero(dep);

    if (recognizedGain <= 0) {
      return 0;
    }

    var recaptureGain = Math.min(depreciation, recognizedGain);
    var capitalGain = Math.max(recognizedGain - recaptureGain, 0);
    var tax = (recaptureGain * p.depRecap) + (capitalGain * (fed + p.niit));

    if (p.waEnabled && capitalGain > p.waThreshold) {
      tax += (capitalGain - p.waThreshold) * p.waRate;
    }
    return tax;
  }

  function adjustedBasis(p) {
    return toFiniteNumber(p.costBasis, 0) - maxZero(p.cumDep);
  }

  function calcDisposition(grossPrice, txRate, p, fedOverride) {
    var safeGrossPrice = maxZero(grossPrice);
    var safeTxRate = maxZero(txRate);
    var txCosts = safeGrossPrice * safeTxRate;
    var netProceeds = safeGrossPrice - txCosts;
    var basis = adjustedBasis(p);
    var recognizedGain = Math.max(netProceeds - basis, 0);
    var tax = calcCGTax(recognizedGain, p.cumDep, p, fedOverride);

    return {
      grossPrice: safeGrossPrice,
      txCosts: txCosts,
      netProceeds: netProceeds,
      adjustedBasis: basis,
      recognizedGain: recognizedGain,
      tax: tax,
      afterTaxProceeds: netProceeds - tax,
    };
  }

  function calcAFromGrossSale(grossSale, p, reinvOverride, txOverride, fedOverride) {
    var reinv = reinvOverride !== undefined ? reinvOverride : p.reinvRate;
    var txRate = txOverride !== undefined ? txOverride : p.txNow;
    var fed = fedOverride !== undefined ? fedOverride : p.fedCG;
    var sale = calcDisposition(grossSale, txRate, p, fed);
    var atProceeds = sale.afterTaxProceeds;
    var fvGross = atProceeds * Math.pow(1 + reinv, p.holdYears);
    var invGain = Math.max(fvGross - atProceeds, 0);
    var invTax = calcCGTax(invGain, 0, p, fed);
    var fvAT = fvGross - invTax;

    return {
      grossSale: sale.grossPrice,
      txCosts: sale.txCosts,
      netSale: sale.netProceeds,
      adjustedBasis: sale.adjustedBasis,
      saleGain: sale.recognizedGain,
      saleTax: sale.tax,
      atProceeds: atProceeds,
      fvGross: fvGross,
      invGain: invGain,
      invTax: invTax,
      fvAT: fvAT,
      npv: atProceeds,
    };
  }

  function calcA(p, reinvOverride, txOverride, fedOverride) {
    return calcAFromGrossSale(p.grossSale, p, reinvOverride, txOverride, fedOverride);
  }

  function leaseForYear(year, p1End, noi1, noi2) {
    if (year <= Math.floor(p1End)) {
      return noi1;
    }
    if (year === Math.ceil(p1End) && p1End !== Math.floor(p1End)) {
      var frac1 = p1End - Math.floor(p1End);
      return (noi1 * frac1) + (noi2 * (1 - frac1));
    }
    return noi2;
  }

  function calcB(exitPrice, p, reinvOverride, discOverride, txOverride, carryOverride, noiP1Override, fedOverride, ordOverride, noiP2Override) {
    var reinv = reinvOverride !== undefined ? reinvOverride : p.reinvRate;
    var disc = discOverride !== undefined ? discOverride : p.discRate;
    var txRate = txOverride !== undefined ? txOverride : p.txFuture;
    var initC = carryOverride !== undefined ? carryOverride : p.initCarry;
    var noi1 = noiP1Override !== undefined ? noiP1Override : p.noiP1;
    var noi2 = noiP2Override !== undefined ? noiP2Override : p.noiP2;
    var p1End = p.p1End;
    var fed = fedOverride !== undefined ? fedOverride : p.fedCG;
    var ord = ordOverride !== undefined ? ordOverride : p.ordRate;

    var compCF = 0;
    var npvCF = 0;
    var annual = [];

    for (var yr = 1; yr <= p.holdYears; yr += 1) {
      var carry = initC * Math.pow(1 + p.carryEsc, yr - 1);
      var lease = leaseForYear(yr, p1End, noi1, noi2);
      var netPre = lease - carry;
      var incTax = netPre > 0 ? netPre * ord : 0;
      var netAT = netPre > 0 ? netPre - incTax : netPre;
      compCF = (compCF * (1 + reinv)) + netAT;
      npvCF += netAT / Math.pow(1 + disc, yr);
      annual.push({
        yr: yr,
        carry: carry,
        lease: lease,
        netPre: netPre,
        incTax: incTax,
        netAT: netAT,
        compCF: compCF,
      });
    }

    var exit = calcDisposition(exitPrice, txRate, p, fed);
    var totalFV = exit.afterTaxProceeds + compCF;
    var pvExit = exit.afterTaxProceeds / Math.pow(1 + disc, p.holdYears);
    var totalNPV = npvCF + pvExit;

    return {
      exitPrice: exit.grossPrice,
      exitTx: exit.txCosts,
      netExit: exit.netProceeds,
      adjustedBasis: exit.adjustedBasis,
      exitGain: exit.recognizedGain,
      exitTax: exit.tax,
      netExitAT: exit.afterTaxProceeds,
      compCF: compCF,
      totalFV: totalFV,
      totalNPV: totalNPV,
      npvCF: npvCF,
      pvExit: pvExit,
      annual: annual,
    };
  }

  function buildCashFlows(opp, b, p) {
    var cf = [-opp];
    for (var i = 0; i < b.annual.length; i += 1) {
      var d = b.annual[i];
      var value = d.netAT;
      if (d.yr === p.holdYears) {
        value += b.netExitAT;
      }
      cf.push(value);
    }
    return cf;
  }

  function countSignChanges(values) {
    var previousSign = 0;
    var changes = 0;
    for (var i = 0; i < values.length; i += 1) {
      var value = values[i];
      if (Math.abs(value) <= EPSILON) {
        continue;
      }
      var currentSign = value > 0 ? 1 : -1;
      if (previousSign !== 0 && currentSign !== previousSign) {
        changes += 1;
      }
      previousSign = currentSign;
    }
    return changes;
  }

  function npvAtRate(cashFlows, rate) {
    if (rate <= -1) {
      return NaN;
    }
    var total = 0;
    for (var t = 0; t < cashFlows.length; t += 1) {
      total += cashFlows[t] / Math.pow(1 + rate, t);
    }
    return total;
  }

  function bisectIRR(cashFlows, lo, hi) {
    var loNPV = npvAtRate(cashFlows, lo);
    for (var i = 0; i < 200; i += 1) {
      var mid = (lo + hi) / 2;
      var midNPV = npvAtRate(cashFlows, mid);
      if (!Number.isFinite(midNPV)) {
        return null;
      }
      if (Math.abs(midNPV) <= 1e-7 || Math.abs(hi - lo) <= 1e-10) {
        return mid;
      }
      if ((loNPV < 0 && midNPV < 0) || (loNPV > 0 && midNPV > 0)) {
        lo = mid;
        loNPV = midNPV;
      } else {
        hi = mid;
      }
    }
    return (lo + hi) / 2;
  }

  function calcIRR(opp, b, p) {
    var cashFlows = buildCashFlows(opp, b, p);
    var hasPositive = false;
    var hasNegative = false;

    for (var i = 0; i < cashFlows.length; i += 1) {
      if (cashFlows[i] > EPSILON) {
        hasPositive = true;
      } else if (cashFlows[i] < -EPSILON) {
        hasNegative = true;
      }
    }
    if (!hasPositive || !hasNegative) {
      return null;
    }
    if (countSignChanges(cashFlows) > 1) {
      return null;
    }

    var prevRate = IRR_GRID[0];
    var prevNPV = npvAtRate(cashFlows, prevRate);
    if (!Number.isFinite(prevNPV)) {
      prevNPV = null;
    } else if (Math.abs(prevNPV) <= 1e-7) {
      return prevRate;
    }

    for (var j = 1; j < IRR_GRID.length; j += 1) {
      var currentRate = IRR_GRID[j];
      var currentNPV = npvAtRate(cashFlows, currentRate);
      if (!Number.isFinite(currentNPV)) {
        continue;
      }
      if (Math.abs(currentNPV) <= 1e-7) {
        return currentRate;
      }
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
        scenarios: [
          { kind: "exit", label: "Exit", price: maxZero(p.exitSingle), wt: 1, rawWeight: 1 },
        ],
        notice: "",
      };
    }

    var rawScenarios = [
      { kind: "bull", label: "Bull", price: maxZero(p.exitBull), rawWeight: maxZero(p.wtBull) },
      { kind: "base", label: "Base", price: maxZero(p.exitBase), rawWeight: maxZero(p.wtBase) },
      { kind: "bear", label: "Bear", price: maxZero(p.exitBear), rawWeight: maxZero(p.wtBear) },
    ];

    var totalWeight = 0;
    for (var i = 0; i < rawScenarios.length; i += 1) {
      totalWeight += rawScenarios[i].rawWeight;
    }

    if (totalWeight <= EPSILON) {
      return {
        scenarios: rawScenarios.map(function (scenario) {
          return {
            kind: scenario.kind,
            label: scenario.label,
            price: scenario.price,
            wt: 1 / rawScenarios.length,
            rawWeight: scenario.rawWeight,
          };
        }),
        notice: "Exit weights totaled 0%. Using equal weights across bull, base, and bear scenarios.",
      };
    }

    var notice = "";
    if (Math.abs(totalWeight - 1) > 1e-4) {
      notice = "Exit weights totaled " + (totalWeight * 100).toFixed(1) + "%. Results have been normalized to 100%.";
    }

    return {
      scenarios: rawScenarios.map(function (scenario) {
        return {
          kind: scenario.kind,
          label: scenario.label,
          price: scenario.price,
          wt: scenario.rawWeight / totalWeight,
          rawWeight: scenario.rawWeight,
        };
      }),
      notice: notice,
    };
  }

  function weightedAnnual(results) {
    if (!results.length) {
      return [];
    }
    var years = results[0].b.annual.length;
    var annual = [];
    for (var i = 0; i < years; i += 1) {
      var item = {
        yr: results[0].b.annual[i].yr,
        carry: 0,
        lease: 0,
        netPre: 0,
        incTax: 0,
        netAT: 0,
        compCF: 0,
      };
      for (var j = 0; j < results.length; j += 1) {
        var weight = results[j].wt;
        var source = results[j].b.annual[i];
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
    var summary = {
      kind: "expected",
      label: "Expected",
      price: 0,
      wt: 1,
      rawWeight: 1,
      b: {
        exitPrice: 0,
        exitTx: 0,
        netExit: 0,
        adjustedBasis: 0,
        exitGain: 0,
        exitTax: 0,
        netExitAT: 0,
        compCF: 0,
        totalFV: 0,
        totalNPV: 0,
        npvCF: 0,
        pvExit: 0,
        annual: [],
      },
      irr: null,
    };

    var allIRRsValid = true;
    var weightedIRR = 0;

    for (var i = 0; i < results.length; i += 1) {
      var result = results[i];
      var weight = result.wt;
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
    var weightInfo = normalizeExitScenarioWeights(p);
    var baseResults = weightInfo.scenarios.map(function (scenario) {
      var b = calcB(scenario.price, p);
      return {
        kind: scenario.kind,
        label: scenario.label,
        price: scenario.price,
        wt: scenario.wt,
        rawWeight: scenario.rawWeight,
        b: b,
        irr: calcIRR(a.atProceeds, b, p),
      };
    });

    var summary = baseResults.length > 1 ? buildExpectedScenario(baseResults) : baseResults[0];
    var displayResults = baseResults.length > 1 ? baseResults.concat([summary]) : baseResults.slice();

    return {
      baseResults: baseResults,
      displayResults: displayResults,
      summary: summary,
      weightNotice: weightInfo.notice,
      scenarioDefs: weightInfo.scenarios,
    };
  }

  function calcBreakevenSalePrice(targetFV, p) {
    if (!Number.isFinite(targetFV)) {
      return { value: null, status: "invalid_target" };
    }

    var zeroSaleFV = calcAFromGrossSale(0, p).fvAT;
    if (targetFV <= zeroSaleFV + EPSILON) {
      return { value: 0, status: "zero_sale_beats_target" };
    }

    var lo = 0;
    var hi = Math.max(maxZero(p.grossSale), 1);
    var hiFV = calcAFromGrossSale(hi, p).fvAT;

    for (var i = 0; i < 60 && hiFV < targetFV; i += 1) {
      hi *= 2;
      hiFV = calcAFromGrossSale(hi, p).fvAT;
    }

    if (hiFV < targetFV) {
      return { value: null, status: "unreachable" };
    }

    for (var j = 0; j < 120; j += 1) {
      var mid = (lo + hi) / 2;
      var midFV = calcAFromGrossSale(mid, p).fvAT;
      if (Math.abs(midFV - targetFV) <= 0.01 || Math.abs(hi - lo) <= 0.01) {
        return { value: mid, status: "ok" };
      }
      if (midFV < targetFV) {
        lo = mid;
      } else {
        hi = mid;
      }
    }

    return { value: (lo + hi) / 2, status: "ok" };
  }

  global.RealEstateEngine = {
    calcCGTax: calcCGTax,
    calcDisposition: calcDisposition,
    calcAFromGrossSale: calcAFromGrossSale,
    calcA: calcA,
    calcB: calcB,
    calcIRR: calcIRR,
    normalizeExitScenarioWeights: normalizeExitScenarioWeights,
    evaluateExitScenarios: evaluateExitScenarios,
    calcBreakevenSalePrice: calcBreakevenSalePrice,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
