void main() {
  String sender = '099226 13190';
  String cleanSender = sender.replaceAll(RegExp(r'[^a-zA-Z0-9]'), '').toUpperCase();
  
  List<String> bankSenders = ['9922613190'];
  bool isKnownSender = bankSenders.any((s) {
    String cleanS = s.replaceAll(RegExp(r'[^a-zA-Z0-9]'), '').toUpperCase();
    return cleanSender.contains(cleanS);
  });
  
  print('cleanSender: \$cleanSender');
  print('isKnownSender: \$isKnownSender');
}
