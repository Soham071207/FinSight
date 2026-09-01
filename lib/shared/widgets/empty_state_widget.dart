import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text.dart';
import 'app_button.dart';

class EmptyStateWidget extends StatelessWidget {
  const EmptyStateWidget({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.ctaText,
    this.onCtaPressed,
  });

  final IconData icon;
  final String title;
  final String message;
  final String? ctaText;
  final VoidCallback? onCtaPressed;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.primaryLight.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 64, color: AppColors.primary),
            ),
            const SizedBox(height: 24),
            Text(title, style: AppText.heading2, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(
              message,
              style: AppText.bodySecondary,
              textAlign: TextAlign.center,
            ),
            if (ctaText != null && onCtaPressed != null) ...[
              const SizedBox(height: 32),
              SizedBox(
                width: 200,
                child: AppButton(
                  label: ctaText!,
                  onPressed: onCtaPressed!,
                  isOutlined: true,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
