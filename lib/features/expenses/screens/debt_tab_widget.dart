import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// lib/features/expenses/screens/debt_tab_widget.dart
// Debt Tracker — Friends Debt Tab for the Expenses module

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../data/local/models/debt_entry.dart';
import '../../../shared/widgets/empty_state_widget.dart';
import '../logic/debt_provider.dart';

// ══════════════════════════════════════════════════════════════════════════════
// DEBT TAB
// ══════════════════════════════════════════════════════════════════════════════

class DebtTabWidget extends ConsumerWidget {
  const DebtTabWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final state = ref.watch(debtProvider);

    if (state.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Column(
      children: [
        // ── Summary Banner ──────────────────────────────────────────────────
        _DebtSummaryBanner(
          iOwe: state.totalIOwe,
          owedToMe: state.totalOwedToMe,
        ),

        // ── Add Debt FAB hint / header ──────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('All Debts', style: AppText.bodyBold),
              Text('${state.debts.length} entries', style: AppText.caption),
            ],
          ),
        ),

        // ── List ────────────────────────────────────────────────────────────
        Expanded(
          child: state.debts.isEmpty
              ? const EmptyStateWidget(
                  icon: Icons.handshake_outlined,
                  title: 'No debts tracked',
                  message:
                      'Tap the + button to add a debt with a friend.',
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 100),
                  itemCount: state.debts.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, i) => _DebtCard(
                    debt: state.debts[i],
                    onTogglePaid: () => ref
                        .read(debtProvider.notifier)
                        .togglePaid(state.debts[i].id),
                    onDelete: () => ref
                        .read(debtProvider.notifier)
                        .deleteDebt(state.debts[i].id),
                    onEdit: () => showAddDebtSheet(
                        context, ref,
                        existing: state.debts[i]),
                  ),
                ),
        ),
      ],
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SUMMARY BANNER
// ══════════════════════════════════════════════════════════════════════════════

class _DebtSummaryBanner extends StatelessWidget {
  const _DebtSummaryBanner(
      {required this.iOwe, required this.owedToMe});
  final double iOwe;
  final double owedToMe;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.primary, AppColors.primaryLight],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Expanded(
            child: _SumTile(
              label: 'I Owe',
              amount: iOwe,
              color: AppColors.danger,
              icon: Icons.arrow_upward_rounded,
            ),
          ),
          Container(
              width: 1, height: 48, color: Colors.white12),
          Expanded(
            child: _SumTile(
              label: 'Owed to Me',
              amount: owedToMe,
              color: AppColors.accent,
              icon: Icons.arrow_downward_rounded,
            ),
          ),
        ],
      ),
    );
  }
}

class _SumTile extends StatelessWidget {
  const _SumTile(
      {required this.label,
      required this.amount,
      required this.color,
      required this.icon});
  final String label;
  final double amount;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 4),
            Text(label,
                style: AppText.caption
                    .copyWith(color: Colors.white70)),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          formatINR(amount),
          style: AppText.heading2.copyWith(color: color),
        ),
      ],
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// DEBT CARD
// ══════════════════════════════════════════════════════════════════════════════

class _DebtCard extends StatelessWidget {
  const _DebtCard({
    required this.debt,
    required this.onTogglePaid,
    required this.onDelete,
    required this.onEdit,
  });
  final DebtEntry debt;
  final VoidCallback onTogglePaid;
  final VoidCallback onDelete;
  final VoidCallback onEdit;

  bool get _iOwe => debt.direction == 'owe';

  Color get _statusColor =>
      debt.isPaid ? AppColors.accent : AppColors.danger;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: debt.isPaid
              ? AppColors.accent.withValues(alpha: 0.3)
              : AppColors.danger.withValues(alpha: 0.3),
          width: 1.5,
        ),
      ),
      child: Column(
        children: [
          // Main row
          Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                // Avatar circle
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: _statusColor.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    debt.friendName.isNotEmpty
                        ? debt.friendName[0].toUpperCase()
                        : '?',
                    style: AppText.bodyBold.copyWith(
                        color: _statusColor, fontSize: 18),
                  ),
                ),
                const SizedBox(width: 12),

                // Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(debt.friendName,
                          style: AppText.bodyBold),
                      if (debt.note.isNotEmpty)
                        Text(debt.note,
                            style: AppText.caption.copyWith(
                                color: AppColors.textSecondary),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 2),
                      Text(
                        DateFormat('d MMM yyyy')
                            .format(debt.createdAt),
                        style: AppText.caption.copyWith(
                            color: AppColors.textSecondary,
                            fontSize: 10),
                      ),
                    ],
                  ),
                ),

                // Amount + direction
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      formatINR(debt.amount),
                      style: AppText.bodyBold.copyWith(
                        fontSize: 15,
                        color: _iOwe
                            ? AppColors.danger
                            : AppColors.accent,
                      ),
                    ),
                    Container(
                      margin: const EdgeInsets.only(top: 2),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: (_iOwe
                                ? AppColors.danger
                                : AppColors.accent)
                            .withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        _iOwe ? 'I Owe' : 'Owed to Me',
                        style: AppText.caption.copyWith(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          color: _iOwe
                              ? AppColors.danger
                              : AppColors.accent,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Action row
          Divider(height: 1, color: AppColors.border),
          Row(
            children: [
              // Paid toggle
              Expanded(
                child: InkWell(
                  onTap: onTogglePaid,
                  borderRadius: const BorderRadius.only(
                      bottomLeft: Radius.circular(14)),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          debt.isPaid
                              ? Icons.check_circle_rounded
                              : Icons.radio_button_unchecked_rounded,
                          size: 16,
                          color: _statusColor,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          debt.isPaid ? 'Paid ✓' : 'Unpaid',
                          style: AppText.caption.copyWith(
                            fontWeight: FontWeight.w700,
                            color: _statusColor,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              Container(width: 1, height: 36, color: AppColors.border),

              // Edit
              Expanded(
                child: InkWell(
                  onTap: onEdit,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.edit_outlined,
                            size: 14, color: AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Text('Edit',
                            style: AppText.caption
                                .copyWith(color: AppColors.textSecondary)),
                      ],
                    ),
                  ),
                ),
              ),

              Container(width: 1, height: 36, color: AppColors.border),

              // Delete
              Expanded(
                child: InkWell(
                  onTap: () {
                    showDialog(
                      context: context,
                      builder: (ctx) => AlertDialog(
                        backgroundColor: AppColors.surface,
                        title: Text('Delete Debt',
                            style: AppText.bodyBold),
                        content: Text(
                            'Remove debt with ${debt.friendName}?',
                            style: AppText.body),
                        actions: [
                          TextButton(
                              onPressed: () => Navigator.pop(ctx),
                              child: const Text('Cancel')),
                          TextButton(
                            onPressed: () {
                              Navigator.pop(ctx);
                              onDelete();
                            },
                            child: Text('Delete',
                                style: TextStyle(
                                    color: AppColors.danger)),
                          ),
                        ],
                      ),
                    );
                  },
                  borderRadius: const BorderRadius.only(
                      bottomRight: Radius.circular(14)),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.delete_outline_rounded,
                            size: 14, color: AppColors.danger),
                        const SizedBox(width: 4),
                        Text('Delete',
                            style: AppText.caption
                                .copyWith(color: AppColors.danger)),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// ADD / EDIT DEBT BOTTOM SHEET
// ══════════════════════════════════════════════════════════════════════════════

void showAddDebtSheet(BuildContext context, WidgetRef ref,
    {DebtEntry? existing}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => ProviderScope(
      parent: ProviderScope.containerOf(context),
      child: _AddDebtSheet(existing: existing),
    ),
  );
}

class _AddDebtSheet extends ConsumerStatefulWidget {
  const _AddDebtSheet({this.existing});
  final DebtEntry? existing;

  @override
  ConsumerState<_AddDebtSheet> createState() => _AddDebtSheetState();
}

class _AddDebtSheetState extends ConsumerState<_AddDebtSheet> {
  final _nameCtrl = TextEditingController();
  final _amountCtrl = TextEditingController();
  final _noteCtrl = TextEditingController();
  String _direction = 'owe'; // 'owe' | 'owed'
  bool _isPaid = false;

  @override
  void initState() {
    super.initState();
    if (widget.existing != null) {
      final e = widget.existing!;
      _nameCtrl.text = e.friendName;
      _amountCtrl.text = e.amount.toStringAsFixed(2);
      _noteCtrl.text = e.note;
      _direction = e.direction;
      _isPaid = e.isPaid;
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _amountCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  void _save() {
    final name = _nameCtrl.text.trim();
    final amount = double.tryParse(_amountCtrl.text.trim());

    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Friend name is required')));
      return;
    }
    if (amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enter a valid amount')));
      return;
    }

    final debt = DebtEntry(
      id: widget.existing?.id ??
          DateTime.now().millisecondsSinceEpoch.toString(),
      friendName: name,
      amount: amount,
      note: _noteCtrl.text.trim(),
      direction: _direction,
      isPaid: _isPaid,
      createdAt: widget.existing?.createdAt ?? DateTime.now(),
    );

    if (widget.existing != null) {
      ref.read(debtProvider.notifier).editDebt(debt);
    } else {
      ref.read(debtProvider.notifier).addDebt(debt);
    }
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final isEditing = widget.existing != null;
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Title
            Text(isEditing ? 'Edit Debt' : 'Add Debt',
                style: AppText.heading2),
            const SizedBox(height: 20),

            // Direction toggle
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                children: [
                  _DirChip(
                    label: 'I Owe Them',
                    value: 'owe',
                    current: _direction,
                    activeColor: AppColors.danger,
                    onTap: (v) => setState(() => _direction = v),
                  ),
                  _DirChip(
                    label: 'They Owe Me',
                    value: 'owed',
                    current: _direction,
                    activeColor: AppColors.accent,
                    onTap: (v) => setState(() => _direction = v),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Friend name
            _Field(
              label: 'Friend Name',
              controller: _nameCtrl,
              hint: 'e.g. Rahul',
              keyboardType: TextInputType.name,
              icon: Icons.person_outline_rounded,
            ),
            const SizedBox(height: 12),

            // Amount
            _Field(
              label: 'Amount (₹)',
              controller: _amountCtrl,
              hint: '0.00',
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              icon: Icons.currency_rupee_rounded,
            ),
            const SizedBox(height: 12),

            // Note
            _Field(
              label: 'Note (optional)',
              controller: _noteCtrl,
              hint: 'e.g. Dinner at Taj',
              keyboardType: TextInputType.text,
              icon: Icons.notes_rounded,
            ),
            const SizedBox(height: 16),

            // Paid toggle
            Row(
              children: [
                Switch(
                  value: _isPaid,
                  onChanged: (v) => setState(() => _isPaid = v),
                  activeThumbColor: AppColors.accent,
                ),
                const SizedBox(width: 8),
                Text(
                  _isPaid ? 'Marked as Paid' : 'Mark as Paid',
                  style: AppText.body.copyWith(
                    color: _isPaid
                        ? AppColors.accent
                        : AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Save button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: AppColors.onPrimary,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                  elevation: 0,
                ),
                onPressed: _save,
                child: Text(isEditing ? 'Save Changes' : 'Add Debt',
                    style: AppText.bodyBold
                        .copyWith(color: AppColors.onPrimary)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Direction Chip ────────────────────────────────────────────────────────────

class _DirChip extends StatelessWidget {
  const _DirChip({
    required this.label,
    required this.value,
    required this.current,
    required this.activeColor,
    required this.onTap,
  });
  final String label;
  final String value;
  final String current;
  final Color activeColor;
  final void Function(String) onTap;

  @override
  Widget build(BuildContext context) {
    final sel = value == current;
    return Expanded(
      child: GestureDetector(
        onTap: () => onTap(value),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: sel ? activeColor : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            style: AppText.caption.copyWith(
              fontWeight: FontWeight.w600,
              color: sel ? Colors.white : AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

// ── Field ─────────────────────────────────────────────────────────────────────

class _Field extends StatelessWidget {
  const _Field({
    required this.label,
    required this.controller,
    required this.hint,
    required this.keyboardType,
    required this.icon,
  });
  final String label;
  final TextEditingController controller;
  final String hint;
  final TextInputType keyboardType;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style:
                AppText.caption.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          style: AppText.body,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: AppText.body
                .copyWith(color: AppColors.textSecondary),
            prefixIcon:
                Icon(icon, size: 18, color: AppColors.textSecondary),
            filled: true,
            fillColor: AppColors.background,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          ),
        ),
      ],
    );
  }
}
