import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';

class ScoreGauge extends StatelessWidget {
  const ScoreGauge({
    super.key,
    required this.score,
    required this.bandColor,
    required this.bandLabel,
  });

  final int score;
  final Color bandColor;
  final String bandLabel;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 300, end: score.toDouble()),
      duration: const Duration(milliseconds: 800),
      curve: Curves.easeOut,
      builder: (context, animatedScore, child) {
        return CustomPaint(
          size: const Size(double.infinity, 160),
          painter: _GaugePainter(
            score: animatedScore,
            bandColor: bandColor,
          ),
          child: SizedBox(
            height: 160,
            width: double.infinity,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Text(
                  animatedScore.toInt().toString(),
                  style: AppText.heading1.copyWith(
                    fontSize: 48,
                    fontWeight: FontWeight.w800,
                    color: bandColor,
                    height: 1.0,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: bandColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    bandLabel.toUpperCase(),
                    style: AppText.label.copyWith(
                      color: bandColor,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.2,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _GaugePainter extends CustomPainter {
  _GaugePainter({required this.score, required this.bandColor});

  final double score;
  final Color bandColor;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height);
    final radius = math.min(size.width / 2, size.height) - 16;
    
    final trackPaint = Paint()
      ..color = AppColors.border
      ..style = PaintingStyle.stroke
      ..strokeWidth = 16
      ..strokeCap = StrokeCap.round;

    final progressPaint = Paint()
      ..color = bandColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 16
      ..strokeCap = StrokeCap.round;

    // Draw background track (half circle)
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      math.pi, // start angle (left)
      math.pi, // sweep angle (180 degrees)
      false,
      trackPaint,
    );

    // Calculate progress angle (score range 300 - 900)
    final clampedScore = score.clamp(300, 900);
    final progressRatio = (clampedScore - 300) / 600;
    final sweepAngle = math.pi * progressRatio;

    // Draw active progress
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      math.pi,
      sweepAngle,
      false,
      progressPaint,
    );

    // Draw needle dot at the end of progress
    final needleAngle = math.pi + sweepAngle;
    final needleX = center.dx + radius * math.cos(needleAngle);
    final needleY = center.dy + radius * math.sin(needleAngle);

    final dotPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;
      
    final dotShadowPaint = Paint()
      ..color = bandColor.withValues(alpha: 0.4)
      ..style = PaintingStyle.fill
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);

    canvas.drawCircle(Offset(needleX, needleY), 12, dotShadowPaint);
    canvas.drawCircle(Offset(needleX, needleY), 10, dotPaint);
    
    final dotInner = Paint()..color = bandColor;
    canvas.drawCircle(Offset(needleX, needleY), 4, dotInner);
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) {
    return oldDelegate.score != score || oldDelegate.bandColor != bandColor;
  }
}
