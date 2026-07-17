import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/api_service.dart';
import '../services/qr_scanner_service.dart';
import '../widgets/analyzing_overlay.dart';
import '../widgets/plexus_background.dart';
import 'home_screen.dart';
import 'result_screen.dart';

class UrlScanScreen extends StatefulWidget {
  const UrlScanScreen({super.key});

  @override
  State<UrlScanScreen> createState() => _UrlScanScreenState();
}

class _UrlScanScreenState extends State<UrlScanScreen> {
  final TextEditingController _urlController = TextEditingController();
  final FocusNode _urlFocusNode = FocusNode();
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _urlController.dispose();
    _urlFocusNode.dispose();
    super.dispose();
  }

  void _submit() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) {
      setState(() => _error = 'Please enter a URL');
      return;
    }

    if (!QrScannerService.isProbableUrl(url)) {
      setState(() => _error = 'Please enter a full URL such as https://example.com');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final response = await ApiService.predictUrl(url, source: 'url');

    if (!mounted) return;

    if (response.ok && response.result != null) {
      final action = await Navigator.of(context).push<ResultScreenAction>(
        MaterialPageRoute(
          builder: (context) => ResultScreen(
            response: response,
            source: ScanFlowSource.url,
          ),
        ),
      );

      if (!mounted) return;

      setState(() {
        _isLoading = false;
        if (action == ResultScreenAction.scanAgain) {
          _urlController.clear();
          _error = null;
        }
      });

      if (action == ResultScreenAction.scanAgain) {
        FocusScope.of(context).requestFocus(_urlFocusNode);
      }

      if (action == ResultScreenAction.backHome) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (context) => const HomePage()),
          (route) => false,
        );
      }
    } else {
      setState(() {
        _isLoading = false;
        _error = response.error ?? 'Prediction failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: PlexusBackground(
        child: Stack(
          children: [
            SafeArea(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  return SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        minHeight: constraints.maxHeight - 40,
                      ),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 1000),
                          child: Container(
                            clipBehavior: Clip.antiAlias,
                            decoration: BoxDecoration(
                              color: const Color(0xC2080D3E),
                              border:
                                  Border.all(color: const Color(0x2AA8C9FF)),
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
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 28, vertical: 22),
                                  decoration: const BoxDecoration(
                                    gradient: LinearGradient(
                                      begin: Alignment.topLeft,
                                      end: Alignment.centerRight,
                                      colors: [
                                        Color(0x2410E6FF),
                                        Color(0x00000000),
                                      ],
                                    ),
                                    border: Border(
                                      bottom:
                                          BorderSide(color: Color(0x28A8C9FF)),
                                    ),
                                  ),
                                  child: Row(
                                    children: [
                                      Container(
                                        width: 58,
                                        height: 58,
                                        decoration: BoxDecoration(
                                          color: const Color(0x0EFFFFFF),
                                          borderRadius:
                                              BorderRadius.circular(16),
                                          border: Border.all(
                                              color: const Color(0x26FFFFFF)),
                                        ),
                                        child: const Icon(Icons.travel_explore,
                                            color: Color(0xFF82E6FF)),
                                      ),
                                      const SizedBox(width: 16),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              'Scan URL',
                                              style: GoogleFonts.michroma(
                                                fontSize: 18,
                                                fontWeight: FontWeight.w700,
                                                color: const Color(0xFFF5F8FF),
                                              ),
                                            ),
                                            const SizedBox(height: 6),
                                            Text(
                                              'Enter a URL and the model will evaluate its risk.',
                                              style: GoogleFonts.spaceGrotesk(
                                                fontSize: 13,
                                                color: const Color(0xFFADBBE3),
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.all(28),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Enter Website URL',
                                        style: GoogleFonts.spaceGrotesk(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w700,
                                          color: const Color(0xFFF5F9FF),
                                          letterSpacing: 0.1,
                                        ),
                                      ),
                                      const SizedBox(height: 14),
                                      TextField(
                                        controller: _urlController,
                                        focusNode: _urlFocusNode,
                                        enabled: !_isLoading,
                                        decoration: InputDecoration(
                                          hintText: 'https://example.com',
                                          hintStyle: GoogleFonts.spaceGrotesk(
                                            color: const Color(0xFF6B7FA0),
                                          ),
                                          prefixIcon: const Icon(Icons.link,
                                              color: Color(0xFF82E6FF)),
                                          filled: true,
                                          fillColor: const Color(0xFF0A0F32),
                                          border: OutlineInputBorder(
                                            borderRadius:
                                                BorderRadius.circular(12),
                                            borderSide: const BorderSide(
                                              color: Color(0xFFA8C9FF),
                                              width: 1.2,
                                            ),
                                          ),
                                          enabledBorder: OutlineInputBorder(
                                            borderRadius:
                                                BorderRadius.circular(12),
                                            borderSide: const BorderSide(
                                              color: Color(0x3FA8C9FF),
                                              width: 1.2,
                                            ),
                                          ),
                                          focusedBorder: OutlineInputBorder(
                                            borderRadius:
                                                BorderRadius.circular(12),
                                            borderSide: const BorderSide(
                                              color: Color(0xFF82E6FF),
                                              width: 1.5,
                                            ),
                                          ),
                                          disabledBorder: OutlineInputBorder(
                                            borderRadius:
                                                BorderRadius.circular(12),
                                            borderSide: const BorderSide(
                                              color: Color(0x2FA8C9FF),
                                              width: 1,
                                            ),
                                          ),
                                        ),
                                        style: GoogleFonts.spaceGrotesk(
                                            color: const Color(0xFFF0F4FF),
                                            fontSize: 14,
                                            fontWeight: FontWeight.w500),
                                        onSubmitted: (_) => _submit(),
                                      ),
                                      const SizedBox(height: 20),
                                      if (_error != null)
                                        Container(
                                          padding: const EdgeInsets.all(12),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFFFF6978)
                                                .withValues(alpha: 0.16),
                                            borderRadius:
                                                BorderRadius.circular(14),
                                            border: Border.all(
                                              color: const Color(0xFFFF6978)
                                                  .withValues(alpha: 0.5),
                                            ),
                                          ),
                                          child: Row(
                                            children: [
                                              const Icon(Icons.error_outline,
                                                  color: Color(0xFFFFD6DC)),
                                              const SizedBox(width: 12),
                                              Expanded(
                                                child: Text(
                                                  _error!,
                                                  style: const TextStyle(
                                                      color: Color(0xFFFFD6DC)),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      const SizedBox(height: 24),
                                      SizedBox(
                                        width: double.infinity,
                                        child: ElevatedButton(
                                          onPressed:
                                              _isLoading ? null : _submit,
                                          style: ElevatedButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(
                                                vertical: 17),
                                            backgroundColor: _isLoading
                                                ? const Color(0xFF3DA9FF)
                                                    .withValues(alpha: 0.6)
                                                : const Color(0xFF3DA9FF),
                                            disabledBackgroundColor:
                                                const Color(0xFF3DA9FF)
                                                    .withValues(alpha: 0.6),
                                            shadowColor:
                                                const Color(0x663DA9FF),
                                            elevation: 4,
                                            shape: RoundedRectangleBorder(
                                              borderRadius:
                                                  BorderRadius.circular(12),
                                            ),
                                          ),
                                          child: _isLoading
                                              ? const SizedBox(
                                                  height: 22,
                                                  width: 22,
                                                  child:
                                                      CircularProgressIndicator(
                                                    strokeWidth: 2.5,
                                                    valueColor:
                                                        AlwaysStoppedAnimation<
                                                            Color>(
                                                      Color(0xFF00133A),
                                                    ),
                                                  ),
                                                )
                                              : Text(
                                                  'Scan URL',
                                                  style:
                                                      GoogleFonts.spaceGrotesk(
                                                    fontWeight: FontWeight.w700,
                                                    fontSize: 15,
                                                  ),
                                                ),
                                        ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.all(16),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFF0A0F32),
                                          border: Border.all(
                                            color: const Color(0xFFA8C9FF)
                                                .withValues(alpha: 0.25),
                                          ),
                                          borderRadius:
                                              BorderRadius.circular(14),
                                          boxShadow: const [
                                            BoxShadow(
                                              color: Color(0x1282E6FF),
                                              blurRadius: 8,
                                              offset: Offset(0, 2),
                                            ),
                                          ],
                                        ),
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              'Tips for Safer Browsing',
                                              style: GoogleFonts.spaceGrotesk(
                                                fontWeight: FontWeight.w700,
                                                color: const Color(0xFF82E6FF),
                                                fontSize: 12,
                                                letterSpacing: 0.15,
                                              ),
                                            ),
                                            const SizedBox(height: 12),
                                            ...[
                                              'Always check the domain name carefully',
                                              'Look for HTTPS in the address bar',
                                              'Avoid clicking suspicious links'
                                            ].map(
                                              (tip) => Padding(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                        vertical: 7),
                                                child: Row(
                                                  crossAxisAlignment:
                                                      CrossAxisAlignment.start,
                                                  children: [
                                                    const Icon(
                                                      Icons.check_circle,
                                                      size: 16,
                                                      color: Color(0xFF63F0A3),
                                                    ),
                                                    const SizedBox(width: 10),
                                                    Expanded(
                                                      child: Text(
                                                        tip,
                                                        style: GoogleFonts
                                                            .spaceGrotesk(
                                                          fontSize: 13,
                                                          color: const Color(
                                                              0xFFE2E8FF),
                                                          height: 1.4,
                                                          fontWeight:
                                                              FontWeight.w400,
                                                        ),
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            AnalyzingOverlay(visible: _isLoading),
          ],
        ),
      ),
    );
  }
}
