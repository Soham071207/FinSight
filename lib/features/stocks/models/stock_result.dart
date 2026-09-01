// lib/features/stocks/models/stock_result.dart

class StockResult {
  final String ticker;
  final String market;
  final String currency;
  final String currencySymbol;
  final String signal; // "BUY" | "SELL" | "HOLD"
  final double confidence;
  final String regimeLabel;
  final double entryPrice;
  final double stopLoss;
  final double targetPrice;
  final double riskReward;
  final String sentimentLabel; // "Bullish" | "Bearish" | "Neutral"
  final double sentimentScore;
  final String topHeadline;
  final String topLink;
  final double backtestReturn;
  final double backtestSharpe;
  final double maxDrawdown;
  final double winRate;
  final String chartEquity;
  final String chartSharpe;
  final String chartSentiment;
  final String chartImportance;

  const StockResult({
    required this.ticker,
    required this.market,
    required this.currency,
    required this.currencySymbol,
    required this.signal,
    required this.confidence,
    required this.regimeLabel,
    required this.entryPrice,
    required this.stopLoss,
    required this.targetPrice,
    required this.riskReward,
    required this.sentimentLabel,
    required this.sentimentScore,
    required this.topHeadline,
    required this.topLink,
    required this.backtestReturn,
    required this.backtestSharpe,
    required this.maxDrawdown,
    required this.winRate,
    required this.chartEquity,
    required this.chartSharpe,
    required this.chartSentiment,
    required this.chartImportance,
  });

  factory StockResult.fromJson(Map<String, dynamic> j) {
    double d(String k) => (j[k] as num?)?.toDouble() ?? 0.0;
    return StockResult(
      ticker:          j['ticker'] as String? ?? '',
      market:          j['market'] as String? ?? '',
      currency:        j['currency'] as String? ?? 'USD',
      currencySymbol:  j['currencySymbol'] as String? ?? '\$',
      signal:          j['signal'] as String? ?? 'HOLD',
      confidence:      d('confidence'),
      regimeLabel:     j['regimeLabel'] as String? ?? '',
      entryPrice:      d('entryPrice'),
      stopLoss:        d('stopLoss'),
      targetPrice:     d('targetPrice'),
      riskReward:      d('riskReward'),
      sentimentLabel:  j['sentimentLabel'] as String? ?? 'Neutral',
      sentimentScore:  d('sentimentScore'),
      topHeadline:     j['topHeadline'] as String? ?? '',
      topLink:         j['topLink'] as String? ?? '',
      backtestReturn:  d('backtestReturn'),
      backtestSharpe:  d('backtestSharpe'),
      maxDrawdown:     d('maxDrawdown'),
      winRate:         d('winRate'),
      chartEquity:     j['chartEquity'] as String? ?? '',
      chartSharpe:     j['chartSharpe'] as String? ?? '',
      chartSentiment:  j['chartSentiment'] as String? ?? '',
      chartImportance: j['chartImportance'] as String? ?? '',
    );
  }
}
