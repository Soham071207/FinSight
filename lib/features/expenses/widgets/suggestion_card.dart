import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../logic/investment_advisor.dart';
import 'expense_list_tile.dart'; // For CategoryStyle
import '../../../core/constants/app_constants.dart';

class SuggestionCard extends StatelessWidget {
  const SuggestionCard({
    super.key,
    required this.suggestion,
  });

  final InvestmentSuggestion suggestion;

  void _showDisclaimer(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      backgroundColor: AppColors.surface,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.info_outline_rounded, color: AppColors.primary, size: 24),
                    const SizedBox(width: 12),
                    Text('About This Projection', style: AppText.heading2),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  'Returns shown are illustrative only, based on historical averages. Actual returns may vary. This is not financial advice. Please consult a SEBI-registered investment advisor before making any investment decisions.',
                  style: AppText.body.copyWith(height: 1.5, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => Navigator.pop(context),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: AppColors.onPrimary,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: Text('Got it', style: AppText.bodyBold),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final color = CategoryStyle.getColor(suggestion.category);

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
        boxShadow: [
          BoxShadow(
            color: AppColors.border.withValues(alpha: 0.5),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Header (Icon + Tag) ──────────────────────────────────────────
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.15),
                        shape: BoxShape.circle,
                      ),
                      child: Text(suggestion.icon, style: const TextStyle(fontSize: 16)),
                    ),
                    const SizedBox(width: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.background,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Text(
                        suggestion.category,
                        style: AppText.caption.copyWith(
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // ── Body (Message) ───────────────────────────────────────────────
                _HighlightMessage(
                  message: suggestion.cardText,
                  highlightColor: AppColors.primary,
                ),
                const SizedBox(height: 20),
                Divider(height: 1, color: AppColors.border),
                const SizedBox(height: 16),

                // ── Footer (Return + CTA) ────────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Projected wealth', style: AppText.caption),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            Icon(Icons.trending_up_rounded, color: AppColors.accent, size: 16),
                            const SizedBox(width: 4),
                            Text(
                              suggestion.displayWealth,
                              style: AppText.heading2.copyWith(color: AppColors.accent),
                            ),
                          ],
                        ),
                      ],
                    ),
                    OutlinedButton(
                      onPressed: () {
                        final p = suggestion.simulatorParams;
                        final queryParams = <String, String>{};
                        if (p.containsKey('mode')) queryParams['mode'] = p['mode'].toString();
                        if (p.containsKey('monthly')) queryParams['monthly'] = p['monthly'].toString();
                        if (p.containsKey('years')) queryParams['years'] = p['years'].toString();

                        context.pushNamed(
                          AppConstants.routeSimulator,
                          queryParameters: queryParams.isNotEmpty ? queryParams : const <String, String>{},
                        );
                      },
                      style: OutlinedButton.styleFrom(
                        side: BorderSide(color: AppColors.primary),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                      child: Row(
                        children: [
                          Text(
                            'Simulate This',
                            style: AppText.bodyBold.copyWith(color: AppColors.primary, fontSize: 13),
                          ),
                          const SizedBox(width: 4),
                          Icon(Icons.arrow_forward_rounded, color: AppColors.primary, size: 16),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Positioned(
            top: 8,
            right: 8,
            child: IconButton(
              icon: const Icon(Icons.info_outline_rounded, color: Color(0xFF888888), size: 20),
              onPressed: () => _showDisclaimer(context),
              tooltip: 'About This Projection',
            ),
          ),
        ],
      ),
    );
  }
}

class _HighlightMessage extends StatelessWidget {
  const _HighlightMessage({required this.message, required this.highlightColor});

  final String message;
  final Color highlightColor;

  @override
  Widget build(BuildContext context) {
    // A quick parser to bold amounts (₹XXX) and %
    final words = message.split(' ');
    return RichText(
      text: TextSpan(
        style: AppText.body.copyWith(height: 1.4, color: AppColors.textPrimary),
        children: words.map((word) {
          final isHighlight = word.contains('₹') || word.contains('%');
          return TextSpan(
            text: '$word ',
            style: isHighlight
                ? TextStyle(color: highlightColor, fontWeight: FontWeight.w700)
                : null,
          );
        }).toList(),
      ),
    );
  }
}
