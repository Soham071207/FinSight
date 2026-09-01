import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../shared/widgets/section_header.dart';
import '../../auth/providers/auth_provider.dart';
import '../../expenses/logic/expense_provider.dart';
import '../../expenses/logic/investment_advisor.dart';
import '../../expenses/widgets/suggestion_card.dart';
import '../../expenses/screens/expense_home_screen.dart';
import '../widgets/summary_card.dart';

// ── Providers ───────────────────────────────────────────────────────────────

final cibilScoreProvider = FutureProvider<int?>((ref) async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getInt('last_cibil_score');
});

// ══════════════════════════════════════════════════════════════════════════════
// HOME SCREEN
// ══════════════════════════════════════════════════════════════════════════════

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: CustomScrollView(
        slivers: [
          // ── SliverAppBar ─────────────────────────────────────────────────
          _GreetingAppBar(
            userName: user?.name ?? 'there',
            initials: user?.initials ?? '?',
          ),

          // ── Body content ─────────────────────────────────────────────────
          SliverPadding(
            padding: const EdgeInsets.only(bottom: 32),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                const SizedBox(height: 8),

                // Summary cards row
                const _SummaryCardsRow(),

                const SizedBox(height: 8),

                // Quick Actions
                const SectionHeader(title: 'Quick Actions'),
                _QuickActionsGrid(),

                // Smart Suggestions
                SectionHeader(
                  title: 'Smart Suggestions',
                  onSeeAll: () => context.go(AppConstants.pathExpenses),
                ),
                const _SmartSuggestionsSection(),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// GREETING APP BAR
// ══════════════════════════════════════════════════════════════════════════════

class _GreetingAppBar extends StatelessWidget {
  const _GreetingAppBar({required this.userName, required this.initials});
  final String userName;
  final String initials;

  String get _greeting {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  @override
  Widget build(BuildContext context) {
    return SliverAppBar(
      pinned: true,
      floating: false,
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      expandedHeight: 96,
      shape: Border(
        bottom: BorderSide(color: AppColors.border, width: 1),
      ),
      flexibleSpace: FlexibleSpaceBar(
        titlePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        title: Row(
          children: [
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$_greeting, ${userName.split(' ').first} 👋',
                    style: AppText.heading2,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    'Here\'s your financial overview',
                    style: AppText.caption,
                  ),
                ],
              ),
            ),

            // Settings
            IconButton(
              icon: Icon(Icons.settings_outlined, color: AppColors.textSecondary),
              onPressed: () => context.pushNamed(AppConstants.routeSmsSettings),
              tooltip: 'Settings',
            ),

            // Avatar
            _Avatar(initials: initials),
          ],
        ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.initials});
  final String initials;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: AppColors.primary,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        initials,
        style: AppText.label.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w700,
          fontSize: 13,
        ),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SUMMARY CARDS ROW
// ══════════════════════════════════════════════════════════════════════════════

class _SummaryCardsRow extends ConsumerWidget {
  const _SummaryCardsRow();

  String _getCibilBandLabel(int score) {
    if (score >= 850) return 'Excellent';
    if (score >= 750) return 'Very Good';
    if (score >= 650) return 'Good';
    if (score >= 550) return 'Fair';
    return 'Poor';
  }

  Color _getCibilBandColor(int score) {
    if (score >= 850) return AppColors.accent;
    if (score >= 750) return AppColors.accent;
    if (score >= 650) return AppColors.primary;
    if (score >= 550) return AppColors.warning;
    return AppColors.danger;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    // Read from providers
    final cibilAsync = ref.watch(cibilScoreProvider);
    final expenseState = ref.watch(expenseProvider);
    final currentMonthSpend = ref.read(expenseProvider.notifier).getMonthlyTotal();
    final budget = ref.watch(budgetProvider); // Live budget from expense_home_screen.dart

    // Evaluate CIBIL logic
    int? cibilScore;
    if (cibilAsync is AsyncData && cibilAsync.value != null) {
      cibilScore = cibilAsync.value;
    }

    return SizedBox(
      height: 190,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          // Card 1 — CIBIL
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: SummaryCard(
              icon: Icons.credit_score_rounded,
              iconColor: cibilScore != null ? _getCibilBandColor(cibilScore) : AppColors.textSecondary,
              label: 'CIBIL Score',
              value: cibilScore?.toString() ?? '---',
              subtitle: cibilScore != null ? _getCibilBandLabel(cibilScore) : 'Not calculated yet',
              subtitleColor: cibilScore != null ? _getCibilBandColor(cibilScore) : AppColors.textSecondary,
              badge: cibilScore != null ? 'View details' : 'Calculate now',
              badgeColor: cibilScore != null ? AppColors.accent : AppColors.primary,
              onTap: () => context.go(AppConstants.pathCibil),
            ).animate().fadeIn(duration: 300.ms).slideX(begin: 0.1),
          ),

          // Card 2 — Monthly Spend
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: SummaryCard(
              icon: Icons.account_balance_wallet_outlined,
              iconColor: AppColors.primary,
              label: 'Monthly Spend',
              value: formatINR(currentMonthSpend),
              subtitle: '${DateTime(DateTime.now().year, DateTime.now().month + 1, 0).day - DateTime.now().day} days left',
              trailing: _SpendProgressBar(spent: currentMonthSpend, budget: budget),
              onTap: () => context.go(AppConstants.pathExpenses),
            ).animate().fadeIn(duration: 300.ms, delay: 60.ms).slideX(begin: 0.1),
          ),

          // Card 3 — Top Fund
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: SummaryCard(
              icon: Icons.bar_chart_rounded,
              iconColor: AppColors.warning,
              label: 'Top Fund',
              value: 'Flexi Cap',
              subtitle: 'Parag Parikh',
              badge: '↑ 18.4%',
              badgeColor: AppColors.accent,
              onTap: () => context.go(AppConstants.pathFunds),
            ).animate().fadeIn(duration: 300.ms, delay: 120.ms).slideX(begin: 0.1),
          ),

          // Card 4 — SIP Projection
          Padding(
            padding: const EdgeInsets.only(right: 0),
            child: SummaryCard(
              icon: Icons.calculate_rounded,
              iconColor: AppColors.danger,
              label: 'SIP Corpus',
              value: formatINRCompact(1400000),
              subtitle: 'in 10 yrs @ 12%',
              badge: 'SIP',
              badgeColor: AppColors.primary,
              onTap: () => context.go(AppConstants.pathSimulator),
            ).animate().fadeIn(duration: 300.ms, delay: 180.ms).slideX(begin: 0.1),
          ),
        ],
      ),
    );
  }
}

class _SpendProgressBar extends StatelessWidget {
  const _SpendProgressBar({required this.spent, required this.budget});
  final double spent;
  final double budget;

  @override
  Widget build(BuildContext context) {
    final ratio = (spent / budget).clamp(0.0, 1.0);
    final color = ratio >= 1.0
        ? AppColors.danger
        : ratio >= 0.8
            ? AppColors.warning
            : AppColors.primary;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: ratio,
            minHeight: 5,
            backgroundColor: AppColors.border,
            color: color,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '${(ratio * 100).toStringAsFixed(0)}% of ${formatINRCompact(budget)}',
          style: AppText.caption.copyWith(fontSize: 10),
        ),
      ],
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// QUICK ACTIONS GRID (2 × 2)
// ══════════════════════════════════════════════════════════════════════════════

class _QuickActionsGrid extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final actions = [
      _QuickAction(
        icon: Icons.add_circle_outline_rounded,
        label: 'Add Expense',
        color: AppColors.primary,
        onTap: () => context.go(AppConstants.pathExpenseAdd),
      ),
      _QuickAction(
        icon: Icons.credit_score_rounded,
        label: 'CIBIL Score',
        color: AppColors.accent,
        onTap: () => context.go(AppConstants.pathCibil),
      ),
      _QuickAction(
        icon: Icons.calculate_rounded,
        label: 'Simulate SIP',
        color: AppColors.warning,
        onTap: () => context.go(AppConstants.pathSimulator),
      ),
      _QuickAction(
        icon: Icons.bar_chart_rounded,
        label: 'Live Funds',
        color: AppColors.danger,
        onTap: () => context.go(AppConstants.pathFunds),
      ),
      _QuickAction(
        icon: Icons.auto_graph_rounded,
        label: 'AI Stocks',
        color: AppColors.textSecondary,
        onTap: () => context.go(AppConstants.pathStocks),
      ),
      _QuickAction(
        icon: Icons.handshake_outlined,
        label: 'Friend Debts',
        color: AppColors.danger,
        onTap: () => context.go(AppConstants.pathExpenses),
      ),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: GridView.count(
        crossAxisCount: 1,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 5.5,
        children: actions
            .asMap()
            .entries
            .map(
              (e) => _QuickActionTile(action: e.value)
                  .animate()
                  .fadeIn(duration: 250.ms, delay: (e.key * 40).ms)
                  .scale(begin: const Offset(0.95, 0.95)),
            )
            .toList(),
      ),
    );
  }
}

class _QuickAction {
  const _QuickAction({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
}

class _QuickActionTile extends StatelessWidget {
  const _QuickActionTile({required this.action});
  final _QuickAction action;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: action.onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: action.color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(action.icon, size: 17, color: action.color),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                action.label,
                style: AppText.label.copyWith(fontWeight: FontWeight.w600),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SMART SUGGESTIONS SECTION
// ══════════════════════════════════════════════════════════════════════════════

class _SmartSuggestionsSection extends ConsumerWidget {
  const _SmartSuggestionsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final expenseState = ref.watch(expenseProvider);
    final suggestions = InvestmentAdvisor.analyze(expenseState.entries).take(2).toList();

    if (suggestions.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: [
              Icon(Icons.lightbulb_outline_rounded, size: 48, color: AppColors.border),
              const SizedBox(height: 12),
              Text('No suggestions yet', style: AppText.bodyBold),
              const SizedBox(height: 4),
              Text(
                'Track your expenses for a few days to unlock personalized investment insights.',
                style: AppText.bodySecondary,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ).animate().fadeIn(duration: 400.ms),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        children: suggestions
            .asMap()
            .entries
            .map((entry) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: SuggestionCard(suggestion: entry.value)
                    .animate()
                    .fadeIn(duration: 300.ms, delay: (entry.key * 80).ms)
                    .slideY(begin: 0.08),
              );
            })
            .toList(),
      ),
    );
  }
}
