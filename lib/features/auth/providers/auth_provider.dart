import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../data/remote/auth_service.dart';

// ══════════════════════════════════════════════════════════════════════════════
// AUTH STATE
// ══════════════════════════════════════════════════════════════════════════════

enum AuthStatus {
  /// App has just launched — session check in progress.
  initialising,

  /// Session restored or login successful.
  authenticated,

  /// No stored session / logged out / token refresh failed.
  unauthenticated,

  /// A login / register / logout operation is in flight.
  loading,

  /// The last operation failed. [AuthState.errorMessage] is non-null.
  error,
}

class AuthState {
  const AuthState({
    this.status = AuthStatus.initialising,
    this.user,
    this.accessToken,
    this.errorMessage,
  });

  final AuthStatus status;
  final AuthUser? user;
  final String? accessToken;
  final String? errorMessage;

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isLoading       => status == AuthStatus.loading;

  AuthState copyWith({
    AuthStatus? status,
    AuthUser? user,
    String? accessToken,
    String? errorMessage,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      accessToken: accessToken ?? this.accessToken,
      // Explicitly pass null to clear the error message.
      errorMessage: errorMessage,
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// AUTH NOTIFIER
// ══════════════════════════════════════════════════════════════════════════════

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState()) {
    _restoreSession();
  }

  final AuthService _service = AuthService.instance;

  // ── Session restore on app start ──────────────────────────────────────────

  /// Reads SharedPreferences and restores the user session.
  /// Called automatically in the constructor — do NOT call manually.
  Future<void> _restoreSession() async {
    try {
      final user = await _service.restoreSession();
      if (user != null) {
        state = AuthState(
          status: AuthStatus.authenticated,
          user: user,
          accessToken: 'mock_token_12345', // replaced by real token in Phase 2
        );
      } else {
        state = const AuthState(status: AuthStatus.unauthenticated);
      }
    } catch (_) {
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  // ── Login ─────────────────────────────────────────────────────────────────

  /// Attempts to log in with [email] and [password].
  ///
  /// Sets status to [AuthStatus.loading] during the call.
  /// On success: [AuthStatus.authenticated].
  /// On failure: [AuthStatus.error] with [AuthState.errorMessage] populated.
  Future<void> login({
    required String email,
    required String password,
  }) async {
    state = const AuthState(status: AuthStatus.loading);
    try {
      final result = await _service.login(email: email, password: password);
      state = AuthState(
        status: AuthStatus.authenticated,
        user: result.user,
        accessToken: result.accessToken,
      );
    } on AuthException catch (e) {
      state = AuthState(
        status: AuthStatus.error,
        errorMessage: e.message,
      );
    } catch (_) {
      state = const AuthState(
        status: AuthStatus.error,
        errorMessage: 'Network error. Please check your connection.',
      );
    }
  }

  // ── Register ──────────────────────────────────────────────────────────────

  /// Registers a new account and auto-logs in on success.
  Future<void> register({
    required String name,
    required String email,
    required String password,
  }) async {
    state = const AuthState(status: AuthStatus.loading);
    try {
      final result = await _service.register(
        name: name,
        email: email,
        password: password,
      );
      state = AuthState(
        status: AuthStatus.authenticated,
        user: result.user,
        accessToken: result.accessToken,
      );
    } on AuthException catch (e) {
      state = AuthState(
        status: AuthStatus.error,
        errorMessage: e.message,
      );
    } catch (_) {
      state = const AuthState(
        status: AuthStatus.error,
        errorMessage: 'Registration failed. Please try again.',
      );
    }
  }

  // ── Refresh token ─────────────────────────────────────────────────────────

  /// Attempts to silently refresh the access token using the stored
  /// refresh token. Transitions to [AuthStatus.unauthenticated] on failure.
  Future<void> refreshToken() async {
    try {
      final result = await _service.refreshToken();
      state = AuthState(
        status: AuthStatus.authenticated,
        user: result.user,
        accessToken: result.accessToken,
      );
    } on AuthException {
      // Refresh failed — send user to login.
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  // ── Logout ────────────────────────────────────────────────────────────────

  /// Clears the session and transitions to [AuthStatus.unauthenticated].
  /// GoRouter's redirect guard will pick this up on the next navigation.
  Future<void> logout() async {
    state = const AuthState(status: AuthStatus.loading);
    await _service.logout();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }

  // ── Error clear ───────────────────────────────────────────────────────────

  /// Clears any displayed error — call when the user dismisses an error
  /// snackbar or edits a form field after a failed attempt.
  void clearError() {
    if (state.status == AuthStatus.error) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        errorMessage: null,
      );
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// PROVIDERS
// ══════════════════════════════════════════════════════════════════════════════

/// Root auth provider. Use this to read [AuthState] or call auth methods.
///
///   // Read state
///   final auth = ref.watch(authProvider);
///   if (auth.isAuthenticated) { … }
///
///   // Trigger login
///   await ref.read(authProvider.notifier).login(email: e, password: p);
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(),
);

/// Convenience provider — resolves to the current [AuthUser] or null.
/// Useful in widgets that only need the user object.
final currentUserProvider = Provider<AuthUser?>(
  (ref) => ref.watch(authProvider).user,
);

/// Convenience provider — true if the user is fully authenticated.
final isAuthenticatedProvider = Provider<bool>(
  (ref) => ref.watch(authProvider).isAuthenticated,
);
