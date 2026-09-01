import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_colors.dart';
import 'core/theme/theme_provider.dart';

class FinSightApp extends ConsumerWidget {
  const FinSightApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    final currentTheme = ref.watch(themeProvider); // This forces rebuild on theme change


    return MaterialApp.router(
      title: 'FinSight',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          background: AppColors.background,
          surface: AppColors.surface,
          brightness: currentTheme.brightness,
        ),
        scaffoldBackgroundColor: AppColors.background,
        textTheme: GoogleFonts.getTextTheme(currentTheme.fontFamily, Theme.of(context).textTheme),
        appBarTheme: AppBarTheme(
          backgroundColor: AppColors.surface,
          foregroundColor: AppColors.textPrimary,
          elevation: 0,
          scrolledUnderElevation: 0,
        ),
        switchTheme: SwitchThemeData(
          thumbColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.selected) ? AppColors.primary : Colors.grey.shade400),
          trackColor: WidgetStateProperty.resolveWith((s) =>
              s.contains(WidgetState.selected) ? AppColors.primaryLight : Colors.grey.shade200),
        ),
        floatingActionButtonTheme: FloatingActionButtonThemeData(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
        ),
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
      ),
      routerConfig: router,
    );
  }
}
