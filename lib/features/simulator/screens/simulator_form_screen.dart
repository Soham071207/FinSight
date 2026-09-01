import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../shared/widgets/app_button.dart';
import '../logic/sip_calculator.dart';

// ══════════════════════════════════════════════════════════════════════════════
// STATE PROVIDER
// ══════════════════════════════════════════════════════════════════════════════

class SimulatorFormNotifier extends Notifier<SimulatorInput> {
  @override
  SimulatorInput build() {
    return const SimulatorInput(
      mode: SimulatorMode.sip,
      monthlySip: 5000,
      lumpsum: 100000,
      annualStepUpPercent: 10,
      cagrPercent: 12,
      years: 10,
    );
  }

  void updateState(SimulatorInput newState) {
    state = newState;
  }
}

final simulatorFormProvider = NotifierProvider<SimulatorFormNotifier, SimulatorInput>(
  () => SimulatorFormNotifier(),
);

// ══════════════════════════════════════════════════════════════════════════════
// SCREEN
// ══════════════════════════════════════════════════════════════════════════════

class SimulatorFormScreen extends ConsumerStatefulWidget {
  final bool hideAppBar;
  const SimulatorFormScreen({
    super.key,
    this.hideAppBar = false,
    this.initMode,
    this.initMonthly,
    this.initYears,
  });

  final String? initMode;
  final String? initMonthly;
  final String? initYears;

  @override
  ConsumerState<SimulatorFormScreen> createState() => _SimulatorFormScreenState();
}

class _SimulatorFormScreenState extends ConsumerState<SimulatorFormScreen> {
  final _monthlyCtrl = TextEditingController();
  final _lumpsumCtrl = TextEditingController();
  final _stepUpCtrl  = TextEditingController();
  final _customCagrCtrl = TextEditingController();

  bool _isCustomCagr = false;
  final List<double> _cagrPresets = [8, 10, 12, 15];

  @override
  void initState() {
    super.initState();
    
    // Parse deep-link query params if provided
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final notifier = ref.read(simulatorFormProvider.notifier);
      SimulatorInput current = ref.read(simulatorFormProvider);

      if (widget.initMode != null) {
        final modeStr = widget.initMode!.toUpperCase();
        if (modeStr == 'SIP') current = current.copyWith(mode: SimulatorMode.sip);
        if (modeStr == 'LUMPSUM') current = current.copyWith(mode: SimulatorMode.lumpsum);
        if (modeStr == 'HYBRID') current = current.copyWith(mode: SimulatorMode.hybrid);
      }

      if (widget.initMonthly != null) {
        final val = double.tryParse(widget.initMonthly!);
        if (val != null) {
          current = current.copyWith(monthlySip: val);
          _monthlyCtrl.text = val.toInt().toString();
        }
      }

      if (widget.initYears != null) {
        final val = int.tryParse(widget.initYears!);
        if (val != null) current = current.copyWith(years: val.clamp(1, 40));
      }

      _syncControllersToState(current);
      notifier.updateState(current);
    });
  }

  void _syncControllersToState(SimulatorInput state) {
    if (_monthlyCtrl.text.isEmpty || double.tryParse(_monthlyCtrl.text) != state.monthlySip) {
      _monthlyCtrl.text = state.monthlySip.toInt().toString();
    }
    if (_lumpsumCtrl.text.isEmpty || double.tryParse(_lumpsumCtrl.text) != state.lumpsum) {
      _lumpsumCtrl.text = state.lumpsum.toInt().toString();
    }
    if (_stepUpCtrl.text.isEmpty || double.tryParse(_stepUpCtrl.text) != state.annualStepUpPercent) {
      _stepUpCtrl.text = state.annualStepUpPercent.toInt().toString();
    }
    
    if (!_cagrPresets.contains(state.cagrPercent)) {
      _isCustomCagr = true;
      _customCagrCtrl.text = state.cagrPercent.toString();
    } else {
      _isCustomCagr = false;
    }
  }

  @override
  void dispose() {
    _monthlyCtrl.dispose();
    _lumpsumCtrl.dispose();
    _stepUpCtrl.dispose();
    _customCagrCtrl.dispose();
    super.dispose();
  }

  void _onModeChanged(SimulatorMode mode) {
    final notifier = ref.read(simulatorFormProvider.notifier);
    final current = ref.read(simulatorFormProvider);
    notifier.updateState(current.copyWith(mode: mode));
  }

  void _onCagrPresetSelected(double cagr) {
    setState(() => _isCustomCagr = false);
    final notifier = ref.read(simulatorFormProvider.notifier);
    final current = ref.read(simulatorFormProvider);
    notifier.updateState(current.copyWith(cagrPercent: cagr));
  }

  void _onCustomCagrSelected() {
    setState(() => _isCustomCagr = true);
    final val = double.tryParse(_customCagrCtrl.text) ?? 12.0;
    final notifier = ref.read(simulatorFormProvider.notifier);
    final current = ref.read(simulatorFormProvider);
    notifier.updateState(current.copyWith(cagrPercent: val));
  }

  void _updateNumericField(String value, void Function(double) updater) {
    final val = double.tryParse(value) ?? 0.0;
    updater(val);
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final input = ref.watch(simulatorFormProvider);
    final notifier = ref.read(simulatorFormProvider.notifier);
    
    // Live preview calculation
    final liveResult = SipCalculator.calculate(input);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: widget.hideAppBar ? null : AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text('SIP / Lumpsum Simulator', style: AppText.heading2),
        shape: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  
                  // ── Mode Toggle ──────────────────────────────────────────────
                  _SegmentedModeToggle(
                    selectedMode: input.mode,
                    onModeChanged: _onModeChanged,
                  ),
                  const SizedBox(height: 32),

                  // ── Animated Inputs ──────────────────────────────────────────
                  AnimatedSize(
                    duration: const Duration(milliseconds: 300),
                    curve: Curves.easeInOut,
                    alignment: Alignment.topCenter,
                    child: Column(
                      children: [
                        if (input.mode == SimulatorMode.sip || input.mode == SimulatorMode.hybrid) ...[
                          _InputField(
                            label: 'Monthly Investment',
                            prefix: '₹',
                            controller: _monthlyCtrl,
                            onChanged: (v) => _updateNumericField(v, (val) => notifier.updateState(input.copyWith(monthlySip: val))),
                          ),
                          const SizedBox(height: 20),
                        ],

                        if (input.mode == SimulatorMode.lumpsum || input.mode == SimulatorMode.hybrid) ...[
                          _InputField(
                            label: 'Lumpsum Amount',
                            prefix: '₹',
                            controller: _lumpsumCtrl,
                            onChanged: (v) => _updateNumericField(v, (val) => notifier.updateState(input.copyWith(lumpsum: val))),
                          ),
                          const SizedBox(height: 20),
                        ],

                        if (input.mode == SimulatorMode.hybrid) ...[
                          _InputField(
                            label: 'Annual Step-up',
                            suffix: '%',
                            controller: _stepUpCtrl,
                            onChanged: (v) => _updateNumericField(v, (val) => notifier.updateState(input.copyWith(annualStepUpPercent: val.clamp(0, 50)))),
                            hint: 'Max 50%',
                          ),
                          const SizedBox(height: 20),
                        ],
                      ],
                    ),
                  ),

                  // ── Expected Return (CAGR) ───────────────────────────────────
                  Text('Expected Return (CAGR)', style: AppText.bodyBold),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 12,
                    children: [
                      ..._cagrPresets.map((cagr) {
                        final isSelected = !_isCustomCagr && input.cagrPercent == cagr;
                        return ChoiceChip(
                          label: Text('$cagr%'),
                          selected: isSelected,
                          onSelected: (_) => _onCagrPresetSelected(cagr),
                          selectedColor: AppColors.primaryLight,
                          labelStyle: AppText.body.copyWith(
                            color: isSelected ? AppColors.primary : AppColors.textPrimary,
                            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                          ),
                          backgroundColor: AppColors.surface,
                          side: BorderSide(
                            color: isSelected ? AppColors.primary : AppColors.border,
                          ),
                        );
                      }),
                      ChoiceChip(
                        label: const Text('Custom'),
                        selected: _isCustomCagr,
                        onSelected: (_) => _onCustomCagrSelected(),
                        selectedColor: AppColors.primaryLight,
                        labelStyle: AppText.body.copyWith(
                          color: _isCustomCagr ? AppColors.primary : AppColors.textPrimary,
                          fontWeight: _isCustomCagr ? FontWeight.w600 : FontWeight.w400,
                        ),
                        backgroundColor: AppColors.surface,
                        side: BorderSide(
                          color: _isCustomCagr ? AppColors.primary : AppColors.border,
                        ),
                      ),
                    ],
                  ),
                  
                  // Custom CAGR Text Field
                  AnimatedSize(
                    duration: const Duration(milliseconds: 250),
                    child: _isCustomCagr
                        ? Padding(
                            padding: const EdgeInsets.only(top: 16),
                            child: _InputField(
                              label: 'Custom Return Rate',
                              suffix: '%',
                              controller: _customCagrCtrl,
                              onChanged: (v) => _updateNumericField(v, (val) => notifier.updateState(input.copyWith(cagrPercent: val.clamp(0, 100)))),
                            ),
                          )
                        : const SizedBox.shrink(),
                  ),
                  const SizedBox(height: 32),

                  // ── Time Horizon Slider ──────────────────────────────────────
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Time Horizon', style: AppText.bodyBold),
                      Text('${input.years} Years', style: AppText.bodyBold.copyWith(color: AppColors.primary)),
                    ],
                  ),
                  const SizedBox(height: 16),
                  SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      activeTrackColor: AppColors.primary,
                      inactiveTrackColor: AppColors.border,
                      thumbColor: AppColors.primary,
                      overlayColor: AppColors.primary.withValues(alpha: 0.12),
                      trackHeight: 6,
                    ),
                    child: Slider(
                      value: input.years.toDouble(),
                      min: 1,
                      max: 40,
                      divisions: 39,
                      label: '${input.years} yr',
                      onChanged: (v) => notifier.updateState(input.copyWith(years: v.toInt())),
                    ),
                  ),

                  // Live Preview Text
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        'Estimated Corpus: ${formatINR(liveResult.finalCorpus)}',
                        style: AppText.caption.copyWith(
                          color: AppColors.accent,
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),

          // ── Calculate Button ───────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppColors.surface,
              border: Border(top: BorderSide(color: AppColors.border)),
            ),
            child: AppButton(
              label: 'Calculate Result',
              onPressed: () {
                // We pass the result directly since it's fully sync
                context.go(AppConstants.pathSimulatorResult, extra: liveResult);
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// WIDGETS
// ══════════════════════════════════════════════════════════════════════════════

class _SegmentedModeToggle extends StatelessWidget {
  const _SegmentedModeToggle({
    required this.selectedMode,
    required this.onModeChanged,
  });

  final SimulatorMode selectedMode;
  final ValueChanged<SimulatorMode> onModeChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.border.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          _buildSegment('SIP', SimulatorMode.sip),
          _buildSegment('Lumpsum', SimulatorMode.lumpsum),
          _buildSegment('Hybrid', SimulatorMode.hybrid),
        ],
      ),
    );
  }

  Widget _buildSegment(String title, SimulatorMode mode) {
    final isSelected = selectedMode == mode;
    return Expanded(
      child: GestureDetector(
        onTap: () => onModeChanged(mode),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.surface : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            boxShadow: isSelected
                ? [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.05),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    )
                  ]
                : [],
          ),
          alignment: Alignment.center,
          child: Text(
            title,
            style: AppText.label.copyWith(
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
              fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
            ),
          ),
        ),
      ),
    );
  }
}

class _InputField extends StatelessWidget {
  const _InputField({
    required this.label,
    this.prefix,
    this.suffix,
    required this.controller,
    required this.onChanged,
    this.hint,
  });

  final String label;
  final String? prefix;
  final String? suffix;
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppText.bodyBold),
        const SizedBox(height: 8),
        TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d+\.?\d*'))],
          onChanged: onChanged,
          style: AppText.body,
          decoration: InputDecoration(
            hintText: hint,
            prefixText: prefix != null ? '$prefix ' : null,
            suffixText: suffix != null ? ' $suffix' : null,
            prefixStyle: AppText.body.copyWith(color: AppColors.textSecondary),
            suffixStyle: AppText.body.copyWith(color: AppColors.textSecondary),
            filled: true,
            fillColor: AppColors.inputFill, // Match Section 1 input specs
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: AppColors.primary, width: 2),
            ),
          ),
        ),
      ],
    );
  }
}
