/// Global constants for the FinSight app.
///
/// All API endpoints, Hive box names, and route paths are defined here.
/// Import this file wherever you need any of these values — never
/// hardcode strings directly in widgets or providers.
library;

class AppConstants {
  const AppConstants._();

  // ══════════════════════════════════════════════════════════════════════════════
  // API
  // ══════════════════════════════════════════════════════════════════════════════

  /// Base URL for the FinSight FastAPI backend.
  /// Replace with your deployed server URL before release.
  /// For local development: 'http://10.0.2.2:8000' (Android emulator)
  ///                        'http://localhost:8000' (Desktop/iOS simulator)
  static const String apiBaseUrl = 'http://10.0.2.2:8000';

  /// API version prefix appended to every endpoint path.
  static const String apiVersion = '/api/v1';

  /// Full-formed API prefix used in Dio baseUrl.
  static const String apiPrefix = '$apiBaseUrl$apiVersion';

  // ── Auth endpoints ───────────────────────────────────────────────────────────
  static const String endpointLogin    = '/auth/login';
  static const String endpointRegister = '/auth/register';
  static const String endpointRefresh  = '/auth/refresh';
  static const String endpointLogout   = '/auth/logout';

  // ── Mutual fund endpoints ────────────────────────────────────────────────────
  static const String endpointFunds    = '/funds';
  static const String endpointSimulate = '/funds/simulate';

  // ── Stock endpoints ──────────────────────────────────────────────────────────
  static const String endpointStockPredict = '/stocks/predict';

  // ── Timeout durations ────────────────────────────────────────────────────────
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 60); // ML inference

  // ══════════════════════════════════════════════════════════════════════════════
  // SHARED PREFERENCES KEYS
  // ══════════════════════════════════════════════════════════════════════════════

  static const String prefAccessToken  = 'access_token';
  static const String prefRefreshToken = 'refresh_token';
  static const String prefUserId       = 'user_id';
  static const String prefUserName     = 'user_name';
  static const String prefUserEmail    = 'user_email';

  // ══════════════════════════════════════════════════════════════════════════════
  // HIVE BOX NAMES
  // ══════════════════════════════════════════════════════════════════════════════

  /// Box storing [ExpenseEntry] HiveObjects for the Expense Tracker module.
  static const String hiveBoxExpenses = 'expenses';

  /// Box storing the user's profile and preferences.
  static const String hiveBoxUser = 'user_profile';

  /// Box storing cached simulation results (SIP / Lumpsum / Hybrid).
  static const String hiveBoxSimulations = 'simulation_results';

  /// Box storing the last computed CIBIL score inputs + result.
  static const String hiveBoxCibil = 'cibil_results';

  /// Box storing friend debt entries for the Debt Tracker module.
  static const String hiveBoxDebts = 'debts';

  // ══════════════════════════════════════════════════════════════════════════════
  // HIVE TYPE IDs
  // Unique integer IDs required by Hive's code generator.
  // Never reuse or change these once data has been persisted.
  // ══════════════════════════════════════════════════════════════════════════════

  static const int hiveTypeExpenseEntry    = 0;
  static const int hiveTypeUserProfile     = 1;
  static const int hiveTypeSimulationResult = 2;
  static const int hiveTypeCibilResult     = 3;

  // ══════════════════════════════════════════════════════════════════════════════
  // GOROUTER ROUTE NAMES
  // Match exactly with GoRouter named routes in core/router/app_router.dart.
  // Use these constants with context.goNamed() — never raw path strings.
  // ══════════════════════════════════════════════════════════════════════════════

  // ── Auth shell ───────────────────────────────────────────────────────────────
  static const String routeSplash   = 'splash';
  static const String routeLogin    = 'login';
  static const String routeRegister = 'register';

  // ── Bottom nav tabs (Section 10) ─────────────────────────────────────────────
  static const String routeHome      = 'home';
  static const String routeFunds     = 'funds';
  static const String routeSimulator = 'simulator';
  static const String routeCibil     = 'cibil';
  static const String routeExpenses  = 'expenses';

  // ── Routes outside bottom nav (push on top) ──────────────────────────────────
  static const String routeFundDetail   = 'fund-detail';   // /funds/:fundId
  static const String routeCibilResult  = 'cibil-result';  // /cibil/result
  static const String routeExpenseAdd   = 'expense-add';   // /expenses/add
  static const String routeExpenseDetail = 'expense-detail'; // /expenses/:id
  static const String routePendingReview = 'pending-review'; // /expenses/pending-review
  static const String routeSmsSettings   = 'sms-settings';   // /expenses/sms-settings
  static const String routeSimulatorResult = 'simulator-result'; // /simulator/result
  static const String routeStocks = 'stocks'; // /stocks

  // ══════════════════════════════════════════════════════════════════════════════
  // GOROUTER ROUTE PATHS
  // Canonical path strings used when registering GoRoute(path: ...).
  // ══════════════════════════════════════════════════════════════════════════════

  static const String pathSplash         = '/';
  static const String pathLogin          = '/login';
  static const String pathRegister       = '/register';
  static const String pathHome           = '/home';
  static const String pathFunds          = '/funds';
  static const String pathFundDetail     = '/funds/:fundId';
  static const String pathSimulator      = '/simulator';
  static const String pathCibil          = '/cibil';
  static const String pathCibilResult    = '/cibil/result';
  static const String pathSimulatorResult = '/simulator/result';
  static const String pathExpenses       = '/expenses';
  static const String pathExpenseAdd     = '/expenses/add';
  static const String pathExpenseDetail  = '/expenses/:id';
  static const String pathPendingReview  = '/expenses/pending-review';
  static const String pathSmsSettings    = '/expenses/sms-settings';
  static const String pathStocks         = '/stocks';

  // ══════════════════════════════════════════════════════════════════════════════
  // QUERY PARAMETER KEYS
  // Used for deep-link pre-filling (e.g. /simulator?mode=SIP&monthly=400)
  // ══════════════════════════════════════════════════════════════════════════════

  static const String queryMode    = 'mode';
  static const String queryMonthly = 'monthly';
  static const String queryLumpsum = 'lumpsum';
  static const String queryYears   = 'years';
  static const String queryCagr    = 'cagr';

  // ══════════════════════════════════════════════════════════════════════════════
  // ASSET PATHS
  // ══════════════════════════════════════════════════════════════════════════════

  /// Bundled mutual fund JSON snapshot — loaded by the Funds module.
  static const String assetFundsSnapshot = 'assets/data/funds_snapshot.json';

  /// Lottie animation shown on the Splash screen.
  static const String assetLottieSplash  = 'assets/lottie/splash.json';

  /// Lottie animation shown during long API computations.
  static const String assetLottieLoading = 'assets/lottie/loading.json';

  // ══════════════════════════════════════════════════════════════════════════════
  // BUSINESS CONSTANTS
  // ══════════════════════════════════════════════════════════════════════════════

  /// Default risk-free rate used in Sharpe/Sortino calculations (RBI Repo).
  static const double riskFreeRate = 0.065;

  /// Mock JWT token stored during offline/Phase 1 testing.
  static const String mockAccessToken  = 'mock_access_token_finsight_dev';
  static const String mockRefreshToken = 'mock_refresh_token_finsight_dev';
  static const String mockUserName     = 'Demo User';
  static const String mockUserEmail    = 'demo@finsight.app';
}
