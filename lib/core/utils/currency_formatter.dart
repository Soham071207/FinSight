import 'package:intl/intl.dart';

/// Utility for formatting monetary values in Indian Rupee format.
///
/// Indian number system uses commas at:
///   - Thousands (rightmost group of 3)
///   - Then every 2 digits to the left
///
/// Examples:
///   formatINR(140000)    → ₹1,40,000
///   formatINR(1200.50)   → ₹1,200.50
///   formatINR(10000000)  → ₹1,00,00,000
///   formatINR(500)       → ₹500
///   formatINR(0)         → ₹0
///   formatINR(-25000)    → -₹25,000
///   formatINRCompact(1400000) → ₹14L
///   formatINRCompact(10000000) → ₹1Cr

/// The [NumberFormat] instance configured for Indian locale (en_IN).
/// This natively produces groupings like 1,40,000.
final _inrFull = NumberFormat.currency(
  locale: 'en_IN',
  symbol: '₹',
  decimalDigits: 0,
);

final _inrWithPaise = NumberFormat.currency(
  locale: 'en_IN',
  symbol: '₹',
  decimalDigits: 2,
);

/// Formats [amount] to Indian number format with ₹ prefix.
///
/// - Whole numbers (no fractional part): zero decimal places.
///   e.g. 140000 → ₹1,40,000
/// - Values with paise (fractional part != 0): two decimal places.
///   e.g. 1200.50 → ₹1,200.50
/// - Negative values: minus sign before ₹.
///   e.g. -25000 → -₹25,000
String formatINR(double amount) {
  // Separate sign so ₹ always precedes the digits.
  final bool isNegative = amount < 0;
  final double abs = amount.abs();

  // Use decimal format only when there are meaningful paise.
  final bool hasPaise = (abs - abs.truncate()) >= 0.005;
  final String formatted =
      hasPaise ? _inrWithPaise.format(abs) : _inrFull.format(abs);

  return isNegative ? '-$formatted' : formatted;
}

/// Compact format for large values — replaces full formatting with
/// abbreviated suffixes used in financial summaries and fund AUM displays.
///
/// Breakpoints follow Indian convention:
///   ≥ 1 Crore  (1,00,00,000) → XCr
///   ≥ 1 Lakh   (1,00,000)    → XL
///   < 1 Lakh                 → full formatINR()
///
/// Examples:
///   formatINRCompact(14000000)  → ₹1.4Cr
///   formatINRCompact(1400000)   → ₹14L
///   formatINRCompact(75000)     → ₹75,000
String formatINRCompact(double amount) {
  final bool isNegative = amount < 0;
  final double abs = amount.abs();

  String result;

  if (abs >= 1e7) {
    // Crores
    final double crores = abs / 1e7;
    final String formatted = crores == crores.truncate()
        ? '₹${crores.toStringAsFixed(0)}Cr'
        : '₹${crores.toStringAsFixed(2).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '')}Cr';
    result = formatted;
  } else if (abs >= 1e5) {
    // Lakhs
    final double lakhs = abs / 1e5;
    final String formatted = lakhs == lakhs.truncate()
        ? '₹${lakhs.toStringAsFixed(0)}L'
        : '₹${lakhs.toStringAsFixed(2).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '')}L';
    result = formatted;
  } else {
    result = formatINR(abs);
  }

  return isNegative ? '-$result' : result;
}

/// Formats a delta value with directional prefix and colour hint string.
///
/// Returns a [_DeltaResult] with:
///   - [text]      e.g. "↑ ₹12,000" or "↓ ₹3,500"
///   - [isPositive] for colour selection in the widget layer
class DeltaResult {
  const DeltaResult({required this.text, required this.isPositive});
  final String text;
  final bool isPositive;
}

/// Formats a delta (change) amount with ↑ / ↓ arrow prefix.
///
/// Example:
///   formatDelta(12000)   → DeltaResult(text: "↑ ₹12,000", isPositive: true)
///   formatDelta(-3500)   → DeltaResult(text: "↓ ₹3,500",  isPositive: false)
DeltaResult formatDelta(double delta) {
  final bool positive = delta >= 0;
  final String arrow = positive ? '↑' : '↓';
  final String amount = formatINR(delta.abs());
  return DeltaResult(text: '$arrow $amount', isPositive: positive);
}

/// Formats a percentage delta with ↑ / ↓ arrow prefix and % suffix.
///
/// Example:
///   formatDeltaPct(14.35)  → DeltaResult(text: "↑ 14.35%", isPositive: true)
///   formatDeltaPct(-3.2)   → DeltaResult(text: "↓ 3.20%",  isPositive: false)
DeltaResult formatDeltaPct(double pct) {
  final bool positive = pct >= 0;
  final String arrow = positive ? '↑' : '↓';
  final String value = '${pct.abs().toStringAsFixed(2)}%';
  return DeltaResult(text: '$arrow $value', isPositive: positive);
}
