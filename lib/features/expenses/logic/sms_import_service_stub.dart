// lib/features/expenses/logic/sms_import_service_stub.dart
//
// Stub implementation for Web platform.
// All functions return safe empty results.

import '../../../data/local/models/pending_sms_entry.dart';
import '../../../data/local/models/expense_entry.dart';
import 'sms_parser.dart';

Future<bool> checkPermissionGranted() async => false;

Future<bool> requestPermission() async => false;

Future<List<Map<String, String>>> dumpRawSms(int days) async => [];

Future<List<PendingSmsEntry>> scanHistorical(
  int days,
  List<ExpenseEntry> existingEntries,
  bool Function(ParsedTransaction, List<ExpenseEntry>) isDuplicate,
) async => [];

void startRealTimeListener(
  List<ExpenseEntry> existingEntries,
  bool Function(ParsedTransaction, List<ExpenseEntry>) isDuplicate,
  Function(PendingSmsEntry)? onNewSmsParsed,
) {}

void stopRealTimeListener() {}
