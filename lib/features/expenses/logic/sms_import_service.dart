import 'dart:async';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../../../data/local/models/pending_sms_entry.dart';
import '../../../data/local/models/expense_entry.dart';
import 'sms_parser.dart';
import 'sms_import_service_mobile.dart' if (dart.library.html) 'sms_import_service_stub.dart' as impl;

class SmsImportService {
  Function(PendingSmsEntry)? onNewSmsParsed;
  
  bool get _isSupported => !kIsWeb;

  Future<bool> checkPermissionGranted() async {
    if (!_isSupported) return false;
    return await impl.checkPermissionGranted();
  }

  Future<bool> requestPermission() async {
    if (!_isSupported) return false;
    return await impl.requestPermission();
  }

  Future<List<Map<String, String>>> dumpRawSms(int days) async {
    if (!_isSupported) return [];
    return await impl.dumpRawSms(days);
  }

  Future<List<PendingSmsEntry>> scanHistorical(
      int days, List<ExpenseEntry> existingEntries, List<String> discardedSignatures) async {
    if (!_isSupported) return [];
    return await impl.scanHistorical(days, existingEntries, _isDuplicate, discardedSignatures);
  }

  void startRealTimeListener(List<ExpenseEntry> existingEntries, List<String> discardedSignatures) {
    if (!_isSupported) return;
    impl.startRealTimeListener(existingEntries, _isDuplicate, onNewSmsParsed, discardedSignatures);
  }

  void stopRealTimeListener() {
    if (!_isSupported) return;
    impl.stopRealTimeListener();
  }

  bool _isDuplicate(ParsedTransaction parsed, List<ExpenseEntry> existing) {
    final parsedDate = parsed.dateTime ?? DateTime.now();
    for (final e in existing) {
      final amtDiff = (e.amount - parsed.amount).abs();
      if (amtDiff <= 1.0) {
        final dateDiff = e.timestamp.difference(parsedDate).inDays.abs();
        if (dateDiff <= 1) return true;
      }
    }
    return false;
  }
}
