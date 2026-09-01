// lib/features/funds/logic/fund_analysis_service.dart
// Calls the local mutual_2_api.py Flask server at localhost:5050

import 'dart:convert';
import 'package:dio/dio.dart';

class FundSearchResult {
  final String code;
  final String name;
  const FundSearchResult({required this.code, required this.name});

  factory FundSearchResult.fromJson(Map<String, dynamic> j) =>
      FundSearchResult(code: j['code'] as String, name: j['name'] as String);
}

class LiveFundResult {
  final int rank;
  final String key;
  final String name;
  final String fundHouse;
  final String category;
  final String expenseRatio;
  final String startDate;
  final String endDate;
  final double durationYears;
  final double invested;
  final double finalValue;
  final double wealthGain;
  final double absReturn;
  final double cagr;
  final double xirr;
  final double maxDrawdown;
  final double volatility;
  final int riskScore;
  final double sortino;
  final double beta;
  final double alpha;
  final double futureInvested;
  final double futureValue;
  final double futureWealthGain;
  final List<String> navDates;
  final List<double> navValues;
  final List<double> valHistSampled;
  final double score;

  const LiveFundResult({
    required this.rank,
    required this.key,
    required this.name,
    required this.fundHouse,
    required this.category,
    required this.expenseRatio,
    required this.startDate,
    required this.endDate,
    required this.durationYears,
    required this.invested,
    required this.finalValue,
    required this.wealthGain,
    required this.absReturn,
    required this.cagr,
    required this.xirr,
    required this.maxDrawdown,
    required this.volatility,
    required this.riskScore,
    required this.sortino,
    required this.beta,
    required this.alpha,
    required this.futureInvested,
    required this.futureValue,
    required this.futureWealthGain,
    required this.navDates,
    required this.navValues,
    required this.valHistSampled,
    required this.score,
  });

  factory LiveFundResult.fromJson(Map<String, dynamic> j) {
    double d(String k) => (j[k] as num?)?.toDouble() ?? 0.0;
    return LiveFundResult(
      rank:             (j['rank'] as num).toInt(),
      key:              j['key'] as String,
      name:             j['name'] as String,
      fundHouse:        j['fundHouse'] as String,
      category:         j['category'] as String,
      expenseRatio:     j['expenseRatio'] as String,
      startDate:        j['startDate'] as String,
      endDate:          j['endDate'] as String,
      durationYears:    d('durationYears'),
      invested:         d('invested'),
      finalValue:       d('finalValue'),
      wealthGain:       d('wealthGain'),
      absReturn:        d('absReturn'),
      cagr:             d('cagr'),
      xirr:             d('xirr'),
      maxDrawdown:      d('maxDrawdown'),
      volatility:       d('volatility'),
      riskScore:        (j['riskScore'] as num?)?.toInt() ?? 5,
      sortino:          d('sortino'),
      beta:             d('beta'),
      alpha:            d('alpha'),
      futureInvested:   d('futureInvested'),
      futureValue:      d('futureValue'),
      futureWealthGain: d('futureWealthGain'),
      navDates:         List<String>.from(j['navDates'] as List),
      navValues:        (j['navValues'] as List).map((e) => (e as num).toDouble()).toList(),
      valHistSampled:   (j['valHistSampled'] as List).map((e) => (e as num).toDouble()).toList(),
      score:            d('score'),
    );
  }
}

class AnalysisResponse {
  final int mode;
  final double actualYears;
  final double futureYears;
  final String benchmarkKey;
  final List<LiveFundResult> results;

  const AnalysisResponse({
    required this.mode,
    required this.actualYears,
    required this.futureYears,
    required this.benchmarkKey,
    required this.results,
  });

  factory AnalysisResponse.fromJson(Map<String, dynamic> j) {
    return AnalysisResponse(
      mode:         (j['mode'] as num).toInt(),
      actualYears:  (j['actualYears'] as num).toDouble(),
      futureYears:  (j['futureYears'] as num).toDouble(),
      benchmarkKey: j['benchmarkKey'] as String,
      results:      (j['results'] as List)
                        .map((e) => LiveFundResult.fromJson(e as Map<String, dynamic>))
                        .toList(),
    );
  }
}

class FundAnalysisService {
  static const String _base = 'https://mutual-funds-api-5vvi.onrender.com';

  late final Dio _dio;

  FundAnalysisService() {
    _dio = Dio(BaseOptions(
      baseUrl: _base,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(minutes: 3), // analysis can take time
      headers: {'Content-Type': 'application/json'},
      // Receive raw string so we can sanitize NaN before JSON decoding
      responseType: ResponseType.plain,
    ));
  }

  /// Sanitize a JSON string from the server: replace NaN / Infinity with 0.
  /// The Render server's compute_metrics can produce NaN for SIP mode when
  /// portfolio value starts at 0, causing Dart's JSON parser to crash.
  dynamic _safeDecode(dynamic data) {
    if (data is String) {
      // Replace JSON-illegal NaN and Infinity values with 0.
      // Use word-boundary matching to avoid mangling fund names.
      final sanitized = data
          .replaceAll(RegExp(r'(?<=[\s,:\[])NaN(?=[\s,}\]])'), '0')
          .replaceAll(RegExp(r'(?<=[\s,:\[])-?Infinity(?=[\s,}\]])'), '0')
          // Also handle : NaN at end of number position (e.g. "key":NaN)
          .replaceAll(RegExp(r':NaN([,}\]])'), ':0\$1')
          .replaceAll(RegExp(r':-?Infinity([,}\]])'), ':0\$1');
      return jsonDecode(sanitized);
    }
    return data;
  }

  /// Ping the server — returns true if the API is available.
  Future<bool> isApiAvailable() async {
    try {
      final res = await _dio.get('/health');
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Search AMFI database for fund names matching [keyword].
  Future<List<FundSearchResult>> search(String keyword) async {
    final res = await _dio.post('/search', data: jsonEncode({'keyword': keyword}));
    final decoded = _safeDecode(res.data) as Map<String, dynamic>;
    final list = (decoded['results'] as List);
    return list.map((e) => FundSearchResult.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Run the full backtest + future projection for the given assets.
  Future<AnalysisResponse> analyze({
    required List<String> assets,
    required int invMode,
    required double baseSip,
    required double stepUpPct,
    required double lumpsumAmt,
    required double targetYears,
    required double futureYears,
  }) async {
    final res = await _dio.post('/analyze', data: jsonEncode({
      'assets':       assets,
      'inv_mode':     invMode,
      'base_sip':     baseSip,
      'step_up_pct':  stepUpPct,
      'lumpsum_amt':  lumpsumAmt,
      'target_years': targetYears,
      'future_years': futureYears,
    }));
    final decoded = _safeDecode(res.data) as Map<String, dynamic>;
    return AnalysisResponse.fromJson(decoded);
  }
}
