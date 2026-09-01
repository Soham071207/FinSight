import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text.dart';
import 'app_button.dart';

class ErrorStateWidget extends StatelessWidget {
  const ErrorStateWidget({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

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
                color: AppColors.danger.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.error_outline_rounded, size: 64, color: AppColors.danger),
            ),
            const SizedBox(height: 24),
            Text('Oops! Something went wrong', style: AppText.heading2, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(
              message,
              style: AppText.bodySecondary,
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 32),
              SizedBox(
                width: 200,
                child: AppButton(
                  label: 'Try Again',
                  onPressed: onRetry!,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
