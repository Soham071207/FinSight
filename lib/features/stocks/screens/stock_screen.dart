import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// lib/features/stocks/screens/stock_screen.dart
// AI Stock Prediction — powered by STOCK/stock_api.py

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../shared/widgets/app_button.dart';
import '../logic/stock_service.dart';
import '../models/stock_result.dart';

// ── Providers ─────────────────────────────────────────────────────────────────

final _stockService = StockService();

final _stockApiAvailableProvider =
    FutureProvider<bool>((ref) => _stockService.isAvailable());

// ══════════════════════════════════════════════════════════════════════════════
// SCREEN
// ══════════════════════════════════════════════════════════════════════════════

class StockScreen extends ConsumerStatefulWidget {
  const StockScreen({super.key});

  @override
  ConsumerState<StockScreen> createState() => _StockScreenState();
}

class _StockScreenState extends ConsumerState<StockScreen> {
  final _ctrl = TextEditingController();
  final List<String> _tickers = [];

  bool _isAnalyzing = false;
  String? _error;
  StockPredictResponse? _result;

  static const _examples = [
    'RELIANCE.NS',
    'TCS.NS',
    'INFY.NS',
    'AAPL',
    'MSFT',
    'GOOGL',
    'HSBA.L',
    'VOD.L',
  ];

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _addTicker() {
    final t = _ctrl.text.trim().toUpperCase();
    if (t.isEmpty) return;
    if (_tickers.contains(t)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Ticker already added')));
      return;
    }
    if (_tickers.length >= 5) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Maximum 5 tickers at a time')));
      return;
    }
    setState(() {
      _tickers.add(t);
      _ctrl.clear();
    });
  }

  Future<void> _runAnalysis() async {
    if (_tickers.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add at least one ticker to analyze')));
      return;
    }
    setState(() {
      _isAnalyzing = true;
      _error = null;
      _result = null;
    });
    try {
      final res = await _stockService.predict(_tickers);
      setState(() => _result = res);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _isAnalyzing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final apiAsync = ref.watch(_stockApiAvailableProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Column(
          children: [
            Text('AI Stock Analysis', style: AppText.heading2),
            Text('Powered by LSTM + LightGBM + GARCH',
                style: AppText.caption.copyWith(color: AppColors.accent)),
          ],
        ),
      ),
      body: apiAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => _buildOffline(),
        data: (available) =>
            available ? _buildContent() : _buildOffline(),
      ),
    );
  }

  // ── Server Offline ────────────────────────────────────────────────────────

  Widget _buildOffline() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppColors.danger.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.cloud_off_rounded,
                  size: 40, color: AppColors.danger),
            ),
            const SizedBox(height: 24),
            Text('Stock Analysis Server Offline', style: AppText.heading2),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('To start the server:', style: AppText.bodyBold),
                  const SizedBox(height: 10),
                  const _CodeStep(step: '1', code: 'cd STOCK/'),
                  const SizedBox(height: 6),
                  const _CodeStep(step: '2', code: 'pip install flask flask-cors'),
                  const SizedBox(height: 6),
                  const _CodeStep(step: '3', code: 'python stock_api.py'),
                  const SizedBox(height: 10),
                  Text(
                    'The server runs on port 5051. Keep that terminal open.',
                    style: AppText.caption.copyWith(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            AppButton(
              label: 'Retry Connection',
              onPressed: () => ref.refresh(_stockApiAvailableProvider),
            ),
          ],
        ),
      ),
    );
  }

  // ── Main Content ─────────────────────────────────────────────────────────

  Widget _buildContent() {
    if (_result != null) return _buildResults();
    return _buildForm();
  }

  Widget _buildForm() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header info card ──────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppColors.primary.withValues(alpha: 0.08),
                  AppColors.accent.withValues(alpha: 0.06),
                ],
              ),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
            ),
            child: Row(
              children: [
                const Text('🤖', style: TextStyle(fontSize: 28)),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Multi-Model AI Engine', style: AppText.bodyBold),
                      const SizedBox(height: 2),
                      Text(
                        'LSTM (deep learning) + LightGBM (regime-aware) + GARCH (volatility) + FinBERT (sentiment)',
                        style: AppText.caption.copyWith(
                            color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),

          // ── Ticker input ──────────────────────────────────────────────────
          Text('1. Enter Stock Tickers', style: AppText.bodyBold),
          const SizedBox(height: 4),
          Text(
            'NSE: RELIANCE.NS   |   US: AAPL, MSFT   |   UK: HSBA.L',
            style: AppText.caption.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 12),

          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  style: AppText.body,
                  textCapitalization: TextCapitalization.characters,
                  onSubmitted: (_) => _addTicker(),
                  decoration: InputDecoration(
                    hintText: 'e.g. RELIANCE.NS or AAPL',
                    hintStyle: AppText.body.copyWith(
                        color: AppColors.textSecondary),
                    filled: true,
                    fillColor: AppColors.surface,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 14),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: AppColors.onPrimary,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10)),
                  elevation: 0,
                ),
                onPressed: _addTicker,
                child: const Text('Add'),
              ),
            ],
          ),

          // Quick example chips
          const SizedBox(height: 12),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: _examples.map((ex) {
              return ActionChip(
                label: Text(ex,
                    style:
                        AppText.caption.copyWith(fontWeight: FontWeight.w600)),
                backgroundColor: AppColors.surface,
                side: BorderSide(color: AppColors.border),
                onPressed: () {
                  if (!_tickers.contains(ex) && _tickers.length < 5) {
                    setState(() => _tickers.add(ex));
                  }
                },
              );
            }).toList(),
          ),

          // Selected tickers
          if (_tickers.isNotEmpty) ...[
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _tickers
                  .map((t) => Chip(
                        label: Text(t,
                            style: AppText.caption
                                .copyWith(fontWeight: FontWeight.w600)),
                        backgroundColor: AppColors.primaryLight,
                        side: BorderSide.none,
                        deleteIconColor: AppColors.primary,
                        onDeleted: () =>
                            setState(() => _tickers.remove(t)),
                      ))
                  .toList(),
            ),
          ],

          const SizedBox(height: 32),

          // ── Analyze button ────────────────────────────────────────────────
          if (_error != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: AppColors.danger.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                    color: AppColors.danger.withValues(alpha: 0.3)),
              ),
              child: Text('Error: $_error',
                  style:
                      AppText.caption.copyWith(color: AppColors.danger)),
            ),

          SizedBox(
            width: double.infinity,
            child: _isAnalyzing
                ? const Center(
                    child: Column(
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(height: 12),
                        Text(
                          'Running AI pipeline…\nFetching data → Features → Sentiment → GARCH → LSTM → LightGBM\nThis may take 2–5 minutes per ticker.',
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  )
                : AppButton(
                    label: 'Run AI Analysis →',
                    onPressed: _runAnalysis,
                  ),
          ),
          const SizedBox(height: 48),
        ],
      ),
    );
  }

  // ── Results ───────────────────────────────────────────────────────────────

  Widget _buildResults() {
    final res = _result!;
    return Column(
      children: [
        // Header
        Container(
          color: AppColors.surface,
          padding:
              const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${res.results.length} stock${res.results.length != 1 ? 's' : ''} analyzed',
                    style: AppText.bodyBold,
                  ),
                  if (res.errors.isNotEmpty)
                    Text(
                      '${res.errors.length} failed: ${res.errors.keys.join(', ')}',
                      style: AppText.caption
                          .copyWith(color: AppColors.danger),
                    ),
                ],
              ),
              TextButton.icon(
                onPressed: () => setState(() {
                  _result = null;
                  _tickers.clear();
                }),
                icon: Icon(Icons.arrow_back_rounded,
                    size: 16, color: AppColors.primary),
                label: Text('New Analysis',
                    style:
                        TextStyle(color: AppColors.primary)),
              ),
            ],
          ),
        ),
        Divider(height: 1, color: AppColors.border),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: res.results.length,
            separatorBuilder: (_, __) => const SizedBox(height: 16),
            itemBuilder: (context, i) =>
                _StockResultCard(result: res.results[i]),
          ),
        ),
      ],
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// STOCK RESULT CARD
// ══════════════════════════════════════════════════════════════════════════════

class _StockResultCard extends StatelessWidget {
  const _StockResultCard({required this.result});
  final StockResult result;

  Color get _signalColor {
    switch (result.signal) {
      case 'BUY':
        return AppColors.accent;
      case 'SELL':
        return AppColors.danger;
      default:
        return AppColors.warning;
    }
  }

  String get _signalIcon {
    switch (result.signal) {
      case 'BUY':
        return '🟢';
      case 'SELL':
        return '🔴';
      default:
        return '🟡';
    }
  }

  Color get _sentimentColor {
    switch (result.sentimentLabel) {
      case 'Bullish':
        return AppColors.accent;
      case 'Bearish':
        return AppColors.danger;
      default:
        return AppColors.warning;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isBuy = result.signal == 'BUY';
    final sym = result.currencySymbol;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isBuy
              ? AppColors.accent.withValues(alpha: 0.4)
              : AppColors.border,
          width: isBuy ? 2 : 1,
        ),
        boxShadow: isBuy
            ? [
                BoxShadow(
                  color: AppColors.accent.withValues(alpha: 0.08),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ]
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header: ticker + signal badge ──────────────────────────────
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                // Signal badge
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: _signalColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                        color: _signalColor.withValues(alpha: 0.4)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_signalIcon,
                          style: const TextStyle(fontSize: 16)),
                      const SizedBox(width: 6),
                      Text(
                        result.signal,
                        style: AppText.bodyBold
                            .copyWith(color: _signalColor, fontSize: 16),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        result.ticker,
                        style: AppText.heading2
                            .copyWith(fontSize: 18),
                      ),
                      Text(
                        '${result.market}  ·  ${result.regimeLabel}',
                        style: AppText.caption
                            .copyWith(color: AppColors.textSecondary),
                      ),
                    ],
                  ),
                ),
                // Confidence chip
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.primaryLight,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${result.confidence.toStringAsFixed(0)}%',
                    style: AppText.caption.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),

          Divider(height: 1, color: AppColors.border),

          // ── Price targets ─────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Row(
                  children: [
                    _PriceTile('Entry', '$sym${result.entryPrice.toStringAsFixed(2)}', flex: 1),
                    _PriceTile('Stop Loss', '$sym${result.stopLoss.toStringAsFixed(2)}',
                        flex: 1, color: AppColors.danger),
                    _PriceTile('Target', '$sym${result.targetPrice.toStringAsFixed(2)}',
                        flex: 1, color: AppColors.accent),
                  ],
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.compare_arrows_rounded,
                          size: 14, color: AppColors.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        'Risk:Reward = 1 : ${result.riskReward.toStringAsFixed(1)}',
                        style: AppText.caption.copyWith(
                            fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          Divider(height: 1, color: AppColors.border),

          // ── Backtest metrics ──────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Walk-Forward Backtest', style: AppText.label.copyWith(
                    color: AppColors.textSecondary)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _MetricBubble('Return',
                        '${result.backtestReturn >= 0 ? '+' : ''}${result.backtestReturn.toStringAsFixed(1)}%',
                        positive: result.backtestReturn >= 0,
                        tooltipMessage: 'Total simulated return from walk-forward testing'),
                    _MetricBubble('Sharpe',
                        result.backtestSharpe.toStringAsFixed(2),
                        tooltipMessage: 'Risk-adjusted return (higher is better, >1 is good)'),
                    _MetricBubble('Max DD',
                        '${result.maxDrawdown.toStringAsFixed(1)}%',
                        positive: false,
                        tooltipMessage: 'Maximum Drawdown: largest drop from a peak to a trough'),
                    _MetricBubble('Win Rate',
                        '${result.winRate.toStringAsFixed(0)}%',
                        positive: result.winRate >= 50,
                        tooltipMessage: 'Percentage of trades that resulted in a profit'),
                  ],
                ),
              ],
            ),
          ),

          Divider(height: 1, color: AppColors.border),

          // ── Sentiment ─────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.newspaper_rounded,
                        size: 16, color: AppColors.textSecondary),
                    const SizedBox(width: 6),
                    Text('Sentiment', style: AppText.label
                        .copyWith(color: AppColors.textSecondary)),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 3),
                      decoration: BoxDecoration(
                        color: _sentimentColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                            color: _sentimentColor.withValues(alpha: 0.3)),
                      ),
                      child: Text(
                        result.sentimentLabel,
                        style: AppText.caption.copyWith(
                          color: _sentimentColor,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
                if (result.topHeadline.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  GestureDetector(
                    onTap: () async {
                      if (result.topLink.isNotEmpty) {
                        await Clipboard.setData(
                            ClipboardData(text: result.topLink));
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('Link copied to clipboard')));
                        }
                      }
                    },
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            result.topHeadline,
                            style: AppText.caption.copyWith(
                              color: result.topLink.isNotEmpty
                                  ? AppColors.primary
                                  : AppColors.textSecondary,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (result.topLink.isNotEmpty)
                          Icon(Icons.open_in_new_rounded,
                              size: 12, color: AppColors.primary),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),

          // ── AI Charts (Base64) ───────────────────────────────────────
          if (result.chartEquity.isNotEmpty ||
              result.chartSharpe.isNotEmpty ||
              result.chartSentiment.isNotEmpty ||
              result.chartImportance.isNotEmpty) ...[
            Divider(height: 1, color: AppColors.border),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.auto_graph_rounded, size: 16, color: AppColors.textSecondary),
                      const SizedBox(width: 6),
                      Text('AI Analysis Charts', style: AppText.label.copyWith(color: AppColors.textSecondary)),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 200,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        if (result.chartEquity.isNotEmpty) _buildChartImage(result.chartEquity),
                        if (result.chartSentiment.isNotEmpty) _buildChartImage(result.chartSentiment),
                        if (result.chartSharpe.isNotEmpty) _buildChartImage(result.chartSharpe),
                        if (result.chartImportance.isNotEmpty) _buildChartImage(result.chartImportance),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildChartImage(String base64Str) {
    return Container(
      margin: const EdgeInsets.only(right: 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.memory(
          base64Decode(base64Str),
          height: 200,
          fit: BoxFit.cover,
        ),
      ),
    );
  }
}

// ── Helper widgets ────────────────────────────────────────────────────────────

class _PriceTile extends StatelessWidget {
  const _PriceTile(this.label, this.value,
      {required this.flex, this.color});
  final String label;
  final String value;
  final int flex;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      flex: flex,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
        decoration: BoxDecoration(
          color: (color ?? AppColors.textPrimary).withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          children: [
            Text(
              value,
              style: AppText.bodyBold.copyWith(
                  fontSize: 13,
                  color: color ?? AppColors.textPrimary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 2),
            Text(label,
                style: AppText.caption.copyWith(
                    color: AppColors.textSecondary, fontSize: 10),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _MetricBubble extends StatelessWidget {
  const _MetricBubble(this.label, this.value, {this.positive, this.tooltipMessage});
  final String label;
  final String value;
  final bool? positive;
  final String? tooltipMessage;

  @override
  Widget build(BuildContext context) {
    Color col = AppColors.textPrimary;
    if (positive == true) col = AppColors.accent;
    if (positive == false) col = AppColors.danger;

    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: AppText.bodyBold
                  .copyWith(fontSize: 12, color: col),
              textAlign: TextAlign.center),
          const SizedBox(height: 2),
          if (tooltipMessage != null)
            Tooltip(
              message: tooltipMessage,
              triggerMode: TooltipTriggerMode.tap,
              showDuration: const Duration(seconds: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(label,
                      style: AppText.caption
                          .copyWith(color: AppColors.textSecondary, fontSize: 9),
                      textAlign: TextAlign.center),
                  const SizedBox(width: 2),
                  Icon(Icons.info_outline_rounded, size: 10, color: AppColors.textSecondary),
                ],
              ),
            )
          else
            Text(label,
                style: AppText.caption
                    .copyWith(color: AppColors.textSecondary, fontSize: 9),
                textAlign: TextAlign.center),
        ],
      ),
    );
  }
}

class _CodeStep extends StatelessWidget {
  const _CodeStep({required this.step, required this.code});
  final String step;
  final String code;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            color: AppColors.primary,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Text(step,
              style: TextStyle(
                  color: AppColors.onPrimary,
                  fontSize: 10,
                  fontWeight: FontWeight.w700)),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(code,
                style: const TextStyle(
                    fontFamily: 'monospace', fontSize: 12)),
          ),
        ),
      ],
    );
  }
}
