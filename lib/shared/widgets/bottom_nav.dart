import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_text.dart';
import '../../core/constants/app_constants.dart';

/// Bottom navigation bar shell widget for the FinSight app.
///
/// Renders 5 tabs matching Section 10. Active tab is highlighted in
/// [AppColors.primary]. Navigation is handled entirely by GoRouter —
/// no Navigator.push() calls.
///
/// This widget is used as the [builder] of the GoRouter ShellRoute,
/// receiving [child] (the active tab's page) from the router.
class BottomNav extends StatelessWidget {
  const BottomNav({super.key, required this.child});

  /// The currently active tab's page widget, injected by GoRouter ShellRoute.
  final Widget child;

  // Ordered tab definitions matching Section 10.
  static const List<_TabItem> _tabs = [
    _TabItem(
      label: 'Home',
      icon: Icons.home_outlined,
      activeIcon: Icons.home_rounded,
      route: AppConstants.pathHome,
    ),
    _TabItem(
      label: 'Funds',
      icon: Icons.bar_chart_outlined,
      activeIcon: Icons.bar_chart_rounded,
      route: AppConstants.pathFunds,
    ),
    _TabItem(
      label: 'Stocks',
      icon: Icons.auto_graph_outlined,
      activeIcon: Icons.auto_graph_rounded,
      route: AppConstants.pathStocks,
    ),
    _TabItem(
      label: 'CIBIL',
      icon: Icons.credit_card_outlined,
      activeIcon: Icons.credit_card_rounded,
      route: AppConstants.pathCibil,
    ),
    _TabItem(
      label: 'Expenses',
      icon: Icons.account_balance_wallet_outlined,
      activeIcon: Icons.account_balance_wallet_rounded,
      route: AppConstants.pathExpenses,
    ),
  ];

  /// Resolves the active tab index from the current GoRouter location.
  int _activeIndex(BuildContext context) {
    final String location = GoRouterState.of(context).uri.toString();
    for (int i = 0; i < _tabs.length; i++) {
      if (location.startsWith(_tabs[i].route)) return i;
    }
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final int activeIndex = _activeIndex(context);

    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          border: Border(
            top: BorderSide(color: AppColors.border, width: 1),
          ),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 60,
            child: Row(
              children: List.generate(_tabs.length, (i) {
                final bool active = i == activeIndex;
                final _TabItem tab = _tabs[i];
                return Expanded(
                  child: _NavItem(
                    tab: tab,
                    isActive: active,
                    onTap: () {
                      if (!active) context.go(tab.route);
                    },
                  ),
                );
              }),
            ),
          ),
        ),
      ),
    );
  }
}

// ── Individual tab item ────────────────────────────────────────────────────────

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.tab,
    required this.isActive,
    required this.onTap,
  });

  final _TabItem tab;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Color color = isActive ? AppColors.primary : AppColors.textSecondary;

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeInOut,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Active indicator dot
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: isActive ? 24 : 0,
              height: isActive ? 3 : 0,
              margin: const EdgeInsets.only(bottom: 4),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Icon(
              isActive ? tab.activeIcon : tab.icon,
              size: 22,
              color: color,
            ),
            const SizedBox(height: 3),
            Text(
              tab.label,
              style: AppText.caption.copyWith(
                color: color,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Tab definition model ───────────────────────────────────────────────────────

class _TabItem {
  const _TabItem({
    required this.label,
    required this.icon,
    required this.activeIcon,
    required this.route,
  });

  final String label;
  final IconData icon;
  final IconData activeIcon;
  final String route;
}
