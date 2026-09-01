import 'dart:convert';
import 'package:dio/dio.dart';
import 'cibil_calculator.dart';

class CibilService {
  static const String _base = 'https://mutual-funds-api-5vvi.onrender.com';

  static final Dio _dio = Dio(BaseOptions(
    baseUrl: _base,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
    headers: {'Content-Type': 'application/json'},
  ));

  /// Calls the ML /predict-cibil API. Returns null if it fails (so we can fallback).
  static Future<CibilResult?> predictCibil(CibilInput input) async {
    try {
      // Map Dart form inputs to ML model features
      final requestData = {
        'age_oldest_tl': (input.creditAgeYears * 12).toInt(),
        'age_newest_tl': (input.creditAgeYears * 12 * 0.3).toInt(), // Approximation
        'time_since_recent_enq': _mapInquiriesToMonths(input.hardInquiries),
        'time_since_recent_payment': input.onTimePaymentPct >= 100 ? 30 : 90,
        'max_recent_level_of_deliq': _mapMissedPaymentsToDeliq(input.missedPayments),
        'recent_level_of_deliq': _mapMissedPaymentsToDeliq(input.missedPayments),
        'time_with_curr_empr': input.monthsWithEmployer,
        'num_std_12mts': input.totalActiveAccounts,
        'enq_l3m': input.hardInquiries,
        'netmonthlyincome': input.netMonthlyIncome,
      };

      final response = await _dio.post('/predict-cibil', data: jsonEncode(requestData));

      if (response.statusCode == 200) {
        final data = response.data;
        
        // Parse the API response to construct CibilResult
        final int score = data['cibil_score'] as int;
        
        // Map the band string from API to CibilBand enum
        final String bandStr = data['band'] as String;
        CibilBand band = _parseBand(bandStr);

        // Map improvement tips
        final List<ImprovementTip> tips = [];
        if (data['improvement_tips'] != null) {
          for (var tipStr in data['improvement_tips']) {
            tips.add(ImprovementTip(
              action: tipStr.toString(),
              estimatedGain: 10, // API doesn't provide exact gain, use default
              difficulty: TipDifficulty.medium,
              factorName: 'General',
            ));
          }
        }

        // We construct a mock FactorScore list to satisfy the UI since ML model
        // doesn't return exact factor breakdowns like the rule-based one.
        // We'll generate a plausible breakdown based on the final score.
        final factors = _generateMockFactors(score);
        final weakest = factors.reduce((a, b) => a.ratio < b.ratio ? a : b);

        return CibilResult(
          totalScore: score,
          band: band,
          factorScores: factors,
          weakestFactor: weakest,
          improvementTips: tips,
          input: input,
          isOfflineFallback: false,
        );
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  static int _mapInquiriesToMonths(int hardInquiries) {
    if (hardInquiries == 0) return 12;
    if (hardInquiries == 1) return 6;
    if (hardInquiries == 2) return 3;
    return 1;
  }

  static int _mapMissedPaymentsToDeliq(int missedPayments) {
    if (missedPayments == 0) return 0;
    if (missedPayments <= 3) return 1;
    return 2;
  }

  static CibilBand _parseBand(String bandStr) {
    final lower = bandStr.toLowerCase();
    if (lower.contains('excellent')) return CibilBand.excellent;
    if (lower.contains('very good')) return CibilBand.veryGood;
    if (lower.contains('good')) return CibilBand.good;
    if (lower.contains('fair')) return CibilBand.fair;
    return CibilBand.poor;
  }

  static List<FactorScore> _generateMockFactors(int score) {
    // A simple heuristic to distribute points
    double p = (score - 300) / 600.0;
    p = p.clamp(0.0, 1.0);

    return [
      FactorScore(name: CibilCalculator.kPayment, earned: 210 * p, max: 210),
      FactorScore(name: CibilCalculator.kUtilization, earned: 180 * p, max: 180),
      FactorScore(name: CibilCalculator.kAge, earned: 90 * p, max: 90),
      FactorScore(name: CibilCalculator.kMix, earned: 60 * p, max: 60),
      FactorScore(name: CibilCalculator.kInquiries, earned: 60 * p, max: 60),
    ];
  }
}
