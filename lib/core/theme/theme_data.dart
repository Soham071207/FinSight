import 'package:flutter/material.dart';

class FinSightTheme {
  final String id;
  final String name;
  final Brightness brightness;
  final Color primary;
  final Color primaryLight;
  final Color accent;
  final Color danger;
  final Color warning;
  final Color background;
  final Color surface;
  final Color border;
  final Color textPrimary;
  final Color textSecondary;
  final Color inputFill;
  final String fontFamily;
  final Color onPrimary;

  const FinSightTheme({
    required this.id,
    required this.name,
    required this.brightness,
    required this.primary,
    required this.onPrimary,
    required this.primaryLight,
    required this.accent,
    required this.danger,
    required this.warning,
    required this.background,
    required this.surface,
    required this.border,
    required this.textPrimary,
    required this.textSecondary,
    required this.inputFill,
    required this.fontFamily,
  });

  // 1. Sky Blue (Formerly Soft Green)
  static const FinSightTheme softGreen = FinSightTheme(
    id: 'softGreen',
    name: 'Sky Blue',
    brightness: Brightness.light,
    primary: Color(0xFF0288D1), // Deep Sky Blue
    onPrimary: Color(0xFFFFFFFF),
    primaryLight: Color(0xFFE1F5FE), // Very light blue
    accent: Color(0xFF81C784), // Positive green for gains
    danger: Color(0xFFE57373),
    warning: Color(0xFFFFB74D),
    background: Color(0xFFF4F9FC), // Cool white background
    surface: Color(0xFFFFFFFF), // Pure white surface
    border: Color(0xFFB3E5FC),
    textPrimary: Color(0xFF01579B), // Dark blue text
    textSecondary: Color(0xFF4F83CC), // Muted blue
    inputFill: Color(0xFFE1F5FE), // Light blue input fill
    fontFamily: 'Outfit',
  );

  // 2. Midnight Blue & Gold (Premium/Wealth)
  static const FinSightTheme midnightBlue = FinSightTheme(
    id: 'midnightBlue',
    name: 'Midnight Blue',
    brightness: Brightness.dark,
    primary: Color(0xFFF59E0B), // Gold
    onPrimary: Color(0xFF0F172A), // Dark Navy
    primaryLight: Color(0xFF475569), // Slate
    accent: Color(0xFF10B981), // Emerald
    danger: Color(0xFFF43F5E), // Rose
    warning: Color(0xFFF59E0B), // Amber
    background: Color(0xFF0F172A), // Navy Base
    surface: Color(0xFF1E293B), // Navy Surface
    border: Color(0xFF334155),
    textPrimary: Color(0xFFF8FAFC),
    textSecondary: Color(0xFF94A3B8),
    inputFill: Color(0xFF1E293B),
    fontFamily: 'Montserrat',
  );

  // 3. Clean Minimalist (Modern Fintech)
  static const FinSightTheme cleanMinimal = FinSightTheme(
    id: 'cleanMinimal',
    name: 'Clean Minimal',
    brightness: Brightness.light,
    primary: Color(0xFF111827), // Charcoal
    onPrimary: Color(0xFFFFFFFF),
    primaryLight: Color(0xFFF3F4F6),
    accent: Color(0xFF3B82F6), // Electric Blue
    danger: Color(0xFFEF4444),
    warning: Color(0xFFF59E0B),
    background: Color(0xFFF9FAFB),
    surface: Color(0xFFFFFFFF),
    border: Color(0xFFE5E7EB),
    textPrimary: Color(0xFF111827),
    textSecondary: Color(0xFF6B7280),
    inputFill: Color(0xFFF3F4F6),
    fontFamily: 'Inter',
  );

  // 4. Neobank Dark (Gen-Z)
  static const FinSightTheme neobankDark = FinSightTheme(
    id: 'neobankDark',
    name: 'Neobank Dark',
    brightness: Brightness.dark,
    primary: Color(0xFFA855F7), // Neon Purple
    onPrimary: Color(0xFFFFFFFF),
    primaryLight: Color(0xFF2D1B4B),
    accent: Color(0xFF14B8A6), // Teal
    danger: Color(0xFFFF2A5F),
    warning: Color(0xFFFFB300),
    background: Color(0xFF09090B), // Almost Black
    surface: Color(0xFF18181B), // Dark Gray
    border: Color(0xFF27272A),
    textPrimary: Color(0xFFFAFAFA),
    textSecondary: Color(0xFFA1A1AA),
    inputFill: Color(0xFF18181B),
    fontFamily: 'Space Grotesk',
  );

  // 5. Pink White (Soft & Elegant)
  static const FinSightTheme pinkWhite = FinSightTheme(
    id: 'pinkWhite',
    name: 'Pink White',
    brightness: Brightness.light,
    primary: Color(0xFFE91E63), // Vibrant Pink
    onPrimary: Color(0xFFFFFFFF),
    primaryLight: Color(0xFFFCE4EC), // Very light pink
    accent: Color(0xFF9C27B0), // Purple accent
    danger: Color(0xFFD32F2F),
    warning: Color(0xFFF57C00),
    background: Color(0xFFFFF7F9), // Soft white-pink background
    surface: Color(0xFFFFFFFF),
    border: Color(0xFFF8BBD0),
    textPrimary: Color(0xFF880E4F), // Deep pink text
    textSecondary: Color(0xFFAD1457), // Muted pink
    inputFill: Color(0xFFFCE4EC),
    fontFamily: 'Inter',
  );

  // 6. Pink Purple (Vibrant & Neon)
  static const FinSightTheme pinkPurple = FinSightTheme(
    id: 'pinkPurple',
    name: 'Pink Purple',
    brightness: Brightness.dark,
    primary: Color(0xFFFF4081), // Neon Pink
    onPrimary: Color(0xFFFFFFFF),
    primaryLight: Color(0xFF4A148C), // Deep Purple
    accent: Color(0xFFE040FB), // Neon Purple
    danger: Color(0xFFFF1744),
    warning: Color(0xFFFF9100),
    background: Color(0xFF1A0021), // Very dark purple background
    surface: Color(0xFF311B3D), // Purple surface
    border: Color(0xFF6A1B9A),
    textPrimary: Color(0xFFFCE4EC),
    textSecondary: Color(0xFFCE93D8),
    inputFill: Color(0xFF311B3D),
    fontFamily: 'Space Grotesk',
  );

  static const List<FinSightTheme> values = [
    softGreen,
    midnightBlue,
    cleanMinimal,
    neobankDark,
    pinkWhite,
    pinkPurple,
  ];
}
