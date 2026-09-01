import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/theme/theme_provider.dart';

// Child screens
import 'live_fund_dashboard_screen.dart';
import 'pro_analysis_screen.dart';
import '../../simulator/screens/simulator_form_screen.dart';

class FundHubScreen extends ConsumerWidget {
  const FundHubScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(themeProvider); // force rebuild on theme change

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: AppColors.surface,
          elevation: 0,
          scrolledUnderElevation: 0,
          centerTitle: true,
          title: Text('Mutual Funds', style: AppText.heading2),
          bottom: PreferredSize(
            preferredSize: const Size.fromHeight(48),
            child: Container(
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: AppColors.border, width: 1),
                ),
              ),
              child: TabBar(
                indicatorColor: AppColors.primary,
                indicatorWeight: 3,
                labelColor: AppColors.primary,
                unselectedLabelColor: AppColors.textSecondary,
                labelStyle: AppText.label.copyWith(fontWeight: FontWeight.w700),
                unselectedLabelStyle: AppText.label.copyWith(fontWeight: FontWeight.w500),
                tabs: const [
                  Tab(text: 'Dashboard'),
                  Tab(text: 'Pro Analysis'),
                  Tab(text: 'Simulator'),
                ],
              ),
            ),
          ),
        ),
        body: const TabBarView(
          children: [
            LiveFundDashboardScreen(hideAppBar: true),
            ProAnalysisScreen(hideAppBar: true),
            SimulatorFormScreen(hideAppBar: true),
          ],
        ),
      ),
    );
  }
}
