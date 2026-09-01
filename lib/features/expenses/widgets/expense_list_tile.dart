import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../data/local/models/expense_entry.dart';

class CategoryStyle {
  static const Map<String, Color> colors = {
    'Food': AppColors.catFood,
    'Transport': AppColors.catTransport,
    'Entertainment': AppColors.catEntertainment,
    'Subscriptions': AppColors.catSubscriptions,
    'Shopping': AppColors.catShopping,
    'Healthcare': AppColors.catHealthcare,
    'Miscellaneous': AppColors.catMisc,
  };

  static const Map<String, IconData> icons = {
    'Food': Icons.restaurant_rounded,
    'Transport': Icons.directions_car_rounded,
    'Entertainment': Icons.celebration_rounded,
    'Subscriptions': Icons.repeat_rounded,
    'Shopping': Icons.shopping_bag_rounded,
    'Healthcare': Icons.favorite_rounded,
    'Miscellaneous': Icons.more_horiz_rounded,
  };

  static Color getColor(String category) {
    return colors[category] ?? colors['Miscellaneous']!;
  }

  static IconData getIcon(String category) {
    return icons[category] ?? icons['Miscellaneous']!;
  }
}

class ExpenseListTile extends StatelessWidget {
  const ExpenseListTile({
    super.key,
    required this.entry,
    required this.onDelete,
    required this.onTap,
  });

  final ExpenseEntry entry;
  final VoidCallback onDelete;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = CategoryStyle.getColor(entry.category);
    final icon = CategoryStyle.getIcon(entry.category);

    return Dismissible(
      key: Key(entry.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        color: AppColors.danger,
        child: const Icon(Icons.delete_outline_rounded, color: Colors.white),
      ),
      onDismissed: (_) => onDelete(),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              // Category Icon
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(width: 16),
              
              // Middle Info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          entry.category,
                          style: AppText.bodyBold,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (entry.source == 'sms_import') ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppColors.border,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              'SMS',
                              style: AppText.caption.copyWith(
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    if (entry.note.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        entry.note,
                        style: AppText.bodySecondary,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 16),
              
              // Right side amounts
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    formatINR(entry.amount),
                    style: AppText.bodyBold,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    DateFormat('h:mm a').format(entry.timestamp),
                    style: AppText.caption,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
