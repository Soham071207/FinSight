// lib/features/stocks/logic/stock_service.dart
// Calls the STOCK/stock_api.py Flask server

import 'dart:convert';
import 'package:dio/dio.dart';
import '../models/stock_result.dart';

class StockPredictResponse {
  final List<StockResult> results;
  final Map<String, String> errors;

  const StockPredictResponse({required this.results, required this.errors});

  factory StockPredictResponse.fromJson(Map<String, dynamic> j) {
    final results = ((j['results'] as List?) ?? [])
        .map((e) => StockResult.fromJson(e as Map<String, dynamic>))
        .toList();
    final errors = <String, String>{};
    final errMap = j['errors'] as Map<String, dynamic>? ?? {};
    errMap.forEach((k, v) => errors[k] = v.toString());
    return StockPredictResponse(results: results, errors: errors);
  }
}

class StockService {
  // ── Cloud / local server URL — update this to your deployed cloud URL ──────
  static const String _base = 'https://stock-prediction-api-lsvu.onrender.com';

  final Dio _dio = Dio(BaseOptions(
    baseUrl: _base,
    connectTimeout: const Duration(seconds: 8),
    receiveTimeout: const Duration(minutes: 5), // ML pipeline takes time
    headers: {'Content-Type': 'application/json'},
  ));

  /// Ping the server — returns true if available.
  Future<bool> isAvailable() async {
    try {
      final res = await _dio.get('/health');
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Run the full AI prediction pipeline for given tickers.
  Future<StockPredictResponse> predict(List<String> tickers) async {
    final res = await _dio.post('/predict',
        data: jsonEncode({'tickers': tickers}));
    return StockPredictResponse.fromJson(res.data as Map<String, dynamic>);
  }
}
