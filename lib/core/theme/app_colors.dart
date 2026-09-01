import 'package:flutter/material.dart';
import 'theme_data.dart';

/// Central color manager for the FinSight design system.
/// Values are now dynamic and update when the theme changes.
class AppColors {
  AppColors._(); 

  // Initialize with default theme to avoid late initialization errors before provider loads
  static FinSightTheme _currentTheme = FinSightTheme.softGreen;

  static void setTheme(FinSightTheme theme) {
    _currentTheme = theme;
  }

  static Brightness get brightness => _currentTheme.brightness;
  static String get fontFamily => _currentTheme.fontFamily;

  // ── Core Brand ───────────────────────────────────────────────────────────────
  static Color get primary => _currentTheme.primary;
  static Color get onPrimary => _currentTheme.onPrimary;
  static Color get primaryLight => _currentTheme.primaryLight;

  // ── Semantic ─────────────────────────────────────────────────────────────────
  static Color get accent => _currentTheme.accent;
  static Color get danger => _currentTheme.danger;
  static Color get warning => _currentTheme.warning;

  // ── Surface & Layout ─────────────────────────────────────────────────────────
  static Color get background => _currentTheme.background;
  static Color get surface => _currentTheme.surface;
  static Color get border => _currentTheme.border;

  // ── Typography ───────────────────────────────────────────────────────────────
  static Color get textPrimary => _currentTheme.textPrimary;
  static Color get textSecondary => _currentTheme.textSecondary;

  // ── Input ────────────────────────────────────────────────────────────────────
  static Color get inputFill => _currentTheme.inputFill;

  // ── Chart Palette (series order) ─────────────────────────────────────────────
  static const Color chart1 = Color(0xFFE8681A);
  static const Color chart2 = Color(0xFF00C48C);
  static const Color chart3 = Color(0xFFFAAD14);
  static const Color chart4 = Color(0xFFFF4D4F);
  static const List<Color> chartPalette = [chart1, chart2, chart3, chart4];

  // ── CIBIL Score Bands ────────────────────────────────────────────────────────
  static const Color cibilPoor = Color(0xFFFF4D4F);
  static const Color cibilFair = Color(0xFFFAAD14);
  static const Color cibilGood = Color(0xFFE8681A);
  static const Color cibilVeryGood = Color(0xFF00C48C);
  static const Color cibilExcellent = Color(0xFF00875A);

  // ── Expense Categories ───────────────────────────────────────────────────────
  static const Color catFood          = Color(0xFFFF7043);
  static const Color catTransport     = Color(0xFFE8681A);
  static const Color catEntertainment = Color(0xFF9C27B0);
  static const Color catSubscriptions = Color(0xFFE91E63);
  static const Color catShopping      = Color(0xFFFF9800);
  static const Color catHealthcare    = Color(0xFF00C48C);
  static const Color catMisc          = Color(0xFF6B7280);

  // ── Fund Score / Return Thresholds ──────────────────────────────────────────
  static const Color returnHigh   = Color(0xFF00C48C);
  static const Color returnMid    = Color(0xFFFAAD14);
  static const Color returnLow    = Color(0xFFFF4D4F);

  // ── Budget Bar States ────────────────────────────────────────────────────────
  static const Color budgetSafe   = Color(0xFFE8681A);
  static const Color budgetCaution = Color(0xFFFAAD14);
  static const Color budgetExceeded = Color(0xFFFF4D4F);
}
