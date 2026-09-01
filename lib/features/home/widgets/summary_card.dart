import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../shared/widgets/shimmer_loader.dart';

/// A compact summary card used in the horizontal scroll row on HomeScreen.
///
/// White surface, 16px radius, 1px border, optional tap.
/// Use [SummaryCard.shimmer()] for the loading skeleton variant.
///
/// Usage:
///   SummaryCard(
///     icon: Icons.credit_score,
///     iconColor: AppColors.accent,
///     label: 'CIBIL Score',
///     value: '742',
///     subtitle: 'Very Good',
///     subtitleColor: AppColors.accent,
///     onTap: () => context.go('/cibil'),
///   )
class SummaryCard extends StatelessWidget {
  const SummaryCard({
    super.key,
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
    this.subtitle,
    this.subtitleColor,
    this.badge,
    this.badgeColor,
    this.trailing,
    this.onTap,
    this.width = 168,
  });

  final IconData icon;

  /// Icon background tint and the icon itself are derived from this color.
  final Color iconColor;

  /// Small label above the value (e.g. "CIBIL Score").
  final String label;

  /// Primary value shown in large text (e.g. "742" or "₹3,200").
  final String value;

  /// Optional helper text below the value (e.g. "Very Good").
  final String? subtitle;

  /// Color for [subtitle]. Defaults to [AppColors.textSecondary].
  final Color? subtitleColor;

  /// Optional small pill badge text (e.g. "↑ 14.2%").
  final String? badge;

  /// Background color for the badge pill.
  final Color? badgeColor;

  /// Arbitrary widget placed at the bottom (e.g. a LinearProgressIndicator).
  final Widget? trailing;

  final VoidCallback? onTap;

  /// Card width. Default 168 fits 2+ cards in a horizontal scroll.
  final double width;

  // ── Shimmer factory ────────────────────────────────────────────────────────

  /// Returns a shimmer skeleton matching the card's layout.
  static Widget shimmer({double width = 168}) => _SummaryCardShimmer(width: width);

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        width: width,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // ── Icon ──────────────────────────────────────────────────────
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 20, color: iconColor),
            ),

            const SizedBox(height: 14),

            // ── Label ──────────────────────────────────────────────────────
            Text(
              label,
              style: AppText.caption,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),

            const SizedBox(height: 4),

            // ── Value ───────────────────────────────────────────────────────
            Text(
              value,
              style: AppText.priceMedium.copyWith(fontSize: 18),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),

            // ── Subtitle / badge row ────────────────────────────────────────
            if (subtitle != null || badge != null) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  if (subtitle != null)
                    Expanded(
                      child: Text(
                        subtitle!,
                        style: AppText.caption.copyWith(
                          color: subtitleColor ?? AppColors.textSecondary,
                          fontWeight: FontWeight.w500,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  if (badge != null) ...[
                    const SizedBox(width: 4),
                    _Badge(text: badge!, color: badgeColor ?? AppColors.accent),
                  ],
                ],
              ),
            ],

            // ── Trailing widget (e.g. progress bar) ─────────────────────────
            if (trailing != null) ...[
              const SizedBox(height: 10),
              trailing!,
            ],
          ],
        ),
      ),
    );
  }
}

// ── Badge pill ────────────────────────────────────────────────────────────────

class _Badge extends StatelessWidget {
  const _Badge({required this.text, required this.color});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: AppText.caption.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// ── Shimmer skeleton ──────────────────────────────────────────────────────────

class _SummaryCardShimmer extends StatelessWidget {
  const _SummaryCardShimmer({required this.width});
  final double width;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          ShimmerBox(width: 36, height: 36, borderRadius: 10),
          SizedBox(height: 14),
          ShimmerBox(width: 72, height: 10, borderRadius: 5),
          SizedBox(height: 6),
          ShimmerBox(width: 90, height: 18, borderRadius: 5),
          SizedBox(height: 8),
          ShimmerBox(width: 56, height: 10, borderRadius: 5),
        ],
      ),
    );
  }
}
