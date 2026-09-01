import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
// lib/features/funds/screens/live_fund_dashboard_screen.dart
// Live Mutual Fund Dashboard — powered by sync_engine.py + mutual_2_api.py

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../shared/widgets/empty_state_widget.dart';
import '../../../shared/widgets/error_state_widget.dart';

// ── Data model ────────────────────────────────────────────────────────────────

class LiveFundEntry {
  final String amfiCode;
  final String fundName;
  final String category;
  final double cagr1Y;
  final double cagr3Y;
  final double cagr5Y;
  final int riskScore;
  final double score;

  const LiveFundEntry({
    required this.amfiCode,
    required this.fundName,
    required this.category,
    required this.cagr1Y,
    required this.cagr3Y,
    required this.cagr5Y,
    required this.riskScore,
    required this.score,
  });

  factory LiveFundEntry.fromJson(Map<String, dynamic> j) {
    double d(String k) => (j[k] as num?)?.toDouble() ?? 0.0;
    return LiveFundEntry(
      amfiCode:    j['amfiCode'] as String? ?? '',
      fundName:    j['fundName'] as String? ?? '',
      category:    j['category'] as String? ?? '',
      cagr1Y:      d('cagr1Y'),
      cagr3Y:      d('cagr3Y'),
      cagr5Y:      d('cagr5Y'),
      riskScore:   (j['riskScore'] as num?)?.toInt() ?? 5,
      score:       d('score'),
    );
  }
}

class LiveFundData {
  final String lastSync;
  final List<LiveFundEntry> funds;
  const LiveFundData({required this.lastSync, required this.funds});
}

// ── Provider ──────────────────────────────────────────────────────────────────

final _liveFundDio = Dio(BaseOptions(
  baseUrl: 'https://mutual-funds-api-5vvi.onrender.com',
  connectTimeout: const Duration(seconds: 10),
  receiveTimeout: const Duration(minutes: 1),
));

final liveFundsProvider = FutureProvider<LiveFundData>((ref) async {
  final res = await _liveFundDio.get('/live-funds');
  final data = res.data as Map<String, dynamic>;
  final funds = (data['funds'] as List)
      .map((e) => LiveFundEntry.fromJson(e as Map<String, dynamic>))
      .toList();
  return LiveFundData(
    lastSync: data['lastSync'] as String? ?? 'Unknown',
    funds: funds,
  );
});

// ── Filter/Sort State ─────────────────────────────────────────────────────────

class LiveFundFilter {
  const LiveFundFilter({
    this.category = 'All',
    this.sort = 'Score',
    this.search = '',
  });
  final String category;
  final String sort;
  final String search;

  LiveFundFilter copyWith({String? category, String? sort, String? search}) =>
      LiveFundFilter(
        category: category ?? this.category,
        sort: sort ?? this.sort,
        search: search ?? this.search,
      );
}

final liveFundFilterProvider =
    StateProvider<LiveFundFilter>((ref) => const LiveFundFilter());

// ── Screen ────────────────────────────────────────────────────────────────────

class LiveFundDashboardScreen extends ConsumerWidget {
  final bool hideAppBar;
  const LiveFundDashboardScreen({super.key, this.hideAppBar = false});

  static const _categories = [
    'All', 'Index / Large Cap', 'Mid Cap', 'Small Cap',
    'Flexi Cap', 'ELSS (Tax Saving)', 'Other Equity', 'International',
  ];
  static const _sorts = ['Score', '3Y CAGR', '1Y CAGR', 'Risk Score'];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final async = ref.watch(liveFundsProvider);
    final filter = ref.watch(liveFundFilterProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: hideAppBar ? null : AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Column(
          children: [
            Text('Live Fund Dashboard', style: AppText.heading2),
            Text('sync_engine.py + AMFI + yfinance',
                style:
                    AppText.caption.copyWith(color: AppColors.accent)),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh_rounded,
                color: AppColors.primary),
            tooltip: 'Refresh',
            onPressed: () => ref.refresh(liveFundsProvider),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => ErrorStateWidget(
          message: err.toString().contains('404')
              ? 'Database not found.\n\nRun sync_engine.py first to build\nthe master_funds_database.csv file.'
              : 'Server offline.\n\nStart mutual_2_api.py and try again.',
          onRetry: () => ref.refresh(liveFundsProvider),
        ),
        data: (data) => _buildBody(context, ref, data, filter),
      ),
    );
  }

  Widget _buildBody(BuildContext context, WidgetRef ref,
      LiveFundData data, LiveFundFilter filter) {
    // Apply filter + sort
    var list = data.funds.where((f) {
      if (filter.category != 'All' && f.category != filter.category) {
        return false;
      }
      if (filter.search.isNotEmpty) {
        return f.fundName.toLowerCase().contains(filter.search.toLowerCase()) ||
            f.amfiCode.contains(filter.search);
      }
      return true;
    }).toList();

    list.sort((a, b) {
      switch (filter.sort) {
        case '3Y CAGR':
          return b.cagr3Y.compareTo(a.cagr3Y);
        case '1Y CAGR':
          return b.cagr1Y.compareTo(a.cagr1Y);
        case 'Risk Score':
          return a.riskScore.compareTo(b.riskScore); // Low risk is better
        default:
          return b.score.compareTo(a.score);
      }
    });

    final domestic = data.funds
        .where((f) => f.category != 'International')
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));
    final international = data.funds
        .where((f) => f.category == 'International')
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));

    return CustomScrollView(
      slivers: [
        // ── Sync badge ────────────────────────────────────────────────────
        SliverToBoxAdapter(
          child: _SyncBanner(lastSync: data.lastSync, total: data.funds.length),
        ),

        // ── Top domestic picks ────────────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text('Top Domestic Picks', style: AppText.bodyBold),
          ),
        ),
        SliverToBoxAdapter(
          child: SizedBox(
            height: 148,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: domestic.take(5).length,
              separatorBuilder: (_, __) => const SizedBox(width: 10),
              itemBuilder: (context, i) =>
                  _TopPickCard(fund: domestic[i], rank: i + 1),
            ),
          ),
        ),

        // ── Top international ETFs ────────────────────────────────────────
        if (international.isNotEmpty) ...[
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
              child: Text('Top International ETFs', style: AppText.bodyBold),
            ),
          ),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 148,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: international.take(5).length,
                separatorBuilder: (_, __) => const SizedBox(width: 10),
                itemBuilder: (context, i) =>
                    _TopPickCard(fund: international[i], rank: i + 1, isInternational: true),
              ),
            ),
          ),
        ],

        // ── Divider ───────────────────────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Divider(color: AppColors.border),
          ),
        ),

        // ── Header: Full Fund Table ───────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text('📊 Full Analysis', style: AppText.bodyBold),
          ),
        ),

        // ── Search ────────────────────────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: TextField(
              onChanged: (v) => ref
                  .read(liveFundFilterProvider.notifier)
                  .state = filter.copyWith(search: v),
              style: AppText.body,
              decoration: InputDecoration(
                hintText: 'Search funds...',
                hintStyle: AppText.body.copyWith(color: AppColors.textSecondary),
                prefixIcon:
                    Icon(Icons.search_rounded, color: AppColors.textSecondary),
                filled: true,
                fillColor: AppColors.surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 0),
              ),
            ),
          ),
        ),

        // ── Category chips ────────────────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(0, 10, 0, 0),
            child: SizedBox(
              height: 36,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _categories.length,
                separatorBuilder: (_, __) => const SizedBox(width: 6),
                itemBuilder: (context, i) {
                  final cat = _categories[i];
                  final sel = filter.category == cat;
                  return ChoiceChip(
                    label: Text(cat),
                    selected: sel,
                    onSelected: (_) => ref
                        .read(liveFundFilterProvider.notifier)
                        .state = filter.copyWith(category: cat),
                    selectedColor: AppColors.primaryLight,
                    backgroundColor: AppColors.surface,
                    labelStyle: AppText.caption.copyWith(
                      color:
                          sel ? AppColors.primary : AppColors.textPrimary,
                      fontWeight:
                          sel ? FontWeight.w700 : FontWeight.w500,
                    ),
                    side: BorderSide(
                        color:
                            sel ? AppColors.primary : AppColors.border),
                  );
                },
              ),
            ),
          ),
        ),

        // ── Sort row ──────────────────────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${list.length} funds', style: AppText.caption),
                Row(
                  children: [
                    Text('Sort: ', style: AppText.caption),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: DropdownButton<String>(
                        value: filter.sort,
                        underline: const SizedBox(),
                        icon: const Icon(Icons.keyboard_arrow_down_rounded,
                            size: 16),
                        style: AppText.caption.copyWith(
                            fontWeight: FontWeight.w600,
                            color: AppColors.primary),
                        items: _sorts
                            .map((s) => DropdownMenuItem(
                                  value: s,
                                  child: Text(s),
                                ))
                            .toList(),
                        onChanged: (v) {
                          if (v != null) {
                            ref
                                .read(liveFundFilterProvider.notifier)
                                .state = filter.copyWith(sort: v);
                          }
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),

        // ── Column header ─────────────────────────────────────────────────
        const SliverToBoxAdapter(
          child: Padding(
            padding: EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: _TableHeader(),
          ),
        ),

        // ── Fund rows ─────────────────────────────────────────────────────
        if (list.isEmpty)
          const SliverFillRemaining(
            child: EmptyStateWidget(
              icon: Icons.search_off_rounded,
              title: 'No funds found',
              message: 'Try a different category or search term.',
            ),
          )
        else
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, i) => _FundRow(fund: list[i]),
              childCount: list.length,
            ),
          ),

        const SliverToBoxAdapter(child: SizedBox(height: 80)),
      ],
    );
  }
}

// ── Sync Banner ───────────────────────────────────────────────────────────────

class _SyncBanner extends StatelessWidget {
  const _SyncBanner({required this.lastSync, required this.total});
  final String lastSync;
  final int total;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.accent.withValues(alpha: 0.08),
            AppColors.primary.withValues(alpha: 0.06),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.accent.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          Icon(Icons.sync_rounded, color: AppColors.accent, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$total funds tracked',
                    style: AppText.bodyBold.copyWith(fontSize: 13)),
                Text('Last sync: $lastSync',
                    style: AppText.caption
                        .copyWith(color: AppColors.textSecondary)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text('LIVE',
                style: AppText.caption.copyWith(
                    color: AppColors.accent, fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}

// ── Top Pick Card ─────────────────────────────────────────────────────────────

class _TopPickCard extends StatelessWidget {
  const _TopPickCard(
      {required this.fund, required this.rank, this.isInternational = false});
  final LiveFundEntry fund;
  final int rank;
  final bool isInternational;

  Color get _cagrColor {
    if (fund.cagr3Y >= 15) return AppColors.accent;
    if (fund.cagr3Y >= 10) return AppColors.warning;
    return AppColors.danger;
  }

  @override
  Widget build(BuildContext context) {
    final medal = '#$rank';

    return Container(
      width: 200,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: rank == 1
              ? AppColors.warning.withValues(alpha: 0.5)
              : AppColors.border,
          width: rank == 1 ? 2 : 1,
        ),
        boxShadow: rank == 1
            ? [
                BoxShadow(
                    color: AppColors.warning.withValues(alpha: 0.1),
                    blurRadius: 10)
              ]
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(medal, style: const TextStyle(fontSize: 16)),
              const SizedBox(width: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isInternational
                      ? AppColors.accent.withValues(alpha: 0.1)
                      : AppColors.primaryLight,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  isInternational ? fund.amfiCode : fund.category,
                  style: AppText.caption.copyWith(
                    fontSize: 9,
                    color: isInternational
                        ? AppColors.accent
                        : AppColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: Text(
              fund.fundName,
              style: AppText.caption
                  .copyWith(fontWeight: FontWeight.w600, fontSize: 11),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${fund.cagr3Y >= 0 ? '+' : ''}${fund.cagr3Y.toStringAsFixed(1)}%',
                    style: AppText.bodyBold
                        .copyWith(fontSize: 16, color: _cagrColor),
                  ),
                  Text('3Y CAGR',
                      style: AppText.caption.copyWith(
                          fontSize: 9, color: AppColors.textSecondary)),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${fund.riskScore}/10',
                    style: AppText.bodyBold.copyWith(fontSize: 13),
                  ),
                  Text('Risk',
                      style: AppText.caption.copyWith(
                          fontSize: 9, color: AppColors.textSecondary)),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Table Header ──────────────────────────────────────────────────────────────

class _TableHeader extends StatelessWidget {
  const _TableHeader();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Expanded(flex: 3,
              child: Text('Fund', style: AppText.caption.copyWith(
                  fontWeight: FontWeight.w700))),
          Expanded(child: Text('1Y', style: AppText.caption.copyWith(
              fontWeight: FontWeight.w700), textAlign: TextAlign.right)),
          Expanded(child: Text('3Y', style: AppText.caption.copyWith(
              fontWeight: FontWeight.w700), textAlign: TextAlign.right)),
          Expanded(child: Text('Risk', style: AppText.caption.copyWith(
              fontWeight: FontWeight.w700), textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}

// ── Fund Row ──────────────────────────────────────────────────────────────────

class _FundRow extends StatelessWidget {
  const _FundRow({required this.fund});
  final LiveFundEntry fund;

  Color _cagrColor(double v) {
    if (v >= 15) return AppColors.accent;
    if (v >= 8) return AppColors.warning;
    return AppColors.danger;
  }

  @override
  Widget build(BuildContext context) {
    final isInternational = fund.category == 'International';
    return Container(
      decoration: BoxDecoration(
        border: Border(
            bottom: BorderSide(color: AppColors.border, width: 0.5)),
      ),
      padding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  fund.fundName,
                  style: AppText.caption
                      .copyWith(fontWeight: FontWeight.w600, fontSize: 11),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: isInternational
                            ? AppColors.accent.withValues(alpha: 0.1)
                            : AppColors.primaryLight,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        isInternational
                            ? fund.amfiCode
                            : fund.category,
                        style: AppText.caption.copyWith(
                          fontSize: 9,
                          color: isInternational
                              ? AppColors.accent
                              : AppColors.primary,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (!isInternational) ...[
                      const SizedBox(width: 4),
                      Text(fund.amfiCode,
                          style: AppText.caption.copyWith(
                              fontSize: 9,
                              color: AppColors.textSecondary)),
                    ]
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: Text(
              '${fund.cagr1Y >= 0 ? '+' : ''}${fund.cagr1Y.toStringAsFixed(1)}%',
              style: AppText.caption.copyWith(
                  fontWeight: FontWeight.w600,
                  color: _cagrColor(fund.cagr1Y)),
              textAlign: TextAlign.right,
            ),
          ),
          Expanded(
            child: Text(
              '${fund.cagr3Y >= 0 ? '+' : ''}${fund.cagr3Y.toStringAsFixed(1)}%',
              style: AppText.bodyBold.copyWith(
                  fontSize: 12, color: _cagrColor(fund.cagr3Y)),
              textAlign: TextAlign.right,
            ),
          ),
          Expanded(
            child: Text(
              '${fund.riskScore}/10',
              style: AppText.caption
                  .copyWith(fontWeight: FontWeight.w600),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }
}
