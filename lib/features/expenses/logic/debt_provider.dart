// lib/features/expenses/logic/debt_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';
import '../../../core/constants/app_constants.dart';
import '../../../data/local/models/debt_entry.dart';

// ══════════════════════════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════════════════════════

class DebtState {
  const DebtState({
    this.debts = const [],
    this.isLoading = false,
    this.error,
  });

  final List<DebtEntry> debts;
  final bool isLoading;
  final String? error;

  DebtState copyWith({
    List<DebtEntry>? debts,
    bool? isLoading,
    String? error,
  }) {
    return DebtState(
      debts:     debts ?? this.debts,
      isLoading: isLoading ?? this.isLoading,
      error:     error ?? this.error,
    );
  }

  /// Total I owe (direction == 'owe', not paid).
  double get totalIOwe => debts
      .where((d) => d.direction == 'owe' && !d.isPaid)
      .fold(0.0, (s, d) => s + d.amount);

  /// Total owed to me (direction == 'owed', not paid).
  double get totalOwedToMe => debts
      .where((d) => d.direction == 'owed' && !d.isPaid)
      .fold(0.0, (s, d) => s + d.amount);
}

// ══════════════════════════════════════════════════════════════════════════════
// NOTIFIER
// ══════════════════════════════════════════════════════════════════════════════

class DebtNotifier extends Notifier<DebtState> {
  Box<dynamic>? _box;

  @override
  DebtState build() {
    // Hive is already initialized by HiveService before runApp, so we can access it directly.
    _box = Hive.box<dynamic>(AppConstants.hiveBoxDebts);
    
    // We defer loading so that the initial build completes before state updates.
    Future.microtask(() => _loadDebts());
    
    return const DebtState(isLoading: true);
  }

  void _loadDebts() {
    if (_box == null) return;
    try {
      final all = _box!.values.whereType<DebtEntry>().toList();
      // Sort: unpaid first, then by date descending
      all.sort((a, b) {
        if (a.isPaid != b.isPaid) return a.isPaid ? 1 : -1;
        return b.createdAt.compareTo(a.createdAt);
      });
      state = state.copyWith(debts: all, isLoading: false, error: null);
    } catch (e) {
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> addDebt(DebtEntry debt) async {
    if (_box == null) return;
    try {
      await _box!.put(debt.id, debt);
      _loadDebts();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> togglePaid(String id) async {
    if (_box == null) return;
    try {
      final debt = _box!.get(id) as DebtEntry?;
      if (debt == null) return;
      final updated = debt.copyWith(isPaid: !debt.isPaid);
      await _box!.put(id, updated);
      _loadDebts();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> deleteDebt(String id) async {
    if (_box == null) return;
    try {
      await _box!.delete(id);
      _loadDebts();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> editDebt(DebtEntry updated) async {
    if (_box == null) return;
    try {
      await _box!.put(updated.id, updated);
      _loadDebts();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// PROVIDER
// ══════════════════════════════════════════════════════════════════════════════

final debtProvider = NotifierProvider<DebtNotifier, DebtState>(() {
  return DebtNotifier();
});
