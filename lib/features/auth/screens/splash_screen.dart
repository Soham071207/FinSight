import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../providers/auth_provider.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fadeController;
  late final Animation<double> _fadeAnim;

  @override
  void initState() {
    super.initState();

    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fadeAnim = CurvedAnimation(parent: _fadeController, curve: Curves.easeIn);
    _fadeController.forward();

    // Wait 1.5s then route based on auth state
    Future.delayed(const Duration(milliseconds: 1500), _checkAuthAndRoute);
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  Future<void> _checkAuthAndRoute() async {
    if (!mounted) return;
    final authState = ref.read(authProvider);

    // While still initialising (race condition on very fast devices), wait
    // a short extra grace period and re-read.
    if (authState.status == AuthStatus.initialising) {
      await Future.delayed(const Duration(milliseconds: 300));
    }

    if (!mounted) return;
    final resolved = ref.read(authProvider);
    if (resolved.isAuthenticated) {
      context.go(AppConstants.pathHome);
    } else {
      context.go(AppConstants.pathLogin);
    }
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    return Scaffold(
      backgroundColor: AppColors.surface,
      body: FadeTransition(
        opacity: _fadeAnim,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // ── Logo mark ──────────────────────────────────────────────
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: AppColors.primaryLight,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Icon(
                  Icons.trending_up_rounded,
                  size: 40,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(height: 20),

              // ── App name ───────────────────────────────────────────────
              Text(
                'FinSight',
                style: AppText.heading1.copyWith(
                  color: AppColors.primary,
                  fontSize: 32,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Your financial clarity partner',
                style: AppText.caption,
              ),

              const SizedBox(height: 48),

              // ── Pulsing dots loader (replaces bare spinner) ────────────
              _PulsingDots(),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Pulsing dots loader ───────────────────────────────────────────────────────

class _PulsingDots extends StatefulWidget {
  @override
  State<_PulsingDots> createState() => _PulsingDotsState();
}

class _PulsingDotsState extends State<_PulsingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final delay = i / 3;
            final t = (_ctrl.value - delay).clamp(0.0, 1.0);
            final opacity = (0.3 + 0.7 * (t < 0.5 ? t * 2 : (1 - t) * 2))
                .clamp(0.3, 1.0);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Opacity(
                opacity: opacity,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
