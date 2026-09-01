import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../../core/theme/app_colors.dart';

/// Reusable shimmer skeleton placeholder for loading states.
///
/// Use this instead of spinners or blank screens while data is loading.
/// Every screen must render shimmer skeletons in its loading state.
///
/// Basic usage:
///   ShimmerBox(width: double.infinity, height: 80)
///   ShimmerBox(width: 120, height: 16, borderRadius: 8)
///
/// Pre-built skeleton layouts:
///   ShimmerLoader.card()        — full summary card skeleton
///   ShimmerLoader.listTile()    — list row skeleton (icon + 2 lines)
///   ShimmerLoader.text(width)   — single text line skeleton
///   ShimmerLoader.chart(height) — chart area skeleton
class ShimmerBox extends StatelessWidget {
  const ShimmerBox({
    super.key,
    required this.width,
    required this.height,
    this.borderRadius = 8.0,
  });

  final double width;
  final double height;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: AppColors.border,
      highlightColor: AppColors.surface,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppColors.border,
          borderRadius: BorderRadius.circular(borderRadius),
        ),
      ),
    );
  }
}

/// Collection of pre-built shimmer skeleton layouts used across screens.
///
/// These are purely presentational — drop them in wherever the real
/// widget will appear while data is loading.
class ShimmerLoader extends StatelessWidget {
  const ShimmerLoader._({super.key, required this.child});

  final Widget child;

  // ── Pre-built layouts ─────────────────────────────────────────────────────

  /// Summary card skeleton — matches the home dashboard summary cards.
  factory ShimmerLoader.card({Key? key}) => ShimmerLoader._(
        key: key,
        child: Container(
          width: 160,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              ShimmerBox(width: 32, height: 32, borderRadius: 8),
              SizedBox(height: 12),
              ShimmerBox(width: 80, height: 10, borderRadius: 5),
              SizedBox(height: 8),
              ShimmerBox(width: 100, height: 20, borderRadius: 5),
              SizedBox(height: 6),
              ShimmerBox(width: 60, height: 10, borderRadius: 5),
            ],
          ),
        ),
      );

  /// List tile skeleton — icon circle + two text lines.
  factory ShimmerLoader.listTile({Key? key}) => ShimmerLoader._(
        key: key,
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            children: [
              ShimmerBox(width: 44, height: 44, borderRadius: 22),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ShimmerBox(width: double.infinity, height: 14, borderRadius: 6),
                    SizedBox(height: 8),
                    ShimmerBox(width: 120, height: 11, borderRadius: 5),
                  ],
                ),
              ),
              SizedBox(width: 12),
              ShimmerBox(width: 56, height: 18, borderRadius: 9),
            ],
          ),
        ),
      );

  /// Single text line skeleton. Pass [width] to match the text it replaces.
  factory ShimmerLoader.text({Key? key, double width = 140, double height = 14}) =>
      ShimmerLoader._(
        key: key,
        child: ShimmerBox(width: width, height: height, borderRadius: 6),
      );

  /// Chart area skeleton — blank rounded rectangle at [height].
  factory ShimmerLoader.chart({Key? key, double height = 200}) => ShimmerLoader._(
        key: key,
        child: Container(
          width: double.infinity,
          height: height,
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Shimmer.fromColors(
            baseColor: AppColors.border,
            highlightColor: AppColors.surface,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: List.generate(
                      7,
                      (i) => Container(
                        width: 24,
                        height: (i % 3 + 1) * (height / 5),
                        decoration: BoxDecoration(
                          color: AppColors.border,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );

  /// Full-screen list shimmer — renders [count] list tile skeletons.
  ///
  /// Example: ShimmerLoader.list(count: 6)
  static Widget list({int count = 5}) => ListView.separated(
        physics: const NeverScrollableScrollPhysics(),
        shrinkWrap: true,
        itemCount: count,
        separatorBuilder: (_, __) => Divider(
          height: 1,
          color: AppColors.border,
          indent: 72,
        ),
        itemBuilder: (_, __) => ShimmerLoader.listTile(),
      );

  @override
  Widget build(BuildContext context) => child;
}
