// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'expense_entry.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class ExpenseEntryAdapter extends TypeAdapter<ExpenseEntry> {
  @override
  final int typeId = 1;

  @override
  ExpenseEntry read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return ExpenseEntry(
      id: fields[0] as String,
      amount: fields[1] as double,
      category: fields[2] as String,
      note: fields[3] as String,
      timestamp: fields[4] as DateTime,
      source: fields[5] as String,
    );
  }

  @override
  void write(BinaryWriter writer, ExpenseEntry obj) {
    writer
      ..writeByte(6)
      ..writeByte(0)
      ..write(obj.id)
      ..writeByte(1)
      ..write(obj.amount)
      ..writeByte(2)
      ..write(obj.category)
      ..writeByte(3)
      ..write(obj.note)
      ..writeByte(4)
      ..write(obj.timestamp)
      ..writeByte(5)
      ..write(obj.source);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ExpenseEntryAdapter &&
          runtimeType == other.runtimeType &&
          typeId == other.typeId;
}
