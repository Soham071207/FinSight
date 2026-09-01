import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'data/local/hive_service.dart';
import 'app.dart';

Future<void> main() async {
  // ── Ensure Flutter engine is ready before any async work ─────────────────
  WidgetsFlutterBinding.ensureInitialized();

  // ── Initialise Hive and open all boxes ────────────────────────────────────
  // HiveService.init() calls Hive.initFlutter() internally, resolves the
  // correct documents directory per platform, registers all type adapters,
  // and opens every application box.
  //
  // Add generated adapters inside HiveService.init() as models are created:
  //   Hive.registerAdapter(ExpenseEntryAdapter());   // typeId 0
  //   Hive.registerAdapter(UserProfileAdapter());    // typeId 1
  //   Hive.registerAdapter(SimulationResultAdapter()); // typeId 2
  //   Hive.registerAdapter(CibilResultAdapter());    // typeId 3
  await HiveService.instance.init();

  // ── Launch the app wrapped in Riverpod ProviderScope ─────────────────────
  // ProviderScope is the root of the Riverpod dependency graph.
  // All providers (auth, expenses, simulator, funds…) are resolved here.
  runApp(
    const ProviderScope(
      child: FinSightApp(),
    ),
  );
}
