import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/utils/currency_formatter.dart';
import '../../../data/local/models/expense_entry.dart';
import '../logic/expense_provider.dart';
import '../logic/investment_advisor.dart';
import '../logic/debt_provider.dart';
import '../widgets/category_donut_chart.dart';
import '../widgets/daily_bar_chart.dart';
import '../widgets/expense_list_tile.dart';
import '../widgets/suggestion_card.dart';
import 'add_expense_sheet.dart';
import 'debt_tab_widget.dart';
import '../../../shared/widgets/empty_state_widget.dart';
import '../../../core/constants/app_constants.dart';

// State provider for budget mock
final budgetProvider = StateProvider<double>((ref) => 20000.0);

// State provider for period selection
enum ExpensePeriod { thisWeek, thisMonth, customRange }
final periodProvider = StateProvider<ExpensePeriod>((ref) => ExpensePeriod.thisMonth);

// State provider for history grouping selection
enum HistoryGroupPeriod { day, week, month }
final historyGroupPeriodProvider = StateProvider<HistoryGroupPeriod>((ref) => HistoryGroupPeriod.day);

// Removed smsBannerDismissedProvider
class ExpenseHomeScreen extends ConsumerStatefulWidget {
  const ExpenseHomeScreen({super.key});

  @override
  ConsumerState<ExpenseHomeScreen> createState() => _ExpenseHomeScreenState();
}

class _ExpenseHomeScreenState extends ConsumerState<ExpenseHomeScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _showAddExpense() {
    // Show appropriate sheet based on current tab
    if (_tabController.index == 3) {
      // Debts tab — open add debt sheet
      showAddDebtSheet(context, ref);
      return;
    }
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const AddExpenseSheet(),
    );
  }

  void _editBudget() {
    final current = ref.read(budgetProvider);
    final ctrl = TextEditingController(text: current.toInt().toString());

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: AppColors.surface,
          title: Text('Set Monthly Budget', style: AppText.heading2),
          content: TextField(
            controller: ctrl,
            keyboardType: TextInputType.number,
            autofocus: true,
            style: AppText.body,
            decoration: InputDecoration(
              prefixText: '₹ ',
              prefixStyle: AppText.body.copyWith(color: AppColors.textSecondary),
              filled: true,
              fillColor: AppColors.background,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text('Cancel', style: TextStyle(color: AppColors.textSecondary)),
            ),
            ElevatedButton(
              onPressed: () {
                final val = double.tryParse(ctrl.text);
                if (val != null && val > 0) {
                  ref.read(budgetProvider.notifier).state = val;
                }
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: AppColors.onPrimary,
              ),
              child: Text('Save', style: AppText.bodyBold),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final expenseState = ref.watch(expenseProvider);
    final isBannerDismissed = expenseState.smsBannerDismissed;
    final showBanner = expenseState.smsImportEnabled &&
        expenseState.pendingSmsEntries.isNotEmpty &&
        !isBannerDismissed;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text('Expenses', style: AppText.heading2),
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () => context.go('/home'),
        ),
        actions: [
          if (expenseState.smsImportEnabled)
            IconButton(
              icon: Icon(Icons.refresh_rounded, color: AppColors.textPrimary),
              onPressed: () {
                ref.read(expenseProvider.notifier).refreshSms();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Scanning inbox for new messages...')),
                );
              },
            ),

        ],
        bottom: PreferredSize(
          preferredSize: Size.fromHeight(48 + (showBanner ? 76 : 0)),
          child: Column(
            children: [
              if (showBanner)
                Dismissible(
                  key: const ValueKey('sms_banner'),
                  onDismissed: (_) {
                    ref.read(expenseProvider.notifier).dismissSmsBanner();
                  },
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppColors.warning.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.warning.withValues(alpha: 0.5)),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.sms_rounded, color: AppColors.warning),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            '${expenseState.pendingSmsEntries.length} bank transactions detected',
                            style: AppText.caption.copyWith(color: AppColors.warning, fontWeight: FontWeight.w700),
                          ),
                        ),
                        TextButton(
                          onPressed: () => context.pushNamed(AppConstants.routePendingReview),
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.warning,
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                          ),
                          child: const Text('Review & Add →'),
                        ),
                      ],
                    ),
                  ),
                ),
              TabBar(
                controller: _tabController,
                labelColor: AppColors.primary,
                unselectedLabelColor: AppColors.textSecondary,
                indicatorColor: AppColors.primary,
                labelStyle: AppText.bodyBold,
                unselectedLabelStyle: AppText.body,
                isScrollable: true,
                tabAlignment: TabAlignment.start,
                tabs: const [
                  Tab(text: 'Overview'),
                  Tab(text: 'History'),
                  Tab(text: 'Smart Invest'),
                  Tab(text: 'Debts'),
                ],
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddExpense,
        backgroundColor: AppColors.primary,
        elevation: 2,
        child: const Icon(Icons.add_rounded, color: Colors.white, size: 28),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _OverviewTab(onEditBudget: _editBudget),
          const _HistoryTab(),
          const _SmartInvestTab(),
          const DebtTabWidget(),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// OVERVIEW TAB
// ══════════════════════════════════════════════════════════════════════════════

class _OverviewTab extends ConsumerWidget {
  const _OverviewTab({required this.onEditBudget});
  final VoidCallback onEditBudget;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final state = ref.watch(expenseProvider);
    final budget = ref.watch(budgetProvider);
    final period = ref.watch(periodProvider);

    // Filter by period logic
    final now = DateTime.now();
    DateTime start;
    DateTime end = now;

    if (period == ExpensePeriod.thisMonth) {
      start = DateTime(now.year, now.month, 1);
    } else if (period == ExpensePeriod.thisWeek) {
      start = now.subtract(Duration(days: now.weekday - 1));
      start = DateTime(start.year, start.month, start.day);
    } else {
      start = DateTime(now.year, 1, 1); // Mock custom range fallback
    }

    final provider = ref.read(expenseProvider.notifier);
    final catTotals = provider.getTotalByCategory(start, end);
    final totalSpend = catTotals.values.fold(0.0, (s, e) => s + e);
    
    // Monthly always uses monthly total for the budget bar, regardless of period selection
    final currentMonthSpend = provider.getMonthlyTotal();

    return RefreshIndicator(
      onRefresh: () async {
        await Future.delayed(const Duration(milliseconds: 500));
        // You can put any specific fetch logic here, or invalidate to rebuild
      },
      child: SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Period Selector
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                _PeriodChip('This Week', ExpensePeriod.thisWeek, period, ref),
                _PeriodChip('This Month', ExpensePeriod.thisMonth, period, ref),
                _PeriodChip('Custom', ExpensePeriod.customRange, period, ref),
              ],
            ),
          ),
          const SizedBox(height: 32),

          // Budget Bar
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Monthly Budget', style: AppText.bodyBold),
                    InkWell(
                      onTap: onEditBudget,
                      borderRadius: BorderRadius.circular(20),
                      child: Padding(
                        padding: EdgeInsets.all(4.0),
                        child: Icon(Icons.edit_outlined, size: 16, color: AppColors.textSecondary),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                
                // Progress Bar
                LayoutBuilder(
                  builder: (context, constraints) {
                    final pct = (currentMonthSpend / budget).clamp(0.0, 1.0);
                    Color barColor = AppColors.budgetSafe;
                    if (pct >= 1.0) {
                      barColor = AppColors.budgetExceeded;
                    } else if (pct >= 0.8) {
                      barColor = AppColors.budgetCaution;
                    }

                    return Stack(
                      children: [
                        Container(
                          height: 10,
                          decoration: BoxDecoration(
                            color: AppColors.border,
                            borderRadius: BorderRadius.circular(5),
                          ),
                        ),
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 500),
                          height: 10,
                          width: constraints.maxWidth * pct,
                          decoration: BoxDecoration(
                            color: barColor,
                            borderRadius: BorderRadius.circular(5),
                          ),
                        ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '${formatINRCompact(currentMonthSpend)} of ${formatINRCompact(budget)} used',
                      style: AppText.caption,
                    ),
                    Text(
                      '${DateTime(now.year, now.month + 1, 0).day - now.day} days left',
                      style: AppText.caption.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),

          // Donut Chart
          Text('Spend Breakdown', style: AppText.bodyBold),
          const SizedBox(height: 24),
          if (catTotals.isEmpty)
            const EmptyStateWidget(
              icon: Icons.pie_chart_outline_rounded,
              title: 'No expenses yet',
              message: 'Add your first expense to see your spend breakdown.',
            )
          else
            CategoryDonutChart(
              categoryTotals: catTotals,
              totalSpend: totalSpend,
            ),
        ],
      ),
      ),
    );
  }

  Widget _PeriodChip(String label, ExpensePeriod p, ExpensePeriod current, WidgetRef ref) {
    final isSelected = p == current;
    return Expanded(
      child: GestureDetector(
        onTap: () => ref.read(periodProvider.notifier).state = p,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primaryLight : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            style: AppText.caption.copyWith(
              fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// HISTORY TAB
// ══════════════════════════════════════════════════════════════════════════════

abstract class _HistoryItem {}

class _HeaderItem extends _HistoryItem {
  final String title;
  final double totalAmount;
  _HeaderItem({required this.title, required this.totalAmount});
}

class _EntryItem extends _HistoryItem {
  final ExpenseEntry entry;
  _EntryItem({required this.entry});
}

class _GroupedExpenses {
  final String title;
  final double totalAmount;
  final List<ExpenseEntry> entries;

  _GroupedExpenses({
    required this.title,
    required this.totalAmount,
    required this.entries,
  });
}

class _GroupHeader extends StatelessWidget {
  const _GroupHeader({
    required this.title,
    required this.totalAmount,
  });

  final String title;
  final double totalAmount;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.surface.withValues(alpha: 0.5),
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: AppText.bodyBold.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
          Text(
            'Total: ${formatINR(totalAmount)}',
            style: AppText.priceSmall.copyWith(
              color: AppColors.primary,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

class _HistoryTab extends ConsumerWidget {
  const _HistoryTab();

  List<_GroupedExpenses> _getGroupedExpenses(List<ExpenseEntry> entries, HistoryGroupPeriod period) {
    if (entries.isEmpty) return [];

    final Map<DateTime, List<ExpenseEntry>> groups = {};

    for (final entry in entries) {
      DateTime key;
      if (period == HistoryGroupPeriod.day) {
        key = DateTime(entry.timestamp.year, entry.timestamp.month, entry.timestamp.day);
      } else if (period == HistoryGroupPeriod.week) {
        final dayOffset = entry.timestamp.weekday - 1;
        final monday = entry.timestamp.subtract(Duration(days: dayOffset));
        key = DateTime(monday.year, monday.month, monday.day);
      } else {
        key = DateTime(entry.timestamp.year, entry.timestamp.month, 1);
      }

      if (!groups.containsKey(key)) {
        groups[key] = [];
      }
      groups[key]!.add(entry);
    }

    final sortedKeys = groups.keys.toList()..sort((a, b) => b.compareTo(a));

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    final currentMonday = today.subtract(Duration(days: today.weekday - 1));
    final lastMonday = currentMonday.subtract(const Duration(days: 7));

    final thisMonth = DateTime(now.year, now.month, 1);
    final lastMonth = DateTime(now.year, now.month - 1, 1);

    return sortedKeys.map((key) {
      String title = '';
      final list = groups[key]!;
      final total = list.fold<double>(0, (sum, e) => sum + e.amount);

      if (period == HistoryGroupPeriod.day) {
        if (key == today) {
          title = 'Today';
        } else if (key == yesterday) {
          title = 'Yesterday';
        } else {
          title = DateFormat('EEEE, MMM d, yyyy').format(key);
        }
      } else if (period == HistoryGroupPeriod.week) {
        if (key == currentMonday) {
          title = 'This Week';
        } else if (key == lastMonday) {
          title = 'Last Week';
        } else {
          final sunday = key.add(const Duration(days: 6));
          title = '${DateFormat('MMM d').format(key)} - ${DateFormat('MMM d, yyyy').format(sunday)}';
        }
      } else {
        if (key.year == thisMonth.year && key.month == thisMonth.month) {
          title = 'This Month';
        } else if (key.year == lastMonth.year && key.month == lastMonth.month) {
          title = 'Last Month';
        } else {
          title = DateFormat('MMMM yyyy').format(key);
        }
      }

      list.sort((a, b) => b.timestamp.compareTo(a.timestamp));

      return _GroupedExpenses(
        title: title,
        totalAmount: total,
        entries: list,
      );
    }).toList();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final state = ref.watch(expenseProvider);
    final activePeriod = ref.watch(historyGroupPeriodProvider);
    final now = DateTime.now();

    final groupedExpenses = _getGroupedExpenses(state.entries, activePeriod);

    final List<_HistoryItem> flatItems = [];
    for (final group in groupedExpenses) {
      flatItems.add(_HeaderItem(title: group.title, totalAmount: group.totalAmount));
      for (final entry in group.entries) {
        flatItems.add(_EntryItem(entry: entry));
      }
    }

    return Column(
      children: [
        // Chart
        Container(
          height: 250,
          padding: const EdgeInsets.all(16),
          color: AppColors.surface,
          child: DailyBarChart(entries: state.entries, month: now),
        ),

        // Group Selector
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            children: [
              _HistoryPeriodChip('Day', HistoryGroupPeriod.day, activePeriod, ref),
              _HistoryPeriodChip('Week', HistoryGroupPeriod.week, activePeriod, ref),
              _HistoryPeriodChip('Month', HistoryGroupPeriod.month, activePeriod, ref),
            ],
          ),
        ),

        // List
        Expanded(
          child: flatItems.isEmpty
              ? const EmptyStateWidget(
                  icon: Icons.receipt_long_rounded,
                  title: 'No transactions found',
                  message: 'You have not added any expenses yet.',
                )
              : ListView.builder(
                  padding: EdgeInsets.zero,
                  itemCount: flatItems.length,
                  itemBuilder: (context, index) {
                    final item = flatItems[index];
                    if (item is _HeaderItem) {
                      return _GroupHeader(
                        title: item.title,
                        totalAmount: item.totalAmount,
                      );
                    } else if (item is _EntryItem) {
                      final entry = item.entry;
                      final nextIsEntry = index + 1 < flatItems.length && flatItems[index + 1] is _EntryItem;

                      return Column(
                        children: [
                          ExpenseListTile(
                            entry: entry,
                            onDelete: () {
                              ref.read(expenseProvider.notifier).deleteEntry(entry.id);
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: const Text('Expense deleted'),
                                  action: SnackBarAction(
                                    label: 'Undo',
                                    onPressed: () {
                                      ref.read(expenseProvider.notifier).addEntry(entry);
                                    },
                                  ),
                                ),
                              );
                            },
                            onTap: () {
                              // Optional edit sheet routing here
                            },
                          ),
                          if (nextIsEntry)
                            Divider(
                              height: 1,
                              indent: 80,
                              color: AppColors.border,
                            ),
                        ],
                      );
                    }
                    return const SizedBox.shrink();
                  },
                ),
        ),
      ],
    );
  }

  Widget _HistoryPeriodChip(String label, HistoryGroupPeriod p, HistoryGroupPeriod current, WidgetRef ref) {
    final isSelected = p == current;
    return Expanded(
      child: GestureDetector(
        onTap: () => ref.read(historyGroupPeriodProvider.notifier).state = p,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primaryLight : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            style: AppText.caption.copyWith(
              fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SMART INVEST TAB
// ══════════════════════════════════════════════════════════════════════════════

class _SmartInvestTab extends ConsumerStatefulWidget {
  const _SmartInvestTab();

  @override
  ConsumerState<_SmartInvestTab> createState() => _SmartInvestTabState();
}

class _SmartInvestTabState extends ConsumerState<_SmartInvestTab> {
  @override
  void initState() {
    super.initState();
    _checkDisclaimer();
  }

  Future<void> _checkDisclaimer() async {
    final prefs = await SharedPreferences.getInstance();
    final shown = prefs.getBool('smart_invest_disclaimer_shown') ?? false;
    if (!shown) {
      if (!mounted) return;
      await showDialog(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: AppColors.surface,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text('How Smart Invest Works 💡', style: AppText.heading2),
          content: Text(
            'We analyse your spending patterns and show hypothetical growth scenarios if excess spend were redirected. These are calculator-based projections, not investment advice. Returns are not guaranteed.',
            style: AppText.body.copyWith(height: 1.5, color: AppColors.textSecondary),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text('Got it!', style: AppText.bodyBold.copyWith(color: AppColors.primary)),
            ),
          ],
        ),
      );
      await prefs.setBool('smart_invest_disclaimer_shown', true);
    }
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    final state = ref.watch(expenseProvider);
    final budget = ref.watch(budgetProvider);
    final suggestions = InvestmentAdvisor.analyze(state.entries, income: budget);

    if (suggestions.isEmpty) {
      return const EmptyStateWidget(
        icon: Icons.lightbulb_outline_rounded,
        title: 'Great job!',
        message: 'Your spending is within healthy limits. No reallocation needed this month.',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(24),
      itemCount: suggestions.length + 1,
      itemBuilder: (context, index) {
        if (index == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Redirect your spending', style: AppText.heading2),
                const SizedBox(height: 4),
                Text('Based on your last 30 days', style: AppText.bodySecondary),
              ],
            ),
          );
        }
        return SuggestionCard(suggestion: suggestions[index - 1]);
      },
    );
  }
}
