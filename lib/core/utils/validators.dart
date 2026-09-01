/// Form field validators for the FinSight app.
///
/// All validators return [String?]:
///   - null  → field is valid (Flutter Form convention)
///   - String → error message to display inline below the field
///
/// Usage:
///   TextFormField(validator: Validators.email)
///   TextFormField(validator: Validators.required('Full name'))
library;

class Validators {
  const Validators._();

  // ── Regex patterns ───────────────────────────────────────────────────────────

  static final _emailRegex = RegExp(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$',
  );

  /// At least one digit somewhere in the string.
  static final _hasDigit = RegExp(r'\d');

  /// Matches characters that are NOT digits or decimal points.
  static final _nonNumeric = RegExp(r'[^\d.]');

  /// Detects more than one decimal point.
  static final _multiDot = RegExp(r'\..*\.');

  // ── Validators ───────────────────────────────────────────────────────────────

  /// Validates a non-empty, properly formatted email address.
  ///
  /// Rules:
  ///   • Must not be blank
  ///   • Must match standard email pattern (RFC-5321 simplified)
  static String? email(String? value) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return 'Email address is required.';
    if (!_emailRegex.hasMatch(v)) return 'Enter a valid email address.';
    return null;
  }

  /// Validates a password that meets minimum security requirements.
  ///
  /// Rules:
  ///   • Must not be blank
  ///   • Minimum 8 characters
  ///   • Must contain at least 1 digit
  static String? password(String? value) {
    final v = value ?? '';
    if (v.isEmpty)   return 'Password is required.';
    if (v.length < 8) return 'Password must be at least 8 characters.';
    if (!_hasDigit.hasMatch(v)) return 'Password must contain at least 1 number.';
    return null;
  }

  /// Validates that [confirmValue] matches [originalPassword].
  ///
  /// Use on the "Confirm password" field during registration.
  static String? Function(String?) confirmPassword(String originalPassword) {
    return (String? value) {
      if (value == null || value.isEmpty) return 'Please confirm your password.';
      if (value != originalPassword) return 'Passwords do not match.';
      return null;
    };
  }

  /// Validates a monetary amount (₹).
  ///
  /// Rules:
  ///   • Must not be blank
  ///   • Must be a valid positive number
  ///   • No more than one decimal point
  ///   • Value must be greater than zero
  ///   • Optional [min] and [max] bounds (inclusive)
  static String? Function(String?) amount({
    double min = 0,
    double? max,
    String fieldName = 'Amount',
  }) {
    return (String? value) {
      final v = value?.trim() ?? '';
      if (v.isEmpty) return '$fieldName is required.';
      if (_nonNumeric.hasMatch(v)) return 'Enter a valid number.';
      if (_multiDot.hasMatch(v)) return 'Enter a valid number.';

      final parsed = double.tryParse(v);
      if (parsed == null) return 'Enter a valid number.';
      if (parsed <= 0) return '$fieldName must be greater than zero.';
      if (parsed < min) return '$fieldName must be at least ₹${min.toStringAsFixed(0)}.';
      if (max != null && parsed > max) {
        return '$fieldName cannot exceed ₹${max.toStringAsFixed(0)}.';
      }
      return null;
    };
  }

  /// Validates that a field is not empty or whitespace-only.
  ///
  /// [fieldName] is used in the error message for context.
  ///
  /// Example:
  ///   validator: Validators.required('Full name')
  static String? Function(String?) required(String fieldName) {
    return (String? value) {
      if (value == null || value.trim().isEmpty) {
        return '$fieldName is required.';
      }
      return null;
    };
  }

  /// Validates a full name (used on the Register screen).
  ///
  /// Rules:
  ///   • Must not be blank
  ///   • Minimum 2 characters
  ///   • No leading/trailing whitespace after trim
  static String? fullName(String? value) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return 'Full name is required.';
    if (v.length < 2) return 'Enter your full name.';
    return null;
  }

  /// Validates an integer count (e.g. number of missed payments, accounts).
  ///
  /// Rules:
  ///   • Must not be blank
  ///   • Must be a non-negative whole number
  ///   • Optional [max] bound
  static String? Function(String?) count({
    int max = 999,
    String fieldName = 'Value',
  }) {
    return (String? value) {
      final v = value?.trim() ?? '';
      if (v.isEmpty) return '$fieldName is required.';
      final parsed = int.tryParse(v);
      if (parsed == null || parsed < 0) return 'Enter a valid whole number.';
      if (parsed > max) return '$fieldName cannot exceed $max.';
      return null;
    };
  }

  /// Validates a percentage value (0–100).
  ///
  /// Rules:
  ///   • Must not be blank
  ///   • Must be a number between [min] and [max] (default 0–100)
  static String? Function(String?) percentage({
    double min = 0,
    double max = 100,
    String fieldName = 'Percentage',
  }) {
    return (String? value) {
      final v = value?.trim() ?? '';
      if (v.isEmpty) return '$fieldName is required.';
      final parsed = double.tryParse(v);
      if (parsed == null) return 'Enter a valid percentage.';
      if (parsed < min || parsed > max) {
        return '$fieldName must be between ${min.toStringAsFixed(0)}% and ${max.toStringAsFixed(0)}%.';
      }
      return null;
    };
  }
}
