import 'dart:math';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../shared/widgets/app_button.dart';
import '../models/fund_model.dart';
import '../../../core/constants/app_constants.dart';

class FundDetailScreen extends StatefulWidget {
  const FundDetailScreen({
    super.key,
    required this.fund,
  });

  final FundModel fund;

  @override
  State<FundDetailScreen> createState() => _FundDetailScreenState();
}

class _FundDetailScreenState extends State<FundDetailScreen> {
  late List<_ChartData> _chartData;

  @override
  void initState() {
    super.initState();
    _chartData = _generateMockNavHistory(widget.fund.nav);
  }

  /// Generates 3 years of weekly NAV data (156 weeks) ending at the current NAV.
  List<_ChartData> _generateMockNavHistory(double currentNav) {
    final random = Random(widget.fund.id.hashCode); // stable randomness per fund
    final data = <_ChartData>[];
    double nav = currentNav;
    
    // Start from today and go backwards
    DateTime date = DateTime.now();
    data.add(_ChartData(date, nav));

    for (int i = 0; i < 156; i++) {
      date = date.subtract(const Duration(days: 7));
      // Walk backwards: previous nav was current nav / (1 + noise)
      // noise is between -2% and +2.5% (slight upward bias overall)
      final noise = (random.nextDouble() * 0.045) - 0.02;
      nav = nav / (1 + noise);
      data.add(_ChartData(date, nav));
    }

    return data.reversed.toList();
  }

  @override
  Widget build(BuildContext context) {
    final f = widget.fund;
    
    Color cagrColor = AppColors.danger;
    if (f.cagr3Y >= 12.0) {
      cagrColor = AppColors.accent;
    } else if (f.cagr3Y >= 8.0) {
      cagrColor = AppColors.warning;
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () => context.pop(),
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.share_rounded, color: AppColors.textPrimary),
            onPressed: () {},
          ),
        ],
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppColors.surface,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: SafeArea(
          child: AppButton(
            label: 'Simulate SIP in this fund',
            onPressed: () {
              context.pushNamed(
                AppConstants.routeSimulator,
                queryParameters: {
                  AppConstants.queryMode: 'SIP',
                  AppConstants.queryCagr: f.cagr3Y.toString(),
                  AppConstants.queryYears: '5',
                },
              );
            },
          ),
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ───────────────────────────────────────────────────────
            Container(
              color: AppColors.surface,
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '${f.category} — ${f.subcategory}',
                          style: AppText.caption.copyWith(
                            color: AppColors.primary,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.background,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.shield_outlined, size: 12, color: AppColors.textSecondary),
                            const SizedBox(width: 4),
                            Text(
                              'Risk ${f.riskRating}/5',
                              style: AppText.caption.copyWith(fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(f.name, style: AppText.heading1),
                  const SizedBox(height: 4),
                  Text('by ${f.fundHouse}', style: AppText.bodySecondary),
                ],
              ),
            ),
            Divider(height: 1, color: AppColors.border),

            // ── Chart Area ───────────────────────────────────────────────────
            Container(
              color: AppColors.surface,
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Text('NAV History (3 Years)', style: AppText.bodyBold),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 250,
                    child: SfCartesianChart(
                      plotAreaBorderWidth: 0,
                      primaryXAxis: DateTimeAxis(
                        majorGridLines: const MajorGridLines(width: 0),
                        axisLine: const AxisLine(width: 0),
                        dateFormat: DateFormat.yMMM(),
                      ),
                      primaryYAxis: NumericAxis(
                        numberFormat: NumberFormat.compactCurrency(symbol: '₹', locale: 'en_IN'),
                        axisLine: const AxisLine(width: 0),
                        majorTickLines: const MajorTickLines(size: 0),
                        majorGridLines: MajorGridLines(
                          width: 1,
                          color: AppColors.border,
                          dashArray: <double>[5, 5],
                        ),
                      ),
                      crosshairBehavior: CrosshairBehavior(
                        enable: true,
                        activationMode: ActivationMode.singleTap,
                        lineType: CrosshairLineType.vertical,
                      ),
                      tooltipBehavior: TooltipBehavior(
                        enable: true,
                        builder: (dynamic data, dynamic point, dynamic series, int pointIndex, int seriesIndex) {
                          final d = data as _ChartData;
                          return Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              boxShadow: [
                                BoxShadow(color: Colors.black.withValues(alpha: 0.1), blurRadius: 4),
                              ],
                            ),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(DateFormat('d MMM yyyy').format(d.date),
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                                const SizedBox(height: 4),
                                Text('NAV: ${formatINR(d.nav)}',
                                    style: TextStyle(color: AppColors.primary, fontSize: 12)),
                              ],
                            ),
                          );
                        },
                      ),
                      zoomPanBehavior: ZoomPanBehavior(
                        enablePinching: true,
                        enablePanning: true,
                      ),
                      series: <CartesianSeries<_ChartData, DateTime>>[
                        LineSeries<_ChartData, DateTime>(
                          dataSource: _chartData,
                          xValueMapper: (_ChartData d, _) => d.date,
                          yValueMapper: (_ChartData d, _) => d.nav,
                          color: AppColors.primary,
                          width: 2,
                          animationDuration: 1500,
                        ),
                        AreaSeries<_ChartData, DateTime>(
                          dataSource: _chartData,
                          xValueMapper: (_ChartData d, _) => d.date,
                          yValueMapper: (_ChartData d, _) => d.nav,
                          color: AppColors.primaryLight.withValues(alpha: 0.5),
                          animationDuration: 1500,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ── Metrics Grid ─────────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Text('Fund Overview', style: AppText.bodyBold),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 3,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.2,
                children: [
                  _MetricCard(label: '3Y CAGR', value: '${f.cagr3Y}%', valueColor: cagrColor, tooltipMessage: 'Compound Annual Growth Rate over the last 3 years'),
                  _MetricCard(label: '5Y CAGR', value: '${f.cagr5Y}%', valueColor: AppColors.textPrimary, tooltipMessage: 'Compound Annual Growth Rate over the last 5 years'),
                  _MetricCard(label: 'Fund Score', value: '${f.score}/100', valueColor: AppColors.textPrimary, tooltipMessage: 'Proprietary FinSight AI fund score combining performance and risk'),
                  _MetricCard(label: 'Current NAV', value: formatINR(f.nav)),
                  _MetricCard(label: 'Fund Size', value: '₹${f.aumCr.toInt()} Cr'),
                  _MetricCard(label: 'Risk', value: '${f.riskRating}/5', tooltipMessage: 'Risk rating (higher is riskier)'),
                ],
              ),
            ),
            const SizedBox(height: 48),
          ],
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.label,
    required this.value,
    this.valueColor,
    this.tooltipMessage,
  });

  final String label;
  final String value;
  final Color? valueColor;
  final String? tooltipMessage;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (tooltipMessage != null)
            Tooltip(
              message: tooltipMessage,
              triggerMode: TooltipTriggerMode.tap,
              showDuration: const Duration(seconds: 4),
              child: Row(
                children: [
                  Text(label, style: AppText.caption.copyWith(fontSize: 11)),
                  const SizedBox(width: 4),
                  Icon(Icons.info_outline_rounded, size: 10, color: AppColors.textSecondary),
                ],
              ),
            )
          else
            Text(label, style: AppText.caption.copyWith(fontSize: 11)),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              value,
              style: AppText.heading2.copyWith(color: valueColor ?? AppColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChartData {
  _ChartData(this.date, this.nav);
  final DateTime date;
  final double nav;
}
