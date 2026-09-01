import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../theme/app_colors.dart';
import '../constants/app_constants.dart';
import '../../shared/widgets/bottom_nav.dart';
import '../../features/expenses/screens/pending_review_screen.dart';
import '../../features/expenses/screens/sms_import_settings_screen.dart';
import '../../features/home/screens/home_screen.dart';
import '../../features/funds/screens/fund_hub_screen.dart';
import '../../features/funds/screens/pro_analysis_screen.dart';
import '../../features/funds/screens/fund_detail_screen.dart';
import '../../features/funds/models/fund_model.dart';
import '../../features/simulator/screens/simulator_form_screen.dart';
import '../../features/simulator/screens/simulator_result_screen.dart';
import '../../features/simulator/logic/sip_calculator.dart';
import '../../features/cibil/screens/cibil_form_screen.dart';
import '../../features/cibil/screens/cibil_result_screen.dart';
import '../../features/cibil/logic/cibil_calculator.dart';
import '../../features/expenses/screens/expense_home_screen.dart';
import '../../features/expenses/screens/add_expense_sheet.dart';
import '../../features/stocks/screens/stock_screen.dart';
import '../../features/auth/screens/splash_screen.dart';
import '../../features/auth/screens/login_screen.dart';
import '../../features/auth/screens/register_screen.dart';

// ── Auth guard helper ─────────────────────────────────────────────────────────

/// Returns true if a valid (non-empty) access token exists in SharedPreferences.
/// Called synchronously by the GoRouter redirect; uses a cached future so it
/// doesn't re-read prefs on every navigation event.
Future<bool> _isLoggedIn() async {
  final prefs = await SharedPreferences.getInstance();
  final token = prefs.getString(AppConstants.prefAccessToken) ?? '';
  return token.isNotEmpty;
}

// ── Router provider ───────────────────────────────────────────────────────────

/// Global GoRouter instance.
///
/// Expose this as a [Provider] so [app.dart] can consume it via Riverpod
/// and individual tests can override it cleanly.
final appRouterProvider = Provider<GoRouter>((ref) => _buildRouter());

GoRouter _buildRouter() {
  return GoRouter(
    initialLocation: AppConstants.pathSplash,
    debugLogDiagnostics: true,

    // ── Global redirect ─────────────────────────────────────────────────────
    redirect: (BuildContext context, GoRouterState state) async {
      final String location = state.uri.toString();

      // Always allow auth screens through — avoid redirect loops.
      final bool isAuthRoute = location == AppConstants.pathSplash ||
          location == AppConstants.pathLogin ||
          location == AppConstants.pathRegister;

      if (isAuthRoute) return null;

      final bool loggedIn = await _isLoggedIn();
      if (!loggedIn) return AppConstants.pathLogin;

      return null; // allow navigation
    },

    routes: [
      // ════════════════════════════════════════════════════════════════════
      // AUTH ROUTES  (outside shell — no bottom nav)
      // ════════════════════════════════════════════════════════════════════

      GoRoute(
        path: AppConstants.pathSplash,
        name: AppConstants.routeSplash,
        pageBuilder: (context, state) => _fadePage(
          state,
          const SplashScreen(),
        ),
      ),

      GoRoute(
        path: AppConstants.pathLogin,
        name: AppConstants.routeLogin,
        pageBuilder: (context, state) => _fadePage(
          state,
          const LoginScreen(),
        ),
      ),

      GoRoute(
        path: AppConstants.pathRegister,
        name: AppConstants.routeRegister,
        pageBuilder: (context, state) => _fadePage(
          state,
          const RegisterScreen(),
        ),
      ),

      // ════════════════════════════════════════════════════════════════════
      // SHELL ROUTE — 5 bottom-nav tabs share one persistent BottomNav
      // ════════════════════════════════════════════════════════════════════

      ShellRoute(
        builder: (context, state, child) => BottomNav(child: child),
        routes: [
          // ── Tab 1: Home ─────────────────────────────────────────────────
          GoRoute(
            path: AppConstants.pathHome,
            name: AppConstants.routeHome,
            pageBuilder: (context, state) => _fadePage(
              state,
              const HomeScreen(),
            ),
          ),

          // ── Tab 2: Funds ────────────────────────────────────────────────
          GoRoute(
            path: AppConstants.pathFunds,
            name: AppConstants.routeFunds,
            pageBuilder: (context, state) => _fadePage(
              state,
              const FundHubScreen(),
            ),
            routes: [
              // /funds/:fundId — pushed on top, NOT inside shell
              GoRoute(
                path: ':fundId',
                name: AppConstants.routeFundDetail,
                pageBuilder: (context, state) {
                  final fundId = state.pathParameters['fundId'] ?? '';
                  // Use dummy fund model since real ones require provider fetch by ID,
                  // ideally this would pass the actual fund or fetch it, but 
                  // using the existing navigation setup for now.
                  // Wait, actually, the user requested to pass Fund object via GoRouter extra!
                  final fund = state.extra as FundModel?;
                  if (fund == null) {
                     return _fadePage(state, const _ErrorPage(error: null));
                  }
                  return _fadePage(
                    state,
                    FundDetailScreen(fund: fund),
                  );
                },
              ),
            ],
          ),

          // ── Tab 3: Simulator ────────────────────────────────────────────
          GoRoute(
            path: AppConstants.pathSimulator,
            name: AppConstants.routeSimulator,
            // Supports deep-link query params: ?mode=SIP&monthly=400&years=5
            pageBuilder: (context, state) {
              final mode    = state.uri.queryParameters[AppConstants.queryMode];
              final monthly = state.uri.queryParameters[AppConstants.queryMonthly];
              final years   = state.uri.queryParameters[AppConstants.queryYears];
              final cagr    = state.uri.queryParameters[AppConstants.queryCagr];
              
              return _fadePage(
                state,
                SimulatorFormScreen(
                  initMode: mode,
                  initMonthly: monthly,
                  initYears: years,
                ),
              );
            },
            routes: [
              GoRoute(
                path: 'result',
                name: AppConstants.routeSimulatorResult,
                pageBuilder: (context, state) {
                  final result = state.extra as SimulatorResult?;
                  return _fadePage(
                    state,
                    SimulatorResultScreen(result: result),
                  );
                },
              ),
            ],
          ),

          // ── Tab 4: CIBIL ────────────────────────────────────────────────
          GoRoute(
            path: AppConstants.pathCibil,
            name: AppConstants.routeCibil,
            pageBuilder: (context, state) => _fadePage(
              state,
              const CibilFormScreen(),
            ),
            routes: [
              GoRoute(
                path: 'result',
                name: AppConstants.routeCibilResult,
                pageBuilder: (context, state) {
                  final result = state.extra as CibilResult?;
                  return _fadePage(
                    state,
                    CibilResultScreen(result: result),
                  );
                },
              ),
            ],
          ),

          // ── Tab 5: Expenses ─────────────────────────────────────────────
          GoRoute(
            path: AppConstants.pathExpenses,
            name: AppConstants.routeExpenses,
            pageBuilder: (context, state) => _fadePage(
              state,
              const ExpenseHomeScreen(),
            ),
            routes: [
              GoRoute(
                path: 'add',
                name: AppConstants.routeExpenseAdd,
                pageBuilder: (context, state) => _fadePage(
                  state,
                  const Scaffold(
                    body: SafeArea(child: AddExpenseSheet()),
                  ),
                ),
              ),
              GoRoute(
                path: 'pending-review',
                name: AppConstants.routePendingReview,
                pageBuilder: (context, state) {
                  return _fadePage(
                    state,
                    const PendingReviewScreen(),
                  );
                },
              ),
              GoRoute(
                path: 'sms-settings',
                name: AppConstants.routeSmsSettings,
                pageBuilder: (context, state) {
                  return _fadePage(
                    state,
                    const SmsImportSettingsScreen(),
                  );
                },
              ),
            ],
          ),

          // ── Stocks (push on top, inside shell so nav bar stays) ──────────
          GoRoute(
            path: AppConstants.pathStocks,
            name: AppConstants.routeStocks,
            pageBuilder: (context, state) => _fadePage(
              state,
              const StockScreen(),
            ),
          ),
        ],
      ),
    ],

    // ── Error page ────────────────────────────────────────────────────────
    errorPageBuilder: (context, state) => _fadePage(
      state,
      _ErrorPage(error: state.error),
    ),
  );
}

// ── Fade page transition helper ───────────────────────────────────────────────

/// Wraps any widget in a [CustomTransitionPage] with a 200ms fade,
/// matching the design system's FadeTransition spec.
CustomTransitionPage<void> _fadePage(GoRouterState state, Widget child) {
  return CustomTransitionPage<void>(
    key: state.pageKey,
    child: child,
    transitionDuration: const Duration(milliseconds: 200),
    reverseTransitionDuration: const Duration(milliseconds: 200),
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(opacity: animation, child: child);
    },
  );
}

// ── Placeholder screen ────────────────────────────────────────────────────────
// Remove these once real screens are wired in per-phase.

class _PlaceholderScreen extends StatelessWidget {
  const _PlaceholderScreen({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Text(
          label,
          style: Theme.of(context).textTheme.bodyLarge,
        ),
      ),
    );
  }
}

// ── Error page ────────────────────────────────────────────────────────────────

class _ErrorPage extends StatelessWidget {
  const _ErrorPage({this.error});
  final Exception? error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 48, color: AppColors.danger),
            const SizedBox(height: 16),
            Text(
              'Page not found',
              style: Theme.of(context).textTheme.displaySmall,
            ),
            if (error != null) ...[
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 24),
            FilledButton(
              onPressed: () => context.go(AppConstants.pathHome),
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    );
  }
}
