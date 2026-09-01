import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants/app_constants.dart';

// ── Token refresh state ───────────────────────────────────────────────────────
// Prevents multiple simultaneous refresh requests when several calls 401 at once.
bool _isRefreshing = false;
final List<RequestOptions> _pendingRequests = [];

/// Singleton Dio HTTP client for all remote API calls in FinSight.
///
/// Features:
///   • Base URL and timeouts from [AppConstants]
///   • Auto-attaches Bearer token from SharedPreferences on every request
///   • Debug-mode request + response logging (stripped from release builds)
///   • 401 interceptor: attempts token refresh once, retries original request,
///     redirects to /login on refresh failure
///
/// Usage:
///   final response = await ApiClient.instance.dio.get('/funds');
class ApiClient {
  ApiClient._() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.apiPrefix,
        connectTimeout: AppConstants.connectTimeout,
        receiveTimeout: AppConstants.receiveTimeout,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    _dio.interceptors.addAll([
      _AuthInterceptor(),
      if (kDebugMode) _LoggingInterceptor(),
    ]);
  }

  static final ApiClient instance = ApiClient._();

  late final Dio _dio;

  /// The configured Dio instance. Use this to make all HTTP requests.
  Dio get dio => _dio;
}

// ══════════════════════════════════════════════════════════════════════════════
// AUTH INTERCEPTOR
// Attaches Bearer token + handles 401 refresh → retry → logout flow.
// ══════════════════════════════════════════════════════════════════════════════

class _AuthInterceptor extends Interceptor {
  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(AppConstants.prefAccessToken) ?? '';

    if (token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode != 401) {
      return handler.next(err);
    }

    // ── 401: attempt token refresh ──────────────────────────────────────────
    if (_isRefreshing) {
      // Queue this request; it will be retried once refresh succeeds.
      _pendingRequests.add(err.requestOptions);
      return;
    }

    _isRefreshing = true;

    try {
      final prefs = await SharedPreferences.getInstance();
      final refreshToken = prefs.getString(AppConstants.prefRefreshToken) ?? '';

      if (refreshToken.isEmpty) {
        _handleLogout(prefs);
        return handler.next(err);
      }

      // Attempt refresh using a clean Dio instance (no interceptors = no loop).
      final refreshDio = Dio(BaseOptions(baseUrl: AppConstants.apiPrefix));
      final refreshResponse = await refreshDio.post(
        AppConstants.endpointRefresh,
        data: {'refresh_token': refreshToken},
      );

      final newAccessToken =
          refreshResponse.data['access_token'] as String? ?? '';
      final newRefreshToken =
          refreshResponse.data['refresh_token'] as String? ?? refreshToken;

      // Persist new tokens.
      await prefs.setString(AppConstants.prefAccessToken, newAccessToken);
      await prefs.setString(AppConstants.prefRefreshToken, newRefreshToken);

      // Retry the original failed request with the new token.
      final retryOptions = err.requestOptions;
      retryOptions.headers['Authorization'] = 'Bearer $newAccessToken';

      final retryResponse = await ApiClient.instance.dio.fetch(retryOptions);

      // Also retry any requests that queued while we were refreshing.
      for (final pending in _pendingRequests) {
        pending.headers['Authorization'] = 'Bearer $newAccessToken';
        ApiClient.instance.dio.fetch(pending);
      }
      _pendingRequests.clear();

      handler.resolve(retryResponse);
    } on DioException {
      // Refresh itself failed — clear auth and send user to login.
      final prefs = await SharedPreferences.getInstance();
      _handleLogout(prefs);
      handler.next(err);
    } finally {
      _isRefreshing = false;
    }
  }

  void _handleLogout(SharedPreferences prefs) {
    prefs.remove(AppConstants.prefAccessToken);
    prefs.remove(AppConstants.prefRefreshToken);
    prefs.remove(AppConstants.prefUserId);
    prefs.remove(AppConstants.prefUserName);
    // Navigation to /login is handled by GoRouter's redirect guard,
    // which re-evaluates on the next navigation event or app resume.
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// LOGGING INTERCEPTOR  (debug builds only — tree-shaken in release)
// ══════════════════════════════════════════════════════════════════════════════

class _LoggingInterceptor extends Interceptor {
  static const _tag = '[ApiClient]';

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    debugPrint(
      '$_tag → ${options.method} ${options.uri}\n'
      '  Headers: ${options.headers}\n'
      '  Body: ${options.data}',
    );
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    debugPrint(
      '$_tag ← ${response.statusCode} ${response.requestOptions.uri}\n'
      '  Data: ${response.data}',
    );
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    debugPrint(
      '$_tag ✗ ${err.response?.statusCode} '
      '${err.requestOptions.uri}: ${err.message}',
    );
    handler.next(err);
  }
}
