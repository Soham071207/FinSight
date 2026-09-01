import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text.dart';
import '../../core/theme/app_sizes.dart';

/// Primary filled button and outlined variant for the FinSight design system.
///
/// Usage:
///   AppButton(label: 'Sign In', onPressed: _submit)
///   AppButton.outlined(label: 'Cancel', onPressed: _cancel)
///   AppButton(label: 'Loading…', onPressed: null, isLoading: true)
class AppButton extends StatelessWidget {
  const AppButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.isOutlined = false,
    this.prefixIcon,
    this.width,
  });

  /// Convenience constructor for the outlined variant.
  const AppButton.outlined({
    super.key,
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.prefixIcon,
    this.width,
  }) : isOutlined = true;

  final String label;

  /// Set to null to disable the button (shows disabled style).
  final VoidCallback? onPressed;

  /// When true, replaces the label with a shimmer bar and blocks taps.
  final bool isLoading;

  /// When true, renders the outlined variant instead of the filled variant.
  final bool isOutlined;

  /// Optional leading icon inside the button.
  final IconData? prefixIcon;

  /// Optional fixed width. Defaults to full width (double.infinity).
  final double? width;

  @override
  Widget build(BuildContext context) {
    final bool disabled = onPressed == null && !isLoading;

    Widget child = _buildLabel(disabled);

    if (isLoading) {
      child = _buildShimmerLabel();
    }

    final buttonStyle = isOutlined ? _outlinedStyle(disabled) : _filledStyle(disabled);

    final button = isOutlined
        ? OutlinedButton(
            style: buttonStyle,
            onPressed: isLoading ? null : onPressed,
            child: child,
          )
        : ElevatedButton(
            style: buttonStyle,
            onPressed: isLoading ? null : onPressed,
            child: child,
          );

    return SizedBox(
      width: width ?? double.infinity,
      height: AppSizes.buttonHeight,
      child: button,
    );
  }

  // ── Label ─────────────────────────────────────────────────────────────────

  Widget _buildLabel(bool disabled) {
    final Color labelColor = isOutlined
        ? (disabled ? AppColors.textSecondary : AppColors.textPrimary)
        : (disabled ? AppColors.textSecondary : AppColors.onPrimary);

    return Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (prefixIcon != null) ...[
          Icon(prefixIcon, size: 18, color: labelColor),
          AppSizes.w8,
        ],
        Text(
          label,
          style: AppText.label.copyWith(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: labelColor,
          ),
        ),
      ],
    );
  }

  // ── Shimmer loading label ─────────────────────────────────────────────────

  Widget _buildShimmerLabel() {
    final Color baseColor = isOutlined
        ? AppColors.primaryLight
        : AppColors.primary.withValues(alpha: 0.6);
    final Color highlightColor = isOutlined
        ? AppColors.surface
        : AppColors.primary.withValues(alpha: 0.9);

    return Shimmer.fromColors(
      baseColor: baseColor,
      highlightColor: highlightColor,
      child: Container(
        width: 100,
        height: 16,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  // ── Button styles ─────────────────────────────────────────────────────────

  ButtonStyle _filledStyle(bool disabled) => ElevatedButton.styleFrom(
        backgroundColor:
            disabled ? AppColors.border : AppColors.primary,
        foregroundColor: AppColors.textPrimary,
        disabledBackgroundColor: AppColors.border,
        disabledForegroundColor: AppColors.textSecondary,
        elevation: 0,
        shadowColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSizes.buttonRadius),
        ),
      );

  ButtonStyle _outlinedStyle(bool disabled) => OutlinedButton.styleFrom(
        foregroundColor:
            disabled ? AppColors.textSecondary : AppColors.textPrimary,
        disabledForegroundColor: AppColors.textSecondary,
        side: BorderSide(
          color: disabled ? AppColors.border : AppColors.primary,
          width: 1.5,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSizes.buttonRadius),
        ),
      );
}
