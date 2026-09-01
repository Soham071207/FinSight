import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter/services.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../core/theme/theme_data.dart';
import '../../../core/theme/theme_provider.dart';
import '../logic/expense_provider.dart';
import '../logic/sms_parser.dart';
import '../logic/sms_import_service.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../shared/widgets/app_button.dart';

class SmsImportSettingsScreen extends ConsumerWidget {
  const SmsImportSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
      ref.watch(themeProvider); // force rebuild on theme change
    final expenseState = ref.watch(expenseProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        centerTitle: true,
        title: Text('App Settings', style: AppText.heading2),
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: AppColors.textPrimary),
          onPressed: () => context.pop(),
        ),
      ),
      body: kIsWeb
          ? _buildWebState(context, ref)
          : _buildAndroidState(context, ref, expenseState),
    );
  }

  Widget _buildWebState(BuildContext context, WidgetRef ref) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72, height: 72,
              decoration: BoxDecoration(
                color: AppColors.primaryLight,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.settings_outlined, size: 36, color: AppColors.primary),
            ),
            const SizedBox(height: 24),
            Text('App Settings', style: AppText.heading2, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            _buildThemeSelector(context, ref),
            const SizedBox(height: 32),
            AppButton(
              label: 'Sign Out',
              isOutlined: true,
              onPressed: () {
                ref.read(authProvider.notifier).logout();
                context.go('/login');
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAndroidState(BuildContext context, WidgetRef ref, ExpenseState state) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Theme Selector
        _buildThemeSelector(context, ref),
        const SizedBox(height: 24),
        
        Text('SMS Auto-Import', style: AppText.heading2),
        const SizedBox(height: 8),

        // Toggle Card
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: SwitchListTile.adaptive(
            value: state.smsImportEnabled,
            onChanged: (val) async {
              if (val) {
                // Requesting enable
                final status = await Permission.sms.status;
                if (status.isPermanentlyDenied) {
                  _showSettingsDialog(context);
                  return;
                }
              } else {
                // Disabling -> clear pending?
                if (state.pendingSmsEntries.isNotEmpty) {
                  final confirm = await _showClearDialog(context, state.pendingSmsEntries.length);
                  if (confirm != true) return;
                }
              }
              ref.read(expenseProvider.notifier).toggleSmsImport();
            },
            title: Text('Auto-import bank SMS', style: AppText.bodyBold),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'FinSight will read debit SMS from your bank and suggest them for review. No data leaves your device.',
                style: AppText.caption,
              ),
            ),
            activeTrackColor: AppColors.primary,
          ),
        ),
        const SizedBox(height: 16),

        // Privacy Note
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.primaryLight.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.lock_outline_rounded, color: AppColors.primary, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Your SMS data never leaves your device.\nFinSight reads only debit messages from known bank senders. OTP and personal SMS are never read.',
                  style: AppText.caption.copyWith(color: AppColors.primary, height: 1.4),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Supported Banks Expandable
        Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            title: Text('Supported Banks', style: AppText.bodyBold),
            subtitle: Text('Tap to view whitelisted sender IDs', style: AppText.caption),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: ['UPI', 'Banks (SBI, HDFC, ICICI, etc)', 'Shortcodes'].map((e) => Chip(
                  label: Text(e, style: AppText.caption),
                  backgroundColor: AppColors.background,
                  side: BorderSide(color: AppColors.border),
                )).toList(),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        AppButton(
          label: 'Debug SMS Parser',
          isOutlined: true,
          onPressed: () {
            _showDebugDialog(context);
          },
        ),
        const SizedBox(height: 12),
        AppButton(
          label: '🔍 Dump Raw SMS (Diagnostic)',
          isOutlined: true,
          onPressed: () {
            _showDumpDialog(context);
          },
        ),
        const SizedBox(height: 12),
        AppButton(
          label: '🔔 Enable Notification Listener',
          isOutlined: true,
          onPressed: () async {
            // Open Android Notification Listener Settings
            // Requires the new native method channel
            try {
              const platform = MethodChannel('com.finsight/notification_permission');
              await platform.invokeMethod('openNotificationSettings');
            } catch (e) {
              debugPrint('Could not open notification settings: $e');
            }
          },
        ),
        const SizedBox(height: 32),
        AppButton(
          label: 'Sign Out',
          isOutlined: true,
          onPressed: () {
            ref.read(authProvider.notifier).logout();
            context.go('/login');
          },
        ),
      ],
    );
  }

  Widget _buildThemeSelector(BuildContext context, WidgetRef ref) {
    final activeTheme = ref.watch(themeProvider);
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Appearance', style: AppText.heading2),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: FinSightTheme.values.map((theme) {
            final isSelected = activeTheme.id == theme.id;
            return GestureDetector(
              onTap: () => ref.read(themeProvider.notifier).changeTheme(theme),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 70,
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: theme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? theme.primary : theme.border,
                    width: isSelected ? 2 : 1,
                  ),
                  boxShadow: isSelected ? [
                    BoxShadow(color: theme.primary.withValues(alpha: 0.3), blurRadius: 8)
                  ] : null,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 24, height: 24,
                      decoration: BoxDecoration(
                        color: theme.primary,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      theme.name.split(' ').first,
                      style: AppText.caption.copyWith(
                        color: theme.textPrimary,
                        fontSize: 10,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  void _showDebugDialog(BuildContext context) {
    final textController = TextEditingController();
    String? resultText;
    
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setState) {
          return AlertDialog(
            title: Text('Debug SMS', style: AppText.heading2),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: textController,
                    maxLines: 4,
                    style: AppText.body,
                    decoration: InputDecoration(
                      hintText: 'Paste raw SMS here...',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  const SizedBox(height: 16),
                  AppButton(
                    label: 'Test Parse',
                    onPressed: () {
                      final parsed = SmsParser.parse(textController.text, '9922613190');
                      setState(() {
                        if (parsed == null) {
                          resultText = 'Failed to parse! Invalid syntax or no debit keywords found.';
                        } else {
                          resultText = 'SUCCESS!\nAmount: ${parsed.amount}\nMerchant: ${parsed.merchantName}\nCategory: ${parsed.category}';
                        }
                      });
                    },
                  ),
                  const SizedBox(height: 16),
                  if (resultText != null)
                    Container(
                      padding: const EdgeInsets.all(12),
                      color: AppColors.surface,
                      child: Text(resultText!, style: AppText.caption),
                    )
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => ctx.pop(), child: const Text('Close')),
            ],
          );
        },
      ),
    );
  }

  void _showDumpDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: Text('Raw SMS Dump', style: AppText.heading2),
          content: SizedBox(
            width: double.maxFinite,
            height: 400,
            child: FutureBuilder<List<Map<String, String>>>(
              future: SmsImportService().dumpRawSms(1),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Text('Error: ${snapshot.error}', style: AppText.caption);
                }
                final data = snapshot.data ?? [];
                if (data.isEmpty) {
                  return Text(
                    'NO SMS FOUND!\n\nThis means neither flutter_sms_inbox nor telephony returned any messages from the last 24 hours.\n\nPossible causes:\n• SMS permission not granted\n• No SMS in inbox',
                    style: AppText.caption,
                  );
                }
                return ListView.separated(
                  itemCount: data.length,
                  separatorBuilder: (_, __) => const Divider(),
                  itemBuilder: (context, index) {
                    final sms = data[index];
                    if (sms.containsKey('error')) {
                      return Text('ERROR [${sms['source']}]: ${sms['error']}',
                          style: AppText.caption.copyWith(color: AppColors.danger));
                    }
                    // Try to parse it and show result
                    final body = sms['body'] ?? '';
                    final addr = sms['address'] ?? '';
                    final parsed = SmsParser.parse(body, addr);
                    
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('📦 Source: ${sms['source']}',
                            style: AppText.caption.copyWith(fontWeight: FontWeight.bold)),
                        Text('📱 Address: ${sms['address']}', style: AppText.caption),
                        Text('👤 Sender: ${sms['sender']}', style: AppText.caption),
                        Text('📅 Date: ${sms['date']}', style: AppText.caption),
                        const SizedBox(height: 4),
                        Text('💬 Body: ${body.length > 120 ? '${body.substring(0, 120)}...' : body}',
                            style: AppText.caption),
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.all(6),
                          color: parsed != null ? Colors.green.withValues(alpha: 0.15) : Colors.red.withValues(alpha: 0.15),
                          child: Text(
                            parsed != null
                                ? '✅ PARSED: ₹${parsed.amount} | ${parsed.merchantName} | ${parsed.category}'
                                : '❌ NOT PARSED (skipped by parser)',
                            style: AppText.caption.copyWith(
                              color: parsed != null ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                );
              },
            ),
          ),
          actions: [
            TextButton(onPressed: () => ctx.pop(), child: const Text('Close')),
          ],
        );
      },
    );
  }

  void _showSettingsDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Permission Required', style: AppText.heading2),
        content: Text(
          'SMS permission is permanently denied. FinSight needs this to automatically detect bank transactions. Please enable it in system settings.',
          style: AppText.bodySecondary,
        ),
        actions: [
          TextButton(onPressed: () => ctx.pop(), child: const Text('Cancel')),
          TextButton(
            onPressed: () {
              ctx.pop();
              openAppSettings();
            },
            child: const Text('Open Settings'),
          ),
        ],
      ),
    );
  }

  Future<bool?> _showClearDialog(BuildContext context, int count) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Clear pending?', style: AppText.heading2),
        content: Text(
          'Disabling auto-import will clear $count pending unreviewed transactions.',
          style: AppText.bodySecondary,
        ),
        actions: [
          TextButton(onPressed: () => ctx.pop(false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => ctx.pop(true),
            child: Text('Clear & Disable', style: AppText.bodyBold.copyWith(color: AppColors.danger)),
          ),
        ],
      ),
    );
  }
}
