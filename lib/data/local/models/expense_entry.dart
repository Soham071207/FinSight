import 'package:hive/hive.dart';

part 'expense_entry.g.dart';

@HiveType(typeId: 1)
class ExpenseEntry extends HiveObject {
  @HiveField(0)
  String id;

  @HiveField(1)
  double amount;

  @HiveField(2)
  String category;

  @HiveField(3)
  String note;

  @HiveField(4)
  DateTime timestamp;

  @HiveField(5)
  String source;

  ExpenseEntry({
    required this.id,
    required this.amount,
    required this.category,
    required this.note,
    required this.timestamp,
    required this.source,
  });

  ExpenseEntry copyWith({
    String? id,
    double? amount,
    String? category,
    String? note,
    DateTime? timestamp,
    String? source,
  }) {
    return ExpenseEntry(
      id: id ?? this.id,
      amount: amount ?? this.amount,
      category: category ?? this.category,
      note: note ?? this.note,
      timestamp: timestamp ?? this.timestamp,
      source: source ?? this.source,
    );
  }
}
