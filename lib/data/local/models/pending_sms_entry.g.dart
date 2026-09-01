// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'pending_sms_entry.dart';

// **************************************************************************
// TypeAdapterGenerator
// **************************************************************************

class PendingSmsEntryAdapter extends TypeAdapter<PendingSmsEntry> {
  @override
  final int typeId = 2;

  @override
  PendingSmsEntry read(BinaryReader reader) {
    final numOfFields = reader.readByte();
    final fields = <int, dynamic>{
      for (int i = 0; i < numOfFields; i++) reader.readByte(): reader.read(),
    };
    return PendingSmsEntry(
      id: fields[0] as String,
      rawSms: fields[1] as String,
      amount: fields[2] as double,
      merchant: fields[3] as String,
      category: fields[4] as String,
      note: fields[5] as String,
      date: fields[6] as DateTime,
      senderOrigin: fields[7] as String,
      isDuplicate: fields[8] as bool,
    );
  }

  @override
  void write(BinaryWriter writer, PendingSmsEntry obj) {
    writer
      ..writeByte(9)
      ..writeByte(0)
      ..write(obj.id)
      ..writeByte(1)
      ..write(obj.rawSms)
      ..writeByte(2)
      ..write(obj.amount)
      ..writeByte(3)
      ..write(obj.merchant)
      ..writeByte(4)
      ..write(obj.category)
      ..writeByte(5)
      ..write(obj.note)
      ..writeByte(6)
      ..write(obj.date)
      ..writeByte(7)
      ..write(obj.senderOrigin)
      ..writeByte(8)
      ..write(obj.isDuplicate);
  }

  @override
  int get hashCode => typeId.hashCode;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is PendingSmsEntryAdapter &&
          runtimeType == other.runtimeType &&
          typeId == other.typeId;
}
