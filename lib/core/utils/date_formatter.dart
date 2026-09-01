import 'package:intl/intl.dart';

/// Date and time formatting utilities for the FinSight app.
///
/// All formatters use the [intl] package with en_IN locale unless
/// otherwise specified. Pass a [DateTime] — never a raw string.

// ── Private formatter instances (created once, reused) ───────────────────────

final _dateFull     = DateFormat('d MMM yyyy', 'en_IN');   // 24 May 2026
final _dateShort    = DateFormat('d MMM', 'en_IN');        // 24 May
final _dateSlash    = DateFormat('dd/MM/yyyy', 'en_IN');   // 24/05/2026
final _dateIso      = DateFormat('yyyy-MM-dd', 'en_IN');   // 2026-05-24
final _time12       = DateFormat('h:mm a', 'en_IN');       // 6:45 PM
final _time24       = DateFormat('HH:mm', 'en_IN');        // 18:45
final _monthYear    = DateFormat('MMMM yyyy', 'en_IN');    // May 2026
final _monthShort   = DateFormat('MMM yyyy', 'en_IN');     // May 2026 (abbrev)
final _dayMonthYear = DateFormat('EEE, d MMM yyyy', 'en_IN'); // Sat, 24 May 2026
final _timeStamp    = DateFormat('d MMM yyyy • h:mm a', 'en_IN'); // 24 May 2026 • 6:45 PM

// ── Public API ───────────────────────────────────────────────────────────────

/// Returns full date: **24 May 2026**
String formatDate(DateTime dt) => _dateFull.format(dt);

/// Returns short date without year: **24 May**
String formatDateShort(DateTime dt) => _dateShort.format(dt);

/// Returns slash-separated date: **24/05/2026**
String formatDateSlash(DateTime dt) => _dateSlash.format(dt);

/// Returns ISO date string: **2026-05-24**
/// Used for API payloads and Hive keys.
String formatDateISO(DateTime dt) => _dateIso.format(dt);

/// Returns day-of-week + full date: **Sat, 24 May 2026**
String formatDateFull(DateTime dt) => _dayMonthYear.format(dt);

/// Returns 12-hour time with AM/PM: **6:45 PM**
String formatTime(DateTime dt) => _time12.format(dt);

/// Returns 24-hour time: **18:45**
String formatTime24(DateTime dt) => _time24.format(dt);

/// Returns full timestamp for receipts and entries: **24 May 2026 • 6:45 PM**
String formatTimestamp(DateTime dt) => _timeStamp.format(dt);

/// Returns full month + year: **May 2026**
/// Used for period selectors and chart axis labels.
String formatMonthYear(DateTime dt) => _monthYear.format(dt);

/// Returns abbreviated month + year: **May 2026**
/// Alias kept separate in case a shorter label format is needed later.
String formatMonthYearShort(DateTime dt) => _monthShort.format(dt);

/// Returns a human-readable relative label for recent timestamps.
///
/// - Same day       → "Today"
/// - Yesterday      → "Yesterday"
/// - Within 7 days  → "3 days ago"
/// - Otherwise      → formatDate()
///
/// Example: formatRelative(DateTime.now()) → "Today"
String formatRelative(DateTime dt) {
  final now  = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final date  = DateTime(dt.year, dt.month, dt.day);
  final diff  = today.difference(date).inDays;

  if (diff == 0) return 'Today';
  if (diff == 1) return 'Yesterday';
  if (diff < 7)  return '$diff days ago';
  return formatDate(dt);
}

/// Returns the month name for a given [month] integer (1–12).
///
/// Example: monthName(5) → "May"
String monthName(int month) =>
    DateFormat('MMMM', 'en_IN').format(DateTime(2000, month));
