import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/empty_state_widget.dart';
import '../../../core/constants/app_constants.dart';
import '../../../data/local/models/pending_sms_entry.dart';
import '../logic/expense_provider.dart';

class PendingReviewScreen extends ConsumerWidget {
  const PendingReviewScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final expenseState = ref.watch(expenseProvider);
    final pendingEntries = expenseState.pendingSmsEntries;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Column(
          children: [
            Text('Review SMS Transactions', style: AppText.heading2),
            Text(
              '${pendingEntries.length} transactions found — confirm to add',
              style: AppText.caption,
            ),
          ],
        ),
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go(AppConstants.pathExpenses);
            }
          },
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: pendingEntries.isEmpty
                ? Center(
                    child: Text('No pending transactions', style: AppText.bodySecondary),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: pendingEntries.length,
                    itemBuilder: (context, index) {
                      final entry = pendingEntries[index];
                      return _PendingEntryCard(entry: entry);
                    },
                  ),
          ),
          if (pendingEntries.length >= 3)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: AppButton(
                      label: 'Discard All',
                      onPressed: () {
                        ref.read(expenseProvider.notifier).discardAll();
                        if (context.canPop()) context.pop();
                      },
                      isOutlined: true,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: AppButton(
                      label: 'Confirm All',
                      onPressed: () {
                        ref.read(expenseProvider.notifier).confirmAll();
                        if (context.canPop()) context.pop();
                      },
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _PendingEntryCard extends ConsumerWidget {
  const _PendingEntryCard({required this.entry});
  final PendingSmsEntry entry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Top Row
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.message_rounded, size: 14, color: AppColors.primary),
                      const SizedBox(width: 6),
                      Text(
                        'From: ${entry.senderOrigin}', 
                        style: AppText.caption.copyWith(
                          fontWeight: FontWeight.w800, 
                          color: AppColors.primary,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(DateFormat('dd MMM, HH:mm').format(entry.date), style: AppText.caption),
              ],
            ),
          ),

          // Middle row: Merchant + Amount
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(entry.merchant, style: AppText.bodyBold),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.primaryLight,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(entry.category, style: AppText.caption.copyWith(color: AppColors.primary)),
                      ),
                    ],
                  ),
                ),
                Text(
                  formatINR(entry.amount),
                  style: AppText.heading2.copyWith(color: AppColors.primary),
                ),
              ],
            ),
          ),

          if (entry.isDuplicate)
            Container(
              margin: const EdgeInsets.only(top: 12),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AppColors.warning.withValues(alpha: 0.1),
              child: Row(
                children: [
                  Icon(Icons.warning_amber_rounded, size: 16, color: AppColors.warning),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Possible duplicate — you may have already added this',
                      style: AppText.caption.copyWith(color: AppColors.warning, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          
          const SizedBox(height: 12),

          // Bottom Actions
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Row(
              children: [
                Expanded(
                  child: InkWell(
                    onTap: () => ref.read(expenseProvider.notifier).discardSmsEntry(entry.id),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        border: Border.all(color: AppColors.danger),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      alignment: Alignment.center,
                      child: Text('Discard ✕', style: AppText.label.copyWith(color: AppColors.danger, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: InkWell(
                    onTap: () => ref.read(expenseProvider.notifier).confirmSmsEntry(entry),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        color: AppColors.accent,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      alignment: Alignment.center,
                      child: Text('Confirm ✓', style: AppText.label.copyWith(color: Colors.white, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
