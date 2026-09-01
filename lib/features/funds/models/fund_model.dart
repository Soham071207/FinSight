class FundModel {
  const FundModel({
    required this.id,
    required this.name,
    required this.category,
    required this.subcategory,
    required this.cagr3Y,
    required this.cagr5Y,
    required this.riskRating,
    required this.nav,
    required this.aumCr,
    required this.fundHouse,
    required this.score,
  });

  final String id;
  final String name;
  final String category;
  final String subcategory;
  final double cagr3Y;
  final double cagr5Y;
  final int riskRating;
  final double nav;
  final double aumCr;
  final String fundHouse;
  final int score;

  factory FundModel.fromJson(Map<String, dynamic> json) {
    return FundModel(
      id: json['id'].toString(),
      name: json['name'].toString(),
      category: json['category'].toString(),
      subcategory: json['subcategory'].toString(),
      cagr3Y: (json['cagr_3y'] as num).toDouble(),
      cagr5Y: (json['cagr_5y'] as num).toDouble(),
      riskRating: (json['risk_rating'] as num).toInt(),
      nav: (json['nav'] as num).toDouble(),
      aumCr: (json['aum_cr'] as num).toDouble(),
      fundHouse: json['fund_house'].toString(),
      score: (json['score'] as num).toInt(),
    );
  }
}
