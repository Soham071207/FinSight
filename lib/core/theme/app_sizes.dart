import 'package:flutter/material.dart';

/// Central sizing, spacing, and dimensions system for the FinSight app.
/// Customize values here to scale margins, padding, border radii, and button heights globally.
class AppSizes {
  const AppSizes._();

  // ── Layout Margins & Spacing (8-Point Grid) ──────────────────────────────────
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 12.0;
  static const double lg = 16.0;
  static const double xl = 24.0;
  static const double xxl = 32.0;

  // ── Border Radii ─────────────────────────────────────────────────────────────
  static const double radiusXs = 4.0;
  static const double radiusSm = 8.0;
  static const double radiusMd = 12.0;
  static const double radiusLg = 16.0;
  static const double radiusXl = 20.0;
  static const double radiusRound = 999.0;

  // ── Component Sizes ──────────────────────────────────────────────────────────
  static const double buttonHeight = 56.0;
  static const double inputHeight = 56.0;
  static const double cardRadius = 24.0;
  static const double buttonRadius = 999.0;
  static const double inputRadius = 16.0;
  static const double chipRadius = 24.0;
  static const double sheetRadius = 32.0;
  static const double dialogRadius = 24.0;
  static const double cardBorderWidth = 0.0;

  // ── Commonly Used SizedBox Helpers for Spacing ──────────────────────────────
  static const SizedBox h4 = SizedBox(height: xs);
  static const SizedBox h8 = SizedBox(height: sm);
  static const SizedBox h12 = SizedBox(height: md);
  static const SizedBox h16 = SizedBox(height: lg);
  static const SizedBox h20 = SizedBox(height: 20.0);
  static const SizedBox h24 = SizedBox(height: xl);
  static const SizedBox h32 = SizedBox(height: xxl);
  static const SizedBox h48 = SizedBox(height: 48.0);

  static const SizedBox w4 = SizedBox(width: xs);
  static const SizedBox w8 = SizedBox(width: sm);
  static const SizedBox w12 = SizedBox(width: md);
  static const SizedBox w16 = SizedBox(width: lg);
  static const SizedBox w20 = SizedBox(width: 20.0);
  static const SizedBox w24 = SizedBox(width: xl);
  static const SizedBox w32 = SizedBox(width: xxl);

  // ── Margins & Padding Insets ────────────────────────────────────────────────
  static const EdgeInsets paddingAllXs = EdgeInsets.all(xs);
  static const EdgeInsets paddingAllSm = EdgeInsets.all(sm);
  static const EdgeInsets paddingAllMd = EdgeInsets.all(md);
  static const EdgeInsets paddingAllLg = EdgeInsets.all(lg);
  static const EdgeInsets paddingAllXl = EdgeInsets.all(xl);

  static const EdgeInsets paddingHorizontalLg = EdgeInsets.symmetric(horizontal: lg);
  static const EdgeInsets paddingVerticalLg = EdgeInsets.symmetric(vertical: lg);
  static const EdgeInsets paddingHorizontalMd = EdgeInsets.symmetric(horizontal: md);
  static const EdgeInsets paddingVerticalMd = EdgeInsets.symmetric(vertical: md);
}
