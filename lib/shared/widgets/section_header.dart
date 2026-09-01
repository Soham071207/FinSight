import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text.dart';

/// A section header row with a bold title on the left and an optional
/// "See all" action link on the right.
///
/// Usage:
///   SectionHeader(title: 'Quick Actions')
///   SectionHeader(title: 'Smart Suggestions', onSeeAll: () => context.go(AppConstants.pathFunds))
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.onSeeAll,
    this.seeAllLabel = 'See all',
    this.padding = const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
  });

  final String title;

  /// When non-null, renders a tappable "See all" link on the right.
  final VoidCallback? onSeeAll;

  /// Label for the right-side action. Defaults to "See all".
  final String seeAllLabel;

  /// Outer padding of the header row.
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: padding,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // ── Title ────────────────────────────────────────────────────────
          Text(title, style: AppText.heading2),

          // ── See all link ──────────────────────────────────────────────────
          if (onSeeAll != null)
            GestureDetector(
              onTap: onSeeAll,
              behavior: HitTestBehavior.opaque,
              child: Padding(
                // Extra tap target padding without affecting visual layout
                padding: const EdgeInsets.only(left: 12, top: 4, bottom: 4),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      seeAllLabel,
                      style: AppText.label.copyWith(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(width: 2),
                    Icon(
                      Icons.arrow_forward_ios_rounded,
                      size: 14,
                      color: AppColors.textPrimary,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
