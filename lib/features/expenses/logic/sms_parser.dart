enum TransactionType { debit, credit }

class ParsedTransaction {
  final double amount;
  final String merchantName;
  final String category;
  final TransactionType type;
  final DateTime? dateTime;
  final String rawBody;
  final String senderOrigin;

  ParsedTransaction({
    required this.amount,
    required this.merchantName,
    required this.category,
    required this.type,
    this.dateTime,
    required this.rawBody,
    this.senderOrigin = '',
  });
}

class SmsParser {
  static ParsedTransaction? parse(String body, String sender) {
    if (body.trim().isEmpty) return null;

    try {
      final lowerBody = body.toLowerCase();
      
      // 1. Transaction Type
      TransactionType? type;
      
      // Strong debit indicators
      if (RegExp(r'\b(debited|spent|withdrawn|paid|sent|deducted)\b').hasMatch(lowerBody) ||
          RegExp(r'\b(?:dr|dr\.|debit)\b').hasMatch(lowerBody) ||
          RegExp(r'(?:payment of|purchase of)').hasMatch(lowerBody)) {
        type = TransactionType.debit;
      } 
      // Strong credit indicators (Ignored as requested)
      else if (RegExp(r'\b(credited|received|added|refunded|deposited)\b').hasMatch(lowerBody) ||
               RegExp(r'\b(?:cr|cr\.|credit)\b').hasMatch(lowerBody) ||
               RegExp(r'(?:refund of|salary of)').hasMatch(lowerBody)) {
        return null; // Ignore credited messages completely
      } else {
        return null; // Not a recognized transactional SMS
      }

      // 2. Amount Extraction
      double? amount;
      final amountPatterns = [
        RegExp(r'(?:rs\.?|inr|₹)\s*:?\s*([\d,]+\.?\d{0,2})', caseSensitive: false),
        RegExp(r'(?:rs\.?|inr|₹)\s*-\s*([\d,]+\.?\d{0,2})', caseSensitive: false), // INR - 500
        RegExp(r'([\d,]+\.?\d{0,2})\s*(?:rs\.?|inr|₹)', caseSensitive: false),
      ];

      for (var pattern in amountPatterns) {
        final match = pattern.firstMatch(lowerBody);
        if (match != null && match.groupCount >= 1) {
          final amtStr = match.group(1)!.replaceAll(',', '');
          amount = double.tryParse(amtStr);
          if (amount != null) break;
        }
      }

      if (amount == null || amount <= 0 || amount > 10000000) return null;

      // 3. Merchant / Payee Extraction
      String merchant = '';
      final merchantPatterns = [
        RegExp(r'fvg\s*:?\s*([a-zA-Z0-9\s]+?)\s+(?:avl|bal|ref|on|via)', caseSensitive: false), // Fvg: XXX Avl
        RegExp(r'vpa\s+([a-zA-Z0-9.\-_@]+)', caseSensitive: false), // VPA xxxx@upi
        RegExp(r'to\s+([a-zA-Z0-9.\-_@]+)\s+ref', caseSensitive: false), // to xxx@upi ref
        RegExp(r'(?:at|info|towards|to)\s+([a-zA-Z0-9\s&*#\-_\.]+?)\s+(?:on|via|ref|txn|a\/c|card)', caseSensitive: false),
        RegExp(r'merchant\s*:\s*([a-zA-Z0-9\s&*#\-_\.]+?)(?:\.|$)', caseSensitive: false), // Merchant: XXX
      ];

      for (var pattern in merchantPatterns) {
        final match = pattern.firstMatch(lowerBody);
        if (match != null && match.groupCount >= 1) {
          merchant = match.group(1)!.trim();
          if (merchant.isNotEmpty) break;
        }
      }

      // Fallback merchant logic
      if (merchant.isEmpty) {
        // Check if there is an uppercase sender code e.g., AD-HDFCBK
        final senderMatch = RegExp(r'[A-Z]{2}-([A-Z0-9]+)').firstMatch(sender);
        if (senderMatch != null) {
          merchant = senderMatch.group(1)!;
        } else {
          merchant = sender;
        }
      }
      
      // Cleanup merchant name
      merchant = merchant.toUpperCase();
      merchant = merchant.replaceAll(RegExp(r'^(?:UPI|VPA|INFO|AT|TO|TOWARDS)\s+'), '');
      if (merchant.length > 25) merchant = merchant.substring(0, 25);
      if (merchant == 'DEBIT' || merchant == 'CREDIT' || merchant.contains('A/C')) {
        merchant = 'Unknown Merchant';
      }

      // 4. Category Inference
      String category = 'Other';
      final fullText = '$lowerBody ${merchant.toLowerCase()}';
      
      if (RegExp(r'(swiggy|zomato|blinkit|zepto|domino|pizza|kfc|mcdonalds|food|cafe|restaurant|hotel|baker)').hasMatch(fullText)) {
        category = 'Food & Dining';
      } else if (RegExp(r'(amazon|flipkart|myntra|ajio|meesho|dmart|reliance|smart|mart|store|supermarket|mall)').hasMatch(fullText)) {
        category = 'Shopping';
      } else if (RegExp(r'(ola|uber|rapido|namma|metro|irctc|train|flight|makemytrip|petrol|fuel|indian oil|bharat petroleum|hpcl|toll|fastag)').hasMatch(fullText)) {
        category = 'Transport';
      } else if (RegExp(r'(electricity|bescom|water|gas|broadband|airtel|jio|vi|recharge|bill|utility)').hasMatch(fullText)) {
        category = 'Utilities';
      } else if (RegExp(r'(hospital|pharmacy|apollo|medplus|netmeds|1mg|doctor|clinic)').hasMatch(fullText)) {
        category = 'Health';
      } else if (RegExp(r'(netflix|prime|hotstar|spotify|bookmyshow|pvr|inox|movie|theatre)').hasMatch(fullText)) {
        category = 'Entertainment';
      } else if (RegExp(r'(school|college|university|tuition|udemy|coursera|fee)').hasMatch(fullText)) {
        category = 'Education';
      } else if (RegExp(r'(emi|loan|mutual fund|sip|zerodha|groww|upstox|insurance|lic|premium)').hasMatch(fullText)) {
        category = 'Finance';
      } else if (RegExp(r'(atm|cash withdrawal)').hasMatch(fullText)) {
        category = 'ATM';
      } else if (RegExp(r'(upi|neft|imps|rtgs|transfer|sent to)').hasMatch(fullText)) {
        category = 'Transfers';
      }

      // 5. Date Extraction (fallback to current time since SMS received timestamp is usually better)
      // Since the actual SMS metadata contains the precise date it was received, we just return DateTime.now() 
      // if we can't parse it. In the service, we overwrite this with the actual SMS received timestamp.
      DateTime dateTime = DateTime.now();

      return ParsedTransaction(
        amount: amount,
        merchantName: merchant,
        category: category,
        type: type,
        dateTime: dateTime,
        rawBody: body,
        senderOrigin: sender,
      );
    } catch (e) {
      return null;
    }
  }
}
