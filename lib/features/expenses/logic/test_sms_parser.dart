import 'dart:io';
import 'sms_parser.dart';

void main() {
  final testCases = [
    // Food & Dining
    {'body': 'Rs. 450.00 debited from a/c XXXXXX towards Swiggy on 12-Oct', 'expected': 'Food & Dining'},
    {'body': 'Paid INR 1200 to Zomato via UPI', 'expected': 'Food & Dining'},
    {'body': 'Rs. 300 deducted for Domino Pizza', 'expected': 'Food & Dining'},
    // Shopping
    {'body': 'Rs. 2500 spent on Amazon via Credit Card', 'expected': 'Shopping'},
    {'body': 'Payment of Rs. 1500 to DMart', 'expected': 'Shopping'},
    {'body': 'Rs 899 debited for Flipkart purchase', 'expected': 'Shopping'},
    // Transport
    {'body': 'Rs. 350 debited for OLA Cabs', 'expected': 'Transport'},
    {'body': 'Paid ₹120 to Namma Metro', 'expected': 'Transport'},
    {'body': 'Payment to IRCTC Rs 1200 successful', 'expected': 'Transport'},
    // Utilities
    {'body': 'Electricity bill payment of Rs. 800 to BESCOM successful', 'expected': 'Utilities'},
    {'body': 'Rs 499 Airtel Broadband recharge', 'expected': 'Utilities'},
    {'body': 'Jio recharge of Rs 299 done', 'expected': 'Utilities'},
    // Entertainment
    {'body': 'Rs. 600 debited towards BookMyShow', 'expected': 'Entertainment'},
    {'body': 'Netflix subscription Rs 199 deducted', 'expected': 'Entertainment'},
    // Finance
    {'body': 'Mutual fund SIP of Rs. 5000 debited', 'expected': 'Finance'},
    {'body': 'EMI of Rs 12000 deducted', 'expected': 'Finance'},
    {'body': 'Zerodha funds added Rs 10000', 'expected': 'Finance'},
    // Health
    {'body': 'Rs. 1200 paid to Apollo Pharmacy', 'expected': 'Health'},
    {'body': 'Doctor consultation Rs 500 paid', 'expected': 'Health'},
    // Edge cases / failures
    {'body': 'Paid Rs 100 to unknown store', 'expected': 'Other'},
    {'body': 'Received Rs 500 from Rahul', 'expected': 'Other'},
  ];

  Map<String, int> truePositives = {};
  Map<String, int> falsePositives = {};
  Map<String, int> falseNegatives = {};
  Map<String, int> support = {};

  for (var tc in testCases) {
    final expected = tc['expected'] as String;
    support[expected] = (support[expected] ?? 0) + 1;
    
    final parsed = SmsParser.parse(tc['body'] as String, 'BANK');
    
    if (parsed == null) {
      if (expected != 'Other') {
        falseNegatives[expected] = (falseNegatives[expected] ?? 0) + 1;
      }
      continue;
    }
    
    if (parsed.category == expected) {
      truePositives[expected] = (truePositives[expected] ?? 0) + 1;
    } else {
      falsePositives[parsed.category] = (falsePositives[parsed.category] ?? 0) + 1;
      falseNegatives[expected] = (falseNegatives[expected] ?? 0) + 1;
    }
  }

  print("====================================================================");
  print("Table IV: Transaction Classification Performance");
  print("====================================================================");
  print("| Category              | Prec (%) | Rec (%) | F1 (%) |");
  print("--------------------------------------------------------------------");
  
  double totalF1 = 0;
  int count = 0;
  
  for (var cat in support.keys) {
    if (cat == 'Other') continue;
    int tp = truePositives[cat] ?? 0;
    int fp = falsePositives[cat] ?? 0;
    int fn = falseNegatives[cat] ?? 0;
    
    double prec = (tp + fp) == 0 ? 0 : tp / (tp + fp) * 100;
    double rec = (tp + fn) == 0 ? 0 : tp / (tp + fn) * 100;
    double f1 = (prec + rec) == 0 ? 0 : 2 * (prec * rec) / (prec + rec);
    
    totalF1 += f1;
    count++;
    
    print("| ${cat.padRight(21)} | ${prec.toStringAsFixed(1).padLeft(8)} | ${rec.toStringAsFixed(1).padLeft(7)} | ${f1.toStringAsFixed(1).padLeft(6)} |");
  }
  
  double macroF1 = count == 0 ? 0 : totalF1 / count;
  print("--------------------------------------------------------------------");
  print("| Macro Average         |          |         | ${macroF1.toStringAsFixed(1).padLeft(6)} |");
  print("====================================================================");
}
