import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// lib/features/funds/screens/pro_analysis_screen.dart
// Mode 2 – live fund analysis powered by mutual_2_api.py

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../shared/widgets/app_button.dart';
import '../logic/fund_analysis_service.dart';

// ── Provider ──────────────────────────────────────────────────────────────────

final _service = FundAnalysisService();

final _apiAvailableProvider = FutureProvider<bool>((ref) => _service.isApiAvailable());

// ══════════════════════════════════════════════════════════════════════════════
// PRO ANALYSIS SCREEN
// ══════════════════════════════════════════════════════════════════════════════

class ProAnalysisScreen extends ConsumerStatefulWidget {
  final bool hideAppBar;
  const ProAnalysisScreen({super.key, this.hideAppBar = false});

  @override
  ConsumerState<ProAnalysisScreen> createState() => _ProAnalysisScreenState();
}

class _ProAnalysisScreenState extends ConsumerState<ProAnalysisScreen> {
  // ── Form state ──────────────────────────────────────────────────────────────
  final List<String> _selectedAssets = [];
  int _invMode      = 1;   // 1=SIP, 2=Lumpsum, 3=Both
  double _baseSip   = 10000;
  double _stepUp    = 10;
  double _lumpsum   = 100000;
  double _backtest  = 5;
  double _future    = 10;

  // ── Search state ────────────────────────────────────────────────────────────
  final _searchCtrl = TextEditingController();
  List<FundSearchResult> _searchResults = [];
  bool _isSearching = false;
  String? _searchError;

  // ── Result state ────────────────────────────────────────────────────────────
  AnalysisResponse? _result;
  bool _isAnalyzing = false;
  String? _analysisError;

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _doSearch(String keyword) async {
    if (keyword.trim().isEmpty) return;
    setState(() { _isSearching = true; _searchError = null; _searchResults = []; });
    try {
      final results = await _service.search(keyword.trim());
      setState(() { _searchResults = results; });
    } catch (e) {
      setState(() { _searchError = e.toString(); });
    } finally {
      setState(() { _isSearching = false; });
    }
  }

  Future<void> _runAnalysis() async {
    if (_selectedAssets.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add at least one fund to analyze')));
      return;
    }
    setState(() { _isAnalyzing = true; _analysisError = null; _result = null; });
    try {
      final res = await _service.analyze(
        assets:      _selectedAssets,
        invMode:     _invMode,
        baseSip:     _invMode != 2 ? _baseSip : 0,
        stepUpPct:   _stepUp,
        lumpsumAmt:  _invMode != 1 ? _lumpsum : 0,
        targetYears: _backtest,
        futureYears: _future,
      );
      setState(() { _result = res; });
    } catch (e) {
      setState(() { _analysisError = e.toString(); });
    } finally {
      setState(() { _isAnalyzing = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final apiAsync = ref.watch(_apiAvailableProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: widget.hideAppBar ? null : AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Column(
          children: [
            Text('Pro Analysis', style: AppText.heading2),
            Text('Powered by live AMFI + yfinance data',
                style: AppText.caption.copyWith(color: AppColors.accent)),
          ],
        ),
      ),
      body: apiAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error:   (_, __) => _buildServerOffline(),
        data: (available) {
          if (!available) return _buildServerOffline();
          return _result != null
              ? _buildResults()
              : _buildForm();
        },
      ),
    );
  }

  // ── Server offline card ───────────────────────────────────────────────────

  Widget _buildServerOffline() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72, height: 72,
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.cloud_off_rounded,
                  size: 36, color: AppColors.warning),
            ),
            const SizedBox(height: 24),
            Text('Pro Analysis Server Offline', style: AppText.heading2),
            const SizedBox(height: 12),
            Text(
              'The live analysis engine requires a local Python server.\n\n'
              'To start it:\n'
              '1. Open a terminal in your project folder\n'
              '2. Run:  pip install flask flask-cors mftool yfinance scipy\n'
              '3. Run:  python mutual_2_api.py\n\n'
              'Keep that terminal open, then come back here.',
              style: AppText.bodySecondary,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            AppButton(
              label: 'Retry Connection',
              onPressed: () => ref.refresh(_apiAvailableProvider),
            ),
          ],
        ),
      ),
    );
  }

  // ── Form ──────────────────────────────────────────────────────────────────

  Widget _buildForm() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Fund search ─────────────────────────────────────────────────
          const _SectionHeader(title: '1. Select Funds to Analyze',
              subtitle: 'Enter fund names (e.g. "HDFC flexi cap"), AMFI codes, or yfinance tickers (SPY, QQQ)'),
          const SizedBox(height: 12),

          // Search bar
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchCtrl,
                  style: AppText.body,
                  onSubmitted: _doSearch,
                  decoration: InputDecoration(
                    hintText: 'Search: "quant small cap" or "119597" or "SPY"',
                    hintStyle: AppText.body.copyWith(color: AppColors.textSecondary),
                    filled: true,
                    fillColor: AppColors.surface,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: AppColors.onPrimary,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  elevation: 0,
                ),
                onPressed: _isSearching ? null : () => _doSearch(_searchCtrl.text),
                child: _isSearching
                    ? SizedBox(width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.onPrimary))
                    : const Icon(Icons.search_rounded),
              ),
            ],
          ),

          // Search error
          if (_searchError != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_searchError!,
                  style: AppText.caption.copyWith(color: AppColors.danger)),
            ),

          // Search results
          if (_searchResults.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                children: _searchResults.take(10).map((r) {
                  final isAdded = _selectedAssets.contains(r.code);
                  return ListTile(
                    dense: true,
                    title: Text(r.name, style: AppText.caption.copyWith(fontWeight: FontWeight.w500)),
                    subtitle: Text('Code: ${r.code}', style: AppText.caption.copyWith(color: AppColors.textSecondary)),
                    trailing: IconButton(
                      onPressed: () {
                        setState(() {
                          if (isAdded) {
                            _selectedAssets.remove(r.code);
                          } else if (_selectedAssets.length < 5) _selectedAssets.add(r.code);
                        });
                      },
                      icon: Icon(
                        isAdded ? Icons.check_circle_rounded : Icons.add_circle_outline_rounded,
                        color: isAdded ? AppColors.accent : AppColors.primary,
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],

          // Manual ticker add
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.info_outline_rounded, size: 14, color: AppColors.textSecondary),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'For yfinance tickers (ETFs/stocks like SPY, QQQ, RELIANCE.NS), type the ticker directly and tap Add.',
                  style: AppText.caption.copyWith(color: AppColors.textSecondary),
                ),
              ),
              TextButton(
                onPressed: () {
                  final t = _searchCtrl.text.trim();
                  if (t.isNotEmpty && !_selectedAssets.contains(t) && _selectedAssets.length < 5) {
                    setState(() => _selectedAssets.add(t.toUpperCase()));
                  }
                },
                child: Text('Add Ticker', style: TextStyle(color: AppColors.primary)),
              ),
            ],
          ),

          // Selected chips
          if (_selectedAssets.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8, runSpacing: 8,
              children: _selectedAssets.map((asset) => Chip(
                label: Text(asset, style: AppText.caption.copyWith(fontWeight: FontWeight.w600)),
                backgroundColor: AppColors.primaryLight,
                side: BorderSide.none,
                deleteIconColor: AppColors.primary,
                onDeleted: () => setState(() => _selectedAssets.remove(asset)),
              )).toList(),
            ),
          ],
          const SizedBox(height: 32),

          // ── Investment mode ─────────────────────────────────────────────
          const _SectionHeader(title: '2. Investment Mode'),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                _ModeChip(label: 'SIP',         value: 1, current: _invMode, onTap: (v) => setState(() => _invMode = v)),
                _ModeChip(label: 'Lumpsum',      value: 2, current: _invMode, onTap: (v) => setState(() => _invMode = v)),
                _ModeChip(label: 'SIP + Lumpsum', value: 3, current: _invMode, onTap: (v) => setState(() => _invMode = v)),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // SIP inputs
          if (_invMode != 2) ...[
            _NumberField(
              label: 'Monthly SIP Amount (₹)',
              value: _baseSip,
              onChanged: (v) => setState(() => _baseSip = v),
            ),
            const SizedBox(height: 12),
            _NumberField(
              label: 'Annual Step-Up % (e.g. 10 = 10% more each year)',
              value: _stepUp,
              onChanged: (v) => setState(() => _stepUp = v),
            ),
            const SizedBox(height: 12),
          ],

          // Lumpsum input
          if (_invMode != 1) ...[
            _NumberField(
              label: 'One-time Lumpsum (₹)',
              value: _lumpsum,
              onChanged: (v) => setState(() => _lumpsum = v),
            ),
            const SizedBox(height: 12),
          ],

          // Horizon inputs
          _NumberField(
            label: 'Backtest Period (years)',
            value: _backtest,
            onChanged: (v) => setState(() => _backtest = v),
          ),
          const SizedBox(height: 12),
          _NumberField(
            label: 'Future Projection (years)',
            value: _future,
            onChanged: (v) => setState(() => _future = v),
          ),
          const SizedBox(height: 32),

          if (_analysisError != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: AppColors.danger.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.danger.withValues(alpha: 0.3)),
              ),
              child: Text('Error: $_analysisError',
                  style: AppText.caption.copyWith(color: AppColors.danger)),
            ),

          SizedBox(
            width: double.infinity,
            child: _isAnalyzing
                ? const Center(
                    child: Column(children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 12),
                      Text('Downloading live NAV data & running analysis…\nThis may take 30–60 seconds.', textAlign: TextAlign.center),
                    ]))
                : AppButton(
                    label: 'Run Pro Analysis →',
                    onPressed: _runAnalysis,
                  ),
          ),
          const SizedBox(height: 48),
        ],
      ),
    );
  }

  // ── Results ────────────────────────────────────────────────────────────────

  Widget _buildResults() {
    final res = _result!;
    return Column(
      children: [
        // Header bar
        Container(
          color: AppColors.surface,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${res.results.length} funds compared · ${res.actualYears.toStringAsFixed(1)}Y backtest',
                      style: AppText.bodyBold),
                  Text('Future: ${res.futureYears.toStringAsFixed(0)} years', style: AppText.caption),
                ],
              ),
              TextButton.icon(
                onPressed: () => setState(() { _result = null; }),
                icon: Icon(Icons.arrow_back_rounded, size: 16, color: AppColors.primary),
                label: Text('New Analysis', style: TextStyle(color: AppColors.primary)),
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
            itemBuilder: (context, index) {
              return _LiveFundCard(fund: res.results[index]);
            },
          ),
        ),
      ],
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// LIVE FUND CARD
// ══════════════════════════════════════════════════════════════════════════════

class _LiveFundCard extends StatelessWidget {
  const _LiveFundCard({required this.fund});
  final LiveFundResult fund;

  @override
  Widget build(BuildContext context) {
    final medal = '#${fund.rank}';
    final isBest = fund.rank == 1;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isBest ? AppColors.accent.withValues(alpha: 0.5) : AppColors.border,
          width: isBest ? 2 : 1,
        ),
        boxShadow: isBest ? [
          BoxShadow(
            color: AppColors.accent.withValues(alpha: 0.08),
            blurRadius: 16, offset: const Offset(0, 4),
          ),
        ] : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(medal, style: const TextStyle(fontSize: 24)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(fund.name, style: AppText.bodyBold),
                      const SizedBox(height: 2),
                      Text('${fund.fundHouse}  ·  ${fund.category}',
                          style: AppText.caption.copyWith(color: AppColors.textSecondary)),
                      const SizedBox(height: 2),
                      Text('Expense Ratio: ${fund.expenseRatio}  ·  ${fund.startDate} → ${fund.endDate}',
                          style: AppText.caption.copyWith(color: AppColors.textSecondary)),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // NAV sparkline
          if (fund.valHistSampled.length > 2) ...[
            SizedBox(
              height: 80,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: LineChart(
                  LineChartData(
                    gridData: const FlGridData(show: false),
                    borderData: FlBorderData(show: false),
                    titlesData: const FlTitlesData(show: false),
                    lineBarsData: [
                      LineChartBarData(
                        spots: fund.valHistSampled.asMap().entries.map((e) =>
                          FlSpot(e.key.toDouble(), e.value)).toList(),
                        isCurved: true,
                        color: isBest ? AppColors.accent : AppColors.primary,
                        barWidth: 2,
                        dotData: const FlDotData(show: false),
                        belowBarData: BarAreaData(
                          show: true,
                          color: (isBest ? AppColors.accent : AppColors.primary).withValues(alpha: 0.08),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],

          Divider(height: 1, color: AppColors.border),

          // Metrics grid
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                // Row 1 — wealth
                Row(
                  children: [
                    _MetricTile('Invested',       formatINRCompact(fund.invested),       flex: 1),
                    _MetricTile('Final Value',    formatINRCompact(fund.finalValue),     flex: 1, highlight: true, positive: true),
                    _MetricTile('Wealth Gain',    formatINRCompact(fund.wealthGain),     flex: 1, highlight: true, positive: fund.wealthGain >= 0),
                  ],
                ),
                const SizedBox(height: 12),
                // Row 2 — returns
                Row(
                  children: [
                    _MetricTile('XIRR',           '${fund.xirr.toStringAsFixed(1)}%',   flex: 1, positive: fund.xirr >= 0, tooltipMessage: 'Extended Internal Rate of Return (annualized return factoring multiple cash flows)'),
                    _MetricTile('CAGR',           '${fund.cagr.toStringAsFixed(1)}%',   flex: 1, positive: fund.cagr >= 0, tooltipMessage: 'Compound Annual Growth Rate'),
                    _MetricTile('Abs Return',     '${fund.absReturn.toStringAsFixed(1)}%', flex: 1, positive: fund.absReturn >= 0, tooltipMessage: 'Absolute Return (total gain without considering time)'),
                  ],
                ),
                const SizedBox(height: 12),
                // Row 3 — risk
                Row(
                  children: [
                    _MetricTile('Risk',           '${fund.riskScore}/10', flex: 1, tooltipMessage: 'Proprietary risk rating (higher = more volatile)'),
                    _MetricTile('Sortino',        fund.sortino.toStringAsFixed(2), flex: 1, tooltipMessage: 'Risk-adjusted return penalizing only downside volatility'),
                    _MetricTile('Max Drawdown',   '${fund.maxDrawdown.toStringAsFixed(1)}%', flex: 1, positive: false, tooltipMessage: 'Largest historical drop from peak to trough'),
                  ],
                ),
                const SizedBox(height: 12),
                // Row 4 — advanced
                Row(
                  children: [
                    _MetricTile('Volatility',     '${fund.volatility.toStringAsFixed(1)}%', flex: 1, tooltipMessage: 'Standard deviation of returns (annualized)'),
                    _MetricTile('Beta',           fund.beta.toStringAsFixed(2), flex: 1, tooltipMessage: 'Volatility relative to the market (1 = market average)'),
                    _MetricTile('Alpha',          '${fund.alpha.toStringAsFixed(2)}%', flex: 1, positive: fund.alpha >= 0, tooltipMessage: 'Excess return compared to the benchmark index'),
                  ],
                ),
                const SizedBox(height: 12),
                // Future prediction banner
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.primaryLight,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Text('🔮', style: TextStyle(fontSize: 16)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Future Value in ${fund.cagr.toStringAsFixed(1)}% CAGR projection',
                                style: AppText.caption.copyWith(color: AppColors.primary, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 2),
                            Text(
                              'Invested ${formatINRCompact(fund.futureInvested)}  →  '
                              '${formatINRCompact(fund.futureValue)}  '
                              '(+${formatINRCompact(fund.futureWealthGain)})',
                              style: AppText.caption.copyWith(color: AppColors.primary),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Small helper widgets ─────────────────────────────────────────────────────

class _MetricTile extends StatelessWidget {
  const _MetricTile(this.label, this.value, {
    required this.flex,
    this.highlight = false,
    this.positive,
    this.tooltipMessage,
  });
  final String label;
  final String value;
  final int flex;
  final bool highlight;
  final bool? positive;
  final String? tooltipMessage;

  @override
  Widget build(BuildContext context) {
    Color valueColor = AppColors.textPrimary;
    if (positive == true)  valueColor = AppColors.accent;
    if (positive == false) valueColor = AppColors.danger;

    return Expanded(
      flex: flex,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        margin: const EdgeInsets.symmetric(horizontal: 2),
        decoration: highlight ? BoxDecoration(
          color: AppColors.primaryLight,
          borderRadius: BorderRadius.circular(8),
        ) : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(value,
                style: AppText.bodyBold.copyWith(fontSize: 13, color: valueColor),
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
                        style: AppText.caption.copyWith(color: AppColors.textSecondary, fontSize: 10),
                        textAlign: TextAlign.center),
                    const SizedBox(width: 2),
                    Icon(Icons.info_outline_rounded, size: 10, color: AppColors.textSecondary),
                  ],
                ),
              )
            else
              Text(label,
                  style: AppText.caption.copyWith(color: AppColors.textSecondary, fontSize: 10),
                  textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({required this.label, required this.value, required this.current, required this.onTap});
  final String label;
  final int value;
  final int current;
  final void Function(int) onTap;

  @override
  Widget build(BuildContext context) {
    final isSelected = value == current;
    return Expanded(
      child: GestureDetector(
        onTap: () => onTap(value),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(label,
              style: AppText.caption.copyWith(
                fontWeight: FontWeight.w600,
                color: isSelected ? AppColors.onPrimary : AppColors.textSecondary,
              )),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.subtitle});
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: AppText.bodyBold),
        if (subtitle != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(subtitle!, style: AppText.caption.copyWith(color: AppColors.textSecondary)),
          ),
      ],
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({required this.label, required this.value, required this.onChanged});
  final String label;
  final double value;
  final void Function(double) onChanged;

  @override
  Widget build(BuildContext context) {
    return TextField(
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      controller: TextEditingController(text: value.toStringAsFixed(value == value.truncate() ? 0 : 1)),
      style: AppText.body,
      onChanged: (v) {
        final parsed = double.tryParse(v);
        if (parsed != null && parsed > 0) onChanged(parsed);
      },
      decoration: InputDecoration(
        labelText: label,
        labelStyle: AppText.caption,
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
    );
  }
}

extension on double {
  double truncate() => this - (this % 1);
}
