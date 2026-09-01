import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../logic/cibil_calculator.dart';

class ImprovementTipCard extends StatelessWidget {
  const ImprovementTipCard({
    super.key,
    required this.tip,
    this.index,
  });

  final ImprovementTip tip;
  final int? index;

  @override
  Widget build(BuildContext context) {
    Color difficultyColor;
    String difficultyText;

    switch (tip.difficulty) {
      case TipDifficulty.easy:
        difficultyColor = AppColors.accent;
        difficultyText = 'Easy';
        break;
      case TipDifficulty.medium:
        difficultyColor = AppColors.warning;
        difficultyText = 'Medium';
        break;
      case TipDifficulty.hard:
        difficultyColor = AppColors.danger;
        difficultyText = 'Hard';
        break;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (index != null) ...[
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                color: AppColors.primaryLight,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Text(
                '$index',
                style: AppText.label.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(width: 12),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  tip.action,
                  style: AppText.bodyBold,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    // Estimated Gain Badge (Amber Pill)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.warning.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.trending_up_rounded,
                            size: 14,
                            color: AppColors.warning, // Darker amber for text contrast
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '+${tip.estimatedGain} pts',
                            style: AppText.caption.copyWith(
                              fontWeight: FontWeight.w700,
                              color: AppColors.warning,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    
                    // Difficulty Chip
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.background,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: difficultyColor,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            difficultyText,
                            style: AppText.caption.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
