import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../data/local/models/expense_entry.dart';
import 'expense_list_tile.dart'; // For CategoryStyle

class DailyBarChart extends StatelessWidget {
  const DailyBarChart({
    super.key,
    required this.entries,
    required this.month,
  });

  final List<ExpenseEntry> entries;
  final DateTime month;

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return const SizedBox(
        height: 250,
        child: Center(child: Text('No daily data available.')),
      );
    }

    // Prepare data: aggregate by day and find dominant category
    final int daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final Map<int, _DailySummary> dailyMap = {};

    for (int d = 1; d <= daysInMonth; d++) {
      dailyMap[d] = _DailySummary(day: d);
    }

    for (final e in entries) {
      if (e.timestamp.year == month.year && e.timestamp.month == month.month) {
        final day = e.timestamp.day;
        dailyMap[day]!.total += e.amount;
        dailyMap[day]!.categorySums[e.category] =
            (dailyMap[day]!.categorySums[e.category] ?? 0) + e.amount;
      }
    }

    // Determine colors
    for (final summary in dailyMap.values) {
      if (summary.categorySums.isNotEmpty) {
        String topCat = '';
        double maxAmt = -1;
        for (final entry in summary.categorySums.entries) {
          if (entry.value > maxAmt) {
            maxAmt = entry.value;
            topCat = entry.key;
          }
        }
        summary.topCategory = topCat;
        summary.color = CategoryStyle.getColor(topCat);
      } else {
        summary.color = AppColors.border;
      }
    }

    final dataList = dailyMap.values.toList()..sort((a, b) => a.day.compareTo(b.day));

    return SfCartesianChart(
      plotAreaBorderWidth: 0,
      primaryXAxis: NumericAxis(
        minimum: 1,
        maximum: daysInMonth.toDouble(),
        interval: 5,
        majorGridLines: const MajorGridLines(width: 0),
        axisLine: const AxisLine(width: 0),
      ),
      primaryYAxis: NumericAxis(
        numberFormat: NumberFormat.compactCurrency(symbol: '₹', locale: 'en_IN'),
        axisLine: const AxisLine(width: 0),
        majorTickLines: const MajorTickLines(size: 0),
        majorGridLines: MajorGridLines(
          width: 1,
          color: AppColors.border,
          dashArray: <double>[5, 5],
        ),
      ),
      zoomPanBehavior: ZoomPanBehavior(
        enablePinching: true,
        enablePanning: true,
      ),
      crosshairBehavior: CrosshairBehavior(
        enable: true,
        activationMode: ActivationMode.singleTap,
        lineType: CrosshairLineType.vertical,
      ),
      tooltipBehavior: TooltipBehavior(
        enable: true,
        builder: (dynamic data, dynamic point, dynamic series, int pointIndex, int seriesIndex) {
          final s = data as _DailySummary;
          return Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              boxShadow: [
                BoxShadow(color: Colors.black.withValues(alpha: 0.1), blurRadius: 4),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${s.day} ${DateFormat('MMM').format(month)}',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                const SizedBox(height: 4),
                Text('Total: ${formatINRCompact(s.total)}',
                    style: const TextStyle(fontSize: 12)),
                if (s.topCategory.isNotEmpty)
                  Text('Top: ${s.topCategory}',
                      style: TextStyle(color: s.color, fontSize: 12, fontWeight: FontWeight.w600)),
              ],
            ),
          );
        },
      ),
      series: <CartesianSeries<_DailySummary, num>>[
        ColumnSeries<_DailySummary, num>(
          dataSource: dataList,
          xValueMapper: (_DailySummary s, _) => s.day,
          yValueMapper: (_DailySummary s, _) => s.total,
          pointColorMapper: (_DailySummary s, _) => s.color,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
        ),
      ],
    );
  }
}

class _DailySummary {
  _DailySummary({required this.day});
  final int day;
  double total = 0;
  Map<String, double> categorySums = {};
  String topCategory = '';
  Color color = Colors.transparent;
}
