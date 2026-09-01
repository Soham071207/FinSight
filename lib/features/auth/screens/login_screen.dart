import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/validators.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey     = GlobalKey<FormState>();
  final _emailCtrl   = TextEditingController();
  final _passCtrl    = TextEditingController();
  final _emailFocus  = FocusNode();
  final _passFocus   = FocusNode();

  // Tracks whether the user has attempted submit — enables real-time validation.
  bool _submitted = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    _emailFocus.dispose();
    _passFocus.dispose();
    super.dispose();
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  Future<void> _submit() async {
    setState(() => _submitted = true);
    if (!_formKey.currentState!.validate()) return;

    ref.read(authProvider.notifier).clearError();

    await ref.read(authProvider.notifier).login(
          email: _emailCtrl.text.trim(),
          password: _passCtrl.text,
        );

    if (!mounted) return;

    final state = ref.read(authProvider);
    if (state.isAuthenticated) {
      context.go(AppConstants.pathHome);
    } else if (state.status == AuthStatus.error &&
        _isNetworkError(state.errorMessage)) {
      // Network errors → snackbar. Credential errors → inline.
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(state.errorMessage ?? 'Network error.')),
      );
    }
  }

  bool _isNetworkError(String? msg) =>
      msg != null && msg.toLowerCase().contains('network');

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final authState  = ref.watch(authProvider);
    final isLoading  = authState.isLoading;
    final errorMsg   = authState.status == AuthStatus.error &&
            !_isNetworkError(authState.errorMessage)
        ? authState.errorMessage
        : null;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Form(
              key: _formKey,
              autovalidateMode: _submitted
                  ? AutovalidateMode.onUserInteraction
                  : AutovalidateMode.disabled,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 48),

                  // ── Header ───────────────────────────────────────────────
                  _Header(),

                  const SizedBox(height: 40),

                  // ── Email ────────────────────────────────────────────────
                  AppTextField(
                    label: 'Email address',
                    controller: _emailCtrl,
                    focusNode: _emailFocus,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    prefixIcon: Icons.email_outlined,
                    validator: Validators.email,
                    onFieldSubmitted: (_) =>
                        FocusScope.of(context).requestFocus(_passFocus),
                  ),

                  const SizedBox(height: 16),

                  // ── Password ──────────────────────────────────────────────
                  AppTextField.password(
                    label: 'Password',
                    controller: _passCtrl,
                    focusNode: _passFocus,
                    textInputAction: TextInputAction.done,
                    prefixIcon: Icons.lock_outline_rounded,
                    validator: (v) =>
                        (v == null || v.isEmpty) ? 'Password is required.' : null,
                    onFieldSubmitted: (_) => _submit(),
                  ),

                  const SizedBox(height: 12),

                  // ── Inline credential error ───────────────────────────────
                  if (errorMsg != null) _InlineError(message: errorMsg),

                  const SizedBox(height: 28),

                  // ── Sign In button ────────────────────────────────────────
                  AppButton(
                    label: 'Sign In',
                    onPressed: isLoading ? null : _submit,
                    isLoading: isLoading,
                  ),

                  const SizedBox(height: 20),

                  // ── Register link ─────────────────────────────────────────
                  _RegisterLink(),

                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ── Sub-widgets ───────────────────────────────────────────────────────────────

class _Header extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.primaryLight,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.trending_up_rounded,
                color: AppColors.primary,
                size: 22,
              ),
            ),
            const SizedBox(width: 10),
            Text('FinSight',
                style: AppText.heading2.copyWith(color: AppColors.primary)),
          ],
        ),
        const SizedBox(height: 28),
        Text('Welcome back 👋', style: AppText.heading1),
        const SizedBox(height: 6),
        Text('Sign in to continue to your dashboard.',
            style: AppText.bodySecondary),
      ],
    );
  }
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        children: [
          Icon(Icons.error_outline_rounded,
              size: 14, color: AppColors.danger),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              message,
              style: AppText.caption.copyWith(color: AppColors.danger),
            ),
          ),
        ],
      ),
    );
  }
}

class _RegisterLink extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text("Don't have an account? ", style: AppText.bodySecondary),
        GestureDetector(
          onTap: () => context.go(AppConstants.pathRegister),
          child: Text(
            'Register',
            style: AppText.bodyBold.copyWith(color: AppColors.primary),
          ),
        ),
      ],
    );
  }
}
