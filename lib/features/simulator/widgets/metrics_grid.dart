import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../logic/sip_calculator.dart';

class MetricsGrid extends StatelessWidget {
  const MetricsGrid({
    super.key,
    required this.result,
  });

  final SimulatorResult result;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          // Invested
          _MetricCell(
            label: 'Invested',
            value: formatINRCompact(result.totalInvested),
          ),
          _divider(),

          // Returns
          _MetricCell(
            label: 'Returns',
            value: formatINRCompact(result.estimatedReturn),
            subValue: '+${result.absoluteReturnPercent.toStringAsFixed(1)}%',
            valueColor: result.estimatedReturn >= 0 ? AppColors.accent : AppColors.danger,
            tooltipMessage: 'Absolute return (total profit without considering time duration)',
          ),
          _divider(),

          // CAGR
          _MetricCell(
            label: 'CAGR',
            value: '${result.cagr.toStringAsFixed(1)}%',
            tooltipMessage: 'Compound Annual Growth Rate (annualized return)',
          ),
        ],
      ),
    );
  }

  Widget _divider() {
    return Container(
      width: 1,
      height: 40,
      color: AppColors.border,
      margin: const EdgeInsets.symmetric(horizontal: 12),
    );
  }
}

class _MetricCell extends StatelessWidget {
  const _MetricCell({
    required this.label,
    required this.value,
    this.subValue,
    this.valueColor,
    this.tooltipMessage,
  });

  final String label;
  final String value;
  final String? subValue;
  final Color? valueColor;
  final String? tooltipMessage;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (tooltipMessage != null)
            Tooltip(
              message: tooltipMessage,
              triggerMode: TooltipTriggerMode.tap,
              showDuration: const Duration(seconds: 4),
              child: Row(
                children: [
                  Flexible(
                    child: Text(
                      label,
                      style: AppText.caption,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Icon(Icons.info_outline_rounded, size: 10, color: AppColors.textSecondary),
                ],
              ),
            )
          else
            Text(
              label,
              style: AppText.caption,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: AppText.bodyBold.copyWith(
                  color: valueColor ?? AppColors.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              if (subValue != null) ...[
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    subValue!,
                    style: AppText.caption.copyWith(
                      color: valueColor ?? AppColors.textPrimary,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
