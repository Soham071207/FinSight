import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../logic/cibil_calculator.dart';

class FactorBreakdownCard extends StatelessWidget {
  const FactorBreakdownCard({
    super.key,
    required this.factor,
    this.isWeakest = false,
  });

  final FactorScore factor;
  final bool isWeakest;

  @override
  Widget build(BuildContext context) {
    final pct = factor.pct;
    
    // Determine bar color based on percentage
    final Color barColor = pct >= 80
        ? AppColors.accent
        : pct >= 60
            ? AppColors.warning
            : AppColors.danger;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isWeakest ? AppColors.danger.withValues(alpha: 0.05) : AppColors.surface,
        border: Border(
          bottom: BorderSide(
            color: isWeakest ? AppColors.danger.withValues(alpha: 0.2) : AppColors.border,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                factor.name,
                style: AppText.bodyBold,
              ),
              Text(
                '${factor.earned.toInt()} / ${factor.max.toInt()}',
                style: AppText.label.copyWith(
                  fontWeight: FontWeight.w700,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          
          // Progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: factor.ratio,
              backgroundColor: AppColors.border,
              color: barColor,
              minHeight: 8,
            ),
          ),

          // Weakness action text (only if < 60% and actionHint exists)
          if (pct < 60 && factor.actionHint != null) ...[
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.info_outline_rounded,
                  size: 16,
                  color: AppColors.danger,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    factor.actionHint!,
                    style: AppText.caption.copyWith(color: AppColors.danger),
                  ),
                ),
              ],
            )
          ]
        ],
      ),
    );
  }
}
