import 'dart:math' as math;

// ══════════════════════════════════════════════════════════════════════════════
// MODELS
// ══════════════════════════════════════════════════════════════════════════════

enum SimulatorMode { sip, lumpsum, hybrid }

class SimulatorInput {
  const SimulatorInput({
    required this.mode,
    required this.monthlySip,
    required this.lumpsum,
    required this.annualStepUpPercent,
    required this.cagrPercent,
    required this.years,
  });

  final SimulatorMode mode;
  final double monthlySip;
  final double lumpsum;
  final double annualStepUpPercent;
  final double cagrPercent;
  final int years;

  SimulatorInput copyWith({
    SimulatorMode? mode,
    double? monthlySip,
    double? lumpsum,
    double? annualStepUpPercent,
    double? cagrPercent,
    int? years,
  }) {
    return SimulatorInput(
      mode: mode ?? this.mode,
      monthlySip: monthlySip ?? this.monthlySip,
      lumpsum: lumpsum ?? this.lumpsum,
      annualStepUpPercent: annualStepUpPercent ?? this.annualStepUpPercent,
      cagrPercent: cagrPercent ?? this.cagrPercent,
      years: years ?? this.years,
    );
  }
}

class YearlyProjection {
  const YearlyProjection({
    required this.year,
    required this.investedCumulative,
    required this.corpusValue,
    required this.gain,
  });

  final int year;
  final double investedCumulative;
  final double corpusValue;
  final double gain;
}

class SimulatorResult {
  const SimulatorResult({
    required this.totalInvested,
    required this.estimatedReturn,
    required this.finalCorpus,
    required this.absoluteReturnPercent,
    required this.cagr,
    required this.projections,
  });

  final double totalInvested;
  final double estimatedReturn;
  final double finalCorpus;
  final double absoluteReturnPercent;
  final double cagr;
  final List<YearlyProjection> projections;
}

// ══════════════════════════════════════════════════════════════════════════════
// CALCULATOR ENGINE
// ══════════════════════════════════════════════════════════════════════════════

class SipCalculator {
  SipCalculator._(); // static-only

  static SimulatorResult calculate(SimulatorInput input) {
    final int n = input.years;
    final double rAnnual = input.cagrPercent / 100.0;
    final double rMonthly = rAnnual / 12.0;

    double currentSip = input.mode == SimulatorMode.sip || input.mode == SimulatorMode.hybrid
        ? input.monthlySip
        : 0.0;
    
    final double initialLumpsum = input.mode == SimulatorMode.lumpsum || input.mode == SimulatorMode.hybrid
        ? input.lumpsum
        : 0.0;

    double sipCorpus = 0.0;
    double sipInvested = 0.0;
    
    final List<YearlyProjection> projections = [];

    for (int y = 1; y <= n; y++) {
      // 1. Process 12 months of SIP for this year
      if (input.mode == SimulatorMode.sip || input.mode == SimulatorMode.hybrid) {
        for (int m = 0; m < 12; m++) {
          sipInvested += currentSip;
          // Investment at the beginning of the month:
          sipCorpus = (sipCorpus + currentSip) * (1 + rMonthly);
        }
      }

      // 2. Process Lumpsum growth for this year
      // Lumpsum FV = P * (1 + r)^n  (Compounded annually as per spec)
      final double lumpsumCorpus = initialLumpsum * math.pow(1 + rAnnual, y);

      // 3. Aggregate for the year
      final double totalInvestedForYear = sipInvested + initialLumpsum;
      final double corpusForYear = sipCorpus + lumpsumCorpus;

      projections.add(YearlyProjection(
        year: y,
        investedCumulative: totalInvestedForYear,
        corpusValue: corpusForYear,
        gain: corpusForYear - totalInvestedForYear,
      ));

      // 4. Apply step-up for the next year (if applicable)
      if (input.mode == SimulatorMode.hybrid && input.annualStepUpPercent > 0) {
        currentSip = currentSip * (1 + input.annualStepUpPercent / 100.0);
      }
    }

    // Spec requirement: Round final corpus to nearest ₹100 for display
    final double rawFinalCorpus = projections.isNotEmpty ? projections.last.corpusValue : 0.0;
    final double finalCorpus = (rawFinalCorpus / 100.0).round() * 100.0;
    
    final double totalInvested = projections.isNotEmpty ? projections.last.investedCumulative : 0.0;
    final double estimatedReturn = finalCorpus - totalInvested;
    
    final double absoluteReturnPercent = totalInvested > 0 
        ? (estimatedReturn / totalInvested) * 100.0 
        : 0.0;

    // effective CAGR based on total invested vs rounded final corpus
    final double effectiveCagr = totalInvested > 0 && n > 0
        ? (math.pow(finalCorpus / totalInvested, 1 / n) - 1) * 100.0
        : 0.0;

    return SimulatorResult(
      totalInvested: totalInvested,
      estimatedReturn: estimatedReturn,
      finalCorpus: finalCorpus,
      absoluteReturnPercent: absoluteReturnPercent,
      cagr: effectiveCagr,
      projections: projections,
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// UNIT TEST CASES (manual verification — run with: dart lib/.../sip_calculator.dart)
// ══════════════════════════════════════════════════════════════════════════════

/*
void main() {
  // ── Test 1: Standard SIP (₹5,000/mo, 10 yrs, 12% CAGR) ────────────────────
  final sipInput = SimulatorInput(
    mode: SimulatorMode.sip,
    monthlySip: 5000,
    lumpsum: 0,
    annualStepUpPercent: 0,
    cagrPercent: 12,
    years: 10,
  );
  final r1 = SipCalculator.calculate(sipInput);
  // Invested: 5000 * 12 * 10 = 6,00,000
  // FV = 5000 * [((1.01)^120 - 1)/0.01] * 1.01 ≈ 11,61,695
  assert(r1.totalInvested == 600000, 'Test 1 FAIL: Invested != 600000');
  assert(r1.finalCorpus >= 1161600 && r1.finalCorpus <= 1161700, 
      'Test 1 FAIL: Corpus was ${r1.finalCorpus}');
  print('Test 1 PASS (SIP) — Invested: ₹${r1.totalInvested}, Corpus: ₹${r1.finalCorpus}');

  // ── Test 2: Lumpsum only (₹1,00,000, 5 yrs, 10% CAGR) ─────────────────────
  final lumpInput = SimulatorInput(
    mode: SimulatorMode.lumpsum,
    monthlySip: 0,
    lumpsum: 100000,
    annualStepUpPercent: 0,
    cagrPercent: 10,
    years: 5,
  );
  final r2 = SipCalculator.calculate(lumpInput);
  // Invested: 1,00,000
  // FV = 100000 * (1.1)^5 = 100000 * 1.61051 = 161051
  // Rounded to nearest 100 -> 161100
  assert(r2.totalInvested == 100000, 'Test 2 FAIL');
  assert(r2.finalCorpus == 161100, 'Test 2 FAIL: Corpus was ${r2.finalCorpus}');
  print('Test 2 PASS (Lumpsum) — Invested: ₹${r2.totalInvested}, Corpus: ₹${r2.finalCorpus}');

  // ── Test 3: Hybrid with Step-Up (₹2000/mo + 10% step-up + ₹50000 lumpsum) ─
  final hybridInput = SimulatorInput(
    mode: SimulatorMode.hybrid,
    monthlySip: 2000,
    lumpsum: 50000,
    annualStepUpPercent: 10,
    cagrPercent: 12,
    years: 3,
  );
  final r3 = SipCalculator.calculate(hybridInput);
  // Manual trace:
  // Lumpsum part: 50000 * (1.12)^3 = 70246.4
  // SIP Year 1 (2000/mo): 2000 * [((1.01)^12-1)/0.01]*1.01 = 25365
  // SIP Year 2 (2200/mo) ... grows...
  // The total invested is 50k + (24k + 26.4k + 29.04k) = 129,440
  assert(r3.totalInvested == 129440, 'Test 3 FAIL: Invested was ${r3.totalInvested}');
  assert(r3.finalCorpus > r3.totalInvested, 'Test 3 FAIL');
  assert(r3.projections.length == 3, 'Test 3 FAIL: Projections length should be 3');
  print('Test 3 PASS (Hybrid Step-Up) — Invested: ₹${r3.totalInvested}, Corpus: ₹${r3.finalCorpus}');

  print('\n✅ All tests passed!');
}
*/
