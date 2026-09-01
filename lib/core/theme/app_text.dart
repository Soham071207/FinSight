import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

/// Central typography system for the FinSight design system.
///
/// All text in the app must use one of these styles (or a `.copyWith()`
/// variant) — never inline `TextStyle(...)` in widgets.
///
/// Fonts:
///   General UI   → Inter (via google_fonts)
///   Prices/Scores → RobotoMono (via google_fonts)
class AppText {
  const AppText._(); // non-instantiable utility class

  // ── Headings ─────────────────────────────────────────────────────────────────

  /// Heading 1 — 24px / w700 / textPrimary
  /// Used for: Screen titles, large metric labels.
  static TextStyle get heading1 => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 24,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
        letterSpacing: -0.3,
      );

  /// Heading 2 — 20px / w600 / textPrimary
  /// Used for: Section headers, card titles.
  static TextStyle get heading2 => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 20,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
        letterSpacing: -0.2,
      );

  /// Heading 3 — 17px / w600 / textPrimary
  /// Used for: Sub-section headers, fund names in detail screens.
  static TextStyle get heading3 => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 17,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      );

  // ── Body ─────────────────────────────────────────────────────────────────────

  /// Body — 15px / w400 / textPrimary
  /// Used for: General content text, descriptions, form labels.
  static TextStyle get body => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 15,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      );

  /// Body Bold — 15px / w600 / textPrimary
  /// Used for: Inline emphasis, highlighted key values in body copy.
  static TextStyle get bodyBold => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 15,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      );

  /// Body Secondary — 15px / w400 / textSecondary
  /// Used for: Supporting descriptions, hint text, secondary metadata.
  static TextStyle get bodySecondary => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 15,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
      );

  // ── Label ────────────────────────────────────────────────────────────────────

  /// Label — 13px / w500 / textPrimary
  /// Used for: Button text, chip labels, form field labels, tab bar items.
  static TextStyle get label => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 13,
        fontWeight: FontWeight.w500,
        color: AppColors.textPrimary,
      );

  /// Label Secondary — 13px / w500 / textSecondary
  /// Used for: Muted chip labels, inactive navigation items.
  static TextStyle get labelSecondary => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 13,
        fontWeight: FontWeight.w500,
        color: AppColors.textSecondary,
      );

  // ── Caption ──────────────────────────────────────────────────────────────────

  /// Caption — 12px / w400 / textSecondary
  /// Used for: Timestamps, metadata, footnotes, chart axis labels.
  static TextStyle get caption => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
      );

  /// Caption Bold — 12px / w600 / textSecondary
  /// Used for: Bold labels inside chips, small badges.
  static TextStyle get captionBold => GoogleFonts.getFont(AppColors.fontFamily, 
        fontSize: 12,
        fontWeight: FontWeight.w600,
        color: AppColors.textSecondary,
      );

  // ── Monospace (Prices, Scores, Metrics) ──────────────────────────────────────

  /// Price Large — 28px / w700 / RobotoMono / textPrimary
  /// Used for: Hero corpus number on simulator result, CIBIL score display.
  static TextStyle get priceLarge => GoogleFonts.robotoMono(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
        letterSpacing: -0.5,
      );

  /// Price Medium — 20px / w600 / RobotoMono / textPrimary
  /// Used for: Summary card amounts, metric grid primary values.
  static TextStyle get priceMedium => GoogleFonts.robotoMono(
        fontSize: 20,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      );

  /// Price Small — 15px / w500 / RobotoMono / textPrimary
  /// Used for: Table cell values, list tile amounts, inline prices.
  static TextStyle get priceSmall => GoogleFonts.robotoMono(
        fontSize: 15,
        fontWeight: FontWeight.w500,
        color: AppColors.textPrimary,
      );

  /// Mono — fully customisable RobotoMono helper.
  ///
  /// Use `.copyWith()` on one of the named [priceX] getters where possible.
  /// This method is provided for edge cases only.
  ///
  /// Note: [color] defaults to [AppColors.textPrimary] (0xFF1A1A2E).
  static TextStyle mono({
    double fontSize = 15,
    FontWeight fontWeight = FontWeight.w400,
    // Raw hex literal used intentionally: Dart requires default parameter
    // values to be compile-time constants; a static const from another class
    // satisfies this, but using the literal avoids any analyser ambiguity.
    Color color = const Color(0xFF1A1A2E),
  }) =>
      GoogleFonts.robotoMono(
        fontSize: fontSize,
        fontWeight: fontWeight,
        color: color,
      );
}
