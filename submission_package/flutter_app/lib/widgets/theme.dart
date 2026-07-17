import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color primaryDark = Color(0xFF010528);
  static const Color primaryMid = Color(0xFF030D4F);
  static const Color primaryLight = Color(0xFF004B8E);

  static const Color accentBlue = Color(0xFF57C3FF);
  static const Color accentBright = Color(0xFF82E6FF);
  static const Color dangerRed = Color(0xFFFF6978);
  static const Color successGreen = Color(0xFF63F0A3);
  static const Color warningYellow = Color(0xFFFFD26F);

  static const Color textPrimary = Color(0xFFE7EDFF);
  static const Color textMuted = Color(0xFFA7B3DD);
  static const Color borderLine = Color(0xFFA8C9FF);

  static const Color surface = Color(0xBF080D3E);
  static const Color surfaceStrong = Color(0xDD040828);

  static ThemeData darkTheme() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: primaryDark,
      primaryColor: accentBlue,
      splashColor: accentBlue.withOpacity(0.18),
      highlightColor: accentBlue.withOpacity(0.12),
      textTheme: GoogleFonts.spaceGroteskTextTheme(
        ThemeData(brightness: Brightness.dark).textTheme,
      ).apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.michroma(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: textPrimary,
        ),
        iconTheme: const IconThemeData(color: textPrimary),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accentBlue,
          foregroundColor: primaryDark,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(999),
          ),
          textStyle: GoogleFonts.spaceGrotesk(
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF080F46),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: borderLine, width: 1.0),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: accentBright, width: 1.5),
        ),
        hintStyle: const TextStyle(color: textMuted),
        labelStyle: const TextStyle(color: textPrimary),
      ),
      cardTheme: CardThemeData(
        color: surfaceStrong,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(28),
          side: const BorderSide(color: borderLine, width: 1.0),
        ),
      ),
    );
  }
}
