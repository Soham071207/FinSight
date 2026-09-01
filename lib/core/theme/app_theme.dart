import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';
import 'app_text.dart';
import 'app_sizes.dart';

class AppTheme {
  const AppTheme._();

  static ThemeData get light => ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,

        // ── Colour Scheme ───────────────────────────────────────────────────
        colorScheme: ColorScheme.light(
          primary: AppColors.primary,
          onPrimary: AppColors.textPrimary,
          primaryContainer: AppColors.primaryLight,
          onPrimaryContainer: AppColors.primary,
          secondary: AppColors.accent,
          onSecondary: AppColors.textPrimary,
          error: AppColors.danger,
          onError: Colors.white,
          surface: AppColors.surface,
          onSurface: AppColors.textPrimary,
          surfaceContainerHighest: AppColors.background,
          outline: AppColors.border,
        ),

        // ── Scaffold ────────────────────────────────────────────────────────
        scaffoldBackgroundColor: AppColors.background,

        // ── Base Text Theme ─────────────────────────────────────────────────
        textTheme: GoogleFonts.interTextTheme().copyWith(
          displayLarge: AppText.heading1,
          displayMedium: AppText.heading2,
          displaySmall: AppText.heading3,
          bodyLarge: AppText.body,
          bodyMedium: AppText.bodySecondary,
          bodySmall: AppText.caption,
          labelLarge: AppText.label,
          labelMedium: AppText.labelSecondary,
          labelSmall: AppText.captionBold,
        ),

        // ── AppBar ──────────────────────────────────────────────────────────
        appBarTheme: AppBarTheme(
          backgroundColor: AppColors.surface,
          foregroundColor: AppColors.textPrimary,
          elevation: 0,
          scrolledUnderElevation: 0,
          shadowColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          centerTitle: false,
          titleTextStyle: AppText.heading2,
          iconTheme: IconThemeData(color: AppColors.textPrimary),
          shape: Border(
            bottom: BorderSide(color: AppColors.border, width: 1),
          ),
        ),

        // ── Card ────────────────────────────────────────────────────────────
        cardTheme: CardThemeData(
          color: AppColors.surface,
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(AppSizes.cardRadius)),
            side: BorderSide.none,
          ),
          clipBehavior: Clip.antiAlias,
          surfaceTintColor: Colors.transparent,
        ),

        // ── Elevated Button ─────────────────────────────────────────────────
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: AppColors.textPrimary,
            minimumSize: const Size.fromHeight(AppSizes.buttonHeight),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppSizes.buttonRadius),
            ),
            elevation: 0,
            shadowColor: Colors.transparent,
            textStyle: AppText.label.copyWith(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
        ),

        // ── Outlined Button ─────────────────────────────────────────────────
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.primary,
            minimumSize: const Size.fromHeight(AppSizes.buttonHeight),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppSizes.buttonRadius),
            ),
            side: BorderSide(color: AppColors.primary, width: 1.5),
            textStyle: AppText.label.copyWith(
              fontSize: 15,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),

        // ── Text Button ─────────────────────────────────────────────────────
        textButtonTheme: TextButtonThemeData(
          style: TextButton.styleFrom(
            foregroundColor: AppColors.primary,
            textStyle: AppText.label.copyWith(fontWeight: FontWeight.w600),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppSizes.chipRadius),
            ),
          ),
        ),

        // ── Input Decoration ────────────────────────────────────────────────
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: AppColors.inputFill,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppSizes.inputRadius),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppSizes.inputRadius),
            borderSide: BorderSide.none,
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppSizes.inputRadius),
            borderSide: BorderSide(color: AppColors.primary, width: 1.5),
          ),
          errorBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppSizes.inputRadius),
            borderSide: BorderSide(color: AppColors.danger),
          ),
          focusedErrorBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppSizes.inputRadius),
            borderSide: BorderSide(color: AppColors.danger, width: 1.5),
          ),
          hintStyle: AppText.bodySecondary,
          labelStyle: AppText.label,
          errorStyle: AppText.caption.copyWith(color: AppColors.danger),
          prefixIconColor: AppColors.textSecondary,
          suffixIconColor: AppColors.textSecondary,
        ),

        // ── Chip ────────────────────────────────────────────────────────────
        chipTheme: ChipThemeData(
          backgroundColor: AppColors.primaryLight,
          selectedColor: AppColors.primary,
          disabledColor: AppColors.background,
          labelStyle: AppText.label,
          secondaryLabelStyle: AppText.label.copyWith(color: AppColors.textPrimary),
          side: BorderSide.none,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSizes.chipRadius),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        ),

        // ── Divider ─────────────────────────────────────────────────────────
        dividerTheme: DividerThemeData(
          color: AppColors.border,
          thickness: 1,
          space: 1,
        ),

        // ── Bottom Navigation Bar ────────────────────────────────────────────
        bottomNavigationBarTheme: BottomNavigationBarThemeData(
          backgroundColor: AppColors.surface,
          selectedItemColor: AppColors.textPrimary,
          unselectedItemColor: AppColors.textSecondary,
          elevation: 0,
          type: BottomNavigationBarType.fixed,
          selectedLabelStyle: AppText.caption.copyWith(
            color: AppColors.textPrimary,
            fontWeight: FontWeight.w600,
          ),
          unselectedLabelStyle: AppText.caption,
          showUnselectedLabels: true,
        ),

        // ── Tab Bar ──────────────────────────────────────────────────────────
        tabBarTheme: TabBarThemeData(
          labelColor: AppColors.textPrimary,
          unselectedLabelColor: AppColors.textSecondary,
          labelStyle: AppText.label.copyWith(fontWeight: FontWeight.w600),
          unselectedLabelStyle: AppText.label,
          indicatorColor: AppColors.textPrimary,
          indicatorSize: TabBarIndicatorSize.label,
          dividerColor: AppColors.border,
        ),

        // ── Snack Bar ────────────────────────────────────────────────────────
        snackBarTheme: SnackBarThemeData(
          backgroundColor: AppColors.textPrimary,
          contentTextStyle: AppText.body.copyWith(color: AppColors.surface),
          actionTextColor: AppColors.accent,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),

        // ── Bottom Sheet ─────────────────────────────────────────────────────
        bottomSheetTheme: BottomSheetThemeData(
          backgroundColor: AppColors.surface,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(AppSizes.sheetRadius)),
          ),
          showDragHandle: true,
          dragHandleColor: AppColors.border,
          elevation: 0,
        ),

        // ── Dialog ───────────────────────────────────────────────────────────
        dialogTheme: DialogThemeData(
          backgroundColor: AppColors.surface,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSizes.dialogRadius),
            side: BorderSide.none,
          ),
          titleTextStyle: AppText.heading2,
          contentTextStyle: AppText.body,
        ),

        // ── List Tile ────────────────────────────────────────────────────────
        listTileTheme: ListTileThemeData(
          tileColor: AppColors.surface,
          iconColor: AppColors.textSecondary,
          contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        ),

        // ── Icon ─────────────────────────────────────────────────────────────
        iconTheme: IconThemeData(
          color: AppColors.textSecondary,
          size: 22,
        ),

        // ── Page Transitions ─────────────────────────────────────────────────
        pageTransitionsTheme: const PageTransitionsTheme(
          builders: {
            TargetPlatform.android: FadeUpwardsPageTransitionsBuilder(),
            TargetPlatform.iOS: FadeUpwardsPageTransitionsBuilder(),
            TargetPlatform.windows: FadeUpwardsPageTransitionsBuilder(),
            TargetPlatform.macOS: FadeUpwardsPageTransitionsBuilder(),
            TargetPlatform.linux: FadeUpwardsPageTransitionsBuilder(),
          },
        ),
        
        // ── Date Picker ──────────────────────────────────────────────────────
        datePickerTheme: DatePickerThemeData(
          backgroundColor: AppColors.surface,
          headerBackgroundColor: AppColors.primary,
          headerForegroundColor: AppColors.onPrimary,
          dayForegroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return AppColors.onPrimary;
            } else if (states.contains(WidgetState.disabled)) {
              return AppColors.textSecondary.withValues(alpha: 0.38);
            }
            return AppColors.textPrimary;
          }),
          todayForegroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return AppColors.onPrimary;
            }
            return AppColors.primary;
          }),
          yearForegroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return AppColors.onPrimary;
            }
            return AppColors.textPrimary;
          }),
          dayBackgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return AppColors.primary;
            }
            return null;
          }),
          todayBackgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return AppColors.primary;
            }
            return null;
          }),
        ),
      );
}
