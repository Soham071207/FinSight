import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants/app_constants.dart';

// ── User model ────────────────────────────────────────────────────────────────

/// Lightweight user model returned by auth operations.
/// Not persisted to Hive — reconstructed from SharedPreferences on app start.
class AuthUser {
  const AuthUser({
    required this.id,
    required this.name,
    required this.email,
  });

  final String id;
  final String name;
  final String email;

  /// Initials for the avatar circle (up to 2 characters).
  String get initials {
    final parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
    }
    return name.isNotEmpty ? name[0].toUpperCase() : '?';
  }
}

// ── Auth result ───────────────────────────────────────────────────────────────

class AuthResult {
  const AuthResult({required this.user, required this.accessToken});
  final AuthUser user;
  final String accessToken;
}

// ── Auth service ──────────────────────────────────────────────────────────────

/// Handles all authentication operations for the FinSight app.
///
/// Phase 1 — Mock mode:
///   All methods are local-only. login() accepts any valid email +
///   password (no real check), stores [AppConstants.mockAccessToken]
///   in SharedPreferences, and returns a fake [AuthUser].
///
/// Phase 2 — Real API (ready to activate):
///   Un-comment the Dio calls and remove the mock blocks. The
///   SharedPreferences storage logic is identical for both modes.
class AuthService {
  AuthService._();
  static final AuthService instance = AuthService._();

  // ── Login ─────────────────────────────────────────────────────────────────

  /// Authenticates a user with [email] and [password].
  ///
  /// MOCK: accepts any non-empty combination, returns fake tokens.
  /// Throws [AuthException] on failure.
  Future<AuthResult> login({
    required String email,
    required String password,
  }) async {
    // ── MOCK IMPLEMENTATION ────────────────────────────────────────────────
    // Simulate network latency so loading states are visible in the UI.
    await Future.delayed(const Duration(milliseconds: 800));

    // Basic gate: reject empty credentials even in mock mode.
    if (email.trim().isEmpty || password.isEmpty) {
      throw const AuthException('Email and password are required.');
    }

    final user = AuthUser(
      id: 'mock_user_001',
      name: _nameFromEmail(email),
      email: email.trim().toLowerCase(),
    );

    await _persistSession(
      accessToken: AppConstants.mockAccessToken,
      refreshToken: AppConstants.mockRefreshToken,
      userId: user.id,
      userName: user.name,
      userEmail: user.email,
    );

    return AuthResult(user: user, accessToken: AppConstants.mockAccessToken);

    // ── REAL API (activate in Phase 2) ────────────────────────────────────
    // try {
    //   final response = await ApiClient.instance.dio.post(
    //     AppConstants.endpointLogin,
    //     data: {'email': email.trim(), 'password': password},
    //   );
    //   final data = response.data as Map<String, dynamic>;
    //   final user = AuthUser(
    //     id: data['user_id'] as String,
    //     name: data['name'] as String,
    //     email: data['email'] as String,
    //   );
    //   await _persistSession(
    //     accessToken: data['access_token'] as String,
    //     refreshToken: data['refresh_token'] as String,
    //     userId: user.id,
    //     userName: user.name,
    //     userEmail: user.email,
    //   );
    //   return AuthResult(user: user, accessToken: data['access_token'] as String);
    // } on DioException catch (e) {
    //   throw AuthException(_mapDioError(e));
    // }
  }

  // ── Register ──────────────────────────────────────────────────────────────

  /// Registers a new account and immediately logs the user in.
  ///
  /// MOCK: stores fake tokens without any real API call.
  /// Throws [AuthException] on failure.
  Future<AuthResult> register({
    required String name,
    required String email,
    required String password,
  }) async {
    // ── MOCK IMPLEMENTATION ────────────────────────────────────────────────
    await Future.delayed(const Duration(milliseconds: 1000));

    if (name.trim().isEmpty || email.trim().isEmpty || password.isEmpty) {
      throw const AuthException('All fields are required.');
    }

    final user = AuthUser(
      id: 'mock_user_${DateTime.now().millisecondsSinceEpoch}',
      name: name.trim(),
      email: email.trim().toLowerCase(),
    );

    await _persistSession(
      accessToken: AppConstants.mockAccessToken,
      refreshToken: AppConstants.mockRefreshToken,
      userId: user.id,
      userName: user.name,
      userEmail: user.email,
    );

    return AuthResult(user: user, accessToken: AppConstants.mockAccessToken);

    // ── REAL API (activate in Phase 2) ────────────────────────────────────
    // try {
    //   final response = await ApiClient.instance.dio.post(
    //     AppConstants.endpointRegister,
    //     data: {'name': name.trim(), 'email': email.trim(), 'password': password},
    //   );
    //   final data = response.data as Map<String, dynamic>;
    //   // Register returns tokens directly → auto-login on success.
    //   return login(email: email, password: password);
    // } on DioException catch (e) {
    //   throw AuthException(_mapDioError(e));
    // }
  }

  // ── Refresh token ─────────────────────────────────────────────────────────

  /// Attempts to exchange the stored refresh token for new access + refresh tokens.
  ///
  /// Returns the new [AuthUser] and token on success, or throws [AuthException].
  Future<AuthResult> refreshToken() async {
    // ── MOCK IMPLEMENTATION ────────────────────────────────────────────────
    final prefs = await SharedPreferences.getInstance();
    final refreshTok = prefs.getString(AppConstants.prefRefreshToken) ?? '';

    if (refreshTok.isEmpty) {
      throw const AuthException('No refresh token available.');
    }

    // In mock mode the refresh token is always valid — just return
    // the persisted session as-is.
    final user = await restoreSession();
    if (user == null) throw const AuthException('Session could not be restored.');

    return AuthResult(user: user, accessToken: AppConstants.mockAccessToken);

    // ── REAL API (activate in Phase 2) ────────────────────────────────────
    // try {
    //   final prefs = await SharedPreferences.getInstance();
    //   final rt = prefs.getString(AppConstants.prefRefreshToken) ?? '';
    //   final response = await ApiClient.instance.dio.post(
    //     AppConstants.endpointRefresh,
    //     data: {'refresh_token': rt},
    //   );
    //   final data = response.data as Map<String, dynamic>;
    //   await prefs.setString(AppConstants.prefAccessToken, data['access_token']);
    //   await prefs.setString(AppConstants.prefRefreshToken, data['refresh_token']);
    //   final user = await restoreSession();
    //   return AuthResult(user: user!, accessToken: data['access_token'] as String);
    // } on DioException catch (e) {
    //   throw AuthException(_mapDioError(e));
    // }
  }

  // ── Logout ────────────────────────────────────────────────────────────────

  /// Clears all authentication tokens and user data from SharedPreferences.
  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConstants.prefAccessToken);
    await prefs.remove(AppConstants.prefRefreshToken);
    await prefs.remove(AppConstants.prefUserId);
    await prefs.remove(AppConstants.prefUserName);
    await prefs.remove(AppConstants.prefUserEmail);
  }

  // ── Restore session ───────────────────────────────────────────────────────

  /// Reads SharedPreferences and reconstructs the [AuthUser] if a valid
  /// session exists. Returns null if no session is stored.
  ///
  /// Called by [auth_provider.dart] on app start.
  Future<AuthUser?> restoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(AppConstants.prefAccessToken) ?? '';
    if (token.isEmpty) return null;

    final id    = prefs.getString(AppConstants.prefUserId) ?? '';
    final name  = prefs.getString(AppConstants.prefUserName) ?? '';
    final email = prefs.getString(AppConstants.prefUserEmail) ?? '';

    if (id.isEmpty) return null;
    return AuthUser(id: id, name: name, email: email);
  }

  // ── Private helpers ───────────────────────────────────────────────────────

  Future<void> _persistSession({
    required String accessToken,
    required String refreshToken,
    required String userId,
    required String userName,
    required String userEmail,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.prefAccessToken, accessToken);
    await prefs.setString(AppConstants.prefRefreshToken, refreshToken);
    await prefs.setString(AppConstants.prefUserId, userId);
    await prefs.setString(AppConstants.prefUserName, userName);
    await prefs.setString(AppConstants.prefUserEmail, userEmail);
  }

  /// Derives a display name from an email address when no name is provided
  /// (mock mode). e.g. "john.doe@gmail.com" → "John Doe"
  String _nameFromEmail(String email) {
    final local = email.split('@').first;
    return local
        .split(RegExp(r'[._]'))
        .map((p) => p.isNotEmpty
            ? '${p[0].toUpperCase()}${p.substring(1)}'
            : '')
        .join(' ')
        .trim();
  }

  // ── Dio error mapper (Phase 2) ────────────────────────────────────────────
  // String _mapDioError(DioException e) {
  //   switch (e.response?.statusCode) {
  //     case 401: return 'Incorrect email or password.';
  //     case 409: return 'An account with this email already exists.';
  //     case 422: return 'Invalid input. Please check your details.';
  //     default:  return 'Network error. Please try again.';
  //   }
  // }
}

// ── Auth exception ────────────────────────────────────────────────────────────

class AuthException implements Exception {
  const AuthException(this.message);
  final String message;

  @override
  String toString() => message;
}
