import 'package:flutter/material.dart';
import 'widgets/theme.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const PhishGuardApp());
}

class PhishGuardApp extends StatelessWidget {
  const PhishGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Phish Guard',
      theme: AppTheme.darkTheme(),
      home: const HomePage(),
      debugShowCheckedModeBanner: false,
    );
  }
}
