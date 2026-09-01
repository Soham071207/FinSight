import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/section_header.dart';
import '../logic/sip_calculator.dart';
import '../widgets/metrics_grid.dart';
import '../widgets/wealth_projection_chart.dart';
import '../../../shared/widgets/empty_state_widget.dart';
import '../../../shared/widgets/error_state_widget.dart';

class SimulatorResultScreen extends StatelessWidget {
  const SimulatorResultScreen({
    super.key,
    required this.result,
  });

  final SimulatorResult? result;

  @override
  Widget build(BuildContext context) {
    if (result == null) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: AppColors.background,
          elevation: 0,
          leading: IconButton(
            icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
            onPressed: () => context.pop(),
          ),
        ),
        body: ErrorStateWidget(
          message: 'Simulation data is missing or corrupted.',
          onRetry: () => context.pop(),
        ),
      );
    }

    final res = result!;

    if (res.projections.isEmpty) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: AppColors.background,
          elevation: 0,
          leading: IconButton(
            icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
            onPressed: () => context.pop(),
          ),
        ),
        body: EmptyStateWidget(
          icon: Icons.show_chart_rounded,
          title: 'No projections',
          message: 'Your inputs resulted in an empty projection.',
          ctaText: 'Recalculate',
          onCtaPressed: () => context.pop(),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text('Projection', style: AppText.heading2),
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () => context.pop(),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.only(bottom: 32),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 16),
                    
                    // ── 1. Hero Number (Final Corpus) ──────────────────────────
                    Center(
                      child: Column(
                        children: [
                          Text('Expected Corpus', style: AppText.bodySecondary),
                          const SizedBox(height: 4),
                          // Countup animation using TweenAnimationBuilder (as flutter_animate doesn't have a native number counter)
                          TweenAnimationBuilder<double>(
                            tween: Tween<double>(begin: 0, end: res.finalCorpus),
                            duration: const Duration(milliseconds: 800),
                            curve: Curves.easeOut,
                            builder: (context, val, child) {
                              return Text(
                                formatINR(val),
                                style: AppText.heading1.copyWith(
                                  fontSize: 40,
                                  fontWeight: FontWeight.w800,
                                  color: AppColors.accent,
                                  height: 1.1,
                                ),
                              );
                            },
                          ),
                        ],
                      ),
                    ).animate().fadeIn(duration: 400.ms).slideY(begin: 0.1),
                    const SizedBox(height: 32),

                    // ── 2. Metrics Grid ────────────────────────────────────────
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: MetricsGrid(result: res),
                    ).animate().fadeIn(duration: 400.ms, delay: 100.ms).slideY(begin: 0.1),
                    const SizedBox(height: 32),

                    // ── 3. Wealth Projection Chart ─────────────────────────────
                    const SectionHeader(title: 'Growth Over Time'),
                    SizedBox(
                      height: 250,
                      child: Padding(
                        padding: const EdgeInsets.only(right: 16, left: 8),
                        child: WealthProjectionChart(projections: res.projections),
                      ),
                    ).animate().fadeIn(duration: 500.ms, delay: 200.ms),
                    const SizedBox(height: 32),

                    // ── 4. Year-by-Year Table ──────────────────────────────────
                    const SectionHeader(title: 'Year-by-Year Breakdown'),
                    _YearlyTable(projections: res.projections)
                        .animate()
                        .fadeIn(duration: 500.ms, delay: 300.ms),
                  ],
                ),
              ),
            ),

            // ── 5. Bottom Actions ──────────────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: AppButton(
                      label: 'Recalculate',
                      onPressed: () => context.pop(),
                      isOutlined: true,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: AppButton(
                      label: 'Share Result',
                      onPressed: () {
                        // Placeholder for sharing functionality
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Share triggered (Placeholder)')),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _YearlyTable extends StatelessWidget {
  const _YearlyTable({required this.projections});

  final List<YearlyProjection> projections;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: DataTable(
          headingTextStyle: AppText.caption.copyWith(fontWeight: FontWeight.w700),
          dataTextStyle: AppText.body.copyWith(fontSize: 13),
          headingRowColor: WidgetStateProperty.all(AppColors.primaryLight.withValues(alpha: 0.5)),
          horizontalMargin: 16,
          columnSpacing: 24,
          dataRowColor: WidgetStateProperty.resolveWith<Color?>((states) {
            // We use standard context-free coloring via logic inside map() instead
            return null;
          }),
          columns: const [
            DataColumn(label: Text('Year')),
            DataColumn(label: Text('Invested'), numeric: true),
            DataColumn(label: Text('Corpus'), numeric: true),
            DataColumn(label: Text('Gain'), numeric: true),
          ],
          rows: projections.asMap().entries.map((entry) {
            final idx = entry.key;
            final p = entry.value;
            return DataRow(
              color: WidgetStateProperty.all(
                idx.isEven ? AppColors.surface : AppColors.background.withValues(alpha: 0.5),
              ),
              cells: [
                DataCell(Text('${p.year}')),
                DataCell(Text(formatINRCompact(p.investedCumulative))),
                DataCell(
                  Text(
                    formatINRCompact(p.corpusValue),
                    style: TextStyle(color: AppColors.accent, fontWeight: FontWeight.w600),
                  ),
                ),
                DataCell(Text(formatINRCompact(p.gain))),
              ],
            );
          }).toList(),
        ),
      ),
    );
  }
}
