import 'dart:math' as math;

// ══════════════════════════════════════════════════════════════════════════════
// INPUT MODEL
// ══════════════════════════════════════════════════════════════════════════════

/// All inputs required by the CIBIL scoring engine.
/// Pure Dart — no Flutter dependency.
class CibilInput {
  const CibilInput({
    // Step 1 — Credit Behaviour
    required this.utilizationPct,     // 0–100
    required this.onTimePaymentPct,   // 0–100
    required this.missedPayments,     // 0–12
    required this.hardInquiries,      // 0–10
    // Step 2 — Credit Profile
    required this.creditAgeYears,     // 0–30
    required this.totalActiveAccounts,// 0–20
    required this.numCreditCards,     // 0–10
    required this.numSecuredLoans,    // 0–5
    required this.numUnsecuredLoans,  // 0–5
    required this.monthsWithEmployer, // 0-360
    required this.netMonthlyIncome,   // 0-500000
  });

  final double utilizationPct;
  final double onTimePaymentPct;
  final int    missedPayments;
  final int    hardInquiries;
  final double creditAgeYears;
  final int    totalActiveAccounts;
  final int    numCreditCards;
  final int    numSecuredLoans;
  final int    numUnsecuredLoans;
  final int    monthsWithEmployer;
  final double netMonthlyIncome;

  /// Creates a copy with selected fields overridden.
  CibilInput copyWith({
    double? utilizationPct,
    double? onTimePaymentPct,
    int? missedPayments,
    int? hardInquiries,
    double? creditAgeYears,
    int? totalActiveAccounts,
    int? numCreditCards,
    int? numSecuredLoans,
    int? numUnsecuredLoans,
    int? monthsWithEmployer,
    double? netMonthlyIncome,
  }) {
    return CibilInput(
      utilizationPct:      utilizationPct      ?? this.utilizationPct,
      onTimePaymentPct:    onTimePaymentPct    ?? this.onTimePaymentPct,
      missedPayments:      missedPayments      ?? this.missedPayments,
      hardInquiries:       hardInquiries       ?? this.hardInquiries,
      creditAgeYears:      creditAgeYears      ?? this.creditAgeYears,
      totalActiveAccounts: totalActiveAccounts ?? this.totalActiveAccounts,
      numCreditCards:      numCreditCards      ?? this.numCreditCards,
      numSecuredLoans:     numSecuredLoans     ?? this.numSecuredLoans,
      numUnsecuredLoans:   numUnsecuredLoans   ?? this.numUnsecuredLoans,
      monthsWithEmployer:  monthsWithEmployer  ?? this.monthsWithEmployer,
      netMonthlyIncome:    netMonthlyIncome    ?? this.netMonthlyIncome,
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// FACTOR SCORE
// ══════════════════════════════════════════════════════════════════════════════

/// Points earned and maximum for a single scoring factor.
class FactorScore {
  const FactorScore({
    required this.name,
    required this.earned,
    required this.max,
    this.actionHint,
  });

  final String  name;
  final double  earned;
  final double  max;

  /// Only non-null for factors scoring below 60% of their max.
  final String? actionHint;

  double get ratio => max > 0 ? earned / max : 0.0;

  /// Percentage of max points earned (0–100).
  double get pct => ratio * 100;
}

// ══════════════════════════════════════════════════════════════════════════════
// IMPROVEMENT TIP
// ══════════════════════════════════════════════════════════════════════════════

enum TipDifficulty { easy, medium, hard }

class ImprovementTip {
  const ImprovementTip({
    required this.action,
    required this.estimatedGain,
    required this.difficulty,
    required this.factorName,
  });

  /// Human-readable, quantified action string.
  final String        action;

  /// Estimated point gain if this action is taken.
  final int           estimatedGain;

  final TipDifficulty difficulty;

  /// The factor this tip improves.
  final String        factorName;
}

// ══════════════════════════════════════════════════════════════════════════════
// CIBIL BAND
// ══════════════════════════════════════════════════════════════════════════════

enum CibilBand { poor, fair, good, veryGood, excellent }

extension CibilBandExt on CibilBand {
  String get label {
    switch (this) {
      case CibilBand.poor:      return 'Poor';
      case CibilBand.fair:      return 'Fair';
      case CibilBand.good:      return 'Good';
      case CibilBand.veryGood:  return 'Very Good';
      case CibilBand.excellent: return 'Excellent';
    }
  }

  /// Band color as a raw ARGB int — avoids Flutter imports.
  /// Convert to Color(bandColorValue) in the UI layer.
  int get colorValue {
    switch (this) {
      case CibilBand.poor:      return 0xFFFF4D4F; // AppColors.danger
      case CibilBand.fair:      return 0xFFFAAD14; // AppColors.warning
      case CibilBand.good:      return 0xFF1A73E8; // AppColors.primary
      case CibilBand.veryGood:  return 0xFF00C48C; // AppColors.accent
      case CibilBand.excellent: return 0xFF00875A; // deep green
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// RESULT MODEL
// ══════════════════════════════════════════════════════════════════════════════

class CibilResult {
  const CibilResult({
    required this.totalScore,
    required this.band,
    required this.factorScores,
    required this.weakestFactor,
    required this.improvementTips,
    required this.input,
    this.isOfflineFallback = false,
  });

  final int                totalScore;
  final CibilBand          band;

  /// Ordered list of factor scores — same order as in the spec.
  final List<FactorScore>  factorScores;

  /// The factor with the lowest ratio (earned/max).
  final FactorScore        weakestFactor;

  /// Top-3 tips ranked by estimated point gain (highest first).
  final List<ImprovementTip> improvementTips;

  /// The original inputs (kept for "Recalculate with preserved inputs").
  final CibilInput input;

  /// True if calculated using the rule-based engine offline
  final bool isOfflineFallback;

  /// Convenience: normalized score progress 0.0 → 1.0 over the 300–900 range.
  double get progress => (totalScore - 300) / 600.0;
}

// ══════════════════════════════════════════════════════════════════════════════
// CALCULATOR ENGINE
// ══════════════════════════════════════════════════════════════════════════════

/// Pure Dart CIBIL scoring engine.
///
/// No Flutter imports — fully unit-testable in isolation.
///
/// Usage:
///   final result = CibilCalculator.calculate(input);
///   print(result.totalScore); // e.g. 742
class CibilCalculator {
  CibilCalculator._(); // static-only class

  // ── Factor max points ─────────────────────────────────────────────────────
  static const double _maxPayment     = 210;
  static const double _maxUtilization = 180;
  static const double _maxAge         = 90;
  static const double _maxMix         = 60;
  static const double _maxInquiries   = 60;
  static const double _baseScore      = 300;

  // ── Factor names (used as keys everywhere) ────────────────────────────────
  static const String kPayment     = 'Payment History';
  static const String kUtilization = 'Credit Utilization';
  static const String kAge         = 'Credit Age';
  static const String kMix         = 'Credit Mix';
  static const String kInquiries   = 'New Inquiries';

  // ── Public entry point ────────────────────────────────────────────────────

  static CibilResult calculate(CibilInput input) {
    final payment     = _paymentScore(input);
    final utilization = _utilizationScore(input);
    final age         = _ageScore(input);
    final mix         = _mixScore(input);
    final inquiries   = _inquiryScore(input);

    final total = (_baseScore +
            payment.earned +
            utilization.earned +
            age.earned +
            mix.earned +
            inquiries.earned)
        .round()
        .clamp(300, 900);

    final factors = [payment, utilization, age, mix, inquiries];

    final weakest = factors.reduce(
      (a, b) => a.ratio < b.ratio ? a : b,
    );

    final tips = _generateTips(input, factors);

    return CibilResult(
      totalScore: total,
      band: _band(total),
      factorScores: factors,
      weakestFactor: weakest,
      improvementTips: tips,
      input: input,
      isOfflineFallback: true, // Internal Dart calculation is considered offline fallback
    );
  }

  // ── Factor 1: Payment History (0–210) ────────────────────────────────────

  static FactorScore _paymentScore(CibilInput i) {
    final base    = i.onTimePaymentPct * 2.1;
    final penalty = i.missedPayments * 15.0;
    final earned  = (base - penalty).clamp(0.0, _maxPayment).toDouble();

    String? hint;
    if (earned / _maxPayment < 0.60) {
      if (i.missedPayments > 0) {
        hint = 'Make all payments on time for the next 6 months '
            '→ estimated +${(i.missedPayments * 12).clamp(0, 60)} pts';
      } else {
        hint = 'Increase on-time payment rate to > 95% → estimated +30 pts';
      }
    }

    return FactorScore(
      name: kPayment, earned: earned, max: _maxPayment, actionHint: hint,
    );
  }

  // ── Factor 2: Credit Utilization (0–180) ─────────────────────────────────

  static FactorScore _utilizationScore(CibilInput i) {
    final u = i.utilizationPct;
    double earned;

    if (u <= 10) {
      earned = 180;
    } else if (u <= 30) {
      earned = 180 - ((u - 10) / 20 * 40);
    } else if (u <= 50) {
      earned = 140 - ((u - 30) / 20 * 60);
    } else if (u <= 75) {
      earned = 80  - ((u - 50) / 25 * 50);
    } else {
      earned = math.max(0, 30 - ((u - 75) / 25 * 30));
    }

    final clamped = earned.clamp(0.0, _maxUtilization).toDouble();

    String? hint;
    if (clamped / _maxUtilization < 0.60) {
      const target = 30.0;
      final gain   = (_utilizationRaw(target) - clamped).round().clamp(0, 180);
      hint = 'Reduce utilization from ${u.toStringAsFixed(0)}% to 30% '
          '→ estimated +$gain pts';
    }

    return FactorScore(
      name: kUtilization, earned: clamped, max: _maxUtilization,
      actionHint: hint,
    );
  }

  static double _utilizationRaw(double u) {
    if (u <= 10) return 180;
    if (u <= 30) return 180 - ((u - 10) / 20 * 40);
    return 140 - ((u - 30) / 20 * 60);
  }

  // ── Factor 3: Credit Age (0–90) ───────────────────────────────────────────

  static FactorScore _ageScore(CibilInput i) {
    final earned = (i.creditAgeYears * 6).clamp(0.0, _maxAge).toDouble();

    String? hint;
    if (earned / _maxAge < 0.60) {
      final needed = ((0.60 * _maxAge) - earned) / 6;
      hint = 'Keep oldest account open — age increases naturally '
          '(need ~${needed.ceil()} more years for Good)';
    }

    return FactorScore(
      name: kAge, earned: earned, max: _maxAge, actionHint: hint,
    );
  }

  // ── Factor 4: Credit Mix (0–60) ───────────────────────────────────────────

  static FactorScore _mixScore(CibilInput i) {
    final hasCards      = i.numCreditCards      > 0 ? 1 : 0;
    final hasSecured    = i.numSecuredLoans     > 0 ? 1 : 0;
    final hasUnsecured  = i.numUnsecuredLoans   > 0 ? 1 : 0;
    final diversity     = hasCards + hasSecured + hasUnsecured;
    final earned        = (diversity * 20).toDouble();

    String? hint;
    if (earned / _maxMix < 0.60) {
      final missing = <String>[];
      if (hasCards == 0)     missing.add('a credit card');
      if (hasSecured == 0)   missing.add('a secured loan');
      if (hasUnsecured == 0) missing.add('an unsecured loan');
      if (missing.isNotEmpty) {
        hint = 'Add ${missing.first} to diversify credit mix → +20 pts';
      }
    }

    return FactorScore(
      name: kMix, earned: earned, max: _maxMix, actionHint: hint,
    );
  }

  // ── Factor 5: New Inquiries (0–60) ────────────────────────────────────────

  static FactorScore _inquiryScore(CibilInput i) {
    final earned = (60 - i.hardInquiries * 10.0).clamp(0.0, _maxInquiries).toDouble();

    String? hint;
    if (earned / _maxInquiries < 0.60) {
      final gain = (_maxInquiries - earned).round();
      hint = 'Avoid new loan applications for 6 months → estimated +$gain pts';
    }

    return FactorScore(
      name: kInquiries, earned: earned, max: _maxInquiries,
      actionHint: hint,
    );
  }

  // ── Band classification ───────────────────────────────────────────────────

  static CibilBand _band(int score) {
    if (score >= 850) return CibilBand.excellent;
    if (score >= 750) return CibilBand.veryGood;
    if (score >= 650) return CibilBand.good;
    if (score >= 550) return CibilBand.fair;
    return CibilBand.poor;
  }

  // ── Improvement tips ──────────────────────────────────────────────────────

  /// Generates ranked tips (up to 3) for factors with the most room to grow.
  static List<ImprovementTip> _generateTips(
    CibilInput input,
    List<FactorScore> factors,
  ) {
    final tips = <ImprovementTip>[];

    // ── Tip from Payment History ──────────────────────────────────────────
    final payment = factors.firstWhere((f) => f.name == kPayment);
    if (payment.ratio < 1.0) {
      if (input.missedPayments > 0) {
        final gain = math.min(
          (input.missedPayments * 15).round(), 
          (_maxPayment - payment.earned).round(),
        );
        tips.add(ImprovementTip(
          factorName: kPayment,
          action: 'No missed payments for 6 months → estimated +$gain pts',
          estimatedGain: gain,
          difficulty: TipDifficulty.medium,
        ));
      } else if (input.onTimePaymentPct < 95) {
        final gain = ((95 - input.onTimePaymentPct) * 2.1).round().clamp(0, 50);
        tips.add(ImprovementTip(
          factorName: kPayment,
          action: 'Raise on-time payments from '
              '${input.onTimePaymentPct.toStringAsFixed(0)}% to 95% '
              '→ estimated +$gain pts',
          estimatedGain: gain,
          difficulty: TipDifficulty.medium,
        ));
      }
    }

    // ── Tip from Credit Utilization ───────────────────────────────────────
    final util = factors.firstWhere((f) => f.name == kUtilization);
    if (input.utilizationPct > 30) {
      final currentScore = util.earned;
      final targetScore  = _utilizationRaw(30);
      final gain         = (targetScore - currentScore).round().clamp(0, 180);
      tips.add(ImprovementTip(
        factorName: kUtilization,
        action: 'Reduce utilization from '
            '${input.utilizationPct.toStringAsFixed(0)}% to 30% '
            '→ estimated +$gain pts',
        estimatedGain: gain,
        difficulty: input.utilizationPct > 75
            ? TipDifficulty.hard
            : TipDifficulty.medium,
      ));
    }

    // ── Tip from New Inquiries ────────────────────────────────────────────
    final inq = factors.firstWhere((f) => f.name == kInquiries);
    if (input.hardInquiries > 0) {
      final gain = math.min(input.hardInquiries * 10, 60);
      tips.add(ImprovementTip(
        factorName: kInquiries,
        action: 'No new loan applications for 6 months → +$gain pts',
        estimatedGain: gain,
        difficulty: TipDifficulty.easy,
      ));
    }

    // ── Tip from Credit Mix ───────────────────────────────────────────────
    final mix = factors.firstWhere((f) => f.name == kMix);
    if (mix.earned < _maxMix) {
      final gain = (_maxMix - mix.earned).round();
      final missing = <String>[];
      if (input.numCreditCards   == 0) missing.add('credit card');
      if (input.numSecuredLoans  == 0) missing.add('secured loan');
      if (input.numUnsecuredLoans == 0) missing.add('personal loan');
      if (missing.isNotEmpty) {
        tips.add(ImprovementTip(
          factorName: kMix,
          action: 'Open a ${missing.first} to diversify mix → +$gain pts',
          estimatedGain: gain,
          difficulty: TipDifficulty.hard,
        ));
      }
    }

    // ── Tip from Credit Age ───────────────────────────────────────────────
    final age = factors.firstWhere((f) => f.name == kAge);
    if (age.ratio < 0.5) {
      final gain = ((_maxAge * 0.5) - age.earned).round().clamp(0, 45);
      tips.add(ImprovementTip(
        factorName: kAge,
        action: 'Keep your oldest credit account open — '
            'age will build naturally → +$gain pts over time',
        estimatedGain: gain,
        difficulty: TipDifficulty.easy,
      ));
    }

    // Sort by estimated gain descending, return top 3.
    tips.sort((a, b) => b.estimatedGain.compareTo(a.estimatedGain));
    return tips.take(3).toList();
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// UNIT TEST CASES (manual verification — run with: dart lib/.../cibil_calculator.dart)
// ══════════════════════════════════════════════════════════════════════════════

/*
void main() {
  // ── Test 1: Perfect inputs → score near 900 ───────────────────────────────
  final perfect = CibilInput(
    utilizationPct:      5,     // ≤10% → full 180
    onTimePaymentPct:    100,   // 100×2.1 = 210, 0 penalty → 210
    missedPayments:      0,
    hardInquiries:       0,     // 60 - 0 = 60
    creditAgeYears:      15,    // 15×6 = 90 (capped at 90)
    totalActiveAccounts: 5,
    numCreditCards:      2,     // has all 3 types → 60
    numSecuredLoans:     1,
    numUnsecuredLoans:   1,
  );
  final r1 = CibilCalculator.calculate(perfect);
  assert(r1.totalScore == 900,
      'Test 1 FAIL: expected 900, got ${r1.totalScore}');
  assert(r1.band == CibilBand.excellent,
      'Test 1 FAIL: expected Excellent, got ${r1.band.label}');
  print('Test 1 PASS — score: ${r1.totalScore} (${r1.band.label})');

  // ── Test 2: High utilization + missed payments → score < 550 (Poor) ───────
  final poor = CibilInput(
    utilizationPct:      90,    // >75% → near 0
    onTimePaymentPct:    60,    // 60×2.1=126, minus 5×15=75 → 51
    missedPayments:      5,
    hardInquiries:       6,     // 60-60=0 (clamped)
    creditAgeYears:      0,     // 0
    totalActiveAccounts: 2,
    numCreditCards:      0,     // all 0 → mix = 0
    numSecuredLoans:     0,
    numUnsecuredLoans:   0,
  );
  final r2 = CibilCalculator.calculate(poor);
  assert(r2.totalScore < 550,
      'Test 2 FAIL: expected < 550, got ${r2.totalScore}');
  assert(r2.band == CibilBand.poor || r2.band == CibilBand.fair,
      'Test 2 FAIL: expected Poor/Fair, got ${r2.band.label}');
  print('Test 2 PASS — score: ${r2.totalScore} (${r2.band.label})');

  // ── Test 3: Mid-range inputs → score 650–750 ─────────────────────────────
  final mid = CibilInput(
    utilizationPct:      35,    // ~120 pts
    onTimePaymentPct:    90,    // 90×2.1=189 minus 1×15=15 → 174
    missedPayments:      1,
    hardInquiries:       2,     // 60-20=40
    creditAgeYears:      7,     // 7×6=42
    totalActiveAccounts: 4,
    numCreditCards:      1,     // cards+secured → 40
    numSecuredLoans:     1,
    numUnsecuredLoans:   0,
  );
  final r3 = CibilCalculator.calculate(mid);
  assert(r3.totalScore >= 650 && r3.totalScore <= 750,
      'Test 3 FAIL: expected 650–750, got ${r3.totalScore}');
  print('Test 3 PASS — score: ${r3.totalScore} (${r3.band.label})');

  // ── Test 4: Utilization boundary check (exactly 30%) ─────────────────────
  final boundary = CibilInput(
    utilizationPct: 30, onTimePaymentPct: 100, missedPayments: 0,
    hardInquiries: 0, creditAgeYears: 15, totalActiveAccounts: 3,
    numCreditCards: 1, numSecuredLoans: 1, numUnsecuredLoans: 1,
  );
  final r4 = CibilCalculator.calculate(boundary);
  // utilization@30% = 180 - ((30-10)/20 × 40) = 180 - 40 = 140
  // total = 300+210+140+90+60+60 = 860 → Excellent
  assert(r4.totalScore == 860,
      'Test 4 FAIL: expected 860, got ${r4.totalScore}');
  print('Test 4 PASS — score: ${r4.totalScore} boundary check ✓');

  // ── Test 5: Improvement tips ranked by gain ───────────────────────────────
  final tipsTest = CibilInput(
    utilizationPct: 80, onTimePaymentPct: 70, missedPayments: 3,
    hardInquiries: 4, creditAgeYears: 3, totalActiveAccounts: 2,
    numCreditCards: 0, numSecuredLoans: 0, numUnsecuredLoans: 0,
  );
  final r5 = CibilCalculator.calculate(tipsTest);
  assert(r5.improvementTips.isNotEmpty, 'Test 5 FAIL: no tips generated');
  assert(r5.improvementTips.length <= 3, 'Test 5 FAIL: more than 3 tips');
  final sorted = r5.improvementTips;
  for (int i = 0; i < sorted.length - 1; i++) {
    assert(sorted[i].estimatedGain >= sorted[i + 1].estimatedGain,
        'Test 5 FAIL: tips not sorted by gain descending');
  }
  print('Test 5 PASS — ${r5.improvementTips.length} tips, '
        'top: "${r5.improvementTips.first.action}"');

  print('\n✅ All tests passed!');
}
*/
