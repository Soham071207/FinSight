import 'dart:math' as math;
import '../../../data/local/models/expense_entry.dart';

// ══════════════════════════════════════════════════════════════════════════════
// MODELS
// ══════════════════════════════════════════════════════════════════════════════

class InvestmentSuggestion {
  const InvestmentSuggestion({
    required this.category,
    required this.icon,
    required this.excessAmount,
    required this.instrument,
    required this.rate,
    required this.years,
    required this.projectedWealth,
    required this.displayWealth,
    required this.cardText,
    required this.simulatorParams,
  });

  final String category;
  final String icon;
  final double excessAmount;
  final String instrument;
  final double rate;
  final int years;
  final double projectedWealth;
  final String displayWealth;
  final String cardText;
  final Map<String, dynamic> simulatorParams;
}

class _Mapping {
  const _Mapping(this.icon, this.instrument, this.ratePct, this.years, this.rateType);
  final String icon;
  final String instrument;
  final double ratePct;
  final int years;
  final String rateType;
}

// ══════════════════════════════════════════════════════════════════════════════
// ADVISOR ENGINE
// ══════════════════════════════════════════════════════════════════════════════

class InvestmentAdvisor {
  InvestmentAdvisor._();

  static double _sipFv(double p, double r, int t) {
    if (p <= 0 || t <= 0) return 0;
    final rMonthly = r / 12.0;
    final months = t * 12;
    // Formula: P × [((1 + r/12)^(12×t) - 1) / (r/12)] × (1 + r/12)
    final fv = p * ((math.pow(1 + rMonthly, months) - 1) / rMonthly) * (1 + rMonthly);
    return (fv / 100).round() * 100.0;
  }

  static String _formatWealth(double fv) {
    if (fv > 99999) {
      return '₹${(fv / 100000).toStringAsFixed(2)}L';
    } else {
      final intValue = fv.toInt();
      final str = intValue.toString().replaceAllMapped(
          RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'), (Match m) => '${m[1]},');
      return '₹$str';
    }
  }

  static List<InvestmentSuggestion> analyze(List<ExpenseEntry> allEntries, {double income = 20000.0}) {
    if (allEntries.isEmpty) return [];

    final sorted = List<ExpenseEntry>.from(allEntries)
      ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
      
    final now = sorted.first.timestamp;
    final thirtyDaysAgo = now.subtract(const Duration(days: 30));

    final cat30 = <String, double>{};
    for (final e in sorted) {
      if (e.timestamp.isAfter(thirtyDaysAgo)) {
        final c = e.category.trim();
        cat30[c] = (cat30[c] ?? 0) + e.amount;
      }
    }

    final thresholds = {
      'Food & Dining': 0.15,
      'Food': 0.15,
      'Shopping': 0.08,
      'Subscriptions': 0.03,
      'Transport': 0.08,
      'Entertainment': 0.05,
      'Travel': 0.10,
      'Utilities': 0.05,
      'Online Orders': 0.05,
      'Medical': 0.04,
      'Education': 0.03,
    };

    final mappings = {
      'Food & Dining': const _Mapping('🍽️', 'PPF', 7.1, 15, 'p.a.'),
      'Food': const _Mapping('🍽️', 'PPF', 7.1, 15, 'p.a.'),
      'Shopping': const _Mapping('🛍️', 'Liquid Fund', 6.5, 1, 'p.a.'),
      'Subscriptions': const _Mapping('📱', 'Flexi-cap SIP', 12.0, 5, 'CAGR'),
      'Transport': const _Mapping('🚗', 'Recurring Deposit', 7.0, 2, 'p.a.'),
      'Entertainment': const _Mapping('🎬', 'Index Fund (Nifty 50)', 11.0, 7, 'CAGR'),
      'Travel': const _Mapping('✈️', 'ELSS', 13.0, 3, 'CAGR'),
      'Utilities': const _Mapping('⚡', 'Sovereign Gold Bond', 8.5, 8, 'p.a.'),
      'Online Orders': const _Mapping('📦', 'Arbitrage Fund', 7.5, 1, 'p.a.'),
      'Medical': const _Mapping('🏥', 'Term Insurance Corpus', 10.0, 10, 'CAGR'),
      'Education': const _Mapping('📚', 'NPS', 10.0, 20, 'CAGR'),
    };

    final suggestions = <InvestmentSuggestion>[];

    for (final entry in cat30.entries) {
      final category = entry.key;
      final actualSpend = entry.value;

      double? thresholdPct;
      _Mapping? mapping;
      
      for (final key in thresholds.keys) {
        if (key.toLowerCase() == category.toLowerCase()) {
          thresholdPct = thresholds[key]!;
          mapping = mappings[key]!;
          break;
        }
      }

      if (thresholdPct == null || mapping == null) continue;

      final limit = income * thresholdPct;
      if (actualSpend > limit) {
        final excess = actualSpend - limit;
        final fv = _sipFv(excess, mapping.ratePct / 100.0, mapping.years);
        final display = _formatWealth(fv);

        final pctString = (thresholdPct * 100).toInt().toString();
        final rateStr = mapping.ratePct == mapping.ratePct.toInt() 
            ? mapping.ratePct.toInt().toString() 
            : mapping.ratePct.toString();
        
        final cardText = "Your ${category.toLowerCase()} spend is ₹${excess.toInt()} above a healthy $pctString% threshold. "
            "Parking this in a ${mapping.instrument} for ${mapping.years} year${mapping.years > 1 ? 's' : ''} at $rateStr% ${mapping.rateType} could return an illustrative $display.";

        suggestions.add(InvestmentSuggestion(
          category: category,
          icon: mapping.icon,
          excessAmount: excess,
          instrument: mapping.instrument,
          rate: mapping.ratePct,
          years: mapping.years,
          projectedWealth: fv,
          displayWealth: display,
          cardText: cardText,
          simulatorParams: {'mode': 'SIP', 'monthly': excess.toInt(), 'years': mapping.years, 'cagr': mapping.ratePct},
        ));
      }
    }

    suggestions.sort((a, b) => b.projectedWealth.compareTo(a.projectedWealth));
    return suggestions.take(6).toList();
  }
}
