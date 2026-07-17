import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../widgets/plexus_background.dart';
import 'url_scan_screen.dart';
import 'qr_scan_screen.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: PlexusBackground(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 860),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 36),
                decoration: BoxDecoration(
                  color: const Color(0xC2080D3E),
                  border: Border.all(color: const Color(0x2AA8C9FF)),
                  borderRadius: BorderRadius.circular(28),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x55010314),
                      blurRadius: 36,
                      offset: Offset(0, 22),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 128,
                      height: 128,
                      padding: const EdgeInsets.all(5),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            Color(0x1AFFFFFF),
                            Color(0x0FFFFFFF),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(26),
                        border: Border.all(color: const Color(0x34FFFFFF)),
                        boxShadow: const [
                          BoxShadow(
                            color: Color(0x1A82E6FF),
                            blurRadius: 12,
                            offset: Offset(0, 4),
                          ),
                        ],
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(22),
                        child: Image.asset(
                          'assets/logo.png',
                          fit: BoxFit.contain,
                        ),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      'PHISH\nGUARD',
                      textAlign: TextAlign.center,
                      style: GoogleFonts.michroma(
                        fontSize: 34,
                        fontWeight: FontWeight.w700,
                        height: 1.15,
                        color: const Color(0xFFF5F9FF),
                        letterSpacing: 2.2,
                        shadows: const [
                          Shadow(
                            color: Color(0x5882E6FF),
                            blurRadius: 18,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 10),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 620),
                      child: Text(
                        'Phish Guard is a machine learning phishing URL detector that evaluates suspicious links and explains risk with clear confidence and safety recommendations before you click.',
                        textAlign: TextAlign.center,
                        style: GoogleFonts.spaceGrotesk(
                          fontSize: 16,
                          color: const Color(0xFFADBBE3),
                          height: 1.65,
                        ),
                      ),
                    ),
                    const SizedBox(height: 28),
                    Row(
                      children: [
                        Expanded(
                          child: _HomeActionButton(
                            title: 'Scan URL',
                            onTap: () {
                              Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (context) => const UrlScanScreen(),
                                ),
                              );
                            },
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _HomeActionButton(
                            title: 'Scan QR Code',
                            onTap: () {
                              Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (context) => const QrScanScreen(),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _HomeActionButton extends StatelessWidget {
  const _HomeActionButton({
    required this.title,
    required this.onTap,
  });

  final String title;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onTap,
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 15, horizontal: 12),
        foregroundColor: const Color(0xFF00133A),
        backgroundColor: const Color(0xFF7EDBFF),
        shadowColor: const Color(0x557EDBFF),
        elevation: 5,
        textStyle: GoogleFonts.spaceGrotesk(
          fontSize: 13.5,
          fontWeight: FontWeight.w700,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(999),
          side: const BorderSide(color: Color(0x33FFFFFF)),
        ),
      ),
      child: Text(
        title,
        maxLines: 1,
        softWrap: false,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
