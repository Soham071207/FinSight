// lib/features/expenses/logic/sms_import_service_mobile.dart
//
// Completely rebuilt SMS architecture.
// Uses ONLY telephony for unified, reliable scanning.

import 'dart:io';
import 'package:uuid/uuid.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:telephony/telephony.dart' as tel;
import '../../../data/local/models/pending_sms_entry.dart';
import '../../../data/local/models/expense_entry.dart';
import 'sms_parser.dart';

final tel.Telephony _telephony = tel.Telephony.instance;

Future<bool> checkPermissionGranted() async {
  if (!Platform.isAndroid) return false;
  return await Permission.sms.status == PermissionStatus.granted;
}

Future<bool> requestPermission() async {
  if (!Platform.isAndroid) return false;
  final status = await Permission.sms.request();
  return status.isGranted;
}

/// Diagnostic: dump ALL raw SMS from the last N days.
Future<List<Map<String, String>>> dumpRawSms(int days) async {
  if (!Platform.isAndroid) return [];
  if (!await checkPermissionGranted()) return [];

  final cutoffDate = DateTime.now().subtract(Duration(days: days));
  final List<Map<String, String>> results = [];

  try {
    final telMessages = await _telephony.getInboxSms(
      columns: [
        tel.SmsColumn.ADDRESS,
        tel.SmsColumn.BODY,
        tel.SmsColumn.DATE,
      ],
      sortOrder: [tel.OrderBy(tel.SmsColumn.DATE, sort: tel.Sort.DESC)],
    );
    for (final m in telMessages) {
      final msgDate = m.date != null ? DateTime.fromMillisecondsSinceEpoch(m.date!) : null;
      if (msgDate == null || msgDate.isBefore(cutoffDate)) continue;
      results.add({
        'source': 'telephony',
        'sender': m.address ?? '(null)',
        'address': m.address ?? '(null)',
        'body': m.body ?? '(null)',
        'date': msgDate.toIso8601String(),
      });
    }
  } catch (e) {
    results.add({'source': 'telephony', 'error': e.toString()});
  }

  return results;
}

Future<List<PendingSmsEntry>> scanHistorical(
  int days,
  List<ExpenseEntry> existingEntries,
  bool Function(ParsedTransaction, List<ExpenseEntry>) isDuplicate,
  List<String> discardedSignatures,
) async {
  if (!Platform.isAndroid) return [];
  if (!await checkPermissionGranted()) return [];

  final cutoffDate = DateTime.now().subtract(Duration(days: days));
  final List<PendingSmsEntry> pendingList = [];
  final Set<String> seenBodies = {}; 

  try {
    final telMessages = await _telephony.getInboxSms(
      columns: [
        tel.SmsColumn.ADDRESS,
        tel.SmsColumn.BODY,
        tel.SmsColumn.DATE,
      ],
      sortOrder: [tel.OrderBy(tel.SmsColumn.DATE, sort: tel.Sort.DESC)],
    );
    for (final message in telMessages) {
      final msgDate = message.date != null ? DateTime.fromMillisecondsSinceEpoch(message.date!) : null;
      if (msgDate == null || msgDate.isBefore(cutoffDate)) continue;
      final body = message.body;
      final addr = message.address;
      if (body == null || addr == null) continue;
      
      // Filter out duplicate identical messages
      if (seenBodies.contains(body)) continue; 

      final parsed = SmsParser.parse(body, addr);
      if (parsed != null) {
        seenBodies.add(body);
        
        final actualDate = msgDate;
        final signature = '${parsed.rawBody.hashCode}_${actualDate.millisecondsSinceEpoch}';
        if (discardedSignatures.contains(signature)) continue;

        final correctedParsed = ParsedTransaction(
           amount: parsed.amount,
           merchantName: parsed.merchantName,
           category: parsed.category,
           type: parsed.type,
           dateTime: actualDate,
           rawBody: parsed.rawBody,
           senderOrigin: parsed.senderOrigin
        );
        
        final isDup = isDuplicate(correctedParsed, existingEntries);
        pendingList.add(PendingSmsEntry(
          id:           const Uuid().v4(),
          rawSms:       correctedParsed.rawBody,
          amount:       correctedParsed.amount,
          merchant:     correctedParsed.merchantName,
          category:     correctedParsed.category,
          note:         correctedParsed.merchantName,
          date:         actualDate,
          senderOrigin: correctedParsed.senderOrigin,
          isDuplicate:  isDup,
        ));
      }
    }
  } catch (_) {}

  pendingList.sort((a, b) => b.date.compareTo(a.date));
  return pendingList;
}

void startRealTimeListener(
  List<ExpenseEntry> existingEntries,
  bool Function(ParsedTransaction, List<ExpenseEntry>) isDuplicate,
  Function(PendingSmsEntry)? onNewSmsParsed,
  List<String> discardedSignatures,
) {
  if (!Platform.isAndroid) return;

  _telephony.listenIncomingSms(
    onNewMessage: (tel.SmsMessage message) {
      if (message.body == null || message.address == null) return;

      final parsed = SmsParser.parse(message.body!, message.address!);
      if (parsed != null && onNewSmsParsed != null) {
        
        final actualDate = message.date != null ? DateTime.fromMillisecondsSinceEpoch(message.date!) : DateTime.now();
        final signature = '${parsed.rawBody.hashCode}_${actualDate.millisecondsSinceEpoch}';
        if (discardedSignatures.contains(signature)) return;
        
        final correctedParsed = ParsedTransaction(
           amount: parsed.amount,
           merchantName: parsed.merchantName,
           category: parsed.category,
           type: parsed.type,
           dateTime: actualDate,
           rawBody: parsed.rawBody,
           senderOrigin: parsed.senderOrigin
        );

        final isDup = isDuplicate(correctedParsed, existingEntries);
        final entry = PendingSmsEntry(
          id:           const Uuid().v4(),
          rawSms:       correctedParsed.rawBody,
          amount:       correctedParsed.amount,
          merchant:     correctedParsed.merchantName,
          category:     correctedParsed.category,
          note:         correctedParsed.merchantName,
          date:         actualDate,
          senderOrigin: correctedParsed.senderOrigin,
          isDuplicate:  isDup,
        );
        onNewSmsParsed(entry);
      }
    },
    listenInBackground: false,
  );
}

void stopRealTimeListener() {
  // Telephony doesn't have an explicit stop — nulling the callback is enough.
}
