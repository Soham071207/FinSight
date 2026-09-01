import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/constants/app_constants.dart';
import '../models/fund_model.dart';

class FundCard extends StatelessWidget {
  const FundCard({
    super.key,
    required this.fund,
  });

  final FundModel fund;

  @override
  Widget build(BuildContext context) {
    // Determine CAGR color
    Color cagrColor = AppColors.danger;
    if (fund.cagr3Y >= 12.0) {
      cagrColor = AppColors.accent;
    } else if (fund.cagr3Y >= 8.0) {
      cagrColor = AppColors.warning;
    }

    // Determine category pill color (dynamic based on category)
    Color catColor = AppColors.primary;
    if (fund.category == 'Debt') catColor = AppColors.textSecondary;
    if (fund.category == 'Hybrid') catColor = AppColors.warning;
    if (fund.category == 'ELSS') catColor = AppColors.danger;
    if (fund.category == 'International') catColor = AppColors.textSecondary;

    return InkWell(
      onTap: () {
        context.pushNamed(
          AppConstants.routeFundDetail,
          pathParameters: {'fundId': fund.id},
        );
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          border: Border(bottom: BorderSide(color: AppColors.border)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Left Column
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: catColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '${fund.category} — ${fund.subcategory}',
                      style: AppText.caption.copyWith(
                        color: catColor,
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    fund.name,
                    style: AppText.bodyBold,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    fund.fundHouse,
                    style: AppText.caption,
                  ),
                ],
              ),
            ),
            
            // Right Column
            Expanded(
              flex: 1,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${fund.cagr3Y}%',
                    style: AppText.heading2.copyWith(color: cagrColor),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '3Y CAGR',
                    style: AppText.caption.copyWith(fontSize: 10),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.background,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.shield_outlined, size: 10, color: AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Text(
                          'Risk ${fund.riskRating}/5',
                          style: AppText.caption.copyWith(fontSize: 10, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  )
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
