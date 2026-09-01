import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import 'expense_list_tile.dart'; // For CategoryStyle

class CategoryDonutChart extends StatefulWidget {
  const CategoryDonutChart({
    super.key,
    required this.categoryTotals,
    required this.totalSpend,
  });

  final Map<String, double> categoryTotals;
  final double totalSpend;

  @override
  State<CategoryDonutChart> createState() => _CategoryDonutChartState();
}

class _CategoryDonutChartState extends State<CategoryDonutChart> {
  int _touchedIndex = -1;

  @override
  Widget build(BuildContext context) {
    if (widget.categoryTotals.isEmpty || widget.totalSpend == 0) {
      return SizedBox(
        height: 250,
        child: Center(
          child: Text('No expenses to display.', style: AppText.bodySecondary),
        ),
      );
    }

    final entries = widget.categoryTotals.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    String centerLabelTitle = 'Total Spend';
    double targetValue = widget.totalSpend;

    if (_touchedIndex != -1 && _touchedIndex < entries.length) {
      centerLabelTitle = entries[_touchedIndex].key;
      targetValue = entries[_touchedIndex].value;
    }

    return Column(
      children: [
        // ── Chart ──────────────────────────────────────────────────────────
        SizedBox(
          height: 220,
          child: Stack(
            children: [
              PieChart(
                PieChartData(
                  pieTouchData: PieTouchData(
                    touchCallback: (FlTouchEvent event, pieTouchResponse) {
                      setState(() {
                        if (!event.isInterestedForInteractions ||
                            pieTouchResponse == null ||
                            pieTouchResponse.touchedSection == null) {
                          _touchedIndex = -1;
                          return;
                        }
                        _touchedIndex = pieTouchResponse.touchedSection!.touchedSectionIndex;
                      });
                    },
                  ),
                  borderData: FlBorderData(show: false),
                  sectionsSpace: 2,
                  centerSpaceRadius: 75,
                  sections: List.generate(entries.length, (i) {
                    final entry = entries[i];
                    final isTouched = i == _touchedIndex;
                    final color = CategoryStyle.getColor(entry.key);
                    final radius = isTouched ? 24.0 : 18.0;

                    return PieChartSectionData(
                      color: color,
                      value: entry.value,
                      title: '',
                      radius: radius,
                    );
                  }),
                ),
              ),
              // Center Label
              Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(centerLabelTitle, style: AppText.caption),
                    const SizedBox(height: 2),
                    TweenAnimationBuilder<double>(
                      tween: Tween<double>(begin: 0, end: targetValue),
                      duration: const Duration(milliseconds: 800),
                      curve: Curves.easeOut,
                      builder: (context, val, child) {
                        return Text(
                          formatINRCompact(val),
                          style: AppText.heading2.copyWith(fontWeight: FontWeight.w800),
                        );
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        
        // ── Legend ─────────────────────────────────────────────────────────
        Wrap(
          spacing: 16,
          runSpacing: 12,
          alignment: WrapAlignment.center,
          children: entries.map((entry) {
            final color = CategoryStyle.getColor(entry.key);
            final pct = ((entry.value / widget.totalSpend) * 100).toStringAsFixed(1);
            
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(entry.key, style: AppText.caption.copyWith(fontWeight: FontWeight.w600)),
                    Text(
                      '${formatINRCompact(entry.value)} ($pct%)',
                      style: AppText.caption.copyWith(fontSize: 10),
                    ),
                  ],
                ),
              ],
            );
          }).toList(),
        ),
      ],
    );
  }
}
