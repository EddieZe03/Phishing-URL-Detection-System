import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../services/api_service.dart';
import '../services/qr_scanner_service.dart';
import '../widgets/analyzing_overlay.dart';
import '../widgets/plexus_background.dart';
import 'home_screen.dart';
import 'result_screen.dart';

class QrScanScreen extends StatefulWidget {
  const QrScanScreen({super.key});

  @override
  State<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends State<QrScanScreen> {
  final ImagePicker _imagePicker = ImagePicker();
  final TextEditingController _urlController = TextEditingController();
  final FocusNode _urlFocusNode = FocusNode();
  MobileScannerController? _cameraController;
  bool _isProcessing = false;
  bool _isScanningDeviceImage = false;
  String? _error;
  String? _scanStatus = 'Ready to scan';

  @override
  void initState() {
    super.initState();
    _cameraController = MobileScannerController(
      facing: CameraFacing.back,
      torchEnabled: false,
    );
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _urlController.dispose();
    _urlFocusNode.dispose();
    super.dispose();
  }

  void _handleBarcode(BarcodeCapture barcodes) async {
    if (_isProcessing) return;

    final barcode = barcodes.barcodes.firstOrNull;
    if (barcode?.rawValue == null) return;

    _isProcessing = true;

    final scannedValue = barcode!.rawValue!;
    final payload = scannedValue.trim();

    setState(() {
      _urlController.text = payload;
      _scanStatus = 'QR detected';
    });

    // Auto-submit after brief delay
    await Future.delayed(const Duration(milliseconds: 500));

    if (mounted) {
      await _submitScannedQr(payload);
    }
  }

  Future<void> _stopCamera() async {
    try {
      await _cameraController?.stop();
    } catch (_) {}
  }

  Future<void> _startCamera() async {
    try {
      await _cameraController?.start();
    } catch (_) {}
  }

  Future<void> _chooseQrFromDevice() async {
    if (_isProcessing) return;

    await _stopCamera();

    final image = await _imagePicker.pickImage(source: ImageSource.gallery);
    if (image == null) {
      await _startCamera();
      return;
    }

    setState(() {
      _isScanningDeviceImage = true;
      _error = null;
      _scanStatus = 'Analyzing QR image from device';
    });

    try {
      final found = await _cameraController?.analyzeImage(image.path) ?? false;

      if (!mounted) return;

      if (!found) {
        setState(() {
          _error = 'No QR code was found in that image.';
          _isScanningDeviceImage = false;
          _scanStatus = 'Ready to scan';
        });
        await _startCamera();
        return;
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not read QR code from that image.';
        _isScanningDeviceImage = false;
        _scanStatus = 'Ready to scan';
      });
      await _startCamera();
    }
  }

  Future<void> _submitScannedQr(String payload) async {
    await _submitPayload(payload, validateManualInput: false);
  }

  Future<void> _submitManualUrl(String url) async {
    await _submitPayload(url, validateManualInput: true);
  }

  Future<void> _submitPayload(
    String url, {
    required bool validateManualInput,
  }) async {
    final candidate = url.trim();
    if (candidate.isEmpty) {
      setState(() {
        _error = 'Please provide QR content or URL';
        _isProcessing = false;
      });
      return;
    }

    if (validateManualInput && !QrScannerService.isProbableUrl(candidate)) {
      setState(() {
        _error = 'Manual entry needs a full URL such as https://example.com';
        _isProcessing = false;
      });
      return;
    }

    setState(() {
      _isProcessing = true;
      _error = null;
    });

    final response = await ApiService.predictUrl(candidate, source: 'qr');

    if (!mounted) return;

    if (response.ok && response.result != null) {
      final action = await Navigator.of(context).push<ResultScreenAction>(
        MaterialPageRoute(
          builder: (context) => ResultScreen(
            response: response,
            source: ScanFlowSource.qr,
          ),
        ),
      );

      if (!mounted) return;

      setState(() {
        _isProcessing = false;
        _scanStatus = 'Ready to scan';
        if (action == ResultScreenAction.scanAgain) {
          _urlController.clear();
          _error = null;
        }
        _isScanningDeviceImage = false;
      });

      if (action == ResultScreenAction.scanAgain) {
        FocusScope.of(context).requestFocus(_urlFocusNode);
        await _startCamera();
      }

      if (action == ResultScreenAction.backHome) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (context) => const HomePage()),
          (route) => false,
        );
      }
    } else {
      setState(() {
        _error = response.error ?? 'Prediction failed';
        _isProcessing = false;
        _isScanningDeviceImage = false;
      });

      if (_cameraController != null) {
        await _startCamera();
      }
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
                                        child: const Icon(
                                            Icons.qr_code_scanner_rounded,
                                            color: Color(0xFF82E6FF)),
                                      ),
                                      const SizedBox(width: 16),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              'Scan QR Code',
                                              style: GoogleFonts.michroma(
                                                fontSize: 18,
                                                fontWeight: FontWeight.w700,
                                                color: const Color(0xFFF5F8FF),
                                              ),
                                            ),
                                            const SizedBox(height: 6),
                                            Text(
                                              'Point the camera at a QR code or type the URL manually.',
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
                                      Container(
                                        decoration: BoxDecoration(
                                          borderRadius:
                                              BorderRadius.circular(14),
                                          border: Border.all(
                                            color: const Color(0xFFA8C9FF)
                                                .withValues(alpha: 0.22),
                                          ),
                                        ),
                                        clipBehavior: Clip.hardEdge,
                                        child: SizedBox(
                                          height: 280,
                                          child: MobileScanner(
                                            controller: _cameraController,
                                            onDetect: _handleBarcode,
                                            errorBuilder:
                                                (context, error, child) {
                                              return Center(
                                                child: Column(
                                                  mainAxisAlignment:
                                                      MainAxisAlignment.center,
                                                  children: [
                                                    const Icon(
                                                        Icons
                                                            .camera_alt_outlined,
                                                        size: 40,
                                                        color:
                                                            Color(0xFF82E6FF)),
                                                    const SizedBox(height: 12),
                                                    Text(
                                                      'Camera access required',
                                                      style: GoogleFonts
                                                          .spaceGrotesk(
                                                        color: const Color(
                                                            0xFFE7EDFF),
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              );
                                            },
                                          ),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      SizedBox(
                                        width: double.infinity,
                                        child: OutlinedButton.icon(
                                          onPressed: (_isProcessing ||
                                                  _isScanningDeviceImage)
                                              ? null
                                              : _chooseQrFromDevice,
                                          style: OutlinedButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(
                                                vertical: 16),
                                            foregroundColor:
                                                const Color(0xFFB9E8FF),
                                            side: const BorderSide(
                                              color: Color(0x5A82E6FF),
                                              width: 1.2,
                                            ),
                                            shape: RoundedRectangleBorder(
                                              borderRadius:
                                                  BorderRadius.circular(12),
                                            ),
                                          ),
                                          icon: const Icon(
                                            Icons.photo_library_outlined,
                                            size: 20,
                                          ),
                                          label: Text(
                                            'Choose from device',
                                            style: GoogleFonts.spaceGrotesk(
                                              fontWeight: FontWeight.w700,
                                              fontSize: 15,
                                            ),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(height: 16),
                                      if (_scanStatus != null)
                                        Text(
                                          _scanStatus!,
                                          style: GoogleFonts.spaceGrotesk(
                                            fontSize: 12,
                                            color: const Color(0xFFA7B3DD),
                                          ),
                                        ),
                                      const SizedBox(height: 24),
                                      Text(
                                        'Or enter URL manually:',
                                        style: GoogleFonts.spaceGrotesk(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w600,
                                          color: const Color(0xFFD8E5FF),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                      TextField(
                                        controller: _urlController,
                                        focusNode: _urlFocusNode,
                                        enabled: !_isProcessing &&
                                            !_isScanningDeviceImage,
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
                                      ),
                                      const SizedBox(height: 16),
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
                                      const SizedBox(height: 16),
                                      SizedBox(
                                        width: double.infinity,
                                        child: ElevatedButton(
                                          onPressed: _isProcessing
                                              ? null
                                              : () => _submitManualUrl(
                                                  _urlController.text),
                                          style: ElevatedButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(
                                                vertical: 17),
                                            backgroundColor: _isProcessing
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
                                          child: _isProcessing
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
                                                  'Submit URL',
                                                  style:
                                                      GoogleFonts.spaceGrotesk(
                                                    fontWeight: FontWeight.w700,
                                                    fontSize: 15,
                                                  ),
                                                ),
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
            AnalyzingOverlay(
              visible: _isProcessing,
              title: 'ANALYZING QR URL',
              subtitle: 'Extracting QR content and evaluating phishing risk.',
            ),
          ],
        ),
      ),
    );
  }
}
