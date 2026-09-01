import 'package:hive/hive.dart';

part 'pending_sms_entry.g.dart';

@HiveType(typeId: 2)
class PendingSmsEntry extends HiveObject {
  PendingSmsEntry({
    required this.id,
    required this.rawSms,
    required this.amount,
    required this.merchant,
    required this.category,
    required this.note,
    required this.date,
    required this.senderOrigin,
    this.isDuplicate = false,
  });

  @HiveField(0)
  final String id;

  @HiveField(1)
  final String rawSms;

  @HiveField(2)
  final double amount;

  @HiveField(3)
  final String merchant;

  @HiveField(4)
  final String category;

  @HiveField(5)
  final String note;

  @HiveField(6)
  final DateTime date;

  @HiveField(7)
  final String senderOrigin;

  @HiveField(8)
  bool isDuplicate;

  /// A deterministic signature to identify this exact SMS (used for ignoring discarded SMS)
  String get signature => '${rawSms.hashCode}_${date.millisecondsSinceEpoch}';
}
