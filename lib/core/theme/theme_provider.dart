import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'theme_data.dart';
import 'app_colors.dart';

class ThemeNotifier extends Notifier<FinSightTheme> {
  static const _themeKey = 'finsight_theme_preference';

  @override
  FinSightTheme build() {
    _loadTheme();
    return FinSightTheme.softGreen; // Default fallback while loading
  }

  Future<void> _loadTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final savedId = prefs.getString(_themeKey);
    final theme = FinSightTheme.values.firstWhere(
      (t) => t.id == savedId,
      orElse: () => FinSightTheme.softGreen,
    );
    AppColors.setTheme(theme);
    state = theme;
  }

  Future<void> changeTheme(FinSightTheme newTheme) async {
    AppColors.setTheme(newTheme);
    state = newTheme;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_themeKey, newTheme.id);
  }
}

final themeProvider = NotifierProvider<ThemeNotifier, FinSightTheme>(() {
  return ThemeNotifier();
});
