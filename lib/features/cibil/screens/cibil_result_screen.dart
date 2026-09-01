import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/section_header.dart';
import '../logic/cibil_calculator.dart';
import '../widgets/factor_breakdown_card.dart';
import '../widgets/improvement_tip_card.dart';
import '../widgets/score_gauge.dart';
import '../../../shared/widgets/error_state_widget.dart';

class CibilResultScreen extends StatelessWidget {
  const CibilResultScreen({
    super.key,
    required this.result,
  });

  final CibilResult? result;

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
          message: 'Failed to load credit score details.',
          onRetry: () => context.pop(),
        ),
      );
    }

    final res = result!;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text('Your Score', style: AppText.heading2),
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
                    if (res.isOfflineFallback)
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 16),
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        color: AppColors.warning.withValues(alpha: 0.1),
                        child: Row(
                          children: [
                            Icon(Icons.wifi_off, color: AppColors.warning, size: 20),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Due to app being offline, the score was calculated using the rule-based system. For higher accuracy, turn on the internet and recalculate.',
                                style: AppText.caption.copyWith(color: AppColors.textPrimary),
                              ),
                            ),
                          ],
                        ),
                      ),
                    const SizedBox(height: 16),
                    
                    // ── 1. Score Gauge ─────────────────────────────────────────
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: ScoreGauge(
                        score: res.totalScore,
                        bandColor: Color(res.band.colorValue),
                        bandLabel: res.band.label,
                      ),
                    ),
                    const SizedBox(height: 48),

                    // ── 2. Factor Breakdown ────────────────────────────────────
                    const SectionHeader(title: "What's affecting your score"),
                    Container(
                      margin: const EdgeInsets.symmetric(horizontal: 16),
                      clipBehavior: Clip.antiAlias,
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Column(
                        children: res.factorScores.map((factor) {
                          return FactorBreakdownCard(
                            factor: factor,
                            isWeakest: factor.name == res.weakestFactor.name,
                          );
                        }).toList(),
                      ),
                    ),
                    const SizedBox(height: 32),

                    // ── 3. Top Actions ─────────────────────────────────────────
                    if (res.improvementTips.isNotEmpty) ...[
                      const SectionHeader(title: "Suggested Improvements"),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Column(
                          children: res.improvementTips.asMap().entries.map((entry) {
                            return ImprovementTipCard(
                              index: entry.key + 1,
                              tip: entry.value,
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),

            // ── Bottom Recalculate Button ────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: AppButton(
                label: 'Recalculate',
                onPressed: () => context.pop(), // Pops back to form with inputs preserved
                isOutlined: true,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
