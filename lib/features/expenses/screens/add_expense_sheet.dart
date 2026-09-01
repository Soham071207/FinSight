import '../../../../core/theme/theme_provider.dart';
import 'package:finsight/core/theme/theme_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_text.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../data/local/models/expense_entry.dart';
import '../logic/expense_provider.dart';
import '../widgets/expense_list_tile.dart'; // For CategoryStyle

class AddExpenseSheet extends ConsumerStatefulWidget {
  const AddExpenseSheet({super.key});

  @override
  ConsumerState<AddExpenseSheet> createState() => _AddExpenseSheetState();
}

class _AddExpenseSheetState extends ConsumerState<AddExpenseSheet> {
  final _amountCtrl = TextEditingController();
  final _noteCtrl = TextEditingController();
  String _selectedCategory = 'Miscellaneous';
  DateTime _selectedDate = DateTime.now();

  final List<String> _categories = CategoryStyle.colors.keys.toList();

  @override
  void dispose() {
    _amountCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  void _onAmountChanged(String val) {
    // Smart parse logic: "400 food" -> fills amount 400, selects Food category
    final match = RegExp(r'^(\d+)\s+([a-zA-Z]+)$').firstMatch(val.trim());
    if (match != null) {
      final amt = match.group(1)!;
      final catRaw = match.group(2)!.toLowerCase();

      final matchedCat = _categories.cast<String?>().firstWhere(
            (c) => c!.toLowerCase().startsWith(catRaw),
            orElse: () => null,
          );

      if (matchedCat != null) {
        setState(() {
          _selectedCategory = matchedCat;
        });
        
        // Remove the text from the amount controller so it just has the number
        _amountCtrl.value = TextEditingValue(
          text: amt,
          selection: TextSelection.collapsed(offset: amt.length),
        );
      }
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 365)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: ColorScheme.light(
              primary: AppColors.primary,
              onPrimary: AppColors.onPrimary,
              onSurface: AppColors.textPrimary,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() => _selectedDate = picked);
    }
  }

  void _saveExpense() {
    final amtText = _amountCtrl.text.trim();
    if (amtText.isEmpty) return;

    final amount = double.tryParse(amtText);
    if (amount == null || amount <= 0) return;

    final entry = ExpenseEntry(
      id: const Uuid().v4(),
      amount: amount,
      category: _selectedCategory,
      note: _noteCtrl.text.trim(),
      timestamp: _selectedDate,
      source: 'manual',
    );

    ref.read(expenseProvider.notifier).addEntry(entry);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
      ref.watch(themeProvider); // force rebuild on theme change
    // Handling keyboard inset padding
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 16,
        bottom: 24 + bottomInset,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Amount Field
            TextField(
              controller: _amountCtrl,
              autofocus: true,
              keyboardType: TextInputType.text, // Allowing text for smart parse
              onChanged: _onAmountChanged,
              style: AppText.heading1.copyWith(fontSize: 32),
              decoration: InputDecoration(
                prefixText: '₹ ',
                prefixStyle: AppText.heading1.copyWith(fontSize: 32, color: AppColors.textSecondary),
                hintText: '0',
                border: InputBorder.none,
              ),
            ),
            const SizedBox(height: 24),

            // Category Chips
            Text('Category', style: AppText.bodyBold),
            const SizedBox(height: 12),
            SizedBox(
              height: 40,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _categories.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, index) {
                  final cat = _categories[index];
                  final isSelected = _selectedCategory == cat;
                  final color = CategoryStyle.getColor(cat);
                  
                  return GestureDetector(
                    onTap: () => setState(() => _selectedCategory = cat),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? color.withValues(alpha: 0.15) : AppColors.surface,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: isSelected ? color : AppColors.border,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(CategoryStyle.getIcon(cat), size: 16, color: isSelected ? color : AppColors.textSecondary),
                          const SizedBox(width: 6),
                          Text(
                            cat,
                            style: AppText.caption.copyWith(
                              fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                              color: isSelected ? color : AppColors.textPrimary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 24),

            // Note Field
            TextField(
              controller: _noteCtrl,
              style: AppText.body,
              decoration: InputDecoration(
                hintText: 'Add a note (optional)',
                filled: true,
                fillColor: AppColors.inputFill,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),
            const SizedBox(height: 16),

            // Date Picker Row
            GestureDetector(
              onTap: _pickDate,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                decoration: BoxDecoration(
                  color: AppColors.inputFill,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    Icon(Icons.calendar_today_rounded, size: 18, color: AppColors.textSecondary),
                    const SizedBox(width: 12),
                    Text(
                      DateFormat('MMM d, yyyy').format(_selectedDate),
                      style: AppText.body,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // Save Button
            SizedBox(
              width: double.infinity,
              child: AppButton(
                label: 'Add Expense',
                onPressed: _saveExpense,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
