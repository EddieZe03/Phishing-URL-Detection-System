import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AnalyzingOverlay extends StatelessWidget {
  const AnalyzingOverlay({
    super.key,
    required this.visible,
    this.title = 'ANALYZING URL',
    this.subtitle = 'Running feature extraction and phishing detection.',
  });

  final bool visible;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: !visible,
      child: AnimatedOpacity(
        opacity: visible ? 1 : 0,
        duration: const Duration(milliseconds: 220),
        child: Container(
          color: const Color(0x8C010528),
          alignment: Alignment.center,
          padding: const EdgeInsets.all(20),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 520),
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
            decoration: BoxDecoration(
              color: const Color(0xDD060D45),
              border: Border.all(color: const Color(0x4A82E6FF)),
              borderRadius: BorderRadius.circular(24),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x80010314),
                  blurRadius: 36,
                  offset: Offset(0, 16),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(
                  height: 82,
                  width: 82,
                  child: CircularProgressIndicator(
                    strokeWidth: 4,
                    valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF78DBFF)),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.michroma(
                    fontSize: 16,
                    letterSpacing: 1.7,
                    color: const Color(0xFFEAF2FF),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  subtitle,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 14,
                    height: 1.5,
                    color: const Color(0xFFB3C5E8),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
