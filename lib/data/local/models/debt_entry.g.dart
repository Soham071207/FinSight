// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'debt_entry.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class DebtEntryAdapter extends TypeAdapter<DebtEntry> {
  @override
  final int typeId = 5;

  @override
  DebtEntry read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return DebtEntry(
      id:         fields[0] as String,
      friendName: fields[1] as String,
      amount:     fields[2] as double,
      note:       fields[3] as String,
      direction:  fields[4] as String,
      isPaid:     fields[5] as bool,
      createdAt:  fields[6] as DateTime,
    );
  }

  @override
  void write(BinaryWriter writer, DebtEntry obj) {
    writer
      ..writeByte(7)
      ..writeByte(0)
      ..write(obj.id)
      ..writeByte(1)
      ..write(obj.friendName)
      ..writeByte(2)
      ..write(obj.amount)
      ..writeByte(3)
      ..write(obj.note)
      ..writeByte(4)
      ..write(obj.direction)
      ..writeByte(5)
      ..write(obj.isPaid)
      ..writeByte(6)
      ..write(obj.createdAt);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DebtEntryAdapter &&
          runtimeType == other.runtimeType &&
          typeId == other.typeId;
}
