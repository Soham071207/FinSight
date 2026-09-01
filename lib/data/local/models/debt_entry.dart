// lib/data/local/models/debt_entry.dart

import 'package:hive/hive.dart';

part 'debt_entry.g.dart';

@HiveType(typeId: 5)
class DebtEntry extends HiveObject {
  @HiveField(0)
  String id;

  @HiveField(1)
  String friendName;

  @HiveField(2)
  double amount;

  @HiveField(3)
  String note;

  /// 'owe'  = I owe this friend money
  /// 'owed' = This friend owes me money
  @HiveField(4)
  String direction;

  @HiveField(5)
  bool isPaid;

  @HiveField(6)
  DateTime createdAt;

  DebtEntry({
    required this.id,
    required this.friendName,
    required this.amount,
    required this.note,
    required this.direction,
    required this.isPaid,
    required this.createdAt,
  });

  DebtEntry copyWith({
    String? id,
    String? friendName,
    double? amount,
    String? note,
    String? direction,
    bool? isPaid,
    DateTime? createdAt,
  }) {
    return DebtEntry(
      id:         id ?? this.id,
      friendName: friendName ?? this.friendName,
      amount:     amount ?? this.amount,
      note:       note ?? this.note,
      direction:  direction ?? this.direction,
      isPaid:     isPaid ?? this.isPaid,
      createdAt:  createdAt ?? this.createdAt,
    );
  }
}
