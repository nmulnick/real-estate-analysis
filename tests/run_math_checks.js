ObjC.import("Foundation");

function readText(path) {
  return $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null).js;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function assertApprox(actual, expected, tolerance, message) {
  if (Math.abs(actual - expected) > tolerance) {
    throw new Error(message + " (expected " + expected + ", got " + actual + ")");
  }
}

var cwd = $.NSFileManager.defaultManager.currentDirectoryPath.js;
eval(readText(cwd + "/engine.js"));
var Engine = RealEstateEngine;

function baseParams() {
  return {
    grossSale: 100000000,
    costBasis: 8425000,
    holdYears: 10,
    reinvRate: 0.06,
    discRate: 0.07,
    multiExit: false,
    exitSingle: 200000000,
    exitBull: 250000000,
    exitBase: 200000000,
    exitBear: 140000000,
    wtBull: 0.25,
    wtBase: 0.5,
    wtBear: 0.25,
    initCarry: 0,
    carryEsc: 0.03,
    noiP1: 600000,
    noiP2: 2000000,
    p1End: 3.5,
    txNow: 0.14,
    txFuture: 0.04,
    fedCG: 0.2,
    niit: 0.038,
    waEnabled: false,
    waRate: 0,
    waThreshold: 250000,
    ordRate: 0.37,
    depRecap: 0.25,
    cumDep: 0,
  };
}

function run() {
  var params = baseParams();

  var withDep = baseParams();
  withDep.cumDep = 5000000;
  var saleOutcome = Engine.calcAFromGrossSale(100000000, withDep, undefined, 0.14, 0.2);
  assertApprox(saleOutcome.saleTax, 19712850, 0.5, "Adjusted basis should increase sale tax when depreciation exists");

  var noGainTax = Engine.calcCGTax(0, 1500000, withDep, 0.2);
  assertApprox(noGainTax, 0, 1e-9, "Depreciation recapture should be capped at recognized gain");

  var waParams = baseParams();
  waParams.waEnabled = true;
  waParams.waRate = 0.07;
  waParams.fedCG = 0.2;
  waParams.niit = 0.038;
  var waTax = Engine.calcCGTax(1000000, 0, waParams, 0.2);
  assertApprox(waTax, 290500, 1e-6, "WA capital gains toggle should add 7% above the threshold");

  var weightInfo = Engine.normalizeExitScenarioWeights({
    multiExit: true,
    exitBull: 250000000,
    exitBase: 200000000,
    exitBear: 140000000,
    wtBull: 0.4,
    wtBase: 0.4,
    wtBear: 0.4,
  });
  assertApprox(weightInfo.scenarios[0].wt, 1 / 3, 1e-9, "Bull weight should normalize to one third");
  assertApprox(weightInfo.scenarios[1].wt, 1 / 3, 1e-9, "Base weight should normalize to one third");
  assert(weightInfo.notice.length > 0, "Normalization should emit a warning message");

  var expectedParams = baseParams();
  expectedParams.multiExit = true;
  expectedParams.costBasis = 80000000;
  expectedParams.cumDep = 5000000;
  expectedParams.exitBull = 200000000;
  expectedParams.exitBase = 90000000;
  expectedParams.exitBear = 40000000;
  expectedParams.wtBull = 0.2;
  expectedParams.wtBase = 0.5;
  expectedParams.wtBear = 0.3;
  expectedParams.noiP1 = 0;
  expectedParams.noiP2 = 0;
  var expectedA = Engine.calcA(expectedParams);
  var expectedAnalysis = Engine.evaluateExitScenarios(expectedParams, expectedA);
  var weightedPrice = (
    (expectedParams.exitBull * expectedParams.wtBull) +
    (expectedParams.exitBase * expectedParams.wtBase) +
    (expectedParams.exitBear * expectedParams.wtBear)
  );
  var shortcut = Engine.calcB(weightedPrice, expectedParams);
  assert(
    Math.abs(expectedAnalysis.summary.b.totalFV - shortcut.totalFV) > 1000000,
    "Expected scenario results should not reuse the weighted-price shortcut"
  );

  var badIRRParams = baseParams();
  badIRRParams.noiP1 = 0;
  badIRRParams.noiP2 = 0;
  badIRRParams.initCarry = 2000000;
  var badB = Engine.calcB(0, badIRRParams);
  assert(Engine.calcIRR(Engine.calcA(badIRRParams).atProceeds, badB, badIRRParams) === null, "Invalid IRR cases should return null");

  var badBreakeven = Engine.calcBreakevenSalePrice(badB.totalFV, badIRRParams);
  assertApprox(badBreakeven.value, 0, 1e-9, "Breakeven should clamp to a non-negative sale price");
  assert(badBreakeven.status === "zero_sale_beats_target", "Negative-target breakeven should report a zero-sale status");

  console.log("All math checks passed.");
}

run();
