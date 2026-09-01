import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../shared/widgets/app_button.dart';
import '../logic/cibil_calculator.dart';
import '../logic/cibil_service.dart';

// ══════════════════════════════════════════════════════════════════════════════
// FORM STATE PROVIDER
// ══════════════════════════════════════════════════════════════════════════════

class CibilFormNotifier extends Notifier<CibilInput> {
  @override
  CibilInput build() {
    // Sensible defaults for the sliders
    return const CibilInput(
      utilizationPct: 30,
      onTimePaymentPct: 100,
      missedPayments: 0,
      hardInquiries: 0,
      creditAgeYears: 5,
      totalActiveAccounts: 2,
      numCreditCards: 1,
      numSecuredLoans: 0,
      numUnsecuredLoans: 1,
      monthsWithEmployer: 24,
      netMonthlyIncome: 50000.0,
    );
  }

  void updateState(CibilInput updated) {
    state = updated;
  }
}

final cibilFormProvider = NotifierProvider<CibilFormNotifier, CibilInput>(
  () => CibilFormNotifier(),
);

// ══════════════════════════════════════════════════════════════════════════════
// SCREEN
// ══════════════════════════════════════════════════════════════════════════════

class CibilFormScreen extends ConsumerStatefulWidget {
  const CibilFormScreen({super.key});

  @override
  ConsumerState<CibilFormScreen> createState() => _CibilFormScreenState();
}

class _CibilFormScreenState extends ConsumerState<CibilFormScreen> {
  int _currentStep = 1;
  bool _isLoading = false;

  void _next() {
    if (_currentStep < 3) setState(() => _currentStep++);
  }

  void _back() {
    if (_currentStep > 1) setState(() => _currentStep--);
  }

  void _calculate() async {
    setState(() => _isLoading = true);
    final input = ref.read(cibilFormProvider);
    
    // Try ML API first
    CibilResult? result = await CibilService.predictCibil(input);
    
    // Fallback to rule-based if offline/failed
    if (result == null) {
      result = CibilCalculator.calculate(input);
    }
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('last_cibil_score', result.totalScore);
    
    if (mounted) {
      setState(() => _isLoading = false);
      context.go(AppConstants.pathCibilResult, extra: result);
    }
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text('Check CIBIL Score', style: AppText.heading2),
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () {
            if (_currentStep > 1) {
              _back();
            } else {
              context.pop();
            }
          },
        ),
      ),
      body: SafeArea(
        child: Stack(
          children: [
            Column(
              children: [
            // ── Step indicator ──────────────────────────────────────────────
            _StepIndicator(currentStep: _currentStep),
            
            // ── Form Body (Animated) ────────────────────────────────────────
            Expanded(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                transitionBuilder: (child, animation) {
                  return FadeTransition(opacity: animation, child: child);
                },
                child: _buildStepContent(_currentStep),
              ),
            ),

            // ── Bottom Navigation Bar ───────────────────────────────────────
            _BottomNavRow(
              step: _currentStep,
              onBack: _back,
              onNext: _next,
              onCalculate: _calculate,
            ),
          ],
        ),
        if (_isLoading)
          Container(
            color: Colors.black.withValues(alpha: 0.3),
            child: const Center(
              child: CircularProgressIndicator(),
            ),
          ),
        ],
      ),
      ),
    );
  }

  Widget _buildStepContent(int step) {
    switch (step) {
      case 1:
        return const _Step1Behavior(key: ValueKey(1));
      case 2:
        return const _Step2Profile(key: ValueKey(2));
      case 3:
        return const _Step3Summary(key: ValueKey(3));
      default:
        return const SizedBox.shrink();
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// STEP 1: CREDIT BEHAVIOUR
// ══════════════════════════════════════════════════════════════════════════════

class _Step1Behavior extends ConsumerWidget {
  const _Step1Behavior({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final input = ref.watch(cibilFormProvider);
    final notifier = ref.read(cibilFormProvider.notifier);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Credit Behaviour', style: AppText.heading1),
          const SizedBox(height: 6),
          Text('Tell us about your payment habits.', style: AppText.bodySecondary),
          const SizedBox(height: 32),

          _SliderField(
            label: 'Credit Utilization (%)',
            infoText: 'Percentage of your available credit limit that you are currently using. Lower is better.',
            value: input.utilizationPct,
            min: 0,
            max: 100,
            divisions: 100,
            valueLabel: '${input.utilizationPct.toInt()}%',
            onChanged: (v) => notifier.updateState(input.copyWith(utilizationPct: v)),
            hint: 'Ideal is under 30%',
          ),
          const SizedBox(height: 24),

          _SliderField(
            label: 'On-time Payments (%)',
            infoText: 'Percentage of payments made on or before the due date.',
            value: input.onTimePaymentPct,
            min: 0,
            max: 100,
            divisions: 100,
            valueLabel: '${input.onTimePaymentPct.toInt()}%',
            onChanged: (v) => notifier.updateState(input.copyWith(onTimePaymentPct: v)),
            hint: 'Ideal is > 95%',
          ),
          const SizedBox(height: 24),

          _SliderField(
            label: 'Missed Payments (Last 12 mo)',
            infoText: 'Number of times you missed a payment deadline in the last year.',
            value: input.missedPayments.toDouble(),
            min: 0,
            max: 12,
            divisions: 12,
            valueLabel: '${input.missedPayments}',
            onChanged: (v) => notifier.updateState(input.copyWith(missedPayments: v.toInt())),
          ),
          const SizedBox(height: 24),

          _SliderField(
            label: 'Hard Inquiries (Last 12 mo)',
            infoText: 'Number of times lenders checked your credit report for new credit applications.',
            value: input.hardInquiries.toDouble(),
            min: 0,
            max: 10,
            divisions: 10,
            valueLabel: '${input.hardInquiries}',
            onChanged: (v) => notifier.updateState(input.copyWith(hardInquiries: v.toInt())),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// STEP 2: CREDIT PROFILE
// ══════════════════════════════════════════════════════════════════════════════

class _Step2Profile extends ConsumerWidget {
  const _Step2Profile({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final input = ref.watch(cibilFormProvider);
    final notifier = ref.read(cibilFormProvider.notifier);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Credit Profile', style: AppText.heading1),
          const SizedBox(height: 6),
          Text('Details about your active accounts.', style: AppText.bodySecondary),
          const SizedBox(height: 32),

          _SliderField(
            label: 'Age of Oldest Account (Years)',
            infoText: 'Age of your oldest active credit account. Longer history improves your score.',
            value: input.creditAgeYears,
            min: 0,
            max: 30,
            divisions: 30,
            valueLabel: '${input.creditAgeYears.toInt()} yrs',
            onChanged: (v) => notifier.updateState(input.copyWith(creditAgeYears: v)),
          ),
          const SizedBox(height: 24),

          _SliderField(
            label: 'Total Active Accounts',
            infoText: 'Total number of credit accounts (cards, loans) currently open.',
            value: input.totalActiveAccounts.toDouble(),
            min: 0,
            max: 20,
            divisions: 20,
            valueLabel: '${input.totalActiveAccounts}',
            onChanged: (v) => notifier.updateState(input.copyWith(totalActiveAccounts: v.toInt())),
          ),
          const SizedBox(height: 24),

          Text('Credit Mix', style: AppText.bodyBold),
          const SizedBox(height: 16),

          _SliderField(
            label: 'Credit Cards',
            infoText: 'Number of active credit cards you hold.',
            value: input.numCreditCards.toDouble(),
            min: 0,
            max: 10,
            divisions: 10,
            valueLabel: '${input.numCreditCards}',
            onChanged: (v) => notifier.updateState(input.copyWith(numCreditCards: v.toInt())),
            compact: true,
          ),
          const SizedBox(height: 16),

          _SliderField(
            label: 'Secured Loans (Home/Auto)',
            infoText: 'Loans backed by an asset like a house or car.',
            value: input.numSecuredLoans.toDouble(),
            min: 0,
            max: 5,
            divisions: 5,
            valueLabel: '${input.numSecuredLoans}',
            onChanged: (v) => notifier.updateState(input.copyWith(numSecuredLoans: v.toInt())),
            compact: true,
          ),
          const SizedBox(height: 16),

          _SliderField(
            label: 'Unsecured Loans (Personal)',
            infoText: 'Loans without collateral, such as personal or education loans.',
            value: input.numUnsecuredLoans.toDouble(),
            min: 0,
            max: 5,
            divisions: 5,
            valueLabel: '${input.numUnsecuredLoans}',
            onChanged: (v) => notifier.updateState(input.copyWith(numUnsecuredLoans: v.toInt())),
            compact: true,
          ),
          const SizedBox(height: 24),

          Text('Employment & Income', style: AppText.bodyBold),
          const SizedBox(height: 16),

          _SliderField(
            label: 'Employment Duration (Months)',
            infoText: 'Number of months with your current employer. Longer duration shows stability.',
            value: input.monthsWithEmployer.toDouble(),
            min: 0,
            max: 360,
            divisions: 360,
            valueLabel: '${input.monthsWithEmployer} mo',
            onChanged: (v) => notifier.updateState(input.copyWith(monthsWithEmployer: v.toInt())),
          ),
          const SizedBox(height: 24),

          _SliderField(
            label: 'Net Monthly Income (₹)',
            infoText: 'Your monthly take-home salary after taxes.',
            value: input.netMonthlyIncome,
            min: 0,
            max: 500000,
            divisions: 100,
            valueLabel: '₹${(input.netMonthlyIncome/1000).toStringAsFixed(0)}k',
            onChanged: (v) => notifier.updateState(input.copyWith(netMonthlyIncome: v)),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// STEP 3: SUMMARY
// ══════════════════════════════════════════════════════════════════════════════

class _Step3Summary extends ConsumerWidget {
  const _Step3Summary({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final input = ref.watch(cibilFormProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Review Inputs', style: AppText.heading1),
          const SizedBox(height: 6),
          Text('Make sure everything looks correct.', style: AppText.bodySecondary),
          const SizedBox(height: 32),

          Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              children: [
                _SummaryRow('Credit Utilization', '${input.utilizationPct.toInt()}%'),
                _SummaryRow('On-time Payments', '${input.onTimePaymentPct.toInt()}%'),
                _SummaryRow('Missed Payments', '${input.missedPayments}'),
                _SummaryRow('Hard Inquiries', '${input.hardInquiries}'),
                Divider(height: 1, color: AppColors.border),
                _SummaryRow('Oldest Account Age', '${input.creditAgeYears.toInt()} years'),
                _SummaryRow('Total Accounts', '${input.totalActiveAccounts}'),
                _SummaryRow('Credit Cards', '${input.numCreditCards}'),
                _SummaryRow('Secured Loans', '${input.numSecuredLoans}'),
                _SummaryRow('Unsecured Loans', '${input.numUnsecuredLoans}'),
                Divider(height: 1, color: AppColors.border),
                _SummaryRow('Employment Duration', '${input.monthsWithEmployer} months'),
                _SummaryRow('Net Monthly Income', '₹${input.netMonthlyIncome.toInt()}', isLast: true),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow(this.label, this.value, {this.isLast = false});
  final String label;
  final String value;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16, right: 16, top: 12, bottom: isLast ? 12 : 0,
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label, style: AppText.bodySecondary),
              Text(value, style: AppText.bodyBold),
            ],
          ),
          if (!isLast) ...[
            const SizedBox(height: 12),
            Divider(height: 1, color: AppColors.border),
          ]
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SHARED WIDGETS
// ══════════════════════════════════════════════════════════════════════════════

class _StepIndicator extends StatelessWidget {
  const _StepIndicator({required this.currentStep});
  final int currentStep;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Step $currentStep of 3', style: AppText.caption),
              Text(
                currentStep == 1
                    ? 'Behaviour'
                    : currentStep == 2
                        ? 'Profile'
                        : 'Review',
                style: AppText.caption.copyWith(
                    color: AppColors.primary, fontWeight: FontWeight.w600),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: List.generate(3, (index) {
              final step = index + 1;
              final isActive = step <= currentStep;
              return Expanded(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  margin: EdgeInsets.only(right: step < 3 ? 8 : 0),
                  height: 4,
                  decoration: BoxDecoration(
                    color: isActive ? AppColors.primary : AppColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

class _SliderField extends StatelessWidget {
  const _SliderField({
    required this.label,
    required this.infoText,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.valueLabel,
    required this.onChanged,
    this.hint,
    this.compact = false,
  });

  final String label;
  final String infoText;
  final double value;
  final double min;
  final double max;
  final int divisions;
  final String valueLabel;
  final ValueChanged<double> onChanged;
  final String? hint;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(compact ? 12 : 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Text(label, style: AppText.bodyBold),
                  const SizedBox(width: 8),
                  Tooltip(
                    triggerMode: TooltipTriggerMode.tap,
                    message: infoText,
                    showDuration: const Duration(seconds: 4),
                    margin: const EdgeInsets.symmetric(horizontal: 24),
                    padding: const EdgeInsets.all(12),
                    child: Icon(Icons.info_outline, size: 16, color: AppColors.textSecondary),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.primaryLight,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  valueLabel,
                  style: AppText.caption.copyWith(
                    color: AppColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          if (hint != null) ...[
            const SizedBox(height: 4),
            Text(hint!, style: AppText.caption),
          ],
          const SizedBox(height: 8),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: AppColors.primary,
              inactiveTrackColor: AppColors.border,
              thumbColor: AppColors.primary,
              overlayColor: AppColors.primary.withValues(alpha: 0.12),
              trackHeight: 4,
              valueIndicatorTextStyle: AppText.caption.copyWith(color: Colors.white),
              showValueIndicator: ShowValueIndicator.onDrag,
            ),
            child: Slider(
              value: value,
              min: min,
              max: max,
              divisions: divisions > 0 ? divisions : null,
              label: valueLabel,
              onChanged: onChanged,
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(min.toInt().toString(), style: AppText.caption.copyWith(fontSize: 10)),
                Text(max.toInt().toString(), style: AppText.caption.copyWith(fontSize: 10)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _BottomNavRow extends StatelessWidget {
  const _BottomNavRow({
    required this.step,
    required this.onBack,
    required this.onNext,
    required this.onCalculate,
  });

  final int step;
  final VoidCallback onBack;
  final VoidCallback onNext;
  final VoidCallback onCalculate;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          if (step > 1) ...[
            Expanded(
              flex: 1,
              child: AppButton(
                label: 'Back',
                onPressed: onBack,
                isOutlined: true,
              ),
            ),
            const SizedBox(width: 16),
          ],
          Expanded(
            flex: 2,
            child: AppButton(
              label: step < 3 ? 'Next' : 'Calculate Score',
              onPressed: step < 3 ? onNext : onCalculate,
            ),
          ),
        ],
      ),
    );
  }
}
