import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text.dart';

/// Styled text input field for the FinSight design system.
///
/// Filled style, 10px border radius, #F0F4FF fill, error state,
/// password-toggle variant, and optional prefix icon.
///
/// Usage:
///   AppTextField(label: 'Email', controller: _email)
///   AppTextField.password(label: 'Password', controller: _pass)
///   AppTextField(
///     label: 'Amount',
///     prefixIcon: Icons.currency_rupee,
///     keyboardType: TextInputType.number,
///   )
class AppTextField extends StatefulWidget {
  const AppTextField({
    super.key,
    required this.label,
    this.controller,
    this.hint,
    this.prefixIcon,
    this.suffixIcon,
    this.onSuffixTap,
    this.keyboardType,
    this.inputFormatters,
    this.validator,
    this.onChanged,
    this.onFieldSubmitted,
    this.textInputAction,
    this.autofocus = false,
    this.enabled = true,
    this.maxLines = 1,
    this.isPassword = false,
    this.focusNode,
  });

  /// Convenience constructor for password fields with built-in toggle.
  const AppTextField.password({
    super.key,
    required this.label,
    this.controller,
    this.hint,
    this.prefixIcon = Icons.lock_outline_rounded,
    this.validator,
    this.onChanged,
    this.onFieldSubmitted,
    this.textInputAction,
    this.autofocus = false,
    this.enabled = true,
    this.focusNode,
  })  : isPassword = true,
        suffixIcon = null,
        onSuffixTap = null,
        keyboardType = TextInputType.visiblePassword,
        inputFormatters = null,
        maxLines = 1;

  final String label;
  final TextEditingController? controller;
  final String? hint;
  final IconData? prefixIcon;
  final IconData? suffixIcon;
  final VoidCallback? onSuffixTap;
  final TextInputType? keyboardType;
  final List<TextInputFormatter>? inputFormatters;
  final String? Function(String?)? validator;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onFieldSubmitted;
  final TextInputAction? textInputAction;
  final bool autofocus;
  final bool enabled;
  final int maxLines;
  final bool isPassword;
  final FocusNode? focusNode;

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  late bool _obscure;

  @override
  void initState() {
    super.initState();
    _obscure = widget.isPassword;
  }

  void _toggleObscure() => setState(() => _obscure = !_obscure);

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: widget.controller,
      focusNode: widget.focusNode,
      obscureText: _obscure,
      keyboardType: widget.keyboardType,
      inputFormatters: widget.inputFormatters,
      validator: widget.validator,
      onChanged: widget.onChanged,
      onFieldSubmitted: widget.onFieldSubmitted,
      textInputAction: widget.textInputAction,
      autofocus: widget.autofocus,
      enabled: widget.enabled,
      maxLines: widget.isPassword ? 1 : widget.maxLines,
      style: AppText.body.copyWith(color: AppColors.textPrimary),
      decoration: InputDecoration(
        labelText: widget.label,
        hintText: widget.hint,
        labelStyle: AppText.label.copyWith(color: AppColors.textSecondary),
        hintStyle: AppText.bodySecondary,

        // Fill
        filled: true,
        fillColor: widget.enabled ? AppColors.inputFill : AppColors.background,

        // Borders
        border: _border(AppColors.border),
        enabledBorder: _border(AppColors.border),
        focusedBorder: _border(AppColors.primary, width: 1.5),
        errorBorder: _border(AppColors.danger),
        focusedErrorBorder: _border(AppColors.danger, width: 1.5),
        disabledBorder: _border(AppColors.border),

        // Prefix icon
        prefixIcon: widget.prefixIcon != null
            ? Icon(widget.prefixIcon, size: 20, color: AppColors.textSecondary)
            : null,

        // Suffix icon — password toggle takes priority
        suffixIcon: _buildSuffix(),

        // Error styling
        errorStyle: AppText.caption.copyWith(color: AppColors.danger),
        errorMaxLines: 2,

        // Spacing
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
    );
  }

  // ── Suffix ────────────────────────────────────────────────────────────────

  Widget? _buildSuffix() {
    if (widget.isPassword) {
      return GestureDetector(
        onTap: _toggleObscure,
        child: Icon(
          _obscure
              ? Icons.visibility_off_outlined
              : Icons.visibility_outlined,
          size: 20,
          color: AppColors.textSecondary,
        ),
      );
    }

    if (widget.suffixIcon != null) {
      return GestureDetector(
        onTap: widget.onSuffixTap,
        child: Icon(
          widget.suffixIcon,
          size: 20,
          color: AppColors.textSecondary,
        ),
      );
    }

    return null;
  }

  // ── Border helper ─────────────────────────────────────────────────────────

  OutlineInputBorder _border(Color color, {double width = 1.0}) =>
      OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: color, width: width),
      );
}
