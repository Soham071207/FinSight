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

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey      = GlobalKey<FormState>();
  final _nameCtrl     = TextEditingController();
  final _emailCtrl    = TextEditingController();
  final _passCtrl     = TextEditingController();
  final _confirmCtrl  = TextEditingController();
  final _nameFocus    = FocusNode();
  final _emailFocus   = FocusNode();
  final _passFocus    = FocusNode();
  final _confirmFocus = FocusNode();

  bool _submitted = false;

  /// Drives the strength bar — recomputed on every password keystroke.
  _PasswordStrength _strength = _PasswordStrength.empty;

  @override
  void initState() {
    super.initState();
    _passCtrl.addListener(_onPasswordChanged);
  }

  void _onPasswordChanged() {
    final s = _evaluateStrength(_passCtrl.text);
    if (s != _strength) setState(() => _strength = s);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _passCtrl.dispose();
    _confirmCtrl.dispose();
    _nameFocus.dispose();
    _emailFocus.dispose();
    _passFocus.dispose();
    _confirmFocus.dispose();
    super.dispose();
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  Future<void> _submit() async {
    setState(() => _submitted = true);
    if (!_formKey.currentState!.validate()) return;

    ref.read(authProvider.notifier).clearError();

    await ref.read(authProvider.notifier).register(
          name: _nameCtrl.text.trim(),
          email: _emailCtrl.text.trim(),
          password: _passCtrl.text,
        );

    if (!mounted) return;

    final state = ref.read(authProvider);
    if (state.isAuthenticated) {
      context.go(AppConstants.pathHome);
    } else if (state.status == AuthStatus.error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(state.errorMessage ?? 'Registration failed.'),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  // ── Password strength ─────────────────────────────────────────────────────

  _PasswordStrength _evaluateStrength(String pass) {
    if (pass.isEmpty) return _PasswordStrength.empty;
    int score = 0;
    if (pass.length >= 8) score++;
    if (pass.length >= 12) score++;
    if (RegExp(r'\d').hasMatch(pass)) score++;
    if (RegExp(r'[A-Z]').hasMatch(pass)) score++;
    if (RegExp(r'[!@#\$%^&*(),.?":{}|<>]').hasMatch(pass)) score++;

    if (score <= 1) return _PasswordStrength.weak;
    if (score <= 3) return _PasswordStrength.medium;
    return _PasswordStrength.strong;
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final authState = ref.watch(authProvider);
    final isLoading = authState.isLoading;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () => context.go(AppConstants.pathLogin),
        ),
      ),
      body: SafeArea(
        top: false,
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
                const SizedBox(height: 8),

                // ── Header ─────────────────────────────────────────────────
                Text('Create account', style: AppText.heading1),
                const SizedBox(height: 6),
                Text('Join FinSight and take control of your finances.',
                    style: AppText.bodySecondary),

                const SizedBox(height: 32),

                // ── Full name ───────────────────────────────────────────────
                AppTextField(
                  label: 'Full name',
                  controller: _nameCtrl,
                  focusNode: _nameFocus,
                  keyboardType: TextInputType.name,
                  textInputAction: TextInputAction.next,
                  prefixIcon: Icons.person_outline_rounded,
                  validator: Validators.fullName,
                  onFieldSubmitted: (_) =>
                      FocusScope.of(context).requestFocus(_emailFocus),
                ),

                const SizedBox(height: 16),

                // ── Email ───────────────────────────────────────────────────
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

                // ── Password ────────────────────────────────────────────────
                AppTextField.password(
                  label: 'Password',
                  controller: _passCtrl,
                  focusNode: _passFocus,
                  textInputAction: TextInputAction.next,
                  validator: Validators.password,
                  onFieldSubmitted: (_) =>
                      FocusScope.of(context).requestFocus(_confirmFocus),
                ),

                const SizedBox(height: 8),

                // ── Strength indicator ──────────────────────────────────────
                _StrengthBar(strength: _strength),

                const SizedBox(height: 16),

                // ── Confirm password ────────────────────────────────────────
                AppTextField.password(
                  label: 'Confirm password',
                  controller: _confirmCtrl,
                  focusNode: _confirmFocus,
                  textInputAction: TextInputAction.done,
                  validator: Validators.confirmPassword(_passCtrl.text),
                  onFieldSubmitted: (_) => _submit(),
                ),

                const SizedBox(height: 32),

                // ── Register button ─────────────────────────────────────────
                AppButton(
                  label: 'Create Account',
                  onPressed: isLoading ? null : _submit,
                  isLoading: isLoading,
                ),

                const SizedBox(height: 20),

                // ── Login link ──────────────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('Already have an account? ', style: AppText.bodySecondary),
                    GestureDetector(
                      onTap: () => context.go(AppConstants.pathLogin),
                      child: Text(
                        'Sign In',
                        style: AppText.bodyBold.copyWith(color: AppColors.primary),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Password strength bar ─────────────────────────────────────────────────────

enum _PasswordStrength { empty, weak, medium, strong }

class _StrengthBar extends StatelessWidget {
  const _StrengthBar({required this.strength});
  final _PasswordStrength strength;

  @override
  Widget build(BuildContext context) {
    if (strength == _PasswordStrength.empty) return const SizedBox.shrink();

    final (filled, color, label) = switch (strength) {
      _PasswordStrength.weak   => (1, AppColors.danger,  'Weak'),
      _PasswordStrength.medium => (2, AppColors.warning, 'Medium'),
      _PasswordStrength.strong => (3, AppColors.accent,  'Strong'),
      _PasswordStrength.empty  => (0, AppColors.border,  ''),
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: List.generate(3, (i) {
            return Expanded(
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                margin: EdgeInsets.only(right: i < 2 ? 4 : 0),
                height: 4,
                decoration: BoxDecoration(
                  color: i < filled ? color : AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            );
          }),
        ),
        const SizedBox(height: 5),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: Align(
            key: ValueKey(label),
            alignment: Alignment.centerLeft,
            child: Text(
              'Password strength: $label',
              style: AppText.caption.copyWith(color: color),
            ),
          ),
        ),
      ],
    );
  }
}
