import 'lib/features/expenses/logic/sms_parser.dart';

void main() {
  final testMessages = [
    ("Union Bank of India A/c *6916 Debited Rs:10.00 on 25-05-2026 22:58:53 by Mob Bk ref no 539024949174, Fvg: Soham Bh Avl Bal Rs:85409.83. Not you?Call 18002333/SMS BLOCK 6916 to 8879365472", "UNIONB"),
  ];

  for (var msg in testMessages) {
    final parsed = SmsParser.parse(msg.$1, msg.$2);
    if (parsed != null) {
      print('''
--- SUCCESS ---
Raw: ${msg.$1}
Amount: ${parsed.amount}
Type: ${parsed.type.name}
Merchant: ${parsed.merchantName}
Category: ${parsed.category}
''');
    } else {
      print('''
--- FAILED ---
Raw: ${msg.$1}
''');
    }
  }
}
