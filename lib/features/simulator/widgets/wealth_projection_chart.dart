import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import '../../../core/theme/app_colors.dart';
import '../logic/sip_calculator.dart';

class WealthProjectionChart extends StatelessWidget {
  const WealthProjectionChart({
    super.key,
    required this.projections,
  });

  final List<YearlyProjection> projections;

  @override
  Widget build(BuildContext context) {
    return SfCartesianChart(
      plotAreaBorderWidth: 0,
      primaryXAxis: NumericAxis(
        title: AxisTitle(
          text: 'Years',
          textStyle: TextStyle(fontSize: 12, color: AppColors.textSecondary),
        ),
        majorGridLines: MajorGridLines(width: 0),
        edgeLabelPlacement: EdgeLabelPlacement.shift,
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
        lineColor: AppColors.textPrimary,
      ),
      tooltipBehavior: TooltipBehavior(
        enable: true,
        shared: true,
        color: Colors.white,
        textStyle: TextStyle(color: AppColors.textPrimary),
        elevation: 4,
        canShowMarker: true,
        header: 'Year',
      ),
      legend: const Legend(
        isVisible: true,
        position: LegendPosition.bottom,
      ),
      series: <CartesianSeries<YearlyProjection, num>>[
        // Drawn first so it acts as background
        AreaSeries<YearlyProjection, num>(
          name: 'Corpus',
          dataSource: projections,
          xValueMapper: (YearlyProjection p, _) => p.year,
          yValueMapper: (YearlyProjection p, _) => p.corpusValue,
          color: AppColors.accent.withValues(alpha: 0.15),
          borderColor: AppColors.accent,
          borderWidth: 2,
        ),
        // Drawn on top
        AreaSeries<YearlyProjection, num>(
          name: 'Invested',
          dataSource: projections,
          xValueMapper: (YearlyProjection p, _) => p.year,
          yValueMapper: (YearlyProjection p, _) => p.investedCumulative,
          color: AppColors.primary.withValues(alpha: 0.15),
          borderColor: AppColors.primary,
          borderWidth: 2,
        ),
      ],
    );
  }
}
