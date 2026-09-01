import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../data/local/models/expense_entry.dart';
import '../../../data/local/models/pending_sms_entry.dart';
import 'sms_import_service.dart';

// ══════════════════════════════════════════════════════════════════════════════
// STATE MODEL
// ══════════════════════════════════════════════════════════════════════════════

class ExpenseState {
  const ExpenseState({
    this.entries = const [],
    this.pendingSmsEntries = const [],
    this.smsImportEnabled = false,
    this.smsBannerDismissed = false,
    this.isLoading = false,
    this.error,
  });

  final List<ExpenseEntry> entries;
  final List<PendingSmsEntry> pendingSmsEntries;
  final bool smsImportEnabled;
  final bool smsBannerDismissed;
  final bool isLoading;
  final String? error;

  ExpenseState copyWith({
    List<ExpenseEntry>? entries,
    List<PendingSmsEntry>? pendingSmsEntries,
    bool? smsImportEnabled,
    bool? smsBannerDismissed,
    bool? isLoading,
    String? error,
  }) {
    return ExpenseState(
      entries: entries ?? this.entries,
      pendingSmsEntries: pendingSmsEntries ?? this.pendingSmsEntries,
      smsImportEnabled: smsImportEnabled ?? this.smsImportEnabled,
      smsBannerDismissed: smsBannerDismissed ?? this.smsBannerDismissed,
      isLoading: isLoading ?? this.isLoading,
      error: error ?? this.error,
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// PROVIDER LOGIC
// ══════════════════════════════════════════════════════════════════════════════

class ExpenseNotifier extends Notifier<ExpenseState> {
  Box<dynamic>? _box;
  static const String _boxName = 'expenses';
  final SmsImportService _smsService = SmsImportService();

  @override
  ExpenseState build() {
    _init();
    return const ExpenseState(isLoading: true);
  }

  Future<void> _init() async {
    try {
      // Use the box that HiveService already opened (Box<dynamic>).
      // Do NOT re-open as Box<ExpenseEntry> — Hive treats them as separate.
      if (Hive.isBoxOpen(_boxName)) {
        _box = Hive.box<dynamic>(_boxName);
      } else {
        _box = await Hive.openBox<dynamic>(_boxName);
      }
      
      final prefs = await SharedPreferences.getInstance();
      final smsEnabled = prefs.getBool('sms_import_enabled') ?? false;

      state = state.copyWith(smsImportEnabled: smsEnabled);
      loadEntries();

      if (smsEnabled) {
        await _startSmsServices();
      }

    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> _startSmsServices() async {
    final prefs = await SharedPreferences.getInstance();
    final discarded = prefs.getStringList('discarded_sms_signatures') ?? [];

    // 1. Scan only the last 1 day (today) to immediately catch any test messages 
    // the user sent right before toggling the switch. The strict sender whitelist
    // guarantees this won't pull in junk.
    final pending = await _smsService.scanHistorical(1, state.entries, discarded);
    state = state.copyWith(pendingSmsEntries: pending, smsBannerDismissed: false);

    _smsService.onNewSmsParsed = (entry) {
      state = state.copyWith(
        pendingSmsEntries: [entry, ...state.pendingSmsEntries],
        smsBannerDismissed: false, // Show banner again for new SMS
      );
    };
    _smsService.startRealTimeListener(state.entries, discarded);
  }

  void loadEntries() {
    if (_box == null) return;
    try {
      final allEntries = _box!.values.whereType<ExpenseEntry>().toList();
      // Sort DESC by timestamp (newest first)
      allEntries.sort((a, b) => b.timestamp.compareTo(a.timestamp));
      state = state.copyWith(entries: allEntries, isLoading: false, error: null);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> addEntry(ExpenseEntry entry) async {
    if (_box == null) return;
    try {
      await _box!.put(entry.id, entry);
      loadEntries();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> deleteEntry(String id) async {
    if (_box == null) return;
    try {
      await _box!.delete(id);
      loadEntries();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> editEntry(ExpenseEntry entry) async {
    if (_box == null) return;
    try {
      await _box!.put(entry.id, entry);
      loadEntries();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  // ── SMS Logic ───────────────────────────────────────────────────────────────

  Future<void> toggleSmsImport() async {
    if (state.smsImportEnabled) {
      // Disable
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('sms_import_enabled', false);
      _smsService.stopRealTimeListener();
      state = state.copyWith(
        smsImportEnabled: false, 
        pendingSmsEntries: [],
        smsBannerDismissed: false,
      );
    } else {
      // Enable -> Request permission
      final granted = await _smsService.requestPermission();
      if (granted) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setBool('sms_import_enabled', true);
        state = state.copyWith(smsImportEnabled: true);
        await _startSmsServices();
      }
    }
  }

  Future<void> refreshSms() async {
    if (!state.smsImportEnabled) return;
    state = state.copyWith(isLoading: true);
    await _startSmsServices();
    state = state.copyWith(isLoading: false);
  }

  Future<void> confirmSmsEntry(PendingSmsEntry pending) async {
    final entry = ExpenseEntry(
      id: pending.id,
      amount: pending.amount,
      category: pending.category,
      note: pending.note,
      timestamp: pending.date,
      source: 'sms_import',
    );
    await addEntry(entry);
    
    // Also save signature so we don't scan it again if they edit/delete it later
    await _saveDiscardedSignature(pending.signature);
    
    discardSmsEntry(pending.id, saveSignature: false);
  }

  Future<void> _saveDiscardedSignature(String signature) async {
    final prefs = await SharedPreferences.getInstance();
    final discarded = prefs.getStringList('discarded_sms_signatures') ?? [];
    if (!discarded.contains(signature)) {
      discarded.add(signature);
      // Keep list from growing infinitely (store last 1000)
      if (discarded.length > 1000) {
        discarded.removeRange(0, discarded.length - 1000);
      }
      await prefs.setStringList('discarded_sms_signatures', discarded);
    }
  }

  void discardSmsEntry(String id, {bool saveSignature = true}) async {
    final pending = state.pendingSmsEntries.firstWhere((e) => e.id == id);
    if (saveSignature) {
      await _saveDiscardedSignature(pending.signature);
    }

    final updatedList = state.pendingSmsEntries.where((e) => e.id != id).toList();
    state = state.copyWith(pendingSmsEntries: updatedList);
  }

  void removePendingSms(String id) {
    state = state.copyWith(
      pendingSmsEntries: state.pendingSmsEntries.where((e) => e.id != id).toList(),
    );
  }

  void dismissSmsBanner() {
    state = state.copyWith(smsBannerDismissed: true);
  }

  Future<void> confirmAll() async {
    for (final pending in state.pendingSmsEntries) {
      final entry = ExpenseEntry(
        id: pending.id,
        amount: pending.amount,
        category: pending.category,
        note: pending.note,
        timestamp: pending.date,
        source: 'sms_import',
      );
      await _box?.put(entry.id, entry);
      await _saveDiscardedSignature(pending.signature);
    }
    loadEntries();
    state = state.copyWith(pendingSmsEntries: []);
  }

  Future<void> discardAll() async {
    for (final pending in state.pendingSmsEntries) {
      await _saveDiscardedSignature(pending.signature);
    }
    state = state.copyWith(pendingSmsEntries: []);
  }

  // ── Queries ─────────────────────────────────────────────────────────────────

  List<ExpenseEntry> getEntriesForPeriod(DateTime start, DateTime end) {
    return state.entries.where((e) {
      return e.timestamp.isAfter(start.subtract(const Duration(seconds: 1))) &&
             e.timestamp.isBefore(end.add(const Duration(seconds: 1)));
    }).toList();
  }

  Map<String, double> getTotalByCategory(DateTime start, DateTime end) {
    final entries = getEntriesForPeriod(start, end);
    final map = <String, double>{};
    for (final e in entries) {
      map[e.category] = (map[e.category] ?? 0.0) + e.amount;
    }
    return map;
  }

  double getMonthlyTotal() {
    final now = DateTime.now();
    final start = DateTime(now.year, now.month, 1);
    final end = DateTime(now.year, now.month + 1, 0, 23, 59, 59);
    final entries = getEntriesForPeriod(start, end);
    return entries.fold(0.0, (sum, e) => sum + e.amount);
  }

  Map<DateTime, double> getDailyTotals() {
    final map = <DateTime, double>{};
    for (final e in state.entries) {
      // Normalize to midnight
      final date = DateTime(e.timestamp.year, e.timestamp.month, e.timestamp.day);
      map[date] = (map[date] ?? 0.0) + e.amount;
    }
    return map;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// EXPORTED PROVIDER
// ══════════════════════════════════════════════════════════════════════════════

final expenseProvider = NotifierProvider<ExpenseNotifier, ExpenseState>(() {
  return ExpenseNotifier();
});
