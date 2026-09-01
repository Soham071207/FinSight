import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shimmer/shimmer.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../models/fund_model.dart';
import '../widgets/fund_card.dart';

import '../../../shared/widgets/empty_state_widget.dart';
import '../../../shared/widgets/error_state_widget.dart';
import 'live_fund_dashboard_screen.dart';
import 'pro_analysis_screen.dart';


// ══════════════════════════════════════════════════════════════════════════════
// PROVIDERS
// ══════════════════════════════════════════════════════════════════════════════

final fundsProvider = FutureProvider<List<FundModel>>((ref) async {
  // Simulate network delay for shimmer effect demonstration
  await Future.delayed(const Duration(milliseconds: 800));
  final String response = await rootBundle.loadString('assets/data/funds_snapshot.json');
  final data = await json.decode(response) as List<dynamic>;
  return data.map((e) => FundModel.fromJson(e as Map<String, dynamic>)).toList();
});

class FundFilterState {
  const FundFilterState({
    this.searchQuery = '',
    this.category = 'All',
    this.sort = 'Score',
  });
  
  final String searchQuery;
  final String category;
  final String sort;

  FundFilterState copyWith({String? searchQuery, String? category, String? sort}) {
    return FundFilterState(
      searchQuery: searchQuery ?? this.searchQuery,
      category: category ?? this.category,
      sort: sort ?? this.sort,
    );
  }
}

final fundFilterProvider = StateProvider<FundFilterState>((ref) => const FundFilterState());

final filteredFundsProvider = Provider<List<FundModel>>((ref) {
  final fundsAsync = ref.watch(fundsProvider);
  final filter = ref.watch(fundFilterProvider);

  return fundsAsync.maybeWhen(
    data: (funds) {
      // 1. Filter by category
      var list = funds.where((f) {
        if (filter.category != 'All' && f.category != filter.category) return false;
        return true;
      }).toList();

      // 2. Filter by search query
      if (filter.searchQuery.isNotEmpty) {
        final query = filter.searchQuery.toLowerCase();
        list = list.where((f) => 
          f.name.toLowerCase().contains(query) || 
          f.fundHouse.toLowerCase().contains(query)
        ).toList();
      }

      // 3. Sort
      list.sort((a, b) {
        switch (filter.sort) {
          case '3Y CAGR':
            return b.cagr3Y.compareTo(a.cagr3Y);
          case '5Y CAGR':
            return b.cagr5Y.compareTo(a.cagr5Y);
          case 'Risk Rating':
            return a.riskRating.compareTo(b.riskRating); // Lower risk is better
          case 'AUM':
            return b.aumCr.compareTo(a.aumCr);
          case 'Score':
          default:
            return b.score.compareTo(a.score);
        }
      });

      return list;
    },
    orElse: () => [],
  );
});

// ══════════════════════════════════════════════════════════════════════════════
// SCREEN
// ══════════════════════════════════════════════════════════════════════════════

class FundListScreen extends ConsumerWidget {
  const FundListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final filter = ref.watch(fundFilterProvider);
    final fundsAsync = ref.watch(fundsProvider);
    final filteredFunds = ref.watch(filteredFundsProvider);

    final categories = ['All', 'Equity', 'Debt', 'Hybrid', 'ELSS', 'International'];
    final sortOptions = ['Score', '3Y CAGR', '5Y CAGR', 'Risk Rating', 'AUM'];

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text('Mutual Funds', style: AppText.heading2),
      ),
      body: Column(
        children: [
          // ── Mode Toggle Banner ─────────────────────────────────────────────
          const _ModeBanner(),

          // ── Search & Filter Header ─────────────────────────────────────────
          Container(
            color: AppColors.surface,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            child: Column(
              children: [
                // Search Bar
                TextField(
                  onChanged: (v) => ref.read(fundFilterProvider.notifier).state = filter.copyWith(searchQuery: v),
                  style: AppText.body,
                  decoration: InputDecoration(
                    hintText: 'Search funds or houses...',
                    hintStyle: AppText.body.copyWith(color: AppColors.textSecondary),
                    prefixIcon: Icon(Icons.search_rounded, color: AppColors.textSecondary),
                    filled: true,
                    fillColor: AppColors.background,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none,
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 0),
                  ),
                ),
                const SizedBox(height: 16),

                // Category Chips
                SizedBox(
                  height: 36,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: categories.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (context, index) {
                      final cat = categories[index];
                      final isSelected = filter.category == cat;
                      return ChoiceChip(
                        label: Text(cat),
                        selected: isSelected,
                        onSelected: (selected) {
                          if (selected) {
                            ref.read(fundFilterProvider.notifier).state = filter.copyWith(category: cat);
                          }
                        },
                        selectedColor: AppColors.primaryLight,
                        backgroundColor: AppColors.background,
                        labelStyle: AppText.caption.copyWith(
                          color: isSelected ? AppColors.primary : AppColors.textPrimary,
                          fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                        ),
                        side: BorderSide(
                          color: isSelected ? AppColors.primary : AppColors.border,
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 16),

                // Sort Dropdown Row
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('${filteredFunds.length} funds found', style: AppText.caption),
                    Row(
                      children: [
                        Text('Sort by: ', style: AppText.caption),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.border),
                          ),
                          child: DropdownButton<String>(
                            value: filter.sort,
                            underline: const SizedBox(),
                            icon: const Icon(Icons.keyboard_arrow_down_rounded, size: 16),
                            style: AppText.caption.copyWith(fontWeight: FontWeight.w600, color: AppColors.primary),
                            items: sortOptions.map((String value) {
                              return DropdownMenuItem<String>(
                                value: value,
                                child: Text(value),
                              );
                            }).toList(),
                            onChanged: (newValue) {
                              if (newValue != null) {
                                ref.read(fundFilterProvider.notifier).state = filter.copyWith(sort: newValue);
                              }
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
          Divider(height: 1, color: AppColors.border),

          // ── List Body ──────────────────────────────────────────────────────
          Expanded(
            child: fundsAsync.when(
              loading: () => _buildShimmerList(),
              error: (err, stack) => ErrorStateWidget(
                message: 'Failed to load mutual funds: $err',
                onRetry: () => ref.refresh(fundsProvider),
              ),
              data: (_) {
                if (filteredFunds.isEmpty) {
                  return EmptyStateWidget(
                    icon: Icons.search_off_rounded,
                    title: 'No funds found',
                    message: 'Try adjusting your search or filters.',
                    ctaText: 'Clear Filters',
                    onCtaPressed: () => ref.read(fundFilterProvider.notifier).state = const FundFilterState(),
                  );
                }
                return ListView.builder(
                  itemCount: filteredFunds.length,
                  itemBuilder: (context, index) {
                    return FundCard(fund: filteredFunds[index]);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildShimmerList() {
    return ListView.builder(
      itemCount: 5,
      itemBuilder: (context, index) {
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            border: Border(bottom: BorderSide(color: AppColors.border)),
          ),
          child: Shimmer.fromColors(
            baseColor: AppColors.border,
            highlightColor: AppColors.background,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  flex: 3,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(height: 14, width: 80, color: Colors.white),
                      const SizedBox(height: 8),
                      Container(height: 18, width: double.infinity, color: Colors.white),
                      const SizedBox(height: 4),
                      Container(height: 14, width: 120, color: Colors.white),
                    ],
                  ),
                ),
                const SizedBox(width: 24),
                Expanded(
                  flex: 1,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(height: 24, width: 60, color: Colors.white),
                      const SizedBox(height: 8),
                      Container(height: 16, width: 80, color: Colors.white),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// MODE BANNER  — switches between Static Snapshot, Pro Analysis & Live Dashboard
// ══════════════════════════════════════════════════════════════════════════════

class _ModeBanner extends StatelessWidget {
  const _ModeBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.primary.withValues(alpha: 0.08),
            AppColors.accent.withValues(alpha: 0.08),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          // Mode 1 — Static Snapshot
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Icon(Icons.grid_view_rounded, size: 20, color: AppColors.primary),
                  const SizedBox(height: 4),
                  Text('Browse Funds', style: AppText.caption.copyWith(
                      fontWeight: FontWeight.w700, color: AppColors.primary)),
                  Text('Snapshot data', style: AppText.caption.copyWith(
                      color: AppColors.textSecondary, fontSize: 10)),
                ],
              ),
            ),
          ),

          // Divider
          Container(width: 1, height: 48, color: AppColors.border),

          // Mode 2 — Live Dashboard (sync_engine.py)
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.zero,
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const LiveFundDashboardScreen(),
              )),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Icon(Icons.sync_rounded, size: 20, color: AppColors.accent),
                    const SizedBox(height: 4),
                    Text('Live Dashboard ✦', style: AppText.caption.copyWith(
                        fontWeight: FontWeight.w700, color: AppColors.accent)),
                    Text('sync_engine data', style: AppText.caption.copyWith(
                        color: AppColors.textSecondary, fontSize: 10)),
                  ],
                ),
              ),
            ),
          ),

          // Divider
          Container(width: 1, height: 48, color: AppColors.border),

          // Mode 3 — Pro Analysis
          Expanded(
            child: InkWell(
              borderRadius: const BorderRadius.horizontal(right: Radius.circular(14)),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => const ProAnalysisScreen(),
              )),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Icon(Icons.analytics_rounded, size: 20, color: AppColors.textSecondary),
                    const SizedBox(height: 4),
                    Text('Pro Analysis ✦', style: AppText.caption.copyWith(
                        fontWeight: FontWeight.w700, color: AppColors.textSecondary)),
                    Text('Live AMFI + yfinance', style: AppText.caption.copyWith(
                        color: AppColors.textSecondary, fontSize: 10)),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

